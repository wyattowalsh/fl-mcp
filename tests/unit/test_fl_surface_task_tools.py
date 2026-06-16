from collections.abc import Callable
from typing import cast

import pytest
from fastmcp import Client

import fl_mcp.bridge.fl_studio as bridge_module
import fl_mcp.tools.fl_surface as fl_surface
from fl_mcp.bridge.bundle import bridge_runner_command
from fl_mcp.bridge.fl_studio import FLStudioBridge
from fl_mcp.resources import surface as surface_resources
from fl_mcp.runtime.state import reset_runtime_state
from fl_mcp.schemas.fl_tools import (
    AudioAnalysisRequest,
    AudioAnalyzeRequest,
    EmptyFLToolRequest,
    RenderExportRequest,
    RenderJobRequest,
    TransportTempoRequest,
)
from fl_mcp.server.factory import create_default_server
from fl_mcp.tools import compact
from fl_mcp.tools.fl_surface import FL_TOOL_HANDLERS


def _task_payload(response: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], response["task"])


def _resource_data(resource: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], resource["data"])


def test_render_task_tools_roundtrip_through_runtime_state() -> None:
    started = FL_TOOL_HANDLERS["render_export"](
        RenderExportRequest(output_path="mix.wav", provider="mock")
    )
    started_task = _task_payload(started)
    task_id = cast(str, started_task["id"])

    fetched = FL_TOOL_HANDLERS["render_get_job"](RenderJobRequest(job_id=task_id))
    canceled = FL_TOOL_HANDLERS["render_cancel_job"](RenderJobRequest(job_id=task_id))
    resource = surface_resources.render_job(task_id)
    fetched_task = _task_payload(fetched)
    canceled_task = _task_payload(canceled)
    resource_data = _resource_data(resource)

    assert started["status"] == "ok"
    assert fetched["status"] == "ok"
    assert fetched_task["id"] == task_id
    assert canceled["status"] == "ok"
    assert canceled_task["state"] == "canceled"
    assert resource_data["id"] == task_id
    assert resource_data["state"] == "canceled"


def test_audio_task_tools_roundtrip_through_runtime_state() -> None:
    started = FL_TOOL_HANDLERS["audio_analyze"](
        AudioAnalyzeRequest(input_path="mix.wav", provider="mock")
    )
    started_task = _task_payload(started)
    task_id = cast(str, started_task["id"])

    fetched = FL_TOOL_HANDLERS["audio_get_analysis"](AudioAnalysisRequest(analysis_id=task_id))
    canceled = FL_TOOL_HANDLERS["audio_cancel_analysis"](AudioAnalysisRequest(analysis_id=task_id))
    resource = surface_resources.audio_analysis(task_id)
    fetched_task = _task_payload(fetched)
    canceled_task = _task_payload(canceled)
    resource_data = _resource_data(resource)

    assert started["status"] == "ok"
    assert fetched["status"] == "ok"
    assert fetched_task["id"] == task_id
    assert canceled["status"] == "ok"
    assert canceled_task["state"] == "canceled"
    assert resource_data["id"] == task_id
    assert resource_data["state"] == "canceled"


def test_live_harness_runs_through_fl_tool_contracts(monkeypatch: pytest.MonkeyPatch) -> None:
    bridge = FLStudioBridge(mode="live", live_command=bridge_runner_command(harness=True))
    monkeypatch.setattr(fl_surface, "DEFAULT_BRIDGE", bridge)
    monkeypatch.setattr(bridge_module, "DEFAULT_BRIDGE", bridge)

    read_result = FL_TOOL_HANDLERS["transport_get_state"](EmptyFLToolRequest())
    mutation_result = FL_TOOL_HANDLERS["transport_set_tempo"](TransportTempoRequest(bpm=120.0))

    assert read_result["status"] == "ok"
    assert read_result["bridge_mode"] == "live"
    assert mutation_result["status"] == "applied"
    assert mutation_result["bridge_mode"] == "live"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "request_payload", "id_field", "resource_getter"),
    [
        (
            "fl_render",
            {"output_path": "native-task-render.wav", "provider": "mock"},
            "job_id",
            surface_resources.render_job,
        ),
        (
            "fl_analyze_audio",
            {"input_path": "native-task-audio.wav", "provider": "mock"},
            "analysis_id",
            surface_resources.audio_analysis,
        ),
    ],
)
async def test_native_fastmcp_task_id_aligns_with_task_resources(
    tool_name: str,
    request_payload: dict[str, object],
    id_field: str,
    resource_getter: Callable[[str], dict[str, object]],
) -> None:
    reset_runtime_state()
    server = create_default_server()

    async with Client(server) as client:
        task = await client.call_tool(tool_name, {"request": request_payload}, task=True)
        await task.wait()
        result = await task.result()

    assert result.is_error is False
    structured_content = cast(dict[str, object], result.structured_content)
    inner_result = cast(dict[str, object], structured_content["result"])
    task_payload = cast(dict[str, object], inner_result["task"])
    task_result = cast(dict[str, object], task_payload["result"])
    resource_data = _resource_data(resource_getter(task.task_id))
    resource_result = cast(dict[str, object], resource_data["result"])

    assert structured_content["task_id"] == task.task_id
    assert inner_result[id_field] == task.task_id
    assert task_payload["id"] == task.task_id
    assert task_result["task_id"] == task.task_id
    assert resource_data["id"] == task.task_id
    assert resource_result["task_id"] == task.task_id


def test_compact_task_entrypoints_attempt_live_backend_in_live_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_runtime_state()
    bridge = FLStudioBridge(mode="live", live_command="/usr/bin/false")
    monkeypatch.setattr(fl_surface, "DEFAULT_BRIDGE", bridge)
    monkeypatch.setattr(bridge_module, "DEFAULT_BRIDGE", bridge)
    monkeypatch.setattr(compact, "DEFAULT_BRIDGE", bridge)

    class Registry:
        def manifests(self) -> list[object]:
            return []

        def resolve_name(self, provider: str) -> str:
            return provider

        def get(self, provider: str) -> object:
            return object()

        def execute(
            self,
            provider: str,
            *,
            domain: str,
            operation: str,
            payload: dict[str, object],
        ) -> object:
            return type(
                "ProviderResult",
                (),
                {
                    "success": False,
                    "provider": provider,
                    "bridge_mode": "live",
                    "execution_id": f"{domain}-{operation}-attempt",
                    "message": f"FL host API callable not found for {domain}.{operation}.",
                    "error_code": "api_missing",
                    "result": {
                        "operation_id": f"{domain}.{operation}",
                        "attempted_modules": [domain],
                        "attempted_functions": [f"{domain}.{operation}"],
                    },
                },
            )()

    monkeypatch.setattr(
        compact, "get_provider_registry", lambda load_entry_points=False: Registry()
    )

    render = compact.fl_render({"output_path": "mix.wav"})
    analysis = compact.fl_analyze_audio({"input_path": "mix.wav"})

    assert render["status"] == "error"
    render_result = cast(dict[str, object], render["result"])
    assert render_result["provider"] == "flapi-live"
    assert render_result["bridge_mode"] == "live"
    assert cast(dict[str, object], render_result["result"])["error_code"] == "api_missing"
    assert analysis["status"] == "error"
    analysis_result = cast(dict[str, object], analysis["result"])
    assert analysis_result["provider"] == "flapi-live"
    assert analysis_result["bridge_mode"] == "live"
    assert cast(dict[str, object], analysis_result["result"])["error_code"] == "api_missing"
