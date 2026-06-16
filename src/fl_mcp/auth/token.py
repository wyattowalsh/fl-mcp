"""Optional local token auth."""

from __future__ import annotations

import hmac
from collections.abc import Mapping
from typing import cast

from fl_mcp.config.settings import settings

_INVALID_TOKEN = object()
_MISSING = object()
_TOKEN_FIELDS = ("token", "access_token", "auth_token")


def check_token(token: str | None) -> bool:
    configured = settings.auth_token
    if configured is None:
        return True
    if token is None:
        return False
    if not isinstance(token, str):
        return False
    return hmac.compare_digest(token, configured)


def _normalize_token_candidate(candidate: object) -> str | None | object:
    if candidate is None:
        return None

    if isinstance(candidate, str):
        normalized = candidate.strip()
        if not normalized:
            return _INVALID_TOKEN
        return normalized

    if isinstance(candidate, Mapping):
        candidate_mapping = cast(Mapping[str, object], candidate)
        if "token" not in candidate_mapping:
            return _INVALID_TOKEN
        return _normalize_token_candidate(candidate_mapping["token"])

    nested = getattr(candidate, "token", _MISSING)
    if nested is _MISSING or nested is candidate:
        return _INVALID_TOKEN
    return _normalize_token_candidate(nested)


def _iter_context_token_sources(context: object) -> list[object]:
    if context is None:
        return []
    if isinstance(context, str):
        return [context]

    sources: list[object] = []
    if isinstance(context, Mapping):
        context_mapping = cast(Mapping[str, object], context)
        for field in _TOKEN_FIELDS:
            if field in context_mapping:
                sources.append(context_mapping[field])

    for field in _TOKEN_FIELDS:
        value = getattr(context, field, _MISSING)
        if value is not _MISSING:
            sources.append(value)
    return sources


def _extract_context_token(context: object) -> tuple[str | None, bool]:
    """Resolve token from supported context shapes.

    Returns `(token, deny)` where `deny=True` indicates ambiguous/invalid token state.
    """

    unique_tokens: set[str] = set()
    invalid = False

    for source in _iter_context_token_sources(context):
        resolved = _normalize_token_candidate(source)
        if resolved is _INVALID_TOKEN:
            invalid = True
            continue
        if isinstance(resolved, str):
            unique_tokens.add(resolved)

    if invalid or len(unique_tokens) > 1:
        return None, True
    if unique_tokens:
        return next(iter(unique_tokens)), False
    return None, False


def check_auth_context(context: object) -> bool:
    """Validate a FastMCP auth context against configured token policy."""

    token_value, deny = _extract_context_token(context)
    if deny:
        return False
    return check_token(token_value)
