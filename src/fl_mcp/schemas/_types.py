"""Shared type aliases for schema modules."""

from __future__ import annotations

from typing import Literal

TaskState = Literal["queued", "running", "completed", "failed", "canceled"]
