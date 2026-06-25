"""Local filesystem path validation helpers."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel

from fl_mcp.plugin_profiles.inventory import inventory_scan_roots


class LocalPathValidationError(ValueError):
    """Raised when a local path fails containment or safety checks."""


def is_uri_path(value: str) -> bool:
    """Return whether ``value`` is a non-local URI (for example ``mock://``)."""

    stripped = value.strip()
    if not stripped:
        return False
    if stripped.startswith("/"):
        return False
    return "://" in stripped


def _resolve_root(root: Path | str) -> Path | None:
    try:
        return Path(root).expanduser().resolve(strict=False)
    except OSError:
        return None


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def validate_local_path(
    raw_path: str,
    *,
    allowed_roots: Iterable[Path | str],
    must_exist: bool = False,
    allow_uri: bool = True,
) -> Path | str:
    """Resolve ``raw_path`` and ensure it stays within ``allowed_roots``.

    Rejects empty paths, symlink targets, traversal outside allowed roots, and
    optionally missing files when ``must_exist`` is true. URI paths such as
    ``mock://sample.wav`` are returned unchanged when ``allow_uri`` is true.
    """

    if not raw_path or not raw_path.strip():
        msg = "Path must not be empty."
        raise LocalPathValidationError(msg)

    if allow_uri and is_uri_path(raw_path):
        return raw_path.strip()

    candidate = Path(raw_path).expanduser()
    if candidate.is_symlink():
        msg = "Symlink paths are not allowed."
        raise LocalPathValidationError(msg)

    try:
        resolved = candidate.resolve(strict=must_exist)
    except FileNotFoundError as exc:
        msg = f"Path does not exist: {raw_path}"
        raise LocalPathValidationError(msg) from exc
    except OSError as exc:
        msg = f"Unable to resolve path: {raw_path}"
        raise LocalPathValidationError(msg) from exc

    normalized_roots = [
        root
        for item in allowed_roots
        if (root := _resolve_root(item)) is not None
    ]
    if not normalized_roots:
        msg = "No allowed path roots are configured."
        raise LocalPathValidationError(msg)

    if not any(_is_within_root(resolved, root) for root in normalized_roots):
        msg = "Path is outside allowed inventory roots."
        raise LocalPathValidationError(msg)

    return resolved


_OPERATION_PATH_FIELDS: dict[str, tuple[tuple[str, bool], ...]] = {
    "channels.load_sample": (("file_path", True),),
    "general.open_project": (("path", True),),
    "general.save_project_as": (("path", False),),
    "plugins.load_profile_preset": (("preset_path", True),),
    "render.export": (("output_path", False),),
    "audio.analyze": (("input_path", False),),
}


def validate_operation_local_paths(operation_id: str, payload: BaseModel) -> None:
    """Validate filesystem paths on ``payload`` for path-bearing operations.

    URI paths (for example ``mock://``) are skipped. Optional path fields that
    are ``None`` or blank are ignored.
    """

    field_specs = _OPERATION_PATH_FIELDS.get(operation_id)
    if field_specs is None:
        return

    allowed_roots = inventory_scan_roots()
    for field_name, must_exist in field_specs:
        raw_value = getattr(payload, field_name, None)
        if not isinstance(raw_value, str) or not raw_value.strip():
            continue
        if is_uri_path(raw_value):
            continue
        validate_local_path(
            raw_value,
            allowed_roots=allowed_roots,
            must_exist=must_exist,
            allow_uri=False,
        )