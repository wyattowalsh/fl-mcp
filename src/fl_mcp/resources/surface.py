"""Resources-first read surface."""

from fl_mcp.graph.model import ProjectGraph
from fl_mcp.runtime.health import RuntimeHealth


def project_snapshot(graph: ProjectGraph) -> dict[str, object]:
    return {"resource": "project://snapshot", "data": graph.model_dump()}


def runtime_health() -> dict[str, object]:
    return {"resource": "runtime://health", "data": RuntimeHealth().model_dump()}
