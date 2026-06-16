#!/usr/bin/env python3
"""Check FL MCP setup readiness for agent production workflows."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT_SECONDS = 60
MAX_CAPTURE_CHARS = 4000


def truncate_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode(errors="replace")
    if not value:
        return ""
    value = value.strip()
    if len(value) <= MAX_CAPTURE_CHARS:
        return value
    return f"{value[:MAX_CAPTURE_CHARS]}... [truncated {len(value) - MAX_CAPTURE_CHARS} chars]"


def parse_python_version(output: str) -> tuple[int, int, int] | None:
    match = re.search(r"Python\s+(\d+)\.(\d+)(?:\.(\d+))?", output)
    if not match:
        return None
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch or 0)


def run_command(
    command: list[str],
    *,
    cwd: Path,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "command": command,
            "returncode": None,
            "stdout": truncate_output(exc.stdout),
            "stderr": truncate_output(exc.stderr),
            "timed_out": True,
        }

    return {
        "ok": completed.returncode == 0,
        "command": command,
        "returncode": completed.returncode,
        "stdout": truncate_output(completed.stdout),
        "stderr": truncate_output(completed.stderr),
        "timed_out": False,
    }


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    ok: bool,
    *,
    details: dict[str, Any] | None = None,
    missing_step: str | None = None,
    missing_steps: list[str],
    evidence: list[dict[str, Any]],
) -> None:
    check = dict(details or {})
    check.update({"name": name, "ok": ok})
    checks.append(check)
    if ok:
        evidence.append({"name": name, "details": details or {}})
    elif missing_step:
        missing_steps.append(missing_step)


def choose_source(source: str, repo_root: Path) -> str:
    if source != "auto":
        return source
    if (repo_root / "pyproject.toml").exists() and (repo_root / "src" / "fl_mcp").exists():
        return "local"
    return "published"


def fl_mcp_command(source: str, repo_root: Path, *args: str) -> list[str]:
    if source == "local":
        root = str(repo_root.resolve())
        return ["uvx", "--from", root, "--with-editable", root, "fl-mcp", *args]
    return ["uvx", "fl-mcp", *args]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["mock", "live"], default="mock")
    parser.add_argument("--source", choices=["auto", "local", "published"], default="auto")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--format", choices=["json"], default="json")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).expanduser().resolve()
    source = choose_source(args.source, repo_root)
    checks: list[dict[str, Any]] = []
    missing_steps: list[str] = []
    evidence: list[dict[str, Any]] = []

    uv_path = shutil.which("uv")
    uvx_path = shutil.which("uvx")
    add_check(
        checks,
        "uv_available",
        uv_path is not None,
        details={"path": uv_path},
        missing_step="Install uv from https://docs.astral.sh/uv/.",
        missing_steps=missing_steps,
        evidence=evidence,
    )
    add_check(
        checks,
        "uvx_available",
        uvx_path is not None,
        details={"path": uvx_path},
        missing_step="Install uv/uvx so FL MCP can run through uvx.",
        missing_steps=missing_steps,
        evidence=evidence,
    )

    if uv_path:
        python_result = run_command(
            ["uv", "run", "python", "--version"],
            cwd=repo_root,
            timeout=args.timeout,
        )
        python_version = parse_python_version(
            f"{python_result.get('stdout', '')}\n{python_result.get('stderr', '')}"
        )
        python_version_ok = python_version is not None and python_version >= (3, 12, 0)
        python_details = {
            **python_result,
            "parsed_version": list(python_version) if python_version else None,
            "minimum_version": [3, 12, 0],
        }
        add_check(
            checks,
            "uv_python_version",
            bool(python_result["ok"]) and python_version_ok,
            details=python_details,
            missing_step="Ensure uv can run Python 3.12 or newer in this checkout.",
            missing_steps=missing_steps,
            evidence=evidence,
        )

    if source == "local":
        local_ok = (repo_root / "pyproject.toml").exists() and (
            repo_root / "src" / "fl_mcp"
        ).exists()
        add_check(
            checks,
            "local_checkout",
            local_ok,
            details={"repo_root": str(repo_root)},
            missing_step=(
                "Run from the fl-mcp checkout or pass --repo-root /absolute/path/to/fl-mcp."
            ),
            missing_steps=missing_steps,
            evidence=evidence,
        )

    if uvx_path:
        version_result = run_command(
            fl_mcp_command(source, repo_root, "--version"),
            cwd=repo_root,
            timeout=args.timeout,
        )
        add_check(
            checks,
            "fl_mcp_version",
            bool(version_result["ok"]),
            details=version_result,
            missing_step=(
                "Make FL MCP available through uvx, or use --source local from a checkout."
            ),
            missing_steps=missing_steps,
            evidence=evidence,
        )

        dry_run_result = run_command(
            fl_mcp_command(source, repo_root, "server", "run", "--mode", "stdio", "--dry-run"),
            cwd=repo_root,
            timeout=args.timeout,
        )
        add_check(
            checks,
            "stdio_dry_run",
            bool(dry_run_result["ok"]),
            details=dry_run_result,
            missing_step="Fix `fl-mcp server run --mode stdio --dry-run` before execution.",
            missing_steps=missing_steps,
            evidence=evidence,
        )

        doctor_result = run_command(
            fl_mcp_command(source, repo_root, "doctor", "--format", "json"),
            cwd=repo_root,
            timeout=args.timeout,
        )
        add_check(
            checks,
            "doctor_json",
            bool(doctor_result["ok"]),
            details=doctor_result,
            missing_step="Run `fl-mcp doctor --format json` and resolve reported setup issues.",
            missing_steps=missing_steps,
            evidence=evidence,
        )

        if args.mode == "live":
            install_result = run_command(
                fl_mcp_command(source, repo_root, "install", "--dry-run"),
                cwd=repo_root,
                timeout=args.timeout,
            )
            add_check(
                checks,
                "install_dry_run",
                bool(install_result["ok"]),
                details=install_result,
                missing_step=(
                    "Run `fl-mcp install --dry-run` and configure the reported bridge environment."
                ),
                missing_steps=missing_steps,
                evidence=evidence,
            )

    fastmcp_config = repo_root / "fastmcp.json"
    if source == "local" and fastmcp_config.exists() and shutil.which("uv"):
        inspect_result = run_command(
            ["uv", "run", "fastmcp", "inspect", "fastmcp.json", "--format", "mcp"],
            cwd=repo_root,
            timeout=args.timeout,
        )
        add_check(
            checks,
            "fastmcp_inspect",
            bool(inspect_result["ok"]),
            details=inspect_result,
            missing_step=None,
            missing_steps=missing_steps,
            evidence=evidence,
        )

    client_config = (
        {
            "command": "uvx",
            "args": [
                "--from",
                str(repo_root),
                "--with-editable",
                str(repo_root),
                "fl-mcp",
                "server",
                "run",
                "--mode",
                "stdio",
            ],
        }
        if source == "local"
        else {"command": "uvx", "args": ["fl-mcp", "server", "run", "--mode", "stdio"]}
    )

    required_mock = {
        "uv_available",
        "uvx_available",
        "uv_python_version",
        "fl_mcp_version",
        "stdio_dry_run",
        "doctor_json",
    }
    required_live = required_mock | {"install_dry_run"}
    ok_by_name = {check["name"]: bool(check["ok"]) for check in checks}
    safe_to_execute_mock = all(ok_by_name.get(name, False) for name in required_mock)
    safe_to_attempt_live = args.mode == "live" and all(
        ok_by_name.get(name, False) for name in required_live
    )
    setup_ready = safe_to_attempt_live if args.mode == "live" else safe_to_execute_mock
    status = "ok" if setup_ready else "blocked"

    output = {
        "status": status,
        "source": source,
        "mode": args.mode,
        "checks": checks,
        "client_config": client_config,
        "missing_steps": missing_steps,
        "evidence": evidence,
        "safe_to_execute_mock": safe_to_execute_mock,
        "safe_to_attempt_live": safe_to_attempt_live,
    }
    json.dump(output, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
