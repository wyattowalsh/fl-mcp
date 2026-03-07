"""Canonical graph serialization utilities."""

from __future__ import annotations

import json
from typing import Any


def serialize_graph(graph: dict[str, Any]) -> str:
    canonical = {
        "nodes": sorted(graph.get("nodes", []), key=lambda n: n["id"]),
        "edges": sorted(
            graph.get("edges", []),
            key=lambda e: (e["source"], e["target"], e.get("type", "")),
        ),
    }
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"))


def deserialize_graph(serialized: str) -> dict[str, Any]:
    return json.loads(serialized)
