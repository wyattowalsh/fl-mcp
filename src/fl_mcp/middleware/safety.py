"""Safety gating middleware skeleton."""


def ensure_safe_mode(safety_mode: str) -> None:
    if safety_mode not in {"strict", "standard", "relaxed"}:
        raise ValueError(f"Unsupported safety mode: {safety_mode}")
