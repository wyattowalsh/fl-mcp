"""Public MCP tool handlers."""

from fl_mcp.graph.model import ProjectGraph
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


def manage_providers() -> dict[str, str]:
    return {"status": "ok", "tool": "manage_providers"}
