"""Tests for live support manifest and status wiring."""

from __future__ import annotations

from pathlib import Path

from fl_mcp.bridge.live_manifest import (
    LiveSupportTier,
    generate_live_support_matrix_markdown,
    live_coverage_counts,
    live_support_tier,
)
from fl_mcp.tools import compact


def test_live_coverage_counts_match_catalog() -> None:
    counts = live_coverage_counts()

    assert counts["total_operations"] == 216
    assert counts["verified_live"] == 8
    assert counts["attemptable_only"] == 208
    assert counts["attemptable_total"] == 216
    assert counts["verified_live"] + counts["attemptable_only"] == counts["attemptable_total"]


def test_transport_get_tempo_is_verified_live() -> None:
    assert live_support_tier("transport", "get_tempo") is LiveSupportTier.VERIFIED_LIVE


def test_automation_create_clip_is_attemptable() -> None:
    assert live_support_tier("automation", "create_clip") is LiveSupportTier.ATTEMPTABLE


def test_fl_status_includes_live_coverage() -> None:
    status = compact.fl_status()
    capabilities = status["capabilities"]
    live_coverage = capabilities["live_coverage"]

    assert live_coverage["verified_live"] == 8
    assert live_coverage["attemptable_total"] == 216


def test_capability_schema_exposes_live_manifest_fields() -> None:
    schema = compact.fl_get_capability_schema("transport.get_tempo")

    assert schema["verified_live"] is True
    assert schema["attemptable"] is True
    assert schema["live_support_tier"] == "verified_live"
    capability = schema["capability"]
    assert capability["verified_live"] is True


def test_search_flapi_live_uses_manifest_tiers() -> None:
    search = compact.fl_search_capabilities(provider="flapi-live", limit=300)

    assert search["status"] == "ok"
    assert search["total"] == 216
    assert all(item["attemptable"] for item in search["results"])


def test_generate_live_support_matrix_markdown_writes_file(tmp_path: Path) -> None:
    output = tmp_path / "live-support-matrix.md"
    content = generate_live_support_matrix_markdown(output_path=output)

    assert "Verified live" in content
    assert output.is_file()
    assert "| transport.get_tempo |" in output.read_text(encoding="utf-8")