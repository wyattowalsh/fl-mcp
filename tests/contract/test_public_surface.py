import asyncio
import json
from types import SimpleNamespace
from typing import Any, cast

import pytest

import fl_mcp.server.factory as factory_module
from fl_mcp.config import RuntimeConfig
from fl_mcp.config.settings import settings
from fl_mcp.prompts.registry import prompt_names
from fl_mcp.resources import surface as surface_resources
from fl_mcp.tools import compact
from fl_mcp.tools.fl_surface import FL_TOOL_SPECS

EXPECTED_COMPACT_TOOL_NAMES = set(compact.COMPACT_TOOL_NAMES)
EXPECTED_PROVIDER_NAMES = {"flapi-live", "piano-roll-script", "midi-fallback", "mock"}
EXPECTED_RESOURCE_URIS = {
    "runtime://health",
    "runtime://capabilities",
    "providers://matrix",
    "project://snapshot",
    "project://arrangement",
}
EXPECTED_RESOURCE_TEMPLATE_URIS = {
    "audio://analyses/{analysis_id}",
    "render://jobs/{job_id}",
    "runtime://capabilities/{domain}",
}


def test_compact_fastmcp_surface_is_exact_12_tool_console(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_token", None)
    server = factory_module.create_server(RuntimeConfig())

    async def inspect() -> tuple[set[str], set[str], set[str]]:
        tools = await server.list_tools()
        resources = await server.list_resources()
        prompts = await server.list_prompts()
        return (
            {str(tool.name) for tool in tools},
            {str(resource.uri) for resource in resources},
            {str(prompt.name) for prompt in prompts},
        )

    tool_names, resource_uris, registered_prompts = asyncio.run(inspect())

    assert tool_names == EXPECTED_COMPACT_TOOL_NAMES
    assert len(tool_names) == 12
    assert "fl_mixer_set_track_volume" not in tool_names
    assert "mixer_set_track_volume" not in tool_names
    assert resource_uris == EXPECTED_RESOURCE_URIS
    assert registered_prompts == set(prompt_names())


def test_runtime_health_resource_payload_is_json_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_token", None)
    server = factory_module.create_server(RuntimeConfig())

    async def read_health_resource() -> str:
        result = await server.read_resource("runtime://health")
        return cast(str, result.contents[0].content)

    payload = json.loads(asyncio.run(read_health_resource()))
    assert payload["service"] == "fl-mcp"
    assert payload["status"] in {"ok", "warning", "error"}


def test_project_resources_are_registered_and_json_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_token", None)
    server = factory_module.create_server(RuntimeConfig())

    async def read_resource(uri: str) -> dict[str, object]:
        result = await server.read_resource(uri)
        return cast(dict[str, object], json.loads(cast(str, result.contents[0].content)))

    snapshot = asyncio.run(read_resource("project://snapshot"))
    arrangement = asyncio.run(read_resource("project://arrangement"))

    assert snapshot["schema_version"] == "1.0"
    assert "tracks" in arrangement
    assert "markers" in arrangement


def test_resource_surface_payloads_cover_capabilities_and_unknown_tasks() -> None:
    capabilities = surface_resources.runtime_capabilities()
    provider_matrix = surface_resources.provider_matrix()
    supported_domain = surface_resources.domain_operations("transport")
    unsupported_domain = surface_resources.domain_operations("not-real")
    unknown_render = surface_resources.render_job("missing-job")
    unknown_analysis = surface_resources.audio_analysis("missing-analysis")

    capability_data = cast(dict[str, object], capabilities["data"])
    capability_domains = cast(list[str], capability_data["domains"])
    first_tool = cast(list[dict[str, object]], capability_data["tools"])[0]

    assert capabilities["resource"] == "runtime://capabilities"
    assert set(capability_domains) >= {"transport", "render"}
    assert "operation_id" in first_tool
    assert provider_matrix["resource"] == "providers://matrix"
    assert set(cast(dict[str, object], provider_matrix["data"]).keys()) == EXPECTED_PROVIDER_NAMES
    assert supported_domain["resource"] == "runtime://capabilities/transport"
    assert cast(dict[str, object], supported_domain["data"])["domain"] == "transport"
    assert unsupported_domain["resource"] == "runtime://capabilities/not-real"
    assert cast(dict[str, object], unsupported_domain["data"])["error"] == "unsupported_domain"
    assert unknown_render["resource"] == "render://jobs/missing-job"
    assert cast(dict[str, object], unknown_render["data"])["message"] == "unknown_job"
    assert unknown_analysis["resource"] == "audio://analyses/missing-analysis"
    assert cast(dict[str, object], unknown_analysis["data"])["message"] == "unknown_analysis"


def test_search_schema_and_execute_cover_every_internal_operation() -> None:
    search = compact.fl_search_capabilities(limit=100)
    assert search["total"] == len(FL_TOOL_SPECS)

    for spec in FL_TOOL_SPECS:
        operation_id = compact.operation_id_for_spec(spec)
        schema = compact.fl_get_capability_schema(operation_id)
        assert schema["status"] == "ok"
        assert cast(dict[str, object], schema["capability"])["operation_id"] == operation_id
        assert schema["request_schema"]
        assert schema["response_schema"]

        request = compact.example_request_for_spec(spec)
        executed = compact.fl_execute(operation_id, request, provider="mock")
        assert executed["operation_id"] == operation_id
        assert executed["tool"] == "fl_execute"
        assert executed["status"] in {"ok", "partial", "error"}
        if executed["status"] == "error":
            result = cast(dict[str, Any], executed.get("result", {}))
            assert result.get("message") in {
                "unknown_job",
                "unknown_analysis",
            } or result.get("error_code") in {
                "calibration_required",
                "preset_unavailable",
                "plugin_not_installed",
                "live_probe_failed",
            }


def test_batch_execute_supports_ordered_workflow_with_readback() -> None:
    result = compact.fl_batch_execute(
        [
            {
                "operation_id": "transport.set_tempo",
                "request": {"bpm": 128},
                "provider": "mock",
                "label": "tempo",
            },
            {
                "operation_id": "mixer.set_track_volume",
                "request": {"track_index": 0, "volume": 0.75},
                "provider": "mock",
                "label": "mix",
            },
        ],
        readback_policy="after_each",
    )

    assert result["status"] == "ok"
    assert result["total"] == 2
    assert result["succeeded"] == 2
    for item in cast(list[dict[str, object]], result["results"]):
        assert "readback" in item


def test_batch_execute_auto_readback_translates_setter_index() -> None:
    result = compact.fl_batch_execute(
        [
            {
                "operation_id": "mixer.set_track_pan",
                "request": {"index": 0, "pan": 0.1},
                "provider": "mock",
            }
        ],
        readback_policy="after_each",
    )
    item = cast(list[dict[str, object]], result["results"])[0]
    readback = cast(dict[str, object], item["readback"])

    assert result["status"] == "ok"
    assert result["succeeded"] == 1
    assert item["status"] == "ok"
    assert readback["status"] == "ok"


def test_batch_execute_after_batch_defers_generated_readback() -> None:
    result = compact.fl_batch_execute(
        [
            {
                "operation_id": "mixer.set_track_pan",
                "request": {"index": 0, "pan": 0.1},
                "provider": "mock",
            }
        ],
        readback_policy="after_batch",
    )
    item = cast(list[dict[str, object]], result["results"])[0]
    readback = cast(dict[str, object], item["readback"])

    assert result["status"] == "ok"
    assert result["succeeded"] == 1
    assert item["status"] == "ok"
    assert readback["operation_id"] == "mixer.get_track_pan"
    assert readback["status"] == "ok"


def test_search_capabilities_uses_agent_safe_provider_and_phrase_matching() -> None:
    phrase = compact.fl_search_capabilities(query="set mixer track volume", provider="auto")
    invalid_provider = compact.fl_search_capabilities(query="tempo", provider="missing-provider")

    assert phrase["status"] == "ok"
    assert cast(list[dict[str, object]], phrase["results"])[0]["operation_id"] == (
        "mixer.set_track_volume"
    )
    assert invalid_provider["status"] == "error"
    assert invalid_provider["error"] == "unknown provider filter: missing-provider"


def test_plugin_profile_capabilities_are_internal_and_discoverable() -> None:
    search = compact.fl_search_capabilities(query="set Sylenth cutoff")
    schema = compact.fl_get_capability_schema("plugins.set_mapped_parameter")

    assert search["status"] == "ok"
    assert cast(list[dict[str, object]], search["results"])[0]["operation_id"] == (
        "plugins.set_mapped_parameter"
    )
    assert schema["status"] == "ok"
    assert "plugins_set_mapped_parameter" not in EXPECTED_COMPACT_TOOL_NAMES
    assert "plugin_profile_metadata" in cast(list[dict[str, object]], schema["examples"])[0]


def test_plugin_browser_returns_profile_inventory_status() -> None:
    browser = compact.fl_browser(action="search", kind="plugin", query="sylenth")
    asset_status = cast(dict[str, object], browser["asset_discovery_status"])
    profile_hits = cast(list[dict[str, object]], asset_status["profile_hits"])

    assert browser["status"] == "ok"
    assert asset_status["asset_catalog"] == "plugin_profile_registry"
    assert any(
        cast(dict[str, object], hit.get("profile", {})).get("profile_id")
        == "lennardigital.sylenth1"
        for hit in profile_hits
    )


def test_plugin_trash_reports_desired_not_installed() -> None:
    schema = compact.fl_get_capability_schema("plugins.resolve_profile")
    browser = compact.fl_browser(action="search", kind="plugin", query="trash")
    asset_status = cast(dict[str, object], browser["asset_discovery_status"])
    profile_hits = cast(list[dict[str, object]], asset_status["profile_hits"])

    assert schema["status"] == "ok"
    assert any(
        cast(dict[str, object], hit.get("inventory") or {}).get("status") == "not_installed"
        and (cast(dict[str, object], hit.get("profile") or {}).get("profile_id") == "izotope.trash")
        for hit in profile_hits
    )


def test_plugin_mapped_parameter_fails_closed_without_calibration() -> None:
    executed = compact.fl_execute(
        "plugins.set_mapped_parameter",
        {
            "profile_id": "lennardigital.sylenth1",
            "control_id": "filter.cutoff",
            "value": 1000.0,
        },
        provider="mock",
    )
    result = cast(dict[str, object], executed["result"])

    assert executed["status"] == "error"
    assert result["error_code"] == "calibration_required"
    assert "calibration" in cast(dict[str, object], result["result"])


def test_capability_schema_exposes_structured_provider_support() -> None:
    schema = compact.fl_get_capability_schema("transport.set_tempo")
    details = cast(list[dict[str, object]], schema["provider_support_details"])
    by_provider = {cast(str, item["provider"]): item for item in details}

    assert schema["status"] == "ok"
    assert "flapi-live" in schema["provider_support"]
    assert by_provider["flapi-live"]["mode"] == "host_file_bridge"
    assert by_provider["flapi-live"]["status"] == "available"


def test_forced_live_provider_is_attemptable_for_every_internal_operation() -> None:
    for spec in FL_TOOL_SPECS:
        operation_id = compact.operation_id_for_spec(spec)
        schema = compact.fl_get_capability_schema(operation_id)
        details = cast(list[dict[str, object]], schema["provider_support_details"])
        by_provider = {cast(str, item["provider"]): item for item in details}

        assert "flapi-live" in schema["provider_support"], operation_id
        assert by_provider["flapi-live"]["mode"] == "host_file_bridge"
        assert by_provider["flapi-live"]["status"] in {"available", "attemptable"}


def test_live_mode_capability_schema_reports_flapi_live_default_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(compact.DEFAULT_BRIDGE, "mode", "live")

    schema = compact.fl_get_capability_schema("automation.create_clip")
    capability = cast(dict[str, object], schema["capability"])

    assert schema["status"] == "ok"
    assert capability["default_provider"] == "flapi-live"


def test_granular_schema_rejects_negative_indices_and_out_of_range_values() -> None:
    negative = compact.fl_execute("mixer.set_track_volume", {"index": -1}, provider="mock")
    too_loud = compact.fl_execute(
        "mixer.set_track_volume",
        {"index": 0, "volume": 99},
        provider="mock",
    )

    assert negative["status"] == "error"
    assert too_loud["status"] == "error"


def test_custom_provider_name_executes_through_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    class Registry:
        def manifests(self) -> list[object]:
            return []

        def resolve_name(self, provider: str) -> str:
            return provider

        def get(self, provider: str) -> object:
            return object()

        def execute(self, provider: str, **_: object) -> object:
            return SimpleNamespace(
                success=True,
                provider=provider,
                bridge_mode="custom",
                execution_id="custom-provider-execution",
                message="custom provider executed transport.set_tempo",
                error_code=None,
                result={"bpm": 141},
            )

    monkeypatch.setattr(
        compact, "get_provider_registry", lambda load_entry_points=False: Registry()
    )

    executed = compact.fl_execute(
        "transport.set_tempo",
        {"bpm": 141},
        provider="studio-custom",
    )

    assert executed["status"] == "ok"
    assert executed["provider"] == "studio-custom"
    assert executed["execution_id"] == "custom-provider-execution"


def test_live_mode_auto_render_attempts_live_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    class Registry:
        def manifests(self) -> list[object]:
            return []

        def resolve_name(self, provider: str) -> str:
            return provider

        def get(self, provider: str) -> object:
            return object()

        def execute(self, provider: str, **_: object) -> object:
            return SimpleNamespace(
                success=False,
                provider=provider,
                bridge_mode="live",
                execution_id="render-live-attempt",
                message="FL host API callable not found for render.export.",
                error_code="api_missing",
                result={
                    "operation_id": "render.export",
                    "attempted_modules": ["render", "general"],
                    "attempted_functions": ["render.render", "general.render"],
                    "remediation": "Register a custom provider or update the bridge.",
                },
            )

    monkeypatch.setattr(
        compact, "get_provider_registry", lambda load_entry_points=False: Registry()
    )
    monkeypatch.setattr(compact.DEFAULT_BRIDGE, "mode", "live")

    render = compact.fl_render({"output_path": "mock://render.wav"})

    assert render["status"] == "error"
    assert render["error"] == "FL host API callable not found for render.export."
    result = cast(dict[str, object], render["result"])
    assert result["provider"] == "flapi-live"
    assert result["bridge_mode"] == "live"


def test_live_mode_apply_auto_routes_through_flapi_live_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[str, dict[str, object]]] = []

    class Registry:
        def manifests(self) -> list[object]:
            return []

        def resolve_name(self, provider: str) -> str:
            return provider

        def get(self, provider: str) -> object:
            return object()

        def execute(self, provider: str, **kwargs: object) -> object:
            captured.append((provider, kwargs))
            return SimpleNamespace(
                success=True,
                provider=provider,
                bridge_mode="live",
                execution_id="apply-live-attempt",
                message="live provider executed transaction change",
                error_code=None,
                result={
                    "operation_id": f"{kwargs['domain']}.{kwargs['operation']}",
                    "payload": kwargs["payload"],
                },
            )

    monkeypatch.setenv("FL_MCP_BRIDGE_MODE", "live")
    monkeypatch.setattr(compact.DEFAULT_BRIDGE, "mode", "live")
    monkeypatch.setattr(
        "fl_mcp.providers.runtime.get_provider_registry",
        lambda load_entry_points=False: Registry(),
    )

    applied = compact.fl_apply(
        {
            "request_id": "compact-live-apply",
            "mode": "apply",
            "execution_policy": "allow-partial",
            "changes": [
                {
                    "domain": "automation",
                    "operation": "create_clip",
                    "rollback_class": "checkpointed",
                    "payload": {"name": "Filter Sweep"},
                }
            ],
        }
    )
    result = cast(dict[str, object], applied["result"])
    diff_summary = cast(dict[str, object], result["diff_summary"])
    reports = cast(list[dict[str, object]], diff_summary["reports"])

    assert applied["status"] == "ok"
    assert result["status"] == "applied"
    assert captured[0][0] == "flapi-live"
    assert captured[0][1]["domain"] == "automation"
    assert captured[0][1]["operation"] == "create_clip"
    assert reports[0]["provider"] == "flapi-live"


