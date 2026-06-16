"""Tests for persistence engine and prompts registry."""

from __future__ import annotations

from sqlalchemy.engine import Engine

from fl_mcp.persistence.db import get_engine, init_db
from fl_mcp.prompts.registry import PROMPTS, PromptDefinition

# ---------------------------------------------------------------------------
# Persistence: get_engine
# ---------------------------------------------------------------------------


def test_get_engine_returns_engine_instance() -> None:
    engine = get_engine()
    assert isinstance(engine, Engine)


def test_get_engine_returns_same_instance_on_repeated_calls() -> None:
    first = get_engine()
    second = get_engine()
    assert first is second


# ---------------------------------------------------------------------------
# Persistence: init_db
# ---------------------------------------------------------------------------


def test_init_db_runs_without_error() -> None:
    init_db()


# ---------------------------------------------------------------------------
# Prompts: PROMPTS registry
# ---------------------------------------------------------------------------


def test_prompts_registry_is_non_empty() -> None:
    assert len(PROMPTS) > 0


def test_each_prompt_has_required_attributes() -> None:
    for prompt in PROMPTS:
        assert isinstance(prompt, PromptDefinition)
        assert hasattr(prompt, "name") and isinstance(prompt.name, str) and prompt.name
        assert (
            hasattr(prompt, "description")
            and isinstance(prompt.description, str)
            and prompt.description
        )
        assert hasattr(prompt, "content") and isinstance(prompt.content, str) and prompt.content
        assert hasattr(prompt, "tags") and isinstance(prompt.tags, set)


def test_prompt_names_are_unique() -> None:
    names = [prompt.name for prompt in PROMPTS]
    assert len(names) == len(set(names)), f"Duplicate prompt names: {names}"


def test_all_prompt_tags_are_strings() -> None:
    for prompt in PROMPTS:
        for tag in prompt.tags:
            assert isinstance(tag, str), f"Tag {tag!r} in prompt {prompt.name!r} is not a string"


def test_diagnostics_prompt_exists() -> None:
    names = {prompt.name for prompt in PROMPTS}
    assert "diagnostics" in names, f"Expected 'diagnostics' prompt, found: {sorted(names)}"
