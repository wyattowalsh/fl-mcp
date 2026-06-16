"""FL MCP package root."""

from fl_mcp.exceptions import (
    BridgeError,
    ConfigurationError,
    FLMCPError,
    ProviderError,
    TransactionError,
)

__all__ = [
    "BridgeError",
    "ConfigurationError",
    "FLMCPError",
    "ProviderError",
    "TransactionError",
    "__version__",
]
__version__ = "0.1.0"
