"""Contract test: every FLToolSpec domain+operation must have a _MOCK_DISPATCH entry."""

from __future__ import annotations

from fl_mcp.bridge.mock_generators import _MOCK_DISPATCH
from fl_mcp.tools.fl_surface import FL_TOOL_SPECS


def test_every_spec_has_mock_handler() -> None:
    """Every FL tool spec must have a matching entry in _MOCK_DISPATCH.

    This test prevents the P1 registry split bug from recurring: operations
    added to FL_TOOL_SPECS but not to _MOCK_DISPATCH silently break mock/CI.
    """
    missing: list[str] = []
    for spec in FL_TOOL_SPECS:
        if (spec.domain, spec.operation) not in _MOCK_DISPATCH:
            missing.append(f"{spec.domain}.{spec.operation} (tool: {spec.name})")

    assert not missing, (
        f"These tool specs have no _MOCK_DISPATCH handler ({len(missing)} missing):\n"
        + "\n".join(f"  - {m}" for m in missing)
    )


def test_mock_dispatch_has_no_orphan_entries() -> None:
    """Every _MOCK_DISPATCH entry should correspond to a registered domain in DOMAINS."""
    from fl_mcp.graph.domains import DOMAINS

    orphan_domains: set[str] = set()
    for domain, _operation in _MOCK_DISPATCH:
        if domain not in DOMAINS:
            orphan_domains.add(domain)

    assert not orphan_domains, (
        f"_MOCK_DISPATCH has entries for unregistered domains: {orphan_domains}"
    )
