"""Prompt registry for FastMCP prompt registration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PromptDefinition(BaseModel):
    """Prompt registration contract."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    content: str = Field(min_length=1)
    tags: set[str] = Field(default_factory=set)


PROMPTS: tuple[PromptDefinition, ...] = (
    PromptDefinition(
        name="diagnostics",
        description="Collect runtime, bridge, and persistence health summaries.",
        content=(
            "Collect runtime, bridge, and persistence health summaries. "
            "Return current status, anomalies, and concrete next actions."
        ),
        tags={"diagnostics", "health"},
    ),
)


def prompt_names() -> tuple[str, ...]:
    """Return sorted prompt names for surface inspection."""

    return tuple(sorted(prompt.name for prompt in PROMPTS))
