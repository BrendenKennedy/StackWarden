"""Interactive CLI wizard — pure UI layer over resolve/ensure pipeline.

Guides users through profile -> intent -> stack -> variants selection,
then either prints a runnable command or executes via ``ensure_internal()``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from stacksmith.domain.models import Plan, Profile, StackSpec
from stacksmith.domain.variants import normalize_variants, validate_variant_flags
from stacksmith.resolvers.rules import evaluate_all

try:
    import questionary
    _HAS_QUESTIONARY = True
except ImportError:
    _HAS_QUESTIONARY = False

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class WizardFlags(BaseModel):
    immutable: bool = False
    upgrade_base: bool = False
    no_hooks: bool = False
    rebuild: bool = False
    explain: bool = False


class WizardSelection(BaseModel):
    profile_id: str
    stack_id: str
    variants: dict[str, bool | str] = Field(default_factory=dict)
    flags: WizardFlags = Field(default_factory=WizardFlags)


class WizardResult(BaseModel):
    selection: WizardSelection
    plan_summary: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    digest_status: str = "unknown_until_pull"
    command: str
    executed: bool = False
    tag: str | None = None


# ---------------------------------------------------------------------------
# Prompt helpers (questionary with Rich fallback)
# ---------------------------------------------------------------------------

_console = Console()


def _select(prompt: str, choices: list[str], default: str | None = None) -> str:
    if _HAS_QUESTIONARY:
        answer = questionary.select(prompt, choices=choices, default=default).ask()
        if answer is None:
            raise KeyboardInterrupt
        return answer
    _console.print(f"\n[bold]{prompt}[/bold]")
    for i, c in enumerate(choices, 1):
        marker = " [cyan](default)[/cyan]" if c == default else ""
        _console.print(f"  {i}. {c}{marker}")
    from rich.prompt import Prompt
    while True:
        raw = Prompt.ask("Choice", default="1" if default is None else str(choices.index(default) + 1))
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass
        _console.print("[red]Invalid choice, try again.[/red]")


def _confirm(prompt: str, default: bool = False) -> bool:
    if _HAS_QUESTIONARY:
        answer = questionary.confirm(prompt, default=default).ask()
        if answer is None:
            raise KeyboardInterrupt
        return answer
    from rich.prompt import Confirm
    return Confirm.ask(prompt, default=default)


# ---------------------------------------------------------------------------
# Profile selection
# ---------------------------------------------------------------------------


def choose_profile(profiles: list[Profile], default_id: str | None = None) -> str:
    """Prompt the user to pick a hardware profile."""
    labels: list[str] = []
    default_label: str | None = None
    for p in profiles:
        cuda_desc = f"cuda{p.cuda.major}.{p.cuda.minor}" if p.cuda else "cuda-unknown"
        label = (
            f"{p.id}  |  {p.arch.value}  |  "
            f"{cuda_desc}  |  {p.container_runtime.value}"
        )
        labels.append(label)
        if p.id == default_id:
            default_label = label
    chosen = _select("Select a hardware profile:", labels, default=default_label)
    return profiles[labels.index(chosen)].id


# ---------------------------------------------------------------------------
# Compatibility filtering
# ---------------------------------------------------------------------------


def filter_compatible_stacks(
    stacks: list[StackSpec], profile: Profile,
) -> list[StackSpec]:
    """Keep only stacks that have no fatal compatibility errors with *profile*."""
    compatible: list[StackSpec] = []
    for s in stacks:
        _warnings, errors = evaluate_all(profile, s)
        if not errors:
            compatible.append(s)
    return compatible


def choose_stack(
    matches: list[StackSpec],
) -> str | None:
    """Prompt user to pick a stack from compatible options."""
    if len(matches) == 1:
        return matches[0].id

    if matches:
        labels = [
            f"{s.id}  |  {s.display_name}" for s in matches
        ]
        chosen = _select("Select a stack:", labels)
        return matches[labels.index(chosen)].id

    _console.print("\n[yellow]No compatible stacks found.[/yellow]")
    return None


# ---------------------------------------------------------------------------
# Variant prompting
# ---------------------------------------------------------------------------


def prompt_variants(
    stack: StackSpec, *, use_defaults: bool = False,
) -> dict[str, bool | str]:
    """Prompt the user for each variant defined by *stack*.

    If *use_defaults* is True, all defaults are accepted without prompting.
    """
    if not stack.variants:
        return {}

    result: dict[str, bool | str] = {}
    for name, vdef in sorted(stack.variants.items()):
        if use_defaults:
            result[name] = vdef.default
            continue

        if vdef.type == "bool":
            result[name] = _confirm(
                f"Enable {name}?", default=bool(vdef.default),
            )
        elif vdef.type == "enum":
            default_str = str(vdef.default) if vdef.default in vdef.options else vdef.options[0]
            result[name] = _select(
                f"Select {name}:", vdef.options, default=default_str,
            )
    return result


# ---------------------------------------------------------------------------
# Plan preview
# ---------------------------------------------------------------------------


def preview_plan(
    profile: Profile,
    stack: StackSpec,
    variants: dict[str, bool | str] | None,
    *,
    explain: bool = False,
    strict_mode: bool = False,
) -> Plan:
    """Resolve a plan and return it (for rendering)."""
    from stacksmith.resolvers.resolver import resolve

    return resolve(profile, stack, variants=variants, explain=explain, strict_mode=strict_mode)


def render_plan_human(plan: Plan, *, console: Console | None = None) -> None:
    """Render a plan preview to the terminal with Rich."""
    con = console or _console

    con.print(Panel(
        f"[bold]{plan.profile_id}[/bold] + [bold]{plan.stack_id}[/bold]",
        title="Wizard Plan Preview",
    ))

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value")
    table.add_row("Base Image", plan.decision.base_image)
    digest_display = plan.decision.base_digest or "pending (will resolve at pull time)"
    table.add_row("Digest", digest_display)
    table.add_row("Output Tag", f"[green]{plan.artifact.tag}[/green]")
    table.add_row("Strategy", plan.decision.builder)
    table.add_row("Fingerprint", plan.artifact.fingerprint[:24] + "...")
    con.print(table)

    if plan.decision.warnings:
        con.print(Panel(
            "\n".join(f"- {w}" for w in plan.decision.warnings),
            title="Warnings",
            border_style="yellow",
        ))

    con.print(f"\n[bold]Steps ({len(plan.steps)}):[/bold]")
    for i, step in enumerate(plan.steps, 1):
        desc = step.type
        if step.image:
            desc += f" {step.image}"
        if step.tags:
            desc += f" -> {step.tags[0]}"
        con.print(f"  {i}. {desc}")


def render_plan_json(plan: Plan, selection: WizardSelection) -> dict[str, Any]:
    """Build the JSON-serializable plan summary."""
    return {
        "plan_id": plan.plan_id,
        "profile_id": plan.profile_id,
        "stack_id": plan.stack_id,
        "base_image": plan.decision.base_image,
        "base_digest": plan.decision.base_digest,
        "digest_status": "known" if plan.decision.base_digest else "unknown_until_pull",
        "output_tag": plan.artifact.tag,
        "fingerprint": plan.artifact.fingerprint,
        "strategy": plan.decision.builder,
        "warnings": plan.decision.warnings,
        "steps": [s.type for s in plan.steps],
        "variants": dict(selection.variants) if selection.variants else {},
    }


# ---------------------------------------------------------------------------
# Command generation
# ---------------------------------------------------------------------------


def build_command(selection: WizardSelection) -> str:
    """Generate a deterministic ``stacksmith ensure`` CLI string."""
    parts = [
        "stacksmith", "ensure",
        "--profile", selection.profile_id,
        "--stack", selection.stack_id,
    ]
    for k, v in sorted(selection.variants.items()):
        val = str(v).lower() if isinstance(v, bool) else str(v)
        parts.extend(["--var", f"{k}={val}"])
    if selection.flags.rebuild:
        parts.append("--rebuild")
    if selection.flags.upgrade_base:
        parts.append("--upgrade-base")
    if selection.flags.immutable:
        parts.append("--immutable")
    if selection.flags.no_hooks:
        parts.append("--no-hooks")
    if selection.flags.explain:
        parts.append("--explain")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Main wizard orchestrator
# ---------------------------------------------------------------------------


def run_wizard(
    *,
    profile_id: str | None = None,
    stack_id: str | None = None,
    var_overrides: dict[str, bool | str] | None = None,
    defaults: bool = False,
    flags: WizardFlags | None = None,
    default_profile: str | None = None,
    console: Console | None = None,
) -> WizardResult:
    """Run the wizard flow and return a ``WizardResult``.

    This function handles both interactive and non-interactive modes.
    When all required inputs are provided via arguments, no prompts are shown.
    """
    from stacksmith.config import compatibility_strict_default, load_profile, load_stack
    from stacksmith.domain.loaders import load_all_profiles, load_all_stacks

    con = console or _console
    wiz_flags = flags or WizardFlags()

    # 1. Profile selection
    if not profile_id:
        if defaults and default_profile:
            profile_id = default_profile
        else:
            profiles = load_all_profiles()
            if not profiles:
                con.print("[red]No profiles found. Run 'stacksmith init' first.[/red]")
                raise SystemExit(1)
            profile_id = choose_profile(profiles, default_id=default_profile)

    profile = load_profile(profile_id)

    # 2. Stack selection
    if not stack_id:
        all_stacks = load_all_stacks()
        compatible = filter_compatible_stacks(all_stacks, profile)
        if not compatible:
            con.print(
                f"[red]No compatible stacks for profile '{profile_id}'.[/red]"
            )
            raise SystemExit(1)
        stack_id = choose_stack(compatible)

    stack = load_stack(stack_id)

    # 3. Variant selection
    if var_overrides is not None:
        variants = normalize_variants(stack, var_overrides) if stack.variants else {}
    elif stack.variants:
        variants = prompt_variants(stack, use_defaults=defaults)
        variants = normalize_variants(stack, variants)
    else:
        variants = {}

    # 4. Build selection and preview plan
    selection = WizardSelection(
        profile_id=profile_id,
        stack_id=stack_id,
        variants=variants,
        flags=wiz_flags,
    )

    plan = preview_plan(
        profile,
        stack,
        variants or None,
        explain=wiz_flags.explain,
        strict_mode=compatibility_strict_default(),
    )
    command = build_command(selection)

    plan_json = render_plan_json(plan, selection)

    return WizardResult(
        selection=selection,
        plan_summary=plan_json,
        warnings=plan.decision.warnings,
        digest_status="known" if plan.decision.base_digest else "unknown_until_pull",
        command=command,
    )
