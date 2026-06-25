"""Per-operation live support manifest for honest flapi-live classification."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from fl_mcp.bridge.live_surface import (
    forced_live_flapi_supports,
    live_flapi_supports,
    selected_controller_supports,
)
from fl_mcp.tools.fl_surface import FL_TOOL_SPECS, FLToolSpec


class LiveSupportTier(StrEnum):
    """How an operation is classified for provider=flapi-live."""

    VERIFIED_LIVE = "verified_live"
    ATTEMPTABLE = "attemptable"
    SELECTED_CONTROLLER_ONLY = "selected_controller_only"
    UNSUPPORTED = "unsupported"


def live_support_tier(domain: str, operation: str) -> LiveSupportTier:
    """Return the manifest tier for one catalog operation."""

    if live_flapi_supports(domain, operation):
        return LiveSupportTier.VERIFIED_LIVE
    if forced_live_flapi_supports(domain, operation):
        return LiveSupportTier.ATTEMPTABLE
    if selected_controller_supports(domain, operation):
        return LiveSupportTier.SELECTED_CONTROLLER_ONLY
    return LiveSupportTier.UNSUPPORTED


def live_support_flags(domain: str, operation: str) -> dict[str, bool]:
    """Return boolean live-support flags used by capability schema responses."""

    tier = live_support_tier(domain, operation)
    return {
        "verified_live": tier is LiveSupportTier.VERIFIED_LIVE,
        "attemptable": tier in {LiveSupportTier.VERIFIED_LIVE, LiveSupportTier.ATTEMPTABLE},
    }


def live_support_for_spec(spec: FLToolSpec) -> dict[str, object]:
    """Return manifest metadata for one FL tool spec."""

    tier = live_support_tier(spec.domain, spec.operation)
    flags = live_support_flags(spec.domain, spec.operation)
    return {
        "live_support_tier": tier.value,
        "verified_live": flags["verified_live"],
        "attemptable": flags["attemptable"],
        "selected_controller_compat": selected_controller_supports(spec.domain, spec.operation),
    }


def live_coverage_counts() -> dict[str, int]:
    """Aggregate live coverage counts for status and matrix generation."""

    verified_live = 0
    attemptable_only = 0
    selected_controller_only = 0
    unsupported = 0
    for spec in FL_TOOL_SPECS:
        tier = live_support_tier(spec.domain, spec.operation)
        if tier is LiveSupportTier.VERIFIED_LIVE:
            verified_live += 1
        elif tier is LiveSupportTier.ATTEMPTABLE:
            attemptable_only += 1
        elif tier is LiveSupportTier.SELECTED_CONTROLLER_ONLY:
            selected_controller_only += 1
        else:
            unsupported += 1

    total = len(FL_TOOL_SPECS)
    return {
        "total_operations": total,
        "verified_live": verified_live,
        "attemptable_only": attemptable_only,
        "attemptable_total": verified_live + attemptable_only,
        "selected_controller_only": selected_controller_only,
        "unsupported": unsupported,
    }


def manifest_entries() -> list[dict[str, object]]:
    """Return per-operation manifest rows sorted by operation id."""

    rows: list[dict[str, object]] = []
    for spec in FL_TOOL_SPECS:
        operation_id = f"{spec.domain}.{spec.operation}"
        row: dict[str, object] = {
            "operation_id": operation_id,
            "domain": spec.domain,
            "operation": spec.operation,
        }
        row.update(live_support_for_spec(spec))
        rows.append(row)
    return sorted(rows, key=lambda item: str(item["operation_id"]))


def generate_live_support_matrix_markdown(*, output_path: Path | None = None) -> str:
    """Render and optionally write the live support matrix document."""

    counts = live_coverage_counts()
    lines = [
        "# Live Support Matrix",
        "",
        "Generated from `src/fl_mcp/bridge/live_manifest.py`.",
        "",
        "## Summary",
        "",
        f"- Total catalog operations: **{counts['total_operations']}**",
        f"- Verified live (`flapi-live` host-file bridge): **{counts['verified_live']}**",
        f"- Attemptable only (forced-live host attempts): **{counts['attemptable_only']}**",
        f"- Attemptable total (verified + attemptable-only): **{counts['attemptable_total']}**",
        f"- Selected-controller compatibility only: **{counts['selected_controller_only']}**",
        f"- Unsupported on shipped live paths: **{counts['unsupported']}**",
        "",
        "## Per-operation tiers",
        "",
        "| operation_id | live_support_tier | verified_live | attemptable | selected_controller_compat |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in manifest_entries():
        lines.append(
            "| {operation_id} | {live_support_tier} | {verified_live} | {attemptable} | "
            "{selected_controller_compat} |".format(**entry)
        )
    content = "\n".join(lines) + "\n"
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
    return content


def main() -> int:
    """CLI entrypoint for regenerating goals/live-support-matrix.md."""

    repo_root = Path(__file__).resolve().parents[3]
    output = repo_root / "goals" / "live-support-matrix.md"
    generate_live_support_matrix_markdown(output_path=output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())