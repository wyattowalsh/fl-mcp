"""FastMCP 3.x server factory initialization."""

from __future__ import annotations

import json
from typing import Any, cast

from fl_mcp.auth.token import check_auth_context, check_token
from fl_mcp.config import RuntimeConfig
from fl_mcp.config.settings import settings
from fl_mcp.graph.model import ProjectGraph
from fl_mcp.prompts.registry import PROMPTS, PromptDefinition
from fl_mcp.runtime.health import health_payload
from fl_mcp.schemas import TransactionEnvelope
from fl_mcp.tools import public

PUBLIC_TOOL_HANDLERS: dict[str, Any] = {
    "query_project": public.query_project,
    "plan_changes": public.plan_changes,
    "apply_changes": public.apply_changes,
    "render_project": public.render_project,
    "analyze_audio": public.analyze_audio,
    "inspect_runtime": public.inspect_runtime,
    "manage_providers": public.manage_providers,
}

PUBLIC_TOOL_METADATA: dict[str, tuple[str, set[str]]] = {
    "query_project": ("Query project graph projections by domain.", {"project", "query"}),
    "plan_changes": ("Preview transaction execution results.", {"transaction", "plan"}),
    "apply_changes": (
        "Apply transaction changes with rollback policy.",
        {"transaction", "apply"},
    ),
    "render_project": ("Queue render project operation.", {"render"}),
    "analyze_audio": ("Queue analyze audio operation.", {"analyze", "audio"}),
    "inspect_runtime": (
        "Inspect runtime capabilities and provider state.",
        {"runtime", "inspect"},
    ),
    "manage_providers": ("Inspect and manage provider lifecycle.", {"providers", "runtime"}),
}

RUNTIME_HEALTH_TOOL_NAME = "runtime_health"
RUNTIME_HEALTH_TOOL_DESCRIPTION = "Get runtime health details."
RUNTIME_HEALTH_TOOL_TAGS = {"runtime", "health"}

RUNTIME_HEALTH_RESOURCE_URI = "runtime://health"
RUNTIME_HEALTH_RESOURCE_NAME = "runtime_health"
RUNTIME_HEALTH_RESOURCE_DESCRIPTION = "Runtime health payload encoded as JSON text."
RUNTIME_HEALTH_RESOURCE_MIME_TYPE = "application/json"
RUNTIME_HEALTH_RESOURCE_TAGS = {"runtime", "health"}


class MinimalMCPServer:
    """Fallback server shell used when FastMCP is unavailable."""

    def __init__(self, runtime_config: RuntimeConfig) -> None:
        self.name = runtime_config.service_name
        self.resources: dict[str, Any] = {
            RUNTIME_HEALTH_RESOURCE_URI: lambda: _health_resource_payload(runtime_config),
        }
        self.tools: dict[str, Any] = {
            RUNTIME_HEALTH_TOOL_NAME: lambda: health_payload(runtime_config),
            **_fallback_public_tool_handlers(runtime_config),
        }
        self.prompts: dict[str, Any] = _fallback_prompt_handlers()


def _fallback_public_tool_handlers(runtime_config: RuntimeConfig) -> dict[str, Any]:
    handlers = dict(PUBLIC_TOOL_HANDLERS)

    def query_project_compat(graph: Any, domain: str) -> dict[str, object]:
        return public.query_project(_coerce_project_graph(graph), domain)

    def plan_changes_compat(envelope: Any) -> dict[str, object]:
        return public.plan_changes(_coerce_transaction_envelope(envelope))

    def apply_changes_compat(envelope: Any) -> dict[str, object]:
        return public.apply_changes(_coerce_transaction_envelope(envelope))

    handlers["query_project"] = query_project_compat
    handlers["plan_changes"] = plan_changes_compat
    handlers["apply_changes"] = apply_changes_compat

    def inspect_runtime_compat() -> dict[str, object]:
        tool_descriptors = [_runtime_health_tool_descriptor()]
        tool_descriptors.extend(_public_tool_descriptor(name) for name in sorted(handlers))
        return public.inspect_runtime(
            tools=tool_descriptors,
            resources=[_runtime_health_resource_descriptor()],
            prompts=[_prompt_descriptor(prompt) for prompt in PROMPTS],
            runtime_health_data=health_payload(runtime_config),
            auth_required=bool(settings.auth_token),
            fastmcp_runtime=False,
            transport="minimal-fallback",
        )

    handlers["inspect_runtime"] = inspect_runtime_compat
    return handlers


