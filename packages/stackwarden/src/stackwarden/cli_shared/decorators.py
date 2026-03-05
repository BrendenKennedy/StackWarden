"""CLI decorators for common patterns."""

from __future__ import annotations

import functools
from typing import Callable, TypeVar

import typer

from stackwarden.cli_shared.errors import exit_code_for

F = TypeVar("F", bound=Callable[..., None])


def with_cli_errors(console) -> Callable[[F], F]:
    """Decorator that catches exceptions, prints to console, and exits with appropriate code."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> None:
            try:
                func(*args, **kwargs)
            except typer.Exit:
                raise
            except Exception as exc:
                console.print(f"[red]Error:[/red] {exc}")
                raise typer.Exit(exit_code_for(exc))

        return wrapper  # type: ignore[return-value]

    return decorator
