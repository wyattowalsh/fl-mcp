"""Builtin provider adapters for the canonical FL Studio capability surface."""

from __future__ import annotations

from fl_mcp.bridge.live_surface import FORCED_LIVE_FLAPI_SUPPORTED_DOMAINS
from fl_mcp.providers.adapters import BridgeBackedProvider, build_manifest


def builtin_providers() -> tuple[BridgeBackedProvider, ...]:
    """Return the tuple of built-in bridge-backed provider adapters.

    Includes ``flapi-live``, ``piano-roll-script``, ``midi-fallback``,
    and ``mock`` providers with their canonical domain mappings.
    """
    return (
        BridgeBackedProvider(
            manifest=build_manifest(
                name="flapi-live",
                description=(
                    "Forced-live provider for attempting every compact FL operation "
                    "through the bundled FL Studio host-file bridge."
                ),
                supported_domains=list(FORCED_LIVE_FLAPI_SUPPORTED_DOMAINS),
                maturity="beta",
                aliases=["flapi"],
            ),
            bridge_provider="flapi-live",
        ),
        BridgeBackedProvider(
            manifest=build_manifest(
                name="piano-roll-script",
                description="Script-backed provider for persistent piano-roll and pattern editing.",
                supported_domains=[
                    "patterns",
                    "piano-roll",
                ],
                maturity="beta",
                aliases=["midi-script", "midi-script-live"],
            ),
            bridge_provider="piano-roll-script",
        ),
        BridgeBackedProvider(
            manifest=build_manifest(
                name="midi-fallback",
                description="Degraded MIDI/SysEx-style provider for bounded live control surfaces.",
                supported_domains=[
                    "connection",
                    "midi",
                    "transport",
                    "channels",
                    "device",
                ],
                maturity="experimental",
            ),
            bridge_provider="midi-fallback",
        ),
        BridgeBackedProvider(
            manifest=build_manifest(
                name="mock",
                description="Deterministic provider for CI and local development.",
                supported_domains=sorted(
                    {
                        "connection",
                        "midi",
                        "transport",
                        "mixer",
                        "channels",
                        "patterns",
                        "playlist",
                        "piano-roll",
                        "plugins",
                        "ui",
                        "general",
                        "render",
                        "audio",
                        "device",
                        "arrangement",
                        "automation",
                    }
                ),
                maturity="stable",
                task_kinds=["render", "audio"],
            ),
            bridge_provider="mock",
        ),
    )