def test_execute_and_batch_surface_failed_transaction_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = "Selected-controller adapter does not implement mixer.set_track_pan."

    class Registry:
        def manifests(self) -> list[object]:
            return []

        def resolve_name(self, provider: str) -> str:
            return provider

        def get(self, provider: str) -> object:
            return object()

        def execute(self, provider: str, **_: object) -> object:
            return SimpleNamespace(
                success=False,
                provider=provider,
                bridge_mode="live",
                execution_id="selected-controller-test",
                message=message,
                error_code="unsupported_operation",
                result={},
            )

    monkeypatch.setattr(
        compact, "get_provider_registry", lambda load_entry_points=False: Registry()
    )

    executed = compact.fl_execute(
        "mixer.set_track_pan",
        {"index": 17, "pan": 0.05},
        provider="flapi-live",
    )
    assert executed["status"] == "error"
    assert executed["provider"] == "flapi-live"
    assert executed["execution_id"] == "selected-controller-test"
    assert executed["error"] == message

    batch = compact.fl_batch_execute(
        [
            {
                "operation_id": "mixer.set_track_pan",
                "request": {"index": 17, "pan": 0.05},
                "provider": "flapi-live",
            }
        ]
    )
    assert batch["status"] == "error"
    assert batch["succeeded"] == 0
    assert batch["failed"] == 1