def _fallback_prompt_handlers() -> dict[str, Any]:
    handlers: dict[str, Any] = {}
    for prompt in PROMPTS:
        prompt_content = prompt.content
        handlers[prompt.name] = lambda prompt_content=prompt_content: prompt_content
    return handlers


def _runtime_health_tool_descriptor() -> public.RuntimeToolDescriptor:
    return {
        "name": RUNTIME_HEALTH_TOOL_NAME,
        "description": RUNTIME_HEALTH_TOOL_DESCRIPTION,
        "tags": sorted(RUNTIME_HEALTH_TOOL_TAGS),
    }


def _public_tool_descriptor(name: str) -> public.RuntimeToolDescriptor:
    metadata = PUBLIC_TOOL_METADATA.get(name)
    description = metadata[0] if metadata else None
    tags = sorted(metadata[1]) if metadata else []
    return {"name": name, "description": description, "tags": tags}


def _runtime_health_resource_descriptor() -> public.RuntimeResourceDescriptor:
    return {
        "uri": RUNTIME_HEALTH_RESOURCE_URI,
        "name": RUNTIME_HEALTH_RESOURCE_NAME,
        "description": RUNTIME_HEALTH_RESOURCE_DESCRIPTION,
        "mime_type": RUNTIME_HEALTH_RESOURCE_MIME_TYPE,
        "tags": sorted(RUNTIME_HEALTH_RESOURCE_TAGS),
    }


def _prompt_descriptor(prompt: PromptDefinition) -> public.RuntimePromptDescriptor:
    return {
        "name": prompt.name,
        "description": prompt.description,
        "tags": sorted(prompt.tags),
    }


def _coerce_project_graph(graph: Any) -> ProjectGraph:
    if isinstance(graph, ProjectGraph):
        return graph
    if isinstance(graph, dict):
        return ProjectGraph.model_validate(graph)
    msg = "query_project expects ProjectGraph or dict payload in fallback mode."
    raise TypeError(msg)


def _coerce_transaction_envelope(envelope: Any) -> TransactionEnvelope:
    if isinstance(envelope, TransactionEnvelope):
        return envelope
    if isinstance(envelope, dict):
        return TransactionEnvelope.model_validate(envelope)
    msg = "transaction tools expect TransactionEnvelope or dict payload in fallback mode."
    raise TypeError(msg)


def _load_fastmcp() -> type[Any] | None:
    try:
        from fastmcp import FastMCP
    except ImportError:
        return None
    return cast(type[Any], FastMCP)


