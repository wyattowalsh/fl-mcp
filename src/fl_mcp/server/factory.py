"""FastMCP server factory for the compact FL Studio agent surface."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast, get_type_hints

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from fastmcp.server.auth import DebugTokenVerifier

from fl_mcp.auth.token import check_auth_context, check_token
from fl_mcp.config import RuntimeConfig
from fl_mcp.config.settings import settings
from fl_mcp.prompts.registry import PROMPTS, PromptDefinition
from fl_mcp.resources.surface import (
    audio_analysis,
    domain_operations,
    project_arrangement,
    project_snapshot,
    provider_matrix,
    render_job,
    runtime_capabilities,
)
from fl_mcp.runtime.health import health_payload
from fl_mcp.schemas.compact_surface import (
    CapabilitySchemaResponse,
    CapabilitySearchResponse,
    FLApplyResponse,
    FLBatchExecuteResponse,
    FLBrowserResponse,
    FLExecuteResponse,
    FLPlanResponse,
    FLProviderManagementResponse,
    FLSnapshotResponse,
    FLStatusResponse,
    FLTaskEntryResponse,
)
from fl_mcp.tools import compact
from fl_mcp.tools.fl_surface import native_task_id_context

logger = logging.getLogger(__name__)

COMPACT_SURFACE = "compact"
COMPACT_TOOL_NAMES = compact.COMPACT_TOOL_NAMES
MAX_COMPACT_TOOL_COUNT = 12
TASK_ENABLED_COMPACT_TOOLS = {"fl_render", "fl_analyze_audio"}
PROGRESS_ENABLED_COMPACT_TOOLS = {
    "fl_batch_execute",
    "fl_render",
    "fl_analyze_audio",
    "fl_manage_providers",
    "fl_browser",
}
_SIGNATURE_ATTRIBUTE = "__signature__"

COMPACT_SERVER_INSTRUCTIONS = """\
You are connected to FL Studio through a compact full-power FastMCP surface.
Use this loop:
1. Call fl_status or fl_snapshot for runtime/project orientation.
2. Call fl_search_capabilities to find the hidden FL operation id by intent.
3. Call fl_get_capability_schema before any unfamiliar operation.
4. Execute with fl_execute for one operation or fl_batch_execute for ordered workflows.
5. For state-changing work, prefer fl_plan/fl_apply when a transaction envelope fits,
   or request readback in fl_execute/fl_batch_execute and verify with fl_snapshot.
