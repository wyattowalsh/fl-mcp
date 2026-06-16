"""Resources-first read surface."""

import logging
from collections.abc import Sequence

from fl_mcp.graph.model import ProjectGraph
from fl_mcp.providers.runtime import get_provider_registry
from fl_mcp.runtime.health import RuntimeHealth
from fl_mcp.runtime.state import get_runtime_state
from fl_mcp.schemas.runtime_surface import (
    AudioAnalysisResource,
    ProjectArrangementResource,
    ProjectSnapshotResource,
    RenderJobResource,
)
from fl_mcp.tools.fl_surface import PROVIDER_MATRIX, capability_catalog, domain_capability_catalog

logger = logging.getLogger(__name__)


def _catalog_domains() -> set[str]:
    domains = capability_catalog().get("domains", [])
    if not isinstance(domains, Sequence) or isinstance(domains, str):
        return set()
    return {str(domain) for domain in domains}


def project_snapshot(graph: ProjectGraph | None = None) -> dict[str, object]:
    """Return a snapshot of the current project graph.

    Args:
        graph: Optional replacement graph to store before snapshotting.

    Returns:
        Resource envelope containing the serialised project snapshot.
    """
    runtime_state = get_runtime_state()
    if graph is not None:
        runtime_state.replace_graph(ProjectGraph.model_validate(graph))
    return ProjectSnapshotResource(data=runtime_state.snapshot_graph()).model_dump()


def project_arrangement() -> dict[str, object]:
    """Return the current project arrangement resource."""
    runtime_state = get_runtime_state()
    return ProjectArrangementResource(data=runtime_state.snapshot_arrangement()).model_dump()


def runtime_health() -> dict[str, object]:
    """Return the runtime health resource."""
    return {"resource": "runtime://health", "data": RuntimeHealth().model_dump()}


def runtime_capabilities() -> dict[str, object]:
    """Return the runtime capabilities catalog resource."""
    return {"resource": "runtime://capabilities", "data": capability_catalog()}


def provider_matrix() -> dict[str, object]:
    """Return the aggregated provider matrix resource with manifests and statuses."""
    provider_registry = get_provider_registry(load_entry_points=False)
    manifests = {manifest.name: manifest.model_dump() for manifest in provider_registry.manifests()}
    statuses: dict[str, dict[str, object]] = {}
    for status in provider_registry.statuses():
        manifest = status.get("manifest")
        if not isinstance(manifest, dict):
            continue
        name = manifest.get("name")
        if isinstance(name, str):
            statuses[name] = status
    data = {
        name: {
            **PROVIDER_MATRIX.get(name, {}),
            **({"manifest": manifests[name]} if name in manifests else {}),
            **({"status": statuses[name]} if name in statuses else {}),
        }
        for name in sorted(set(PROVIDER_MATRIX) | set(manifests) | set(statuses))
    }
    return {"resource": "providers://matrix", "data": data}


def domain_operations(domain: str) -> dict[str, object]:
    """Return the capability catalog for a single FL Studio domain.

    Args:
        domain: Domain name (e.g. ``"mixer"``, ``"channels"``).

    Returns:
        Resource envelope with available tools and providers, or an error
        payload when the domain is unsupported.
    """
    try:
        canonical_domain = domain.strip().replace("_", "-")
    except (AttributeError, TypeError) as exc:
        logger.warning("Invalid domain argument in domain_operations: %s", exc)
        return {"status": "error", "error": str(exc)}
    available_domains = _catalog_domains()
    if canonical_domain not in available_domains:
        return {
            "resource": f"runtime://capabilities/{canonical_domain}",
            "data": {
                "domain": canonical_domain,
                "error": "unsupported_domain",
                "available_domains": sorted(available_domains),
                "tools": [],
                "providers": {},
            },
        }
    return {
        "resource": f"runtime://capabilities/{canonical_domain}",
        "data": domain_capability_catalog(canonical_domain),
    }


def render_job(job_id: str) -> dict[str, object]:
    """Return the render job resource for the given job ID.

    Args:
        job_id: Unique identifier of the render job.
    """
    record = get_runtime_state().get_render_job(job_id)
    if record is None:
        return {
            "resource": f"render://jobs/{job_id}",
            "data": {"id": job_id, "kind": "render", "state": "failed", "message": "unknown_job"},
        }
    return RenderJobResource(resource=f"render://jobs/{job_id}", data=record).model_dump()


def audio_analysis(analysis_id: str) -> dict[str, object]:
    """Return the audio analysis resource for the given analysis ID.

    Args:
        analysis_id: Unique identifier of the audio analysis record.
    """
    record = get_runtime_state().get_audio_analysis(analysis_id)
    if record is None:
        return {
            "resource": f"audio://analyses/{analysis_id}",
            "data": {
                "id": analysis_id,
                "kind": "audio-analysis",
                "state": "failed",
                "message": "unknown_analysis",
            },
        }
    return AudioAnalysisResource(
        resource=f"audio://analyses/{analysis_id}",
        data=record,
    ).model_dump()
