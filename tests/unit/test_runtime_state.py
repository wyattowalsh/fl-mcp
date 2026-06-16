from fl_mcp.runtime.state import RuntimeState


def test_runtime_state_normalizes_task_records_and_cancellation() -> None:
    state = RuntimeState()

    render_job = state.create_render_job(
        provider="mock",
        tool="render_project",
        operation="render.export",
        payload={"output_path": "mix.wav"},
        result={
            "task_status": "unexpected",
            "message": "Queued by mock bridge",
            "artifacts": ["mix.wav", 42],
        },
    )

    assert render_job.state == "queued"
    assert render_job.artifacts == ["mix.wav", "42"]

    canceled = state.cancel_render_job(render_job.id)

    assert canceled is not None
    assert canceled.state == "canceled"
    assert canceled.message == "Render job canceled."

    analysis = state.create_audio_analysis(
        provider="mock",
        tool="analyze_audio",
        operation="audio.analyze",
        payload={"input_path": "mix.wav"},
        result={
            "state": "running",
            "artifacts": "not-a-list",
        },
    )

    assert analysis.state == "running"
    assert analysis.artifacts == []
