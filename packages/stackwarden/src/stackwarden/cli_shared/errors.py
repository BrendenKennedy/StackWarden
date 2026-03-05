"""Error and messaging helpers for CLI surfaces."""

from __future__ import annotations

from stackwarden.domain.errors import StackWardenError


def deprecated_alias_notice(console, alias_cmd: str, replacement_cmd: str) -> None:
    console.print(
        f"[yellow]Deprecated command alias:[/yellow] `{alias_cmd}`. "
        f"Use `{replacement_cmd}` instead."
    )


def exit_code_for(exc: Exception) -> int:
    if isinstance(exc, StackWardenError):
        return exc.exit_code
    return 1
