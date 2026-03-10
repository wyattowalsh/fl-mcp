"""FastMCP 3.x server factory initialization."""

from __future__ import annotations

import json
from typing import Any, cast

from fl_mcp.auth.token import check_auth_context, check_token
from fl_mcp.config import RuntimeConfig
from fl_mcp.config.settings import settings
from fl_mcp.graph.model import ProjectGraph
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


class MinimalMCPServer:
    """Fallback server shell used when FastMCP is unavailable."""

    def __init__(self, runtime_config: RuntimeConfig) -> None:
        self.name = runtime_config.service_name
        self.resources: dict[str, Any] = {
            "runtime://health": lambda: _health_resource_payload(runtime_config),
        }
        self.tools: dict[str, Any] = {
            "runtime_health": lambda: health_payload(runtime_config),
            **_fallback_public_tool_handlers(),
        }


def _fallback_public_tool_handlers() -> dict[str, Any]:
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
    return handlers


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
    if auth_provider is None:
        server = fastmcp_cls(name=runtime_config.service_name)
    else:
        server = fastmcp_cls(name=runtime_config.service_name, auth=auth_provider)

    def runtime_health_resource() -> str:
        return _health_resource_payload(runtime_config)

    server.resource("runtime://health", auth=check_auth_context)(runtime_health_resource)

    def runtime_health_tool() -> dict[str, str]:
        return health_payload(runtime_config)

    server.tool(
        name="runtime_health",
        description="Get runtime health details.",
        auth=check_auth_context,
    )(runtime_health_tool)

    for name, handler in PUBLIC_TOOL_HANDLERS.items():
        server.tool(name=name, auth=check_auth_context)(handler)

    return server


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
