"""Unit tests for shared local path validation helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from fl_mcp.util.paths import LocalPathValidationError, is_uri_path, validate_local_path


def test_is_uri_path_detects_mock_and_absolute_paths() -> None:
    assert is_uri_path("mock://sample.wav")
    assert is_uri_path("file:///tmp/sample.wav")
    assert not is_uri_path("/tmp/sample.wav")
    assert not is_uri_path("relative/sample.wav")


def test_validate_local_path_allows_file_within_root(tmp_path: Path) -> None:
    sample = tmp_path / "kick.wav"
    sample.write_text("audio", encoding="utf-8")

    resolved = validate_local_path(
        str(sample),
        allowed_roots=[tmp_path],
        must_exist=True,
    )

    assert resolved == sample.resolve()


def test_validate_local_path_rejects_traversal_outside_root(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    with pytest.raises(LocalPathValidationError, match="outside allowed inventory roots"):
        validate_local_path(
            str(outside),
            allowed_roots=[allowed],
            must_exist=True,
        )


def test_validate_local_path_rejects_parent_traversal(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()

    with pytest.raises(LocalPathValidationError, match="outside allowed inventory roots"):
        validate_local_path(
            str(allowed / ".." / "escape.txt"),
            allowed_roots=[allowed],
            must_exist=False,
        )


def test_validate_local_path_rejects_symlinks(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    target = tmp_path / "target.wav"
    target.write_text("audio", encoding="utf-8")
    link = allowed / "linked.wav"
    link.symlink_to(target)

    with pytest.raises(LocalPathValidationError, match="Symlink paths are not allowed"):
        validate_local_path(
            str(link),
            allowed_roots=[allowed],
            must_exist=True,
        )


def test_validate_local_path_allows_uri_without_filesystem_checks() -> None:
    resolved = validate_local_path(
        "mock://sample.wav",
        allowed_roots=[],
        must_exist=True,
    )

    assert resolved == "mock://sample.wav"