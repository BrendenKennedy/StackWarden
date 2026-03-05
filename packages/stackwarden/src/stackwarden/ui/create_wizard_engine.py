"""Shared prompt/runtime helpers for guided create wizards."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from rich.console import Console
from rich.syntax import Syntax

try:
    import questionary

    _HAS_QUESTIONARY = True
except ImportError:  # pragma: no cover - optional dependency
    _HAS_QUESTIONARY = False


class CreateWizardResult(BaseModel):
    entity: str
    id: str
    valid: bool = True
    created: bool = False
    path: str | None = None
    yaml: str = ""
    errors: list[dict[str, str]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WizardPrompts:
    """Prompt adapter with questionary + rich fallback."""

    def __init__(self, *, console: Console | None = None, non_interactive: bool = False):
        self.console = console or Console()
        self.non_interactive = non_interactive

    def choose(self, prompt: str, choices: list[str], default: str | None = None) -> str:
        if not choices:
            raise ValueError(f"No choices available for: {prompt}")
        if self.non_interactive:
            if default and default in choices:
                return default
            return choices[0]
        if _HAS_QUESTIONARY:
            answer = questionary.select(prompt, choices=choices, default=default).ask()
            if answer is None:
                raise KeyboardInterrupt
            return answer
        from rich.prompt import Prompt

        self.console.print(f"\n[bold]{prompt}[/bold]")
        for idx, choice in enumerate(choices, 1):
            marker = " [cyan](default)[/cyan]" if choice == default else ""
            self.console.print(f"  {idx}. {choice}{marker}")
        default_idx = str(choices.index(default) + 1) if default in choices else "1"
        while True:
            raw = Prompt.ask("Choice", default=default_idx)
            try:
                selected = int(raw) - 1
            except ValueError:
                selected = -1
            if 0 <= selected < len(choices):
                return choices[selected]
            self.console.print("[red]Invalid choice, try again.[/red]")

    def text(
        self,
        prompt: str,
        *,
        default: str | None = None,
        required: bool = True,
    ) -> str:
        if self.non_interactive:
            if default is None:
                return ""
            return default
        if _HAS_QUESTIONARY:
            answer = questionary.text(prompt, default=default or "").ask()
            if answer is None:
                raise KeyboardInterrupt
            value = answer.strip()
        else:
            from rich.prompt import Prompt

            value = Prompt.ask(prompt, default=default or "").strip()
        if required and not value:
            self.console.print("[red]This field is required.[/red]")
            return self.text(prompt, default=default, required=required)
        return value

    def confirm(self, prompt: str, *, default: bool = False) -> bool:
        if self.non_interactive:
            return default
        if _HAS_QUESTIONARY:
            answer = questionary.confirm(prompt, default=default).ask()
            if answer is None:
                raise KeyboardInterrupt
            return bool(answer)
        from rich.prompt import Confirm

        return Confirm.ask(prompt, default=default)

    def print_yaml_preview(self, yaml_text: str) -> None:
        if not yaml_text.strip():
            return
        self.console.print("\n[bold]Generated YAML preview[/bold]")
        self.console.print(Syntax(yaml_text, "yaml", theme="ansi_dark", word_wrap=True))

    def maybe_write_output(self, output: str | None, yaml_text: str) -> None:
        if not output:
            return
        path = Path(output).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml_text, encoding="utf-8")
        self.console.print(f"[green]Wrote YAML preview:[/green] {path}")
