"""Public MCP tool handlers."""

from fl_mcp.graph.model import ProjectGraph
from fl_mcp.providers.runtime import get_provider_registry
from fl_mcp.schemas import TransactionEnvelope
from fl_mcp.transactions.apply import apply_changes as apply_engine
from fl_mcp.transactions.planner import plan_changes as plan_engine


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


def inspect_runtime() -> dict[str, str]:
    return {"status": "ok", "tool": "inspect_runtime"}


def manage_providers(
    action: str = "list",
    *,
    module: str | None = None,
    group: str = "fl_mcp.providers",
) -> dict[str, object]:
    provider_registry = get_provider_registry(load_entry_points=False)

    if action == "discover":
        loaded = provider_registry.load_from_entry_points(group=group)
        return {
            "status": "ok",
            "tool": "manage_providers",
            "action": action,
            "loaded": [manifest.model_dump() for manifest in loaded],
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
