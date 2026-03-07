from fl_mcp.schemas.generation import generate_schema_json


def test_schema_json_generation_is_consistent() -> None:
    first = generate_schema_json()
    second = generate_schema_json()

    assert first == second
    assert '"$schema"' in first
