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
        tags={"diagnostics", "health", "public"},
    ),
    PromptDefinition(
        name="transaction_guidance",
        description=(
            "Explain the safe, agent-preferred workflow for inspecting state and "
            "making controlled changes to an FL Studio project."
        ),
        content=(
            "Preferred agent workflow for FL Studio projects:\n"
            "1. Use fl_status and fl_snapshot to understand runtime and project state.\n"
            "2. Use fl_search_capabilities and fl_get_capability_schema to find the\n"
            " exact operation id and request contract.\n"
            "3. Build a TransactionEnvelope describing the intended mutations when a\n"
            " transaction is a better fit than direct execution.\n"
            "4. Call fl_plan to validate and preview exact diffs, conflicts,\n"
            " and rollback behavior.\n"
            "5. If the preview looks correct, call fl_apply with the desired\n"
            " rollback policy.\n"
            "For final audio assets use fl_render (poll via render://jobs/{job_id}).\n"
            "For audio understanding use fl_analyze_audio (poll via audio://analyses/{analysis_id}).\n"
            "For provider health use fl_manage_providers.\n"
            "Primitive FL operations are intentionally hidden from list_tools; reach\n"
            "them through fl_execute(operation_id=...) or fl_batch_execute."
        ),
        tags={"transaction", "workflow", "guidance", "public"},
    ),
    PromptDefinition(
        name="build_beat",
        description="Guide a compact-surface workflow for creating a beat.",
        content=(
            "Build a beat using the compact FL MCP surface: snapshot project state,\n"
            "search schemas for patterns, channels, piano-roll, playlist, and browser\n"
            "operations, then batch pattern creation, notes, channel/sample loading,\n"
            "and playlist placement with readback."
        ),
        tags={"workflow", "beat", "browser", "public"},
    ),
    PromptDefinition(
        name="load_instrument_or_effect",
        description="Guide plugin, preset, sample, instrument, and effect loading.",
        content=(
            "Use fl_browser first for plugins, presets, samples, drum kits,\n"
            "instruments, and effects. If needed, fetch schemas for plugins.load,\n"
            "plugins.replace, plugins.load_preset_by_name, or channels.load_sample,\n"
            "then execute with readback through fl_execute."
        ),
        tags={"workflow", "browser", "plugins", "public"},
    ),
    PromptDefinition(
        name="create_automation",
        description="Guide an automation-clip workflow with safety/readback.",
        content=(
            "Use fl_search_capabilities(domain='automation') and schema lookup to\n"
            "create automation clips, write points, and link parameters. Prefer\n"
            "fl_batch_execute with readback for create/write/link workflows."
        ),
        tags={"workflow", "automation", "public"},
    ),
    PromptDefinition(
        name="arrange_sections",
        description="Guide arrangement, playlist, marker, and section workflows.",
        content=(
            "Use fl_snapshot(domain='arrangement'), search playlist and arrangement\n"
            "capabilities, then batch marker creation, clip placement, movement, and\n"
            "section duplication through operation ids with readback."
        ),
        tags={"workflow", "arrangement", "playlist", "public"},
    ),
    PromptDefinition(
        name="safe_mix_adjustment",
        description="Guide reversible mixer/channel adjustments with readback.",
        content=(
            "For mix changes, inspect mixer/channel state, fetch exact schemas, then\n"
            "use fl_execute or fl_batch_execute with readback for volume, pan, mute,\n"
            "solo, routing, EQ, and plugin parameter changes."
        ),
        tags={"workflow", "mix", "mixer", "public"},
    ),
    PromptDefinition(
        name="render_and_analyze",
        description="Guide render and audio-analysis task workflows.",
        content=(
            "Use fl_render for export tasks and fl_analyze_audio for analysis tasks.\n"
            "Capture task ids, poll render://jobs/{job_id} or audio://analyses/{analysis_id},\n"
            "and summarize artifacts, task state, provider, and bridge mode."
        ),
        tags={"workflow", "render", "audio", "public"},
    ),
)


def prompt_names() -> tuple[str, ...]:
    """Return sorted prompt names for surface inspection."""

    return tuple(sorted(prompt.name for prompt in PROMPTS))
