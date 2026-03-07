from fl_mcp.config.loading import load_config


def test_config_loading_is_deterministic_with_source_ordering() -> None:
    base = {"z_key": "z", "a_key": "a"}
    env = {"m_key": "m", "b_key": "b"}

    first = load_config(base, env)
    second = load_config(dict(reversed(list(base.items()))), dict(reversed(list(env.items()))))

    assert first == second
    assert list(first.keys()) == sorted(first.keys())
