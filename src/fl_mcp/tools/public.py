"""Public MCP tool handlers."""

from __future__ import annotations

from typing import TypedDict

from fl_mcp.graph.model import ProjectGraph
from fl_mcp.providers.runtime import get_provider_registry
from fl_mcp.schemas import TransactionEnvelope
from fl_mcp.transactions.apply import apply_changes as apply_engine
from fl_mcp.transactions.planner import plan_changes as plan_engine


class RuntimeToolDescriptor(TypedDict):
    name: str
    description: str | None
    tags: list[str]


class RuntimeResourceDescriptor(TypedDict):
    uri: str
    name: str | None
    description: str | None
    mime_type: str | None
    tags: list[str]


class RuntimePromptDescriptor(TypedDict):
    name: str
    description: str | None
    tags: list[str]


def query_project(graph: ProjectGraph, domain: str) -> dict[str, object]:
    return graph.to_projection(domain)


def plan_changes(envelope: TransactionEnvelope) -> dict[str, object]:
    return plan_engine(envelope).model_dump()


def apply_changes(envelope: TransactionEnvelope) -> dict[str, object]:
    return apply_engine(envelope).model_dump()


def render_project() -> dict[str, str]:
    return {"status": "queued", "tool": "render_project"}


def analyze_audio() -> dict[str, str]:
    return {"status": "queued", "tool": "analyze_audio"}


def inspect_runtime(
    *,
    tools: list[RuntimeToolDescriptor] | None = None,
    resources: list[RuntimeResourceDescriptor] | None = None,
    prompts: list[RuntimePromptDescriptor] | None = None,
    runtime_health_data: dict[str, str] | None = None,
    auth_required: bool = False,
    fastmcp_runtime: bool | None = None,
    transport: str = "unknown",
) -> dict[str, object]:
    provider_registry = get_provider_registry(load_entry_points=False)

    runtime_tools = sorted(tools or [], key=lambda item: item["name"])
    runtime_resources = sorted(resources or [], key=lambda item: item["uri"])
    runtime_prompts = sorted(prompts or [], key=lambda item: item["name"])

    return {
        "status": "ok",
        "tool": "inspect_runtime",
        "transport": transport,
        "fastmcp_runtime": fastmcp_runtime,
        "auth_required": auth_required,
        "runtime_health": runtime_health_data or {},
        "capabilities": {
            "tool_count": len(runtime_tools),
            "resource_count": len(runtime_resources),
            "prompt_count": len(runtime_prompts),
        },
        "tools": runtime_tools,
        "resources": runtime_resources,
        "prompts": runtime_prompts,
        "provider_count": len(provider_registry.manifests()),
        "providers": provider_registry.statuses(),
    }


def manage_providers(
    action: str = "list",
    *,
    module: str | None = None,
    group: str = "fl_mcp.providers",
) -> dict[str, object]:
    provider_registry = get_provider_registry(load_entry_points=False)

    if action == "discover":
        discovery = provider_registry.load_from_entry_points(group=group)
        discovery_status = "ok"
        if discovery.errors and discovery.loaded:
            discovery_status = "partial"
        elif discovery.errors:
            discovery_status = "error"
        return {
            "status": discovery_status,
            "tool": "manage_providers",
            "action": action,
            "loaded": [manifest.model_dump() for manifest in discovery.loaded],
            "errors": [error.model_dump() for error in discovery.errors],
            "loaded_count": len(discovery.loaded),
            "error_count": len(discovery.errors),
            "provider_count": len(provider_registry.manifests()),
            "providers": provider_registry.statuses(),
        }
    if action == "load_module":
        if not module:
            return {
                "status": "error",
                "tool": "manage_providers",
                "action": action,
                "error": "module is required for action=load_module",
            }
        loaded_manifest = provider_registry.load_from_module(module)
        return {
            "status": "ok",
            "tool": "manage_providers",
            "action": action,
            "loaded": loaded_manifest.model_dump(),
            "provider_count": len(provider_registry.manifests()),
            "providers": provider_registry.statuses(),
        }
    if action == "startup":
        started = provider_registry.startup_all()
        return {
            "status": "ok",
            "tool": "manage_providers",
            "action": action,
            "started": started,
            "providers": provider_registry.statuses(),
        }
    if action == "shutdown":
        stopped = provider_registry.shutdown_all()
        return {
            "status": "ok",
            "tool": "manage_providers",
            "action": action,
            "stopped": stopped,
            "providers": provider_registry.statuses(),
        }
    return {
        "status": "ok",
        "tool": "manage_providers",
        "action": "list",
        "provider_count": len(provider_registry.manifests()),
        "providers": provider_registry.statuses(),
    }
