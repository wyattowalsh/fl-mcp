"""Tests for the fl-mcp custom exception hierarchy."""

from __future__ import annotations

import pytest

from fl_mcp.exceptions import (
    BridgeError,
    ConfigurationError,
    FLMCPError,
    ProviderError,
    TransactionError,
)


class TestImportability:
    """All exception classes are importable from fl_mcp.exceptions."""

    def test_flmcp_error_importable(self) -> None:
        assert FLMCPError is not None

    def test_bridge_error_importable(self) -> None:
        assert BridgeError is not None

    def test_provider_error_importable(self) -> None:
        assert ProviderError is not None

    def test_transaction_error_importable(self) -> None:
        assert TransactionError is not None

    def test_configuration_error_importable(self) -> None:
        assert ConfigurationError is not None


class TestInheritance:
    """Exception classes have the correct inheritance chain."""

    def test_flmcp_error_is_subclass_of_exception(self) -> None:
        assert issubclass(FLMCPError, Exception)

    def test_bridge_error_is_subclass_of_flmcp_error(self) -> None:
        assert issubclass(BridgeError, FLMCPError)

    def test_provider_error_is_subclass_of_flmcp_error(self) -> None:
        assert issubclass(ProviderError, FLMCPError)

    def test_transaction_error_is_subclass_of_flmcp_error(self) -> None:
        assert issubclass(TransactionError, FLMCPError)

    def test_configuration_error_is_subclass_of_flmcp_error(self) -> None:
        assert issubclass(ConfigurationError, FLMCPError)


class TestCatchByParent:
    """Each exception can be raised and caught by the parent class."""

    def test_bridge_error_caught_by_flmcp_error(self) -> None:
        with pytest.raises(FLMCPError):
            raise BridgeError("bridge failure")

    def test_provider_error_caught_by_flmcp_error(self) -> None:
        with pytest.raises(FLMCPError):
            raise ProviderError("provider failure")

    def test_transaction_error_caught_by_flmcp_error(self) -> None:
        with pytest.raises(FLMCPError):
            raise TransactionError("transaction failure")

    def test_configuration_error_caught_by_flmcp_error(self) -> None:
        with pytest.raises(FLMCPError):
            raise ConfigurationError("configuration failure")

    def test_flmcp_error_caught_by_exception(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            raise FLMCPError("base failure")


class TestMessagePropagation:
    """Exception messages propagate correctly through str() and args."""

    def test_flmcp_error_message(self) -> None:
        exc = FLMCPError("base message")
        assert str(exc) == "base message"
        assert exc.args == ("base message",)

    def test_bridge_error_message(self) -> None:
        exc = BridgeError("bridge message")
        assert str(exc) == "bridge message"
        assert exc.args == ("bridge message",)

    def test_provider_error_message(self) -> None:
        exc = ProviderError("provider message")
        assert str(exc) == "provider message"
        assert exc.args == ("provider message",)

    def test_transaction_error_message(self) -> None:
        exc = TransactionError("transaction message")
        assert str(exc) == "transaction message"
        assert exc.args == ("transaction message",)

    def test_configuration_error_message(self) -> None:
        exc = ConfigurationError("configuration message")
        assert str(exc) == "configuration message"
        assert exc.args == ("configuration message",)