def create_server(runtime_config: RuntimeConfig) -> Any:
    """Create server instance, falling back to a local minimal shell."""

    auth_required = bool(settings.auth_token)
    fastmcp_cls = _load_fastmcp()
    if fastmcp_cls is None:
        if auth_required:
            msg = (
                "FL_MCP_AUTH_TOKEN is configured, but FastMCP runtime is unavailable; "
                "cannot start an unauthenticated fallback server."
            )
            raise RuntimeError(msg)
        return MinimalMCPServer(runtime_config)

    auth_provider = _build_static_token_auth_provider()
    server_kwargs: dict[str, Any] = {
        "name": runtime_config.service_name,
        "version": runtime_config.service_version,
    }
    if auth_provider is not None:
        server_kwargs["auth"] = auth_provider
    server = fastmcp_cls(**server_kwargs)

    def runtime_health_resource() -> str:
        return _health_resource_payload(runtime_config)

    server.resource(
        RUNTIME_HEALTH_RESOURCE_URI,
        name=RUNTIME_HEALTH_RESOURCE_NAME,
        description=RUNTIME_HEALTH_RESOURCE_DESCRIPTION,
        mime_type=RUNTIME_HEALTH_RESOURCE_MIME_TYPE,
        tags=RUNTIME_HEALTH_RESOURCE_TAGS,
        auth=check_auth_context,
    )(runtime_health_resource)

    def runtime_health_tool() -> dict[str, str]:
        return health_payload(runtime_config)

    server.tool(
        name=RUNTIME_HEALTH_TOOL_NAME,
        description=RUNTIME_HEALTH_TOOL_DESCRIPTION,
        tags=RUNTIME_HEALTH_TOOL_TAGS,
        auth=check_auth_context,
    )(runtime_health_tool)

    for name, handler in PUBLIC_TOOL_HANDLERS.items():
        if name == "inspect_runtime":
            continue
        metadata = PUBLIC_TOOL_METADATA.get(name)
        description = metadata[0] if metadata else None
        tags = set(metadata[1]) if metadata else None
        server.tool(
            name=name,
            description=description,
            tags=tags,
            auth=check_auth_context,
        )(handler)

    _register_prompts(server)

    async def inspect_runtime_tool() -> dict[str, object]:
        tools = await server.list_tools()
        resources = await server.list_resources()
        prompts = await server.list_prompts()
        return public.inspect_runtime(
            tools=[
                {
                    "name": str(tool.name),
                    "description": tool.description,
                    "tags": sorted(str(tag) for tag in (tool.tags or set())),
                }
                for tool in tools
            ],
            resources=[
                {
                    "uri": str(resource.uri),
                    "name": resource.name,
                    "description": resource.description,
                    "mime_type": resource.mime_type,
                    "tags": sorted(str(tag) for tag in (resource.tags or set())),
                }
                for resource in resources
            ],
            prompts=[
                {
                    "name": str(prompt.name),
                    "description": prompt.description,
                    "tags": sorted(str(tag) for tag in (prompt.tags or set())),
                }
                for prompt in prompts
            ],
            runtime_health_data=health_payload(runtime_config),
            auth_required=auth_provider is not None,
            fastmcp_runtime=True,
            transport="fastmcp",
        )

    inspect_runtime_metadata = PUBLIC_TOOL_METADATA["inspect_runtime"]
    server.tool(
        name="inspect_runtime",
        description=inspect_runtime_metadata[0],
        tags=set(inspect_runtime_metadata[1]),
        auth=check_auth_context,
    )(inspect_runtime_tool)

    return server


def _register_prompts(server: Any) -> None:
    for prompt in PROMPTS:
        _register_prompt(server, prompt)


def _register_prompt(server: Any, prompt: PromptDefinition) -> None:
    prompt_name = prompt.name
    prompt_description = prompt.description
    prompt_content = prompt.content
    prompt_tags = set(prompt.tags)

    def prompt_handler() -> str:
        return prompt_content

    server.prompt(
        name=prompt_name,
        description=prompt_description,
        tags=prompt_tags,
        auth=check_auth_context,
    )(prompt_handler)


def create_default_server() -> Any:
    """No-arg entrypoint for fastmcp.json bootstrap."""

    return create_server(RuntimeConfig())


def _health_resource_payload(runtime_config: RuntimeConfig) -> str:
    return json.dumps(health_payload(runtime_config), sort_keys=True)


def _build_static_token_auth_provider() -> Any | None:
    if not settings.auth_token:
        return None

    debug_token_verifier = _load_debug_token_verifier()
    return debug_token_verifier(validate=check_token)


def _load_debug_token_verifier() -> type[Any]:
    try:
        from fastmcp.server.auth import DebugTokenVerifier
    except ImportError as exc:
        msg = (
            "FL_MCP_AUTH_TOKEN is configured, but fastmcp.server.auth.DebugTokenVerifier "
            "is unavailable."
        )
        raise RuntimeError(msg) from exc
    return cast(type[Any], DebugTokenVerifier)
