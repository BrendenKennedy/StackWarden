"""CLI composition metadata for staged decomposition."""

from __future__ import annotations

from stackwarden.cli import app
from stackwarden.cli import CLI_HIGH_RISK_COMMAND_MAP, CLI_LOW_RISK_COMMAND_MAP

__all__ = ["app", "CLI_LOW_RISK_COMMAND_MAP", "CLI_HIGH_RISK_COMMAND_MAP"]