6. Use fl_browser for plugin, preset, sample, drum-kit, and browser-like loading flows.
Visible tools are intentionally limited to the compact console; the internal operation
catalog remains available through operation ids and resource/schema discovery.
"""

COMPACT_TOOL_METADATA: dict[str, dict[str, object]] = {
    "fl_status": {
        "title": "FL Status",
        "description": (
            "Inspect runtime, FL connection, provider, bridge, task, and catalog health."
        ),
        "tags": {"compact", "runtime", "health", "read"},
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": True},
        "output_schema": FLStatusResponse.model_json_schema(),
    },
    "fl_snapshot": {
        "title": "FL Snapshot",
        "description": "Read project, session, arrangement, capability, or domain state.",
        "tags": {"compact", "project", "snapshot", "read"},
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": True},
        "output_schema": FLSnapshotResponse.model_json_schema(),
    },
    "fl_search_capabilities": {
        "title": "FL Search Capabilities",
        "description": (
            "Search the hidden 216-operation FL catalog by intent, domain, provider, and safety."
        ),
        "tags": {"compact", "capabilities", "search", "read"},
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": True},
        "output_schema": CapabilitySearchResponse.model_json_schema(),
    },
    "fl_get_capability_schema": {
        "title": "FL Capability Schema",
        "description": (
            "Fetch exact request/response schemas, examples, providers, and safety guidance."
        ),
        "tags": {"compact", "capabilities", "schema", "read"},
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": True},
        "output_schema": CapabilitySchemaResponse.model_json_schema(),
    },
    "fl_execute": {
        "title": "FL Execute",
        "description": "Execute one validated FL operation by canonical operation id.",
        "tags": {"compact", "execute", "operation", "write"},
        "annotations": {"readOnlyHint": False, "idempotentHint": False, "openWorldHint": True},
        "output_schema": FLExecuteResponse.model_json_schema(),
    },
    "fl_batch_execute": {
        "title": "FL Batch Execute",
        "description": (
            "Execute ordered FL operation batches with stop/continue and readback policy."
        ),
        "tags": {"compact", "batch", "workflow", "write"},
        "annotations": {"readOnlyHint": False, "idempotentHint": False, "openWorldHint": True},
        "output_schema": FLBatchExecuteResponse.model_json_schema(),
    },
    "fl_plan": {
        "title": "FL Plan",
        "description": "Preview transaction envelope changes before applying them.",
        "tags": {"compact", "transaction", "plan", "read"},
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": True},
        "output_schema": FLPlanResponse.model_json_schema(),
    },
    "fl_apply": {
        "title": "FL Apply",
        "description": "Apply planned or typed transaction changes with rollback policy.",
        "tags": {"compact", "transaction", "apply", "write"},
        "annotations": {"readOnlyHint": False, "idempotentHint": False, "openWorldHint": True},
        "output_schema": FLApplyResponse.model_json_schema(),
    },
    "fl_render": {
        "title": "FL Render",
        "description": "Queue render/export work and return task status metadata.",
        "tags": {"compact", "render", "task", "write"},
        "annotations": {"readOnlyHint": False, "idempotentHint": False, "openWorldHint": True},
        "output_schema": FLTaskEntryResponse.model_json_schema(),
    },
    "fl_analyze_audio": {
        "title": "FL Analyze Audio",
        "description": "Queue audio analysis and return task status metadata.",
        "tags": {"compact", "audio", "analysis", "task"},
        "annotations": {"readOnlyHint": False, "idempotentHint": False, "openWorldHint": True},
        "output_schema": FLTaskEntryResponse.model_json_schema(),
    },
    "fl_manage_providers": {
        "title": "FL Manage Providers",
        "description": "Inspect provider lifecycle and routing for mock/live/bridge execution.",
        "tags": {"compact", "providers", "runtime"},
        "annotations": {"readOnlyHint": False, "idempotentHint": False, "openWorldHint": True},
        "output_schema": FLProviderManagementResponse.model_json_schema(),
    },
    "fl_browser": {
        "title": "FL Browser",
        "description": "Search/load plugins, presets, samples, drum kits, and browser-like assets.",
        "tags": {"compact", "browser", "plugins", "samples", "workflow"},
        "annotations": {"readOnlyHint": False, "idempotentHint": False, "openWorldHint": True},
        "output_schema": FLBrowserResponse.model_json_schema(),
    },
}

RUNTIME_HEALTH_RESOURCE_URI = "runtime://health"
RUNTIME_HEALTH_RESOURCE_NAME = "runtime_health"
RUNTIME_HEALTH_RESOURCE_DESCRIPTION = "Runtime health payload encoded as JSON text."
RUNTIME_HEALTH_RESOURCE_MIME_TYPE = "application/json"
RUNTIME_HEALTH_RESOURCE_TAGS = {"runtime", "health"}
RUNTIME_CAPABILITIES_RESOURCE_URI = "runtime://capabilities"
RUNTIME_CAPABILITIES_RESOURCE_NAME = "runtime_capabilities"
RUNTIME_CAPABILITIES_RESOURCE_DESCRIPTION = "Runtime capability catalog encoded as JSON text."
RUNTIME_CAPABILITIES_RESOURCE_TAGS = {"runtime", "capabilities"}
PROVIDER_MATRIX_RESOURCE_URI = "providers://matrix"
PROVIDER_MATRIX_RESOURCE_NAME = "provider_matrix"
PROVIDER_MATRIX_RESOURCE_DESCRIPTION = "Built-in provider capability matrix encoded as JSON text."
PROVIDER_MATRIX_RESOURCE_TAGS = {"providers", "capabilities"}
PROJECT_SNAPSHOT_RESOURCE_URI = "project://snapshot"
PROJECT_SNAPSHOT_RESOURCE_NAME = "project_snapshot"
PROJECT_SNAPSHOT_RESOURCE_DESCRIPTION = "Server-owned project graph snapshot encoded as JSON text."
PROJECT_ARRANGEMENT_RESOURCE_URI = "project://arrangement"
PROJECT_ARRANGEMENT_RESOURCE_NAME = "project_arrangement"
PROJECT_ARRANGEMENT_RESOURCE_DESCRIPTION = "Server-owned arrangement snapshot encoded as JSON text."
PROJECT_RESOURCE_TAGS = {"project", "state"}
DOMAIN_CAPABILITIES_TEMPLATE_URI = "runtime://capabilities/{domain}"
DOMAIN_CAPABILITIES_TEMPLATE_NAME = "domain_capabilities"
DOMAIN_CAPABILITIES_TEMPLATE_DESCRIPTION = "Capability catalog for one FL Studio domain."
DOMAIN_CAPABILITIES_TEMPLATE_TAGS = {"runtime", "capabilities"}
RENDER_JOB_TEMPLATE_URI = "render://jobs/{job_id}"
RENDER_JOB_TEMPLATE_NAME = "render_job"
RENDER_JOB_TEMPLATE_DESCRIPTION = "Render job state encoded as JSON text."
RENDER_JOB_TEMPLATE_TAGS = {"render", "task"}
AUDIO_ANALYSIS_TEMPLATE_URI = "audio://analyses/{analysis_id}"
AUDIO_ANALYSIS_TEMPLATE_NAME = "audio_analysis"
AUDIO_ANALYSIS_TEMPLATE_DESCRIPTION = "Audio analysis state encoded as JSON text."
AUDIO_ANALYSIS_TEMPLATE_TAGS = {"audio", "task"}


def _load_fastmcp() -> type[FastMCP] | None:
    try:
        from fastmcp import FastMCP as _FastMCP
    except ImportError:
        return None
    fastmcp_cls: object = _FastMCP
    return cast("type[FastMCP]", fastmcp_cls)


def _fastmcp_tasks_available(fastmcp_cls: type[FastMCP]) -> bool:
    try:
        probe_server = fastmcp_cls(name="fl-mcp-task-probe")

        async def probe_handler() -> dict[str, str]:
            return {"status": "ok"}

        probe_server.tool(name="_task_probe", task=True)(probe_handler)
    except (ImportError, ValueError):
        return False
    return True


def _tool_supports_native_task(name: str, tasks_available: bool) -> bool:
    return bool(tasks_available and name in TASK_ENABLED_COMPACT_TOOLS)


def _current_fastmcp_task_id() -> str | None:
    try:
        from fastmcp.server.dependencies import get_task_context
    except ImportError:
        return None
    try:
        task_info = get_task_context()
    except RuntimeError:
        return None
    return task_info.task_id if task_info is not None else None


def _current_fastmcp_context() -> Any | None:
    try:
        from fastmcp.server.dependencies import get_context
    except ImportError:
        return None
    try:
        return get_context()
    except RuntimeError:
        return None


def _async_tool_handler(
    name: str,
    handler: Callable[..., dict[str, object]],
) -> Callable[..., Any]:
    async def async_handler(*args: Any, **kwargs: Any) -> dict[str, object]:
        task_id = _current_fastmcp_task_id()
        ctx = _current_fastmcp_context()
        if ctx is not None and name in PROGRESS_ENABLED_COMPACT_TOOLS:
            await ctx.info(f"{name} started")
            await ctx.report_progress(progress=0, total=100)

        def invoke() -> dict[str, object]:
            with native_task_id_context(task_id):
                return handler(*args, **kwargs)

        try:
            result = await asyncio.to_thread(invoke)
        except Exception as exc:
            if ctx is not None:
                await ctx.error(f"{name} failed: {exc}")
            raise

        if ctx is not None and name in PROGRESS_ENABLED_COMPACT_TOOLS:
            await ctx.report_progress(progress=100, total=100)
            await ctx.info(f"{name} completed")
        return result

    signature = inspect.signature(handler)
    try:
        type_hints = get_type_hints(handler)
    except (NameError, TypeError):
        type_hints = dict(getattr(handler, "__annotations__", {}))
    parameters = [
        parameter.replace(annotation=type_hints.get(parameter.name, parameter.annotation))
        for parameter in signature.parameters.values()
    ]
    async_handler.__name__ = getattr(handler, "__name__", name)
    async_handler.__qualname__ = getattr(handler, "__qualname__", name)
    async_handler.__doc__ = getattr(handler, "__doc__", None)
    async_handler.__annotations__ = type_hints
    setattr(
        async_handler,
        _SIGNATURE_ATTRIBUTE,
        signature.replace(
            parameters=parameters,
            return_annotation=type_hints.get("return", signature.return_annotation),
        ),
    )
    return async_handler


def _assert_compact_surface_size() -> None:
    tool_count = len(COMPACT_TOOL_NAMES)
    if tool_count != MAX_COMPACT_TOOL_COUNT:
        msg = f"Compact surface size guard tripped: {tool_count} tools != {MAX_COMPACT_TOOL_COUNT}."
        raise RuntimeError(msg)


def _status_handler(runtime_config: RuntimeConfig) -> Callable[[], dict[str, object]]:
    def handler() -> dict[str, object]:
        return compact.fl_status(runtime_config)

    handler.__name__ = "fl_status"
    handler.__qualname__ = "fl_status"
    handler.__doc__ = compact.fl_status.__doc__
    handler.__annotations__ = {"return": dict[str, object]}
    return handler


def _compact_tool_handler(
    name: str,
    runtime_config: RuntimeConfig,
) -> Callable[..., dict[str, object]]:
    if name == "fl_status":
        return _status_handler(runtime_config)
    handler = getattr(compact, name)
    return cast(Callable[..., dict[str, object]], handler)


def _register_compact_tools(
    server: FastMCP,
    runtime_config: RuntimeConfig,
    tasks_available: bool,
) -> None:
    _assert_compact_surface_size()
    for name in COMPACT_TOOL_NAMES:
        metadata = COMPACT_TOOL_METADATA[name]
        handler = _compact_tool_handler(name, runtime_config)
        server.tool(
            name=name,
            title=cast(str, metadata["title"]),
            description=cast(str, metadata["description"]),
            tags=cast(set[str], metadata["tags"]),
            annotations=cast(dict[str, object], metadata["annotations"]),
            output_schema=cast(dict[str, Any], metadata["output_schema"]),
            task=_tool_supports_native_task(name, tasks_available),
            auth=check_auth_context,
        )(_async_tool_handler(name, handler))


def _register_prompts(server: FastMCP) -> None:
    for prompt in PROMPTS:
        _register_prompt(server, prompt)


def _register_prompt(server: FastMCP, prompt: PromptDefinition) -> None:
    prompt_content = prompt.content

    async def prompt_handler() -> str:
        return prompt_content

    server.prompt(
        name=prompt.name,
        description=prompt.description,
        tags=set(prompt.tags),
        task=False,
        auth=check_auth_context,
    )(prompt_handler)


def _register_resources(server: FastMCP, runtime_config: RuntimeConfig) -> None:
    def _rh() -> str:
        return _health_resource_payload(runtime_config)

    server.resource(
        uri=RUNTIME_HEALTH_RESOURCE_URI,
        name=RUNTIME_HEALTH_RESOURCE_NAME,
        description=RUNTIME_HEALTH_RESOURCE_DESCRIPTION,
        mime_type=RUNTIME_HEALTH_RESOURCE_MIME_TYPE,
        tags=RUNTIME_HEALTH_RESOURCE_TAGS,
    )(_rh)
    server.resource(
        uri=RUNTIME_CAPABILITIES_RESOURCE_URI,
        name=RUNTIME_CAPABILITIES_RESOURCE_NAME,
        description=RUNTIME_CAPABILITIES_RESOURCE_DESCRIPTION,
        mime_type=RUNTIME_HEALTH_RESOURCE_MIME_TYPE,
        tags=RUNTIME_CAPABILITIES_RESOURCE_TAGS,
    )(lambda: _runtime_capabilities_payload())
    server.resource(
        uri=PROVIDER_MATRIX_RESOURCE_URI,
        name=PROVIDER_MATRIX_RESOURCE_NAME,
        description=PROVIDER_MATRIX_RESOURCE_DESCRIPTION,
        mime_type=RUNTIME_HEALTH_RESOURCE_MIME_TYPE,
        tags=PROVIDER_MATRIX_RESOURCE_TAGS,
    )(lambda: _provider_matrix_payload())
    server.resource(
        uri=PROJECT_SNAPSHOT_RESOURCE_URI,
        name=PROJECT_SNAPSHOT_RESOURCE_NAME,
        description=PROJECT_SNAPSHOT_RESOURCE_DESCRIPTION,
        mime_type=RUNTIME_HEALTH_RESOURCE_MIME_TYPE,
        tags=PROJECT_RESOURCE_TAGS,
    )(_project_snapshot_payload)
    server.resource(
        uri=PROJECT_ARRANGEMENT_RESOURCE_URI,
        name=PROJECT_ARRANGEMENT_RESOURCE_NAME,
        description=PROJECT_ARRANGEMENT_RESOURCE_DESCRIPTION,
        mime_type=RUNTIME_HEALTH_RESOURCE_MIME_TYPE,
        tags=PROJECT_RESOURCE_TAGS,
    )(_project_arrangement_payload)
    _register_resource_templates(server)


def _register_resource_templates(server: FastMCP) -> None:
    server.resource(
        uri=DOMAIN_CAPABILITIES_TEMPLATE_URI,
        name=DOMAIN_CAPABILITIES_TEMPLATE_NAME,
        description=DOMAIN_CAPABILITIES_TEMPLATE_DESCRIPTION,
        mime_type=RUNTIME_HEALTH_RESOURCE_MIME_TYPE,
        tags=DOMAIN_CAPABILITIES_TEMPLATE_TAGS,
    )(_domain_capabilities_payload)
    server.resource(
        uri=RENDER_JOB_TEMPLATE_URI,
        name=RENDER_JOB_TEMPLATE_NAME,
        description=RENDER_JOB_TEMPLATE_DESCRIPTION,
        mime_type=RUNTIME_HEALTH_RESOURCE_MIME_TYPE,
        tags=RENDER_JOB_TEMPLATE_TAGS,
    )(_render_job_payload)
    server.resource(
        uri=AUDIO_ANALYSIS_TEMPLATE_URI,
        name=AUDIO_ANALYSIS_TEMPLATE_NAME,
        description=AUDIO_ANALYSIS_TEMPLATE_DESCRIPTION,
        mime_type=RUNTIME_HEALTH_RESOURCE_MIME_TYPE,
        tags=AUDIO_ANALYSIS_TEMPLATE_TAGS,
    )(_audio_analysis_payload)


def create_server(runtime_config: RuntimeConfig) -> FastMCP:
    """Create the single supported compact FastMCP server."""

    auth_required = bool(settings.auth_token)
    if not auth_required:
        logger.warning(
            "No FL_MCP_AUTH_TOKEN configured; server accepts unauthenticated requests. "
            "Set FL_MCP_AUTH_TOKEN for production deployments."
        )
    fastmcp_cls = _load_fastmcp()
    if fastmcp_cls is None:
        msg = "FastMCP runtime is required; the minimal fallback server has been removed."
        raise RuntimeError(msg)

    auth_provider = _build_static_token_auth_provider()
    tasks_available = _fastmcp_tasks_available(fastmcp_cls)
    server = fastmcp_cls(
        name=runtime_config.service_name,
        instructions=COMPACT_SERVER_INSTRUCTIONS,
        version=runtime_config.service_version,
        strict_input_validation=True,
        list_page_size=100,
        tasks=False,
        auth=auth_provider,
    )
    _register_compact_tools(server, runtime_config, tasks_available)
    _register_prompts(server)
    _register_resources(server, runtime_config)
    cast(Any, server)._fl_mcp_surface = COMPACT_SURFACE
    return server


def create_default_server() -> FastMCP:
    """Return the default compact FastMCP server."""

    return create_server(RuntimeConfig())


def _health_resource_payload(runtime_config: RuntimeConfig) -> str:
    return json.dumps(health_payload(runtime_config), sort_keys=True)


def _runtime_capabilities_payload() -> str:
    return json.dumps(runtime_capabilities()["data"], sort_keys=True)


def _provider_matrix_payload() -> str:
    return json.dumps(provider_matrix()["data"], sort_keys=True)


def _project_snapshot_payload() -> str:
    return json.dumps(project_snapshot()["data"], sort_keys=True)


def _project_arrangement_payload() -> str:
    return json.dumps(project_arrangement()["data"], sort_keys=True)


def _domain_capabilities_payload(domain: str) -> str:
    return json.dumps(domain_operations(domain)["data"], sort_keys=True)


def _render_job_payload(job_id: str) -> str:
    return json.dumps(render_job(job_id)["data"], sort_keys=True)


def _audio_analysis_payload(analysis_id: str) -> str:
    return json.dumps(audio_analysis(analysis_id)["data"], sort_keys=True)


def _build_static_token_auth_provider() -> DebugTokenVerifier | None:
    if not settings.auth_token:
        return None

    debug_token_verifier = _load_debug_token_verifier()
    return debug_token_verifier(validate=check_token)


def _load_debug_token_verifier() -> type[DebugTokenVerifier]:
    try:
        from fastmcp.server.auth import DebugTokenVerifier as _DebugTokenVerifier
    except ImportError as exc:
        msg = (
            "FL_MCP_AUTH_TOKEN is configured, but fastmcp.server.auth.DebugTokenVerifier "
            "is unavailable."
        )
        raise RuntimeError(msg) from exc
    debug_token_verifier: object = _DebugTokenVerifier
    return cast("type[DebugTokenVerifier]", debug_token_verifier)
