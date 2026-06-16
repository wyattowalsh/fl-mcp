"""Tests for fl_mcp.bridge.mock_generators dispatch table and factories."""

from __future__ import annotations

import pytest

from fl_mcp.bridge.mock_generators import (
    _MOCK_DISPATCH,
    _prop_getter,
    _prop_setter,
    mock_result,
)

# ---------------------------------------------------------------------------
# 1. mock_result returns a dict for every entry in _MOCK_DISPATCH
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "domain_op",
    list(_MOCK_DISPATCH.keys()),
    ids=[f"{d}.{o}" for d, o in _MOCK_DISPATCH.keys()],
)
def test_mock_result_returns_dict_for_every_dispatch_entry(
    domain_op: tuple[str, str],
) -> None:
    domain, operation = domain_op
    result = mock_result(domain, operation, {}, rollback_class=None)
    assert isinstance(result, dict)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# 2. Unknown domain/operation returns a noop-style default result
# ---------------------------------------------------------------------------


def test_mock_result_unknown_domain_operation_returns_default() -> None:
    result = mock_result("nonexistent_domain", "nonexistent_op", {}, rollback_class=None)
    assert isinstance(result, dict)
    assert result["acknowledged"] is True
    assert result["payload"] == {}


def test_mock_result_unknown_with_rollback_class_includes_it() -> None:
    result = mock_result(
        "nonexistent_domain",
        "nonexistent_op",
        {"key": "val"},
        rollback_class="checkpointed",
    )
    assert result["acknowledged"] is True
    assert result["rollback_class"] == "checkpointed"
    assert result["payload"] == {"key": "val"}


def test_mock_result_noop_operation_returns_noop() -> None:
    """Any domain with operation='noop' is routed to _mock_noop."""
    result = mock_result("anything", "noop", {"x": 1}, rollback_class=None)
    assert result["noop"] is True
    assert result["acknowledged"] is True
    assert result["payload"] == {"x": 1}


# ---------------------------------------------------------------------------
# 3. _prop_getter factory
# ---------------------------------------------------------------------------


class TestPropGetter:
    def test_returns_correct_structure_with_default_index(self) -> None:
        handler = _prop_getter("volume", 0.78, "index", "channel_index")
        result = handler({})
        assert result == {"volume": 0.78, "index": 0}

    def test_resolves_first_index_key(self) -> None:
        handler = _prop_getter("color", 16711680, "index", "channel_index")
        result = handler({"index": 5})
        assert result == {"color": 16711680, "index": 5}

    def test_resolves_second_index_key(self) -> None:
        handler = _prop_getter("pan", 0.0, "index", "channel_index")
        result = handler({"channel_index": 3})
        assert result == {"pan": 0.0, "index": 3}

    def test_first_key_takes_priority(self) -> None:
        handler = _prop_getter("volume", 0.5, "index", "track_index")
        result = handler({"index": 10, "track_index": 20})
        assert result["index"] == 10


# ---------------------------------------------------------------------------
# 4. _prop_setter factory
# ---------------------------------------------------------------------------


class TestPropSetter:
    def test_returns_correct_structure_with_defaults(self) -> None:
        handler = _prop_setter("volume", 0.78, "index", "channel_index")
        result = handler({})
        assert result == {"acknowledged": True, "index": 0, "volume": 0.78}

    def test_picks_up_value_from_payload(self) -> None:
        handler = _prop_setter("volume", 0.78, "index", "channel_index")
        result = handler({"volume": 0.5, "channel_index": 2})
        assert result["acknowledged"] is True
        assert result["index"] == 2
        assert result["volume"] == 0.5

    def test_resolves_first_index_key(self) -> None:
        handler = _prop_setter("color", 0, "index", "track_index")
        result = handler({"index": 7, "color": 255})
        assert result["index"] == 7
        assert result["color"] == 255

    def test_resolves_second_index_key_as_fallback(self) -> None:
        handler = _prop_setter("pan", 0.0, "index", "track_index")
        result = handler({"track_index": 4, "pan": -0.5})
        assert result["index"] == 4
        assert result["pan"] == -0.5


# ---------------------------------------------------------------------------
# 5. Sampling of specific handlers return expected keys
# ---------------------------------------------------------------------------


class TestSpecificHandlerKeys:
    def test_transport_get_state(self) -> None:
        result = mock_result("transport", "get_state", {}, rollback_class=None)
        expected_keys = {
            "playing",
            "recording",
            "bpm",
            "position_beats",
            "loop_mode",
            "playback_speed",
        }
        assert expected_keys.issubset(result.keys())
        assert result["playing"] is False
        assert result["bpm"] == 128.0

    def test_mixer_list_tracks(self) -> None:
        result = mock_result("mixer", "list_tracks", {}, rollback_class=None)
        assert "tracks" in result
        assert isinstance(result["tracks"], list)
        assert len(result["tracks"]) > 0
        assert result["tracks"][0]["name"] == "Master"

    def test_channels_list(self) -> None:
        result = mock_result("channels", "list_channels", {}, rollback_class=None)
        assert "channels" in result
        assert isinstance(result["channels"], list)
        assert result["channels"][0]["name"] == "Kick"

    def test_patterns_list(self) -> None:
        result = mock_result("patterns", "list_patterns", {}, rollback_class=None)
        assert "patterns" in result
        assert result["patterns"][0]["name"] == "Intro"

    def test_piano_roll_get_state(self) -> None:
        result = mock_result("piano-roll", "get_state", {}, rollback_class=None)
        assert "ppq" in result
        assert "notes" in result
        assert result["ppq"] == 96

    def test_general_get_version(self) -> None:
        result = mock_result("general", "get_version", {}, rollback_class=None)
        assert result["version"] == "FL Studio Mock"
        assert result["build"] == "mock"

    def test_midi_list_ports(self) -> None:
        result = mock_result("midi", "list_ports", {}, rollback_class=None)
        assert "inputs" in result
        assert "outputs" in result

    def test_connection_status(self) -> None:
        result = mock_result("connection", "status", {}, rollback_class=None)
        assert result["connected"] is False
        assert result["mode"] == "mock"

    def test_render_export(self) -> None:
        result = mock_result("render", "export", {}, rollback_class=None)
        assert result["task_status"] == "queued"
        assert result["format"] == "wav"

    def test_ui_get_visibility(self) -> None:
        result = mock_result("ui", "get_visibility", {}, rollback_class=None)
        assert result["visible"] is True

    def test_device_is_assigned(self) -> None:
        result = mock_result("device", "is_assigned", {}, rollback_class=None)
        assert result["assigned"] is True

    def test_arrangement_get_current_time(self) -> None:
        result = mock_result("arrangement", "get_current_time", {}, rollback_class=None)
        assert "time" in result
        assert "snap" in result


# ---------------------------------------------------------------------------
# 6. All handlers accept an empty dict as payload without error
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "domain_op",
    list(_MOCK_DISPATCH.keys()),
    ids=[f"{d}.{o}" for d, o in _MOCK_DISPATCH.keys()],
)
def test_all_handlers_accept_empty_payload(
    domain_op: tuple[str, str],
) -> None:
    handler = _MOCK_DISPATCH[domain_op]
    result = handler({})
    assert isinstance(result, dict)
