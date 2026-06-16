"""Oldschool hardstyle template preflight and build recipe.

The recipe deliberately refuses live mutation until the selected-controller path
can create a scratch project, create patterns, place playlist clips, and render.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from fl_mcp.bridge.selected_controller_client import (
    DEFAULT_SELECTED_CONTROLLER_TIMEOUT_SECONDS,
    SelectedControllerClient,
    selected_controller_supports,
)
from fl_mcp.schemas.bridge import BridgeLiveResponse

TEMPLATE_NAME = "fl-mcp-hardstyle-oldschool-template"
DEFAULT_TEMPO_BPM = 150.0
DEFAULT_KEY = "F minor"

FULL_TEMPLATE_REQUIRED_OPERATIONS: tuple[str, ...] = (
    "general.save_project_as",
    "patterns.create_pattern",
    "piano-roll.send_notes",
    "playlist.create_marker",
    "playlist.place_clip",
    "plugins.load",
    "render.export",
)

READ_ONLY_PREFLIGHT: tuple[tuple[str, str, dict[str, object]], ...] = (
    ("transport", "get_state", {}),
    ("mixer", "get_track_count", {}),
    ("mixer", "list_tracks", {"include_empty": True}),
    ("channels", "list_channels", {}),
    ("channels", "get_selected", {}),
    ("plugins", "get_name", {"channel_index": 0}),
)

MIXER_BUS_PLAN: tuple[tuple[int, str, int], ...] = (
    (0, "Master", 0xF2F2F2),
    (1, "HS Pre-master", 0xB8B8B8),
    (2, "HS Kick", 0xF06030),
    (3, "HS Kick Tail / Bass", 0xB43C28),
    (4, "HS Reverse Bass", 0xE0A030),
    (5, "HS Lead Bus", 0x50B8E8),
    (6, "HS Screech Bus", 0x8E63D9),
    (7, "HS Drums", 0x58B368),
    (8, "HS FX", 0x3AA6A6),
    (9, "HS Atmos", 0x5973D9),
    (10, "HS Vox", 0xD96BAA),
    (11, "HS Sidechain / Ducking", 0xF2D24B),
)

ARRANGEMENT_PLAN: tuple[tuple[str, int], ...] = (
    ("Intro", 32),
    ("Mid-intro", 32),
    ("Break", 32),
    ("Buildup", 16),
    ("Climax / Drop", 64),
    ("Anti / Drop Variation", 32),
    ("Outro", 32),
)

MUSICAL_PLAN: dict[str, object] = {
    "tempo_bpm": DEFAULT_TEMPO_BPM,
    "key": DEFAULT_KEY,
    "style": "classic late-2000s / early-2010s oldschool euphoric hardstyle",
    "progression": ["Fm", "Db", "Ab", "Eb"],
    "core_elements": [
        "pitched tok/body/tail hardstyle kick",
        "reverse bass and offbeat bass support",
        "supersaw lead motif with call-and-response variation",
        "oldschool screech/stab layer",
        "claps, hats, rides, impacts, reverses, risers, and downlifters",
        "filter, send, buildup, pre-drop, and sidechain-style automation",
    ],
}


class ControllerClient(Protocol):
    """Selected-controller client protocol used by the recipe."""

    def execute(
        self,
        domain: str,
        operation: str,
        payload: dict[str, object] | None = None,
    ) -> BridgeLiveResponse: ...


@dataclass(frozen=True, slots=True)
class HardstyleTemplateRun:
    """Structured result for a hardstyle-template preflight/build attempt."""

    status: str
    created_at: str
    template_name: str
    mutations_attempted: bool
    blockers: tuple[str, ...]
    preflight: tuple[dict[str, object], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "created_at": self.created_at,
            "template_name": self.template_name,
            "mutations_attempted": self.mutations_attempted,
            "blockers": list(self.blockers),
            "preflight": list(self.preflight),
            "template_spec": {
                "musical": MUSICAL_PLAN,
                "arrangement": [
                    {"section": section, "bars": bars} for section, bars in ARRANGEMENT_PLAN
                ],
                "mixer_buses": [
                    {"track_index": index, "name": name, "color": color}
                    for index, name, color in MIXER_BUS_PLAN
                ],
            },
        }


def unsupported_required_operations(
    required_operations: Iterable[str] = FULL_TEMPLATE_REQUIRED_OPERATIONS,
) -> tuple[str, ...]:
    """Return full-template operations unsupported by the selected-controller adapter."""

    unsupported: list[str] = []
    for operation_id in required_operations:
        domain, operation = operation_id.split(".", 1)
        if not selected_controller_supports(domain, operation):
            unsupported.append(operation_id)
    return tuple(unsupported)


def _preflight_step(
    client: ControllerClient,
    domain: str,
    operation: str,
    payload: dict[str, object],
) -> dict[str, object]:
    try:
        response = client.execute(domain, operation, payload)
    except Exception as exc:
        return {
            "operation_id": f"{domain}.{operation}",
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "operation_id": f"{domain}.{operation}",
        "status": "ok" if response.success else "error",
        "response": response.model_dump(mode="json"),
    }


def _write_audit(audit_dir: Path, run: HardstyleTemplateRun) -> None:
    audit_dir.mkdir(parents=True, exist_ok=True)
    payload = run.to_dict()
    (audit_dir / "hardstyle-template-preflight.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    blockers = "\n".join(f"- {blocker}" for blocker in run.blockers) or "- none"
    preflight = "\n".join(f"- {item['operation_id']}: {item['status']}" for item in run.preflight)
    (audit_dir / "hardstyle-template-preflight.md").write_text(
        "\n".join(
            [
                f"# {TEMPLATE_NAME}",
                "",
                f"- status: `{run.status}`",
                f"- created_at: `{run.created_at}`",
                f"- mutations_attempted: `{run.mutations_attempted}`",
                "",
                "## Blockers",
                "",
                blockers,
                "",
                "## Read-only Preflight",
                "",
                preflight,
                "",
            ]
        ),
        encoding="utf-8",
    )


def build_hardstyle_template(
    *,
    client: ControllerClient | None = None,
    audit_dir: Path | None = None,
    allow_current_project_edits: bool = False,
) -> HardstyleTemplateRun:
    """Run selected-controller preflight and refuse unsafe full-template mutation.

    The full template requires scratch-project creation/save-as, pattern creation,
    playlist arrangement, plugin loading, and render support. Until those
    operations are live-supported by the selected-controller path, this function
    records the blockers and leaves the current FL Studio project untouched.
    """

    active_client = client or SelectedControllerClient()
    created_at = datetime.now(UTC).isoformat()
    preflight = tuple(
        _preflight_step(active_client, domain, operation, payload)
        for domain, operation, payload in READ_ONLY_PREFLIGHT
    )
    unsupported = unsupported_required_operations()
    blockers = list(unsupported)
    if not allow_current_project_edits:
        blockers.append(
            "current-project mutation refused: selected-controller path cannot yet create "
            "or save a scratch FLP before writing template content"
        )

    run = HardstyleTemplateRun(
        status="blocked" if blockers else "ready",
        created_at=created_at,
        template_name=TEMPLATE_NAME,
        mutations_attempted=False,
        blockers=tuple(blockers),
        preflight=preflight,
    )
    if audit_dir is not None:
        _write_audit(audit_dir, run)
    return run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preflight the oldschool hardstyle template build")
    parser.add_argument("--controller-dir", type=Path, default=None)
    parser.add_argument("--audit-dir", type=Path, default=None)
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_SELECTED_CONTROLLER_TIMEOUT_SECONDS,
        help="Selected-controller response timeout in seconds",
    )
    parser.add_argument("--poll-interval", type=float, default=None)
    parser.add_argument("--allow-current-project-edits", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    client = SelectedControllerClient(
        controller_dir=args.controller_dir,
        timeout_seconds=args.timeout,
        poll_interval_seconds=args.poll_interval,
    )
    run = build_hardstyle_template(
        client=client,
        audit_dir=args.audit_dir,
        allow_current_project_edits=args.allow_current_project_edits,
    )
    print(json.dumps(run.to_dict(), indent=2, sort_keys=True))
    return 2 if run.status == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
