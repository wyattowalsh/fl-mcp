"""Install helpers for syncing the bundled FL Studio MIDI controller script."""

from __future__ import annotations

import filecmp
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fl_mcp.bridge.bundle import controller_script_path, default_hardware_script_dir

CONTROLLER_FILE_NAME = "device_FL_MCP_Bridge.py"


@dataclass(slots=True)
class ControllerSyncResult:
    """Outcome of syncing the bundled controller script to FL Studio hardware dir."""

    source: str
    target_dir: str
    target_file: str
    dry_run: bool
    action: str
    status: str
    backup_file: str | None = None
    byte_match_verified: bool = False
    remediation: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "source": self.source,
            "target_dir": self.target_dir,
            "target_file": self.target_file,
            "dry_run": self.dry_run,
            "action": self.action,
            "status": self.status,
            "byte_match_verified": self.byte_match_verified,
        }
        if self.backup_file is not None:
            payload["backup_file"] = self.backup_file
        if self.remediation is not None:
            payload["remediation"] = self.remediation
        if self.error is not None:
            payload["error"] = self.error
        return payload


def _timestamped_backup_path(target_file: Path) -> Path:
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return target_file.with_name(f"{target_file.name}.bak.{stamp}")


def sync_controller_script(
    *,
    dry_run: bool = False,
    source: Path | None = None,
    target_dir: Path | None = None,
) -> ControllerSyncResult:
    """Copy the bundled controller script into FL Studio hardware settings.

    When an existing target file differs from the bundled source, a timestamped
    backup is created before overwrite. A byte-for-byte ``filecmp`` check verifies
    the installed script after copy.
    """

    bundled_source = (source or controller_script_path()).expanduser().resolve()
    hardware_dir = (target_dir or default_hardware_script_dir()).expanduser()
    target_file = hardware_dir / CONTROLLER_FILE_NAME

    def _result(
        *,
        status: str,
        backup_file: str | None = None,
        byte_match_verified: bool = False,
        remediation: str | None = None,
        error: str | None = None,
    ) -> ControllerSyncResult:
        return ControllerSyncResult(
            source=str(bundled_source),
            target_dir=str(hardware_dir),
            target_file=str(target_file),
            dry_run=dry_run,
            action="sync_controller",
            status=status,
            backup_file=backup_file,
            byte_match_verified=byte_match_verified,
            remediation=remediation,
            error=error,
        )

    if not bundled_source.is_file():
        return _result(
            status="error",
            error=f"Bundled controller script missing: {bundled_source}.",
        )

    if target_file.exists() and filecmp.cmp(bundled_source, target_file, shallow=False):
        return _result(
            status="unchanged",
            byte_match_verified=True,
            remediation=(
                "Controller script already matches the bundled release. "
                "Select FL MCP Bridge in FL Studio MIDI Settings if live bridge "
                "requests time out."
            ),
        )

    backup_file: str | None = None
    if target_file.exists():
        backup_path = _timestamped_backup_path(target_file)
        backup_file = str(backup_path)
        if dry_run:
            return _result(
                status="planned",
                backup_file=backup_file,
                remediation=(
                    f"Run `fl-mcp install --sync-controller` to copy {bundled_source.name} "
                    f"to {hardware_dir} and back up the existing script."
                ),
            )
        shutil.copy2(target_file, backup_path)

    if dry_run:
        return _result(
            status="planned",
            remediation=(
                f"Run `fl-mcp install --sync-controller` to install {bundled_source.name} "
                f"into {hardware_dir}."
            ),
        )

    hardware_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bundled_source, target_file)
    verified = filecmp.cmp(bundled_source, target_file, shallow=False)
    if not verified:
        return _result(
            status="error",
            backup_file=backup_file,
            remediation="Re-run `fl-mcp install --sync-controller` after resolving file permissions.",
            error=(
                f"Installed controller script at {target_file} does not byte-match "
                f"the bundled source at {bundled_source}."
            ),
        )

    return _result(
        status="synced",
        backup_file=backup_file,
        byte_match_verified=True,
        remediation=(
            "Open FL Studio > MIDI Settings, set Controller type to FL MCP Bridge, "
            "and confirm bridge status.json updates while FL is open."
        ),
    )