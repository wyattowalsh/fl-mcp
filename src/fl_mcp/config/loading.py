"""Deterministic configuration loading utilities."""

from __future__ import annotations

from collections.abc import Mapping


def load_config(*sources: Mapping[str, object]) -> dict[str, object]:
    """Merge mappings in order and return a key-sorted deterministic config."""
    merged: dict[str, object] = {}
    for source in sources:
        for key in sorted(source.keys()):
            merged[key] = source[key]
    return {key: merged[key] for key in sorted(merged.keys())}