def test_execute_successful_transaction_omits_error_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Registry:
        def manifests(self) -> list[object]:
            return []

        def resolve_name(self, provider: str) -> str:
            return provider

        def get(self, provider: str) -> object:
            return object()

        def execute(self, provider: str, **_: object) -> object:
            return SimpleNamespace(
                success=True,
                provider=provider,
                bridge_mode="live",
                execution_id="selected-controller-success",
                message="Selected controller executed mixer.set_track_pan.",
                error_code=None,
                result={"value": 0.05},
            )

    monkeypatch.setattr(
        compact, "get_provider_registry", lambda load_entry_points=False: Registry()
    )

    executed = compact.fl_execute(
        "mixer.set_track_pan",
        {"index": 17, "pan": 0.05},
        provider="flapi-live",
    )

    assert executed["status"] == "ok"
    assert executed["provider"] == "flapi-live"
    assert executed["execution_id"] == "selected-controller-success"
    assert "error" not in executed


def test_selected_controller_live_capabilities_are_discoverable() -> None:
    schema = compact.fl_get_capability_schema("mixer.set_track_pan")
    capability = cast(dict[str, object], schema["capability"])
    provider_support = cast(list[str], schema["provider_support"])

    assert schema["status"] == "ok"
    assert "flapi-live" in provider_support
    assert capability["default_provider"] == "mock"


def test_browser_render_and_audio_entrypoints_are_structured() -> None:
    browser = compact.fl_browser(action="search", kind="plugin", query="preset")
    render = compact.fl_render({"output_path": "mock://render.wav"})
    audio = compact.fl_analyze_audio({"input_path": "mock://render.wav"})

    assert browser["status"] == "ok"
    assert browser["results"]
    assert render["status"] == "ok"
    assert render["task_id"]
    assert audio["status"] == "ok"
    assert audio["task_id"]


def test_runtime_domain_capability_template_is_registered_when_fastmcp_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_token", None)
    server = factory_module.create_server(RuntimeConfig())

    async def get_templates() -> set[str]:
        templates = await server.list_resource_templates()
        uris: set[str] = set()
        for template in templates:
            try:
                uri = template.uri_template
            except AttributeError:
                uri = template.uriTemplate
            uris.add(str(uri))
        return uris

    assert asyncio.run(get_templates()) == EXPECTED_RESOURCE_TEMPLATE_URIS
