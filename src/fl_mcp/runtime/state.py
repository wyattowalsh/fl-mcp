"""In-memory runtime state for project and task resources."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import cast
from uuid import uuid4

from fl_mcp.graph.model import ProjectGraph
from fl_mcp.schemas._types import TaskState
from fl_mcp.schemas.runtime_surface import (
    ProjectArrangementModel,
    ProviderTaskRecord,
)

_STATE_LOCK = threading.Lock()
_MAX_TASK_RECORDS = 1000


def _normalize_task_state(value: object) -> TaskState:
    if value == "cancelled":
        return "canceled"
    if value in {"queued", "running", "completed", "canceled", "failed"}:
        return cast(TaskState, value)
    return "queued"


def _artifact_list(result: dict[str, object]) -> list[str]:
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, list):
        return []
    return [str(item) for item in artifacts]


@dataclass(slots=True)
class RuntimeState:
    """Thread-safe in-memory store for project graph and async task records."""

    graph: ProjectGraph = field(default_factory=ProjectGraph)
    arrangement: ProjectArrangementModel = field(default_factory=ProjectArrangementModel)
    render_jobs: dict[str, ProviderTaskRecord] = field(default_factory=dict)
    audio_analyses: dict[str, ProviderTaskRecord] = field(default_factory=dict)

    def snapshot_graph(self) -> ProjectGraph:
        """Return a deep copy of the current project graph."""
        with _STATE_LOCK:
            return self.graph.model_copy(deep=True)

    def snapshot_arrangement(self) -> ProjectArrangementModel:
        """Return a deep copy of the current arrangement state."""
        with _STATE_LOCK:
            return self.arrangement.model_copy(deep=True)

    def replace_graph(self, graph: ProjectGraph) -> ProjectGraph:
        """Atomically replace the project graph and return the stored copy.

        Args:
            graph: New project graph to store.

        Returns:
            Deep copy of the newly stored graph.
        """
        with _STATE_LOCK:
            self.graph = graph.model_copy(deep=True)
            return self.graph.model_copy(deep=True)

    def replace_arrangement(self, arrangement: ProjectArrangementModel) -> ProjectArrangementModel:
        """Atomically replace the arrangement state and return the stored copy.

        Args:
            arrangement: New arrangement model to store.

        Returns:
            Deep copy of the newly stored arrangement.
        """
        with _STATE_LOCK:
            self.arrangement = arrangement.model_copy(deep=True)
            return self.arrangement.model_copy(deep=True)

    def create_render_job(
        self,
        *,
        provider: str,
        tool: str,
        operation: str,
        payload: dict[str, object],
        result: dict[str, object],
    ) -> ProviderTaskRecord:
        """Create and store a render job record from a provider execution result.

        Args:
            provider: Name of the provider that executed the render.
            tool: Tool name that initiated the render.
            operation: Specific operation within the tool.
            payload: Original request payload.
            result: Provider execution result containing job metadata.

        Returns:
            The newly created task record.
        """
        job_id = str(
            result.get("job_id")
            or result.get("task_id")
            or result.get("execution_id")
            or f"render-{uuid4().hex[:12]}"
        )
        record = ProviderTaskRecord(
            id=job_id,
            kind="render",
            provider=provider,
            state=_normalize_task_state(result.get("task_status") or result.get("state")),
            message=str(result.get("message")) if result.get("message") is not None else None,
            created_from_tool=tool,
            created_from_operation=operation,
            payload=dict(payload),
            result=dict(result),
            artifacts=_artifact_list(result),
        )
        with _STATE_LOCK:
            self.render_jobs[job_id] = record
            while len(self.render_jobs) > _MAX_TASK_RECORDS:
                oldest_key = next(iter(self.render_jobs))
                del self.render_jobs[oldest_key]
        return record

    def create_audio_analysis(
        self,
        *,
        provider: str,
        tool: str,
        operation: str,
        payload: dict[str, object],
        result: dict[str, object],
    ) -> ProviderTaskRecord:
        """Create and store an audio analysis record from a provider execution result.

        Args:
            provider: Name of the provider that executed the analysis.
            tool: Tool name that initiated the analysis.
            operation: Specific operation within the tool.
            payload: Original request payload.
            result: Provider execution result containing analysis metadata.

        Returns:
            The newly created task record.
        """
        analysis_id = str(
            result.get("analysis_id")
            or result.get("task_id")
            or result.get("execution_id")
            or f"analysis-{uuid4().hex[:12]}"
        )
        record = ProviderTaskRecord(
            id=analysis_id,
            kind="audio-analysis",
            provider=provider,
            state=_normalize_task_state(result.get("task_status") or result.get("state")),
            message=str(result.get("message")) if result.get("message") is not None else None,
            created_from_tool=tool,
            created_from_operation=operation,
            payload=dict(payload),
            result=dict(result),
            artifacts=_artifact_list(result),
        )
        with _STATE_LOCK:
            self.audio_analyses[analysis_id] = record
            while len(self.audio_analyses) > _MAX_TASK_RECORDS:
                oldest_key = next(iter(self.audio_analyses))
                del self.audio_analyses[oldest_key]
        return record

    def get_render_job(self, job_id: str) -> ProviderTaskRecord | None:
        """Retrieve a deep copy of a render job record by ID.

        Args:
            job_id: Unique identifier of the render job.

        Returns:
            Copy of the task record, or None if not found.
        """
        with _STATE_LOCK:
            record = self.render_jobs.get(job_id)
        return None if record is None else record.model_copy(deep=True)

    def get_audio_analysis(self, analysis_id: str) -> ProviderTaskRecord | None:
        """Retrieve a deep copy of an audio analysis record by ID.

        Args:
            analysis_id: Unique identifier of the audio analysis.

        Returns:
            Copy of the task record, or None if not found.
        """
        with _STATE_LOCK:
            record = self.audio_analyses.get(analysis_id)
        return None if record is None else record.model_copy(deep=True)

    def cancel_render_job(self, job_id: str) -> ProviderTaskRecord | None:
        """Mark a render job as canceled.

        Args:
            job_id: Unique identifier of the render job to cancel.

        Returns:
            Updated task record, or None if the job was not found.
        """
        with _STATE_LOCK:
            record = self.render_jobs.get(job_id)
            if record is None:
                return None
            updated = record.model_copy(
                update={"state": "canceled", "message": "Render job canceled."},
                deep=True,
            )
            self.render_jobs[job_id] = updated
        return updated.model_copy(deep=True)

    def cancel_audio_analysis(self, analysis_id: str) -> ProviderTaskRecord | None:
        """Mark an audio analysis as canceled.

        Args:
            analysis_id: Unique identifier of the audio analysis to cancel.

        Returns:
            Updated task record, or None if the analysis was not found.
        """
        with _STATE_LOCK:
            record = self.audio_analyses.get(analysis_id)
            if record is None:
                return None
            updated = record.model_copy(
                update={"state": "canceled", "message": "Audio analysis canceled."},
                deep=True,
            )
            self.audio_analyses[analysis_id] = updated
        return updated.model_copy(deep=True)


_GLOBAL_RUNTIME_STATE: RuntimeState | None = None


def get_runtime_state() -> RuntimeState:
    """Return the global singleton RuntimeState, creating it on first access."""
    global _GLOBAL_RUNTIME_STATE
    with _STATE_LOCK:
        if _GLOBAL_RUNTIME_STATE is None:
            _GLOBAL_RUNTIME_STATE = RuntimeState()
        return _GLOBAL_RUNTIME_STATE


def reset_runtime_state() -> None:
    """Reset the global RuntimeState singleton to None for testing."""
    global _GLOBAL_RUNTIME_STATE
    with _STATE_LOCK:
        _GLOBAL_RUNTIME_STATE = None
