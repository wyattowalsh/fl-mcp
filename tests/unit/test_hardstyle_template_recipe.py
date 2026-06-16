from __future__ import annotations

import json
from pathlib import Path

from fl_mcp.recipes.hardstyle_template import (
    READ_ONLY_PREFLIGHT,
    build_hardstyle_template,
    unsupported_required_operations,
)
from fl_mcp.schemas.bridge import BridgeLiveResponse


class FakeControllerClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def execute(
        self,
        domain: str,
        operation: str,
        payload: dict[str, object] | None = None,
    ) -> BridgeLiveResponse:
        self.calls.append((domain, operation, payload))
        return BridgeLiveResponse(
            success=True,
            message="fake ok",
            execution_id=f"fake-{domain}-{operation}",
            provider="flapi-live",
            result={"domain": domain, "operation": operation},
        )


def test_hardstyle_template_preflight_refuses_mutation_until_scratch_project_supported(
    tmp_path: Path,
) -> None:
    client = FakeControllerClient()
    run = build_hardstyle_template(client=client, audit_dir=tmp_path)

    assert run.status == "blocked"
    assert run.mutations_attempted is False
    assert "general.save_project_as" in run.blockers
    assert "playlist.place_clip" in run.blockers
    assert "render.export" in run.blockers
    assert client.calls == [
        (domain, operation, payload) for domain, operation, payload in READ_ONLY_PREFLIGHT
    ]

    audit = json.loads((tmp_path / "hardstyle-template-preflight.json").read_text())
    assert audit["status"] == "blocked"
    assert audit["mutations_attempted"] is False
    assert audit["template_spec"]["musical"]["tempo_bpm"] == 150.0
    assert (tmp_path / "hardstyle-template-preflight.md").exists()


def test_selected_controller_required_operation_blockers_are_explicit() -> None:
    unsupported = unsupported_required_operations()

    assert unsupported == (
        "general.save_project_as",
        "patterns.create_pattern",
        "piano-roll.send_notes",
        "playlist.create_marker",
        "playlist.place_clip",
        "plugins.load",
        "render.export",
    )
