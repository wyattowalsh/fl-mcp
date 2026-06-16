"""Custom exception hierarchy for fl-mcp."""

from __future__ import annotations


class FLMCPError(Exception):
    """Base exception for all fl-mcp errors."""


class BridgeError(FLMCPError):
    """Error during FL Studio bridge communication."""


class ProviderError(FLMCPError):
    """Error in provider lifecycle or execution."""


class TransactionError(FLMCPError):
    """Error during transaction planning or execution."""


class ConfigurationError(FLMCPError):
    """Error in configuration or settings."""
