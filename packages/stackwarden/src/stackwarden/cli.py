"""StackWarden CLI — Typer application."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Any, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from stackwarden import __version__
from stackwarden.domain.errors import StackWardenError
from stackwarden.cli_commands.high_risk import command_map as high_risk_command_map
from stackwarden.cli_commands.list_commands import register_list_commands
from stackwarden.cli_commands.low_risk import command_map as low_risk_command_map
from stackwarden.cli_shared.catalog import get_catalog
from stackwarden.cli_shared.context import setup_cli
from stackwarden.cli_shared.errors import deprecated_alias_notice, exit_code_for
from stackwarden.cli_shared.help_content import HELP_EPILOG, get_help_for_topic
from stackwarden.cli_shared.io_yaml import atomic_write_spec, edit_yaml_via_editor, load_yaml_file
from stackwarden.cli_shared.decorators import with_cli_errors
from stackwarden.cli_shared.render import print_rationale

app = typer.Typer(
    name="stackwarden",
    help="Hardware-aware ML container build manager.",
    no_args_is_help=True,
    epilog=HELP_EPILOG,
)
list_app = typer.Typer(help="List available profiles and stacks.")
profiles_app = typer.Typer(help="Manage hardware profiles.")
stacks_app = typer.Typer(help="Manage stack specs.")
blocks_app = typer.Typer(help="Manage reusable blocks.")
catalog_app = typer.Typer(help="Query and manage the artifact catalog.")
export_app = typer.Typer(help="Export run helpers for built artifacts.")
migrate_app = typer.Typer(help="Migrate v1 specs to v2 contracts.")
app.add_typer(list_app, name="list")
app.add_typer(profiles_app, name="profiles")
app.add_typer(stacks_app, name="stacks")
app.add_typer(blocks_app, name="blocks")
app.add_typer(catalog_app, name="catalog")
app.add_typer(export_app, name="export")
app.add_typer(migrate_app, name="migrate")

console = Console()
log = logging.getLogger("stackwarden")
CLI_LOW_RISK_COMMAND_MAP = low_risk_command_map()
CLI_HIGH_RISK_COMMAND_MAP = high_risk_command_map()

# ---------------------------------------------------------------------------
# Shared options
# ---------------------------------------------------------------------------

_verbose_option = typer.Option(False, "--verbose", "-v", help="Enable debug logging")
_json_option = typer.Option(False, "--json", "-j", help="Output machine-readable JSON")
_var_option = typer.Option(
    None,
    "--var",
    help="Variant override in key=value form (repeatable). Example: --var python=3.11 --var cuda=12.4",
)


def _deprecated_alias_notice(alias_cmd: str, replacement_cmd: str) -> None:
    deprecated_alias_notice(console, alias_cmd, replacement_cmd)


def _artifact_runtime_and_ports(record) -> tuple[str | None, list[int]]:
    from stackwarden.config import load_profile
    from stackwarden.domain.snapshots import artifact_dir, load_snapshot

    runtime: str | None = None
    ports: list[int] = []
    art_dir = artifact_dir(record.fingerprint)

    profile_path = art_dir / "profile.json"
    if profile_path.exists():
        try:
            profile_data = load_snapshot(art_dir, "profile")
            value = profile_data.get("container_runtime")
            runtime = str(value).strip() if value else None
        except Exception as exc:
            log.debug("Failed to load profile snapshot for %s: %s", record.tag, exc)
    if runtime is None:
        try:
            profile = load_profile(record.profile_id)
            runtime = profile.container_runtime.value
        except Exception as exc:
            log.debug("Failed to load profile %s for export: %s", record.profile_id, exc)

    stack_path = art_dir / "stack.json"
    if stack_path.exists():
        try:
            stack_data = load_snapshot(art_dir, "stack")
            ports = [int(p) for p in stack_data.get("ports", []) if isinstance(p, int)]
        except Exception as exc:
            log.debug("Failed to load stack snapshot for %s: %s", record.tag, exc)

    return runtime, ports


def _normalize_legacy_block_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Accept legacy block schema shapes and normalize to create DTO."""
    data = dict(raw)
    components = data.get("components") if isinstance(data.get("components"), dict) else {}
    files = data.get("files") if isinstance(data.get("files"), dict) else {}
    entrypoint = data.get("entrypoint") if isinstance(data.get("entrypoint"), dict) else {}

    env = data.get("env", {})
    if isinstance(env, list):
        env_dict: dict[str, str] = {}
        for item in env:
            if isinstance(item, str) and "=" in item:
                k, v = item.split("=", 1)
                env_dict[k] = v
        env = env_dict
    if not isinstance(env, dict):
        env = {}

    data.setdefault("schema_version", 1)
    data.setdefault("tags", [])
    data.setdefault("build_strategy", data.get("build_strategy"))
    data.setdefault("base_role", components.get("base_role"))
    data.setdefault("pip", components.get("pip", []))
    data.setdefault("pip_install_mode", "index")
    data.setdefault("pip_wheelhouse_path", "")
    data.setdefault("npm", components.get("npm", []))
    data.setdefault("npm_install_mode", "spec")
    data.setdefault("apt", components.get("apt", []))
    data.setdefault("apt_constraints", {})
    data.setdefault("apt_install_mode", "repo")
    data["env"] = env
    data.setdefault("ports", data.get("ports", []))
    if "entrypoint_cmd" not in data and entrypoint.get("cmd"):
        data["entrypoint_cmd"] = entrypoint.get("cmd")
    data.setdefault("copy_items", files.get("copy", data.get("copy_items", [])))
    data.setdefault("variants", {})
    data.setdefault("requires", data.get("requires", {}))
    data.setdefault("conflicts", data.get("conflicts", []))
    data.setdefault("incompatible_with", data.get("incompatible_with", []))
    data.setdefault("provides", data.get("provides", {}))
    return data


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    """Hardware-aware ML container build manager."""
    ctx.ensure_object(dict)
    from stackwarden.config import AppConfig

    ctx.obj["config"] = AppConfig.load()


# ---------------------------------------------------------------------------
# list commands
# ---------------------------------------------------------------------------

list_profiles, list_stacks, list_blocks = register_list_commands(
    list_app,
    verbose_option=_verbose_option,
    json_option=_json_option,
    setup_fn=setup_cli,
    console=console,
)

# ---------------------------------------------------------------------------
# entity-first commands
# ---------------------------------------------------------------------------


@profiles_app.command("list")
def profiles_list_cmd(
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """List profiles (entity-first alias)."""
    _deprecated_alias_notice("stackwarden profiles list", "stackwarden list profiles")
    list_profiles(verbose=verbose, output_json=output_json)


@profiles_app.command("show")
@with_cli_errors(console)
def profiles_show_cmd(
    id: str = typer.Option(..., "--id", help="Profile ID"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Show profile details."""
    setup_cli(verbose=verbose)
    from stackwarden.config import load_profile
    from stackwarden.web.util.write_yaml import serialize_for_yaml

    profile = load_profile(id)
    data = serialize_for_yaml(profile)
    if output_json:
        console.print_json(json.dumps(data, indent=2))
        return

    console.print(Panel(f"[bold]{profile.display_name}[/bold]", title=f"Profile: {profile.id}"))
    console.print(f"  Arch: {profile.arch.value}")
    console.print(f"  OS: {profile.os}")
    console.print(f"  Runtime: {profile.container_runtime.value}")
    if profile.cuda:
        console.print(f"  CUDA: {profile.cuda.major}.{profile.cuda.minor} ({profile.cuda.variant})")
    else:
        console.print("  CUDA: not declared")
    console.print(f"  GPU: {profile.gpu.vendor}/{profile.gpu.family}")


@profiles_app.command("create")
@with_cli_errors(console)
def profiles_create_cmd(
    file: str = typer.Option(..., "--file", "-f", help="Profile YAML file to create from"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Create a profile from a YAML file."""
    setup_cli(verbose=verbose)
    from stackwarden.application.create_flows import create_profile
    from stackwarden.web.schemas import ProfileCreateRequest

    raw = load_yaml_file(file)
    req = ProfileCreateRequest.model_validate(raw)
    target = create_profile(req)
    if output_json:
        console.print_json(json.dumps({"id": req.id, "path": str(target)}, indent=2))
        return
    console.print(f"[green]Created profile:[/green] {req.id}")
    console.print(f"  Path: {target}")


@profiles_app.command("edit")
@with_cli_errors(console)
def profiles_edit_cmd(
    id: str = typer.Option(..., "--id", help="Profile ID to edit"),
    file: str | None = typer.Option(None, "--file", "-f", help="Optional YAML file to apply"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Edit an existing profile from file or $EDITOR."""
    setup_cli(verbose=verbose)
    from stackwarden.application.create_flows import update_profile
    from stackwarden.config import load_profile
    from stackwarden.web.schemas import ProfileCreateRequest
    from stackwarden.web.util.write_yaml import serialize_for_yaml

    original = load_profile(id)
    raw = load_yaml_file(file) if file else edit_yaml_via_editor(serialize_for_yaml(original))
    req = ProfileCreateRequest.model_validate(raw)
    target = update_profile(id, req)
    if output_json:
        console.print_json(json.dumps({"id": id, "path": str(target)}, indent=2))
        return
    console.print(f"[green]Updated profile:[/green] {id}")


@profiles_app.command("detect")
@with_cli_errors(console)
def profiles_detect_cmd(
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Detect profile hints on the current server host."""
    setup_cli(verbose=verbose)
    from stackwarden.web.services.host_detection import detect_server_hints

    hints = detect_server_hints()
    data = hints.model_dump(mode="json")
    if output_json:
        console.print_json(json.dumps(data, indent=2))
        return
    console.print(Panel("[bold]Server-host detection[/bold]", title="Profile Detect"))
    console.print(f"  Arch: {data.get('arch') or 'unknown'}")
    console.print(f"  OS: {data.get('os') or 'unknown'}")
    console.print(f"  Runtime: {data.get('container_runtime') or 'unknown'}")
    if data.get("cuda"):
        c = data["cuda"]
        console.print(f"  CUDA: {c.get('major')}.{c.get('minor')} ({c.get('variant')})")


@profiles_app.command("wizard")
@with_cli_errors(console)
def profiles_wizard_cmd(
    id: str | None = typer.Option(None, "--id", help="Profile id override"),
    display_name: str | None = typer.Option(None, "--display-name", help="Profile display name override"),
    arch: str | None = typer.Option(None, "--arch", help="Architecture id override"),
    container_runtime: str | None = typer.Option(None, "--container-runtime", help="Container runtime override"),
    non_interactive: bool = typer.Option(False, "--non-interactive", help="Do not prompt; use provided/default values"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and preview YAML without writing"),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation and create immediately"),
    output: str | None = typer.Option(None, "--output", help="Optional path to write preview YAML"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Guided profile wizard with constrained inputs."""
    setup_cli(verbose=verbose)
    from stackwarden.ui.wizard_entities import run_profile_create_wizard

    result = run_profile_create_wizard(
        profile_id=id,
        display_name=display_name,
        arch=arch,
        container_runtime=container_runtime,
        non_interactive=non_interactive,
        dry_run=dry_run,
        yes=yes,
        output=output,
        console=console,
    )
    if output_json:
        console.print_json(result.model_dump_json(indent=2))
        return
    if result.created:
        console.print(f"[green]Created profile:[/green] {result.id}")
        if result.path:
            console.print(f"  Path: {result.path}")
        return
    if result.valid:
        console.print(f"[green]Profile preview valid:[/green] {result.id}")
    else:
        console.print(f"[red]Profile preview invalid:[/red] {result.id}")
        for err in result.errors:
            console.print(f"  - {err.get('field')}: {err.get('message')}")


@stacks_app.command("list")
def stacks_list_cmd(
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """List stacks (entity-first alias)."""
    _deprecated_alias_notice("stackwarden stacks list", "stackwarden list stacks")
    list_stacks(verbose=verbose, output_json=output_json)


@stacks_app.command("show")
@with_cli_errors(console)
def stacks_show_cmd(
    id: str = typer.Option(..., "--id", help="Stack ID"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Show stack details."""
    setup_cli(verbose=verbose)
    from stackwarden.config import load_stack
    from stackwarden.web.util.write_yaml import serialize_for_yaml

    stack = load_stack(id)
    data = serialize_for_yaml(stack)
    if output_json:
        console.print_json(json.dumps(data, indent=2))
        return
    console.print(Panel(f"[bold]{stack.display_name}[/bold]", title=f"Stack: {stack.id}"))
    console.print(f"  Strategy: {stack.build_strategy.value}")
    console.print(f"  Blocks: {len(getattr(stack, 'blocks', []) or [])}")


@stacks_app.command("create")
@with_cli_errors(console)
def stacks_create_cmd(
    file: str = typer.Option(..., "--file", "-f", help="Stack YAML file to create from"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Create a stack from a YAML file."""
    setup_cli(verbose=verbose)
    from stackwarden.application.create_flows import create_stack
    from stackwarden.web.schemas import StackCreateRequest

    raw = load_yaml_file(file)
    req = StackCreateRequest.model_validate(raw)
    target = create_stack(req)
    stack_id = req.id
    if output_json:
        console.print_json(json.dumps({"id": stack_id, "path": str(target)}, indent=2))
        return
    console.print(f"[green]Created stack:[/green] {stack_id}")
    console.print(f"  Path: {target}")


@stacks_app.command("edit")
@with_cli_errors(console)
def stacks_edit_cmd(
    id: str = typer.Option(..., "--id", help="Stack ID to edit"),
    file: str | None = typer.Option(None, "--file", "-f", help="Optional YAML file to apply"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Edit an existing stack from file or $EDITOR."""
    setup_cli(verbose=verbose)
    from stackwarden.application.create_flows import update_stack
    from stackwarden.config import load_stack
    from stackwarden.web.schemas import StackCreateRequest
    from stackwarden.web.util.write_yaml import serialize_for_yaml

    original = load_stack(id)
    raw = load_yaml_file(file) if file else edit_yaml_via_editor(serialize_for_yaml(original))
    req = StackCreateRequest.model_validate(raw)
    target = update_stack(id, req)
    if output_json:
        console.print_json(json.dumps({"id": id, "path": str(target)}, indent=2))
        return
    console.print(f"[green]Updated stack:[/green] {id}")


@stacks_app.command("wizard")
@with_cli_errors(console)
def stacks_wizard_cmd(
    id: str | None = typer.Option(None, "--id", help="Stack id override"),
    display_name: str | None = typer.Option(None, "--display-name", help="Stack display name override"),
    target_profile: str | None = typer.Option(None, "--target-profile", help="Target profile id for guided flow"),
    build_strategy: str | None = typer.Option(None, "--build-strategy", help="Build strategy override"),
    block: Optional[list[str]] = typer.Option(None, "--block", help="Pre-selected block id (repeatable)"),
    non_interactive: bool = typer.Option(False, "--non-interactive", help="Do not prompt; use provided/default values"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and preview YAML without writing"),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation and create immediately"),
    output: str | None = typer.Option(None, "--output", help="Optional path to write preview YAML"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Guided stack wizard with explicit build strategy step."""
    setup_cli(verbose=verbose)
    from stackwarden.ui.wizard_entities import run_stack_create_wizard

    result = run_stack_create_wizard(
        stack_id=id,
        display_name=display_name,
        target_profile_id=target_profile,
        build_strategy=build_strategy,
        blocks=block,
        non_interactive=non_interactive,
        dry_run=dry_run,
        yes=yes,
        output=output,
        console=console,
    )
    if output_json:
        console.print_json(result.model_dump_json(indent=2))
        return
    if result.created:
        console.print(f"[green]Created stack:[/green] {result.id}")
        if result.path:
            console.print(f"  Path: {result.path}")
        return
    if result.valid:
        console.print(f"[green]Stack preview valid:[/green] {result.id}")
    else:
        console.print(f"[red]Stack preview invalid:[/red] {result.id}")
        for err in result.errors:
            console.print(f"  - {err.get('field')}: {err.get('message')}")


@stacks_app.command("delete")
@with_cli_errors(console)
def stacks_delete_cmd(
    id: str = typer.Argument(..., help="Stack ID to delete"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Delete a stack by ID."""
    setup_cli(verbose=verbose)
    from stackwarden.config import get_stacks_dir

    stacks_dir = get_stacks_dir()
    target = (stacks_dir / f"{id}.yaml").resolve()
    if not target.is_relative_to(stacks_dir.resolve()):
        console.print(f"[red]Error:[/red] Invalid stack id: {id}")
        raise typer.Exit(1)
    if not target.exists():
        console.print(f"[red]Error:[/red] Stack not found: {id}")
        raise typer.Exit(1)
    target.unlink()
    if output_json:
        console.print_json(json.dumps({"deleted": True, "id": id}))
    else:
        console.print(f"[green]Deleted stack:[/green] {id}")


@blocks_app.command("list")
def blocks_list_cmd(
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """List blocks (entity-first alias)."""
    _deprecated_alias_notice("stackwarden blocks list", "stackwarden list blocks")
    list_blocks(verbose=verbose, output_json=output_json)


@blocks_app.command("show")
@with_cli_errors(console)
def blocks_show_cmd(
    id: str = typer.Option(..., "--id", help="Block ID"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Show block details."""
    setup_cli(verbose=verbose)
    from stackwarden.config import load_block
    from stackwarden.web.util.write_yaml import serialize_for_yaml

    block = load_block(id)
    data = serialize_for_yaml(block)
    if output_json:
        console.print_json(json.dumps(data, indent=2))
        return
    console.print(Panel(f"[bold]{block.display_name}[/bold]", title=f"Block: {block.id}"))
    console.print(f"  Tags: {', '.join(block.tags) if block.tags else '-'}")


@blocks_app.command("create")
@with_cli_errors(console)
def blocks_create_cmd(
    file: str = typer.Option(..., "--file", "-f", help="Block YAML file to create from"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Create a block from a YAML file."""
    setup_cli(verbose=verbose)
    from stackwarden.application.create_flows import create_block
    from stackwarden.web.schemas import BlockCreateRequest

    raw = _normalize_legacy_block_payload(load_yaml_file(file))
    req = BlockCreateRequest.model_validate(raw)
    target = create_block(req)
    if output_json:
        console.print_json(json.dumps({"id": req.id, "path": str(target)}, indent=2))
        return
    console.print(f"[green]Created block:[/green] {req.id}")
    console.print(f"  Path: {target}")


@blocks_app.command("edit")
@with_cli_errors(console)
def blocks_edit_cmd(
    id: str = typer.Option(..., "--id", help="Block ID to edit"),
    file: str | None = typer.Option(None, "--file", "-f", help="Optional YAML file to apply"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Edit an existing block from file or $EDITOR."""
    setup_cli(verbose=verbose)
    from stackwarden.application.create_flows import update_block
    from stackwarden.config import load_block
    from stackwarden.web.schemas import BlockCreateRequest
    from stackwarden.web.util.write_yaml import serialize_for_yaml

    original = load_block(id)
    raw = load_yaml_file(file) if file else edit_yaml_via_editor(serialize_for_yaml(original))
    raw = _normalize_legacy_block_payload(raw)
    req = BlockCreateRequest.model_validate(raw)
    target = update_block(id, req)
    if output_json:
        console.print_json(json.dumps({"id": id, "path": str(target)}, indent=2))
        return
    console.print(f"[green]Updated block:[/green] {id}")


@blocks_app.command("wizard")
@with_cli_errors(console)
def blocks_wizard_cmd(
    id: str | None = typer.Option(None, "--id", help="Block id override"),
    display_name: str | None = typer.Option(None, "--display-name", help="Block display name override"),
    preset: str | None = typer.Option(None, "--preset", help="Preset id"),
    profile_mode: str = typer.Option("base", "--profile-mode", help="Preset overlay mode: base|cpu|gpu|dev|prod"),
    build_strategy: str | None = typer.Option(None, "--build-strategy", help="Build strategy override"),
    requirements_file: str | None = typer.Option(None, "--requirements-file", help="Optional requirements.txt import"),
    package_json_file: str | None = typer.Option(None, "--package-json-file", help="Optional package.json import"),
    apt_file: str | None = typer.Option(None, "--apt-file", help="Optional apt list import"),
    non_interactive: bool = typer.Option(False, "--non-interactive", help="Do not prompt; use provided/default values"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and preview YAML without writing"),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation and create immediately"),
    output: str | None = typer.Option(None, "--output", help="Optional path to write preview YAML"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Guided block wizard with preset/runtime/review flow."""
    setup_cli(verbose=verbose)
    from stackwarden.ui.wizard_entities import run_block_create_wizard

    result = run_block_create_wizard(
        block_id=id,
        display_name=display_name,
        preset_id=preset,
        profile_mode=profile_mode,  # type: ignore[arg-type]
        build_strategy=build_strategy,
        requirements_file=requirements_file,
        package_json_file=package_json_file,
        apt_file=apt_file,
        non_interactive=non_interactive,
        dry_run=dry_run,
        yes=yes,
        output=output,
        console=console,
    )
    if output_json:
        console.print_json(result.model_dump_json(indent=2))
        return
    if result.created:
        console.print(f"[green]Created block:[/green] {result.id}")
        if result.path:
            console.print(f"  Path: {result.path}")
        return
    if result.valid:
        console.print(f"[green]Block preview valid:[/green] {result.id}")
    else:
        console.print(f"[red]Block preview invalid:[/red] {result.id}")
        for err in result.errors:
            console.print(f"  - {err.get('field')}: {err.get('message')}")

# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------

@app.command()
@with_cli_errors(console)
def plan(
    profile: str = typer.Option(..., "--profile", "-p", help="Hardware profile ID"),
    stack: str = typer.Option(..., "--stack", "-s", help="Stack spec ID"),
    explain: bool = typer.Option(False, "--explain", help="Show detailed decision rationale"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Resolve a plan for the given profile + stack."""
    setup_cli(verbose=verbose)
    from stackwarden.config import compatibility_strict_default, load_block, load_profile, load_stack
    from stackwarden.resolvers.resolver import resolve

    p = load_profile(profile)
    s = load_stack(stack)
    blocks = [load_block(block_id) for block_id in (s.blocks or [])]
    result = resolve(
        p,
        s,
        blocks=blocks,
        explain=explain,
        strict_mode=compatibility_strict_default(),
    )
    if output_json:
        console.print_json(json.dumps(result.to_json(), indent=2))
        return

    console.print(Panel(f"[bold]Plan:[/bold] {result.plan_id}", title="StackWarden Plan"))
    console.print(f"  Profile: [cyan]{result.profile_id}[/cyan]")
    console.print(f"  Stack:   [cyan]{result.stack_id}[/cyan]")
    console.print(f"  Base:    {result.decision.base_image}")
    console.print(f"  Builder: {result.decision.builder}")
    console.print(f"  Tag:     [green]{result.artifact.tag}[/green]")
    console.print(f"  FP:      {result.artifact.fingerprint[:24]}...")

    if result.decision.warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for w in result.decision.warnings:
            console.print(f"  - {w}")

    console.print(f"\n[bold]Steps ({len(result.steps)}):[/bold]")
    for i, step in enumerate(result.steps, 1):
        desc = step.type
        if step.image:
            desc += f" {step.image}"
        if step.tags:
            desc += f" -> {step.tags[0]}"
        console.print(f"  {i}. {desc}")

    if result.decision.rationale:
        _print_rationale(result.decision.rationale)


# ---------------------------------------------------------------------------
# check / validate
# ---------------------------------------------------------------------------

@app.command("check")
@with_cli_errors(console)
def check_cmd(
    profile: str = typer.Option(..., "--profile", "-p", help="Hardware profile ID"),
    stack: str = typer.Option(..., "--stack", "-s", help="Stack spec ID"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
    strict: Optional[bool] = typer.Option(
        None,
        "--strict/--no-strict",
        help="Override strict compatibility. Default from STACKWARDEN_COMPAT_STRICT env.",
    ),
) -> None:
    """Validate compatibility for profile + stack without building."""
    setup_cli(verbose=verbose)
    from stackwarden.config import compatibility_strict_default, load_block, load_profile, load_stack
    from stackwarden.resolvers.compatibility import evaluate_compatibility

    strict_mode = compatibility_strict_default() if strict is None else strict

    p = load_profile(profile)
    s = load_stack(stack)
    blocks = [load_block(block_id) for block_id in (s.blocks or [])]
    report = evaluate_compatibility(p, s, blocks=blocks, strict_mode=strict_mode)
    if output_json:
        console.print_json(json.dumps(report.model_dump(mode="json"), indent=2))
    else:
        status = "[green]compatible[/green]" if report.compatible else "[red]incompatible[/red]"
        console.print(f"Compatibility status: {status}")
        for e in report.errors:
            console.print(f"  - [red]{e.code}[/red]: {e.message}")
        for w in report.warnings:
            console.print(f"  - [yellow]{w.code}[/yellow]: {w.message}")
        for i in report.info:
            console.print(f"  - [cyan]{i.code}[/cyan]: {i.message}")

    if not report.compatible:
        raise typer.Exit(2)


# ---------------------------------------------------------------------------
# ensure
# ---------------------------------------------------------------------------

@app.command()
def ensure(
    profile: str = typer.Option(..., "--profile", "-p", help="Hardware profile ID"),
    stack: str = typer.Option(..., "--stack", "-s", help="Stack spec ID"),
    rebuild: bool = typer.Option(False, "--rebuild", help="Force rebuild even if image exists"),
    upgrade_base: bool = typer.Option(False, "--upgrade-base", help="Force fresh base pull"),
    immutable: bool = typer.Option(
        False, "--immutable", help="Fail on drift instead of rebuilding (CI mode)"
    ),
    no_hooks: bool = typer.Option(False, "--no-hooks", help="Skip post-build validation hooks"),
    explain: bool = typer.Option(False, "--explain", help="Show detailed decision rationale"),
    var: Optional[list[str]] = _var_option,
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Ensure the image for profile + stack exists (build/pull if needed)."""
    setup_cli(verbose=verbose)
    from stackwarden.domain.ensure import ensure_internal
    from stackwarden.domain.variants import parse_variants

    variants = parse_variants(var)

    record = None
    result = None
    try:
        record, result = ensure_internal(
            profile, stack, variants,
            rebuild=rebuild,
            upgrade_base=upgrade_base,
            immutable=immutable,
            run_hooks=not no_hooks,
            explain=explain,
        )
    except Exception as exc:
        from stackwarden.domain.errors import BuildError
        from stackwarden.domain.compatibility_fix import (
            analyze_build_failure,
            apply_compatibility_fix,
        )

        if isinstance(exc, BuildError) and not output_json:
            base_image = None
            try:
                from stackwarden.config import compatibility_strict_default, load_block, load_profile, load_stack
                from stackwarden.resolvers.resolver import resolve
                p = load_profile(profile)
                s = load_stack(stack)
                blocks = [load_block(bid) for bid in (s.blocks or [])]
                plan = resolve(p, s, blocks=blocks, variants=variants, strict_mode=compatibility_strict_default())
                base_image = plan.decision.base_image
            except Exception:
                pass
            fix_result = analyze_build_failure(str(exc), base_image=base_image)
            if fix_result.applicable and fix_result.suggested_overrides:
                if typer.confirm(
                    f"\n[yellow]Compatibility fix available:[/yellow] {fix_result.message}\n"
                    "Apply fix and retry build?",
                    default=True,
                ):
                    apply_compatibility_fix(
                        fix_result.suggested_overrides,
                        base_image_contains=fix_result.base_image_hint,
                    )
                    console.print("[green]Fix applied.[/green] Retrying build...")
                    record, result = ensure_internal(
                        profile, stack, variants,
                        rebuild=True,
                        upgrade_base=upgrade_base,
                        immutable=immutable,
                        run_hooks=not no_hooks,
                        explain=explain,
                    )
                else:
                    console.print(f"[red]Error:[/red] {exc}")
                    raise typer.Exit(exit_code_for(exc))
            else:
                console.print(f"[red]Error:[/red] {exc}")
                raise typer.Exit(exit_code_for(exc))
        else:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(exit_code_for(exc))

    if explain and result.decision.rationale:
        _print_rationale(result.decision.rationale)

    if output_json:
        console.print_json(json.dumps(record.model_dump(mode="json"), indent=2, default=str))
        return

    console.print(f"[green]Image ready:[/green] {record.tag}")
    console.print(f"  Status: {record.status.value}")
    if record.image_id:
        console.print(f"  Image ID: {record.image_id[:19]}")
    if record.digest:
        console.print(f"  Digest: {record.digest}")


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------

@app.command()
@with_cli_errors(console)
def verify(
    tag_or_id: str = typer.Argument(help="Image tag, artifact fingerprint, or artifact ID"),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Treat missing snapshots as errors (default: warn only)",
    ),
    fix: bool = typer.Option(False, "--fix", help="Mark stale on mismatch (no rebuild)"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Verify that an artifact is valid and matches its recorded identity."""
    setup_cli(verbose=verbose)
    from stackwarden.domain.verify import verify_artifact, apply_fix
    from stackwarden.runtime.docker_client import DockerClient
    from stackwarden.catalog.store import CatalogStore

    docker = DockerClient()
    catalog = get_catalog()

    report = verify_artifact(tag_or_id, docker, catalog, strict=strict)

    if fix and not report.ok:
        actions = apply_fix(tag_or_id, report, catalog)
        for a in actions:
            console.print(f"[yellow]Fix:[/yellow] {a}")
    if output_json:
        console.print_json(report.model_dump_json(indent=2))
        if not report.ok:
            raise typer.Exit(2)
        return

    if report.ok:
        console.print("[green]PASS[/green] Artifact verified successfully")
    else:
        console.print("[red]FAIL[/red] Artifact verification failed")

    if report.facts:
        console.print("\n[bold]Facts:[/bold]")
        for k, v in report.facts.items():
            console.print(f"  {k}: {v}")

    if report.warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for w in report.warnings:
            console.print(f"  - {w}")

    if report.errors:
        console.print("\n[red]Errors:[/red]")
        for e in report.errors:
            console.print(f"  - {e}")
        raise typer.Exit(2)


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------

@app.command("inspect")
@with_cli_errors(console)
def inspect_cmd(
    tag: str = typer.Argument(help="Image tag to inspect"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Inspect a container image and show StackWarden metadata."""
    setup_cli(verbose=verbose)
    from stackwarden.runtime.docker_client import DockerClient
    from stackwarden.runtime.inspect import format_image_info
    from stackwarden.catalog.store import CatalogStore

    docker = DockerClient()
    attrs = docker.inspect_image(tag)

    catalog = get_catalog()
    cat_record = catalog.get_artifact_by_tag(tag)
    cat_dict = cat_record.model_dump(mode="json") if cat_record else None

    info = format_image_info(attrs, catalog_entry=cat_dict)

    if output_json:
        console.print_json(json.dumps(info, indent=2, default=str))
        return

    console.print(Panel(f"[bold]{tag}[/bold]", title="Image Inspect"))
    console.print(f"  ID:      {info['id']}")
    console.print(f"  Created: {info['created']}")
    console.print(f"  Size:    {info['size_mb']} MB")
    if info.get("stackwarden"):
        console.print("\n[bold]StackWarden Labels:[/bold]")
        for k, v in info["stackwarden"].items():
            console.print(f"  {k}: {v}")
    if cat_dict:
        console.print("\n[bold]Catalog:[/bold]")
        console.print(f"  Fingerprint: {cat_dict.get('fingerprint', 'N/A')}")
        console.print(f"  Status: {cat_dict.get('status', 'N/A')}")
        console.print(f"  Base: {cat_dict.get('base_image', 'N/A')}")

        components = catalog.get_components(cat_record.id) if cat_record else []
        if components:
            console.print("\n[bold]Components:[/bold]")
            for c in components:
                line = f"  [{c['type']}] {c['name']}"
                if c.get("version"):
                    line += f" {c['version']}"
                if c.get("license_spdx"):
                    line += f"  (license: {c['license_spdx']})"
                if c.get("license_severity"):
                    sev = c["license_severity"]
                    color = {"ok": "green", "review": "yellow", "restricted": "red"}.get(sev, "")
                    line += f" [{color}]{sev}[/{color}]" if color else f" {sev}"
                console.print(line)


@app.command("inspect-block")
@with_cli_errors(console)
def inspect_block_cmd(
    block_id: str = typer.Option(..., "--id", help="Block ID to inspect"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Inspect a block definition."""
    setup_cli(verbose=verbose)
    from stackwarden.config import load_block

    block = load_block(block_id)
    data = block.model_dump(mode="json", by_alias=True)
    if output_json:
        console.print_json(json.dumps(data, indent=2))
        return

    console.print(Panel(f"[bold]{block.id}[/bold]", title="Block Inspect"))
    console.print(f"  Display Name: {block.display_name}")
    if block.tags:
        console.print(f"  Tags:         {', '.join(block.tags)}")
    if block.components.base_role:
        console.print(f"  Base Role:    {block.components.base_role}")
    if block.components.pip:
        console.print(f"  Pip deps:     {len(block.components.pip)}")
    if block.components.apt:
        console.print(f"  Apt packages: {len(block.components.apt)}")
    if block.entrypoint:
        console.print(f"  Entrypoint:   {' '.join(block.entrypoint.cmd)}")


@app.command("compose")
@with_cli_errors(console)
def compose_cmd(
    stack: str = typer.Option(..., "--stack", "-s", help="Stack spec ID"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Render a resolved stack spec from block-recipe composition."""
    setup_cli(verbose=verbose)
    from stackwarden.config import load_stack

    resolved = load_stack(stack)
    data = resolved.model_dump(mode="json", by_alias=True)
    if output_json:
        console.print_json(json.dumps(data, indent=2))
        return

    console.print(Panel(f"[bold]{resolved.id}[/bold]", title="Composed Stack"))
    console.print(f"  Display Name: {resolved.display_name}")
    console.print(f"  Task/API:     {resolved.task.value} / {resolved.api.value}")
    console.print(f"  Serve:        {resolved.serve.value}")
    console.print(f"  Build:        {resolved.build_strategy.value}")
    console.print(f"  Base Role:    {resolved.components.base_role}")
    console.print(f"  Pip deps:     {len(resolved.components.pip)}")
    console.print(f"  Apt packages: {len(resolved.components.apt)}")


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------

@app.command("manifest")
@with_cli_errors(console)
def manifest_cmd(
    tag: str = typer.Argument(help="Image tag or artifact fingerprint"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Display the stored manifest for a built artifact."""
    setup_cli(verbose=verbose)
    from stackwarden.catalog.store import CatalogStore
    from stackwarden.domain.manifest import load_manifest

    catalog = get_catalog()
    record = (
        catalog.get_artifact_by_tag(tag)
        or catalog.get_artifact_by_fingerprint(tag)
        or catalog.get_artifact_by_id(tag)
    )

    if not record or not record.manifest_path:
        console.print("[red]No manifest found for this artifact.[/red]")
        raise typer.Exit(1)

    manifest = load_manifest(record.fingerprint)
    if output_json:
        console.print_json(manifest.model_dump_json(indent=2))
        return

    console.print(Panel(f"[bold]Manifest[/bold] {record.tag}", title="Resolved Manifest"))
    console.print(f"  Profile:   {manifest.profile_id}")
    console.print(f"  Stack:     {manifest.stack_id}")
    console.print(f"  Python:    {manifest.python_version}")
    console.print(f"  Base:      {manifest.base_image}")
    console.print(f"  Digest:    {manifest.base_digest or 'N/A'}")
    if manifest.pip_freeze:
        console.print(f"\n[bold]pip freeze ({len(manifest.pip_freeze)}):[/bold]")
        for p in manifest.pip_freeze[:20]:
            console.print(f"  {p}")
        if len(manifest.pip_freeze) > 20:
            console.print(f"  ... and {len(manifest.pip_freeze) - 20} more")
    if manifest.apt_packages:
        console.print(f"\n[bold]apt packages ({len(manifest.apt_packages)}):[/bold]")
        for p in manifest.apt_packages[:20]:
            console.print(f"  {p}")
        if len(manifest.apt_packages) > 20:
            console.print(f"  ... and {len(manifest.apt_packages) - 20} more")


# ---------------------------------------------------------------------------
# repro
# ---------------------------------------------------------------------------

@app.command("repro")
@with_cli_errors(console)
def repro_cmd(
    artifact_id: str = typer.Argument(help="Artifact ID or fingerprint to reproduce"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Reproduce a build from its stored manifest with pinned dependencies."""
    setup_cli(verbose=verbose)
    from stackwarden.config import compatibility_strict_default, load_profile, load_stack
    from stackwarden.resolvers.resolver import resolve
    from stackwarden.runtime.docker_client import DockerClient
    from stackwarden.catalog.store import CatalogStore
    from stackwarden.builders.plan_executor import execute_plan
    from stackwarden.domain.manifest import load_manifest
    from stackwarden.domain.repro import repro_stack_from_manifest

    catalog = get_catalog()
    record = (
        catalog.get_artifact_by_id(artifact_id)
        or catalog.get_artifact_by_fingerprint(artifact_id)
    )
    if not record or not record.manifest_path:
        console.print("[red]No manifest found for this artifact.[/red]")
        raise typer.Exit(1)

    manifest = load_manifest(record.fingerprint)
    p = load_profile(manifest.profile_id)
    original_stack = load_stack(manifest.stack_id)
    pinned_stack = repro_stack_from_manifest(manifest, original_stack)

    docker = DockerClient()
    variants = manifest.variant_overrides or {}
    result = resolve(
        p,
        pinned_stack,
        variants=variants,
        strict_mode=compatibility_strict_default(),
    )

    catalog.upsert_profile(p)
    catalog.upsert_stack(pinned_stack)

    new_record = execute_plan(result, p, pinned_stack, docker, catalog, rebuild=True)
    if output_json:
        console.print_json(json.dumps(new_record.model_dump(mode="json"), indent=2, default=str))
        return

    console.print(f"[green]Repro build complete:[/green] {new_record.tag}")
    console.print(f"  Original fingerprint: {record.fingerprint[:24]}...")
    console.print(f"  New fingerprint:      {new_record.fingerprint[:24]}...")
    console.print(f"  Status: {new_record.status.value}")


# ---------------------------------------------------------------------------
# catalog commands
# ---------------------------------------------------------------------------

@catalog_app.command("search")
def catalog_search(
    profile: Optional[str] = typer.Option(None, "--profile", "-p"),
    stack: Optional[str] = typer.Option(None, "--stack", "-s"),
    status: Optional[str] = typer.Option(None, "--status"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Search the artifact catalog."""
    setup_cli(verbose=verbose)
    from stackwarden.catalog.store import CatalogStore

    catalog = get_catalog()
    records = catalog.search_artifacts(profile_id=profile, stack_id=stack, status=status)

    if output_json:
        console.print_json(json.dumps(
            [r.model_dump(mode="json") for r in records], indent=2, default=str
        ))
        return

    if not records:
        console.print("[dim]No artifacts found.[/dim]")
        return

    table = Table(title="Catalog Artifacts")
    table.add_column("ID", style="cyan")
    table.add_column("Profile")
    table.add_column("Stack")
    table.add_column("Tag")
    table.add_column("Status")
    table.add_column("Created")
    for r in records:
        status_color = {
            "built": "green", "building": "yellow", "failed": "red", "stale": "dim"
        }.get(r.status.value, "")
        styled_status = f"[{status_color}]{r.status.value}[/{status_color}]" if status_color else r.status.value
        table.add_row(
            r.id or "",
            r.profile_id,
            r.stack_id,
            r.tag,
            styled_status,
            str(r.created_at)[:19] if r.created_at else "",
        )
    console.print(table)


@catalog_app.command("build")
def catalog_build(
    profile: str = typer.Option(..., "--profile", "-p", help="Hardware profile ID"),
    stack: str = typer.Option(..., "--stack", "-s", help="Stack spec ID"),
    rebuild: bool = typer.Option(False, "--rebuild", help="Force rebuild"),
    upgrade_base: bool = typer.Option(False, "--upgrade-base", help="Force fresh base pull"),
    immutable: bool = typer.Option(False, "--immutable", help="Fail on drift"),
    no_hooks: bool = typer.Option(False, "--no-hooks", help="Skip post-build hooks"),
    explain: bool = typer.Option(False, "--explain", help="Show rationale"),
    var: Optional[list[str]] = _var_option,
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Build from catalog surface (alias for ensure)."""
    _deprecated_alias_notice("stackwarden catalog build", "stackwarden ensure")
    ensure(
        profile=profile,
        stack=stack,
        rebuild=rebuild,
        upgrade_base=upgrade_base,
        immutable=immutable,
        no_hooks=no_hooks,
        explain=explain,
        var=var,
        verbose=verbose,
        output_json=output_json,
    )


@catalog_app.command("show")
def catalog_show(
    artifact_id: str = typer.Argument(help="Artifact ID to show"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Show details for a catalog artifact."""
    setup_cli(verbose=verbose)
    from stackwarden.catalog.store import CatalogStore

    catalog = get_catalog()
    record = catalog.get_artifact_by_id(artifact_id)

    if not record:
        console.print(f"[red]Artifact not found:[/red] {artifact_id}")
        raise typer.Exit(1)

    if output_json:
        data = record.model_dump(mode="json")
        data["components"] = catalog.get_components(artifact_id)
        console.print_json(json.dumps(data, indent=2, default=str))
        return

    console.print(Panel(f"[bold]Artifact {artifact_id}[/bold]", title="Catalog Entry"))
    console.print(f"  Profile: {record.profile_id}")
    console.print(f"  Stack: {record.stack_id}")
    console.print(f"  Tag: {record.tag}")
    console.print(f"  Fingerprint: {record.fingerprint}")
    console.print(f"  Base Image: {record.base_image}")
    console.print(f"  Base Digest: {record.base_digest or 'N/A'}")
    console.print(f"  Strategy: {record.build_strategy}")
    console.print(f"  Status: {record.status.value}")
    console.print(f"  Created: {record.created_at}")

    components = catalog.get_components(artifact_id)
    if components:
        console.print("\n[bold]Components:[/bold]")
        for c in components:
            console.print(f"  [{c['type']}] {c['name']} {c.get('version', '')}")


@catalog_app.command("stale")
def catalog_stale(
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """List stale artifacts."""
    setup_cli(verbose=verbose)
    from stackwarden.catalog.store import CatalogStore

    catalog = get_catalog()
    records = catalog.search_artifacts(status="stale")

    if output_json:
        console.print_json(json.dumps(
            [r.model_dump(mode="json") for r in records], indent=2, default=str
        ))
        return

    if not records:
        console.print("[dim]No stale artifacts.[/dim]")
        return

    table = Table(title="Stale Artifacts")
    table.add_column("ID", style="cyan")
    table.add_column("Profile")
    table.add_column("Stack")
    table.add_column("Tag")
    table.add_column("Reason")
    table.add_column("Created")
    for r in records:
        table.add_row(
            r.id or "",
            r.profile_id,
            r.stack_id,
            r.tag,
            r.stale_reason or "",
            str(r.created_at)[:19] if r.created_at else "",
        )
    console.print(table)


@catalog_app.command("prune")
def catalog_prune(
    verbose: bool = _verbose_option,
) -> None:
    """Remove failed and stale artifacts from the catalog."""
    setup_cli(verbose=verbose)
    from stackwarden.catalog.store import CatalogStore
    from stackwarden.domain.enums import ArtifactStatus

    catalog = get_catalog()
    failed = catalog.prune_by_status(ArtifactStatus.FAILED)
    stale = catalog.prune_by_status(ArtifactStatus.STALE)
    console.print(f"Pruned {failed} failed + {stale} stale artifacts.")


@catalog_app.command("disk-usage")
def catalog_disk_usage(
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Report disk usage per profile, stack, and artifact."""
    setup_cli(verbose=verbose)
    from stackwarden.catalog.store import CatalogStore
    from stackwarden.runtime.docker_client import DockerClient

    catalog = get_catalog()
    records = catalog.search_artifacts(status="built")

    try:
        docker = DockerClient()
    except Exception:
        docker = None

    profile_sizes: dict[str, float] = {}
    stack_sizes: dict[str, float] = {}
    rows: list[tuple[str, str, str, float]] = []
    inspect_failures = 0
    inspect_cache: dict[str, float] = {}

    for r in records:
        size_mb = 0.0
        if docker:
            if r.tag in inspect_cache:
                size_mb = inspect_cache[r.tag]
            else:
                try:
                    attrs = docker.inspect_image(r.tag)
                    size_mb = round(attrs.get("Size", 0) / 1_048_576, 1)
                    inspect_cache[r.tag] = size_mb
                except Exception as exc:
                    inspect_failures += 1
                    log.debug("disk-usage inspect failed for %s: %s", r.tag, exc)
        profile_sizes[r.profile_id] = profile_sizes.get(r.profile_id, 0) + size_mb
        stack_sizes[r.stack_id] = stack_sizes.get(r.stack_id, 0) + size_mb
        rows.append((r.id or "", r.tag, r.profile_id, size_mb))

    if output_json:
        console.print_json(json.dumps({
            "by_profile": profile_sizes,
            "by_stack": stack_sizes,
            "artifacts": [{"id": r[0], "tag": r[1], "profile": r[2], "size_mb": r[3]} for r in rows],
            "inspect_failures": inspect_failures,
        }, indent=2))
        return

    total = sum(r[3] for r in rows)
    console.print(Panel(f"[bold]Disk Usage[/bold]  Total: {total:.0f} MB", title="Catalog"))
    table = Table(title="By Profile")
    table.add_column("Profile", style="cyan")
    table.add_column("Size (MB)", justify="right")
    for pid, sz in sorted(profile_sizes.items()):
        table.add_row(pid, f"{sz:.0f}")
    console.print(table)

    table2 = Table(title="By Stack")
    table2.add_column("Stack", style="cyan")
    table2.add_column("Size (MB)", justify="right")
    for sid, sz in sorted(stack_sizes.items()):
        table2.add_row(sid, f"{sz:.0f}")
    console.print(table2)
    if inspect_failures:
        console.print(f"[yellow]WARN[/yellow] {inspect_failures} image inspect call(s) failed.")


# ---------------------------------------------------------------------------
# sbom
# ---------------------------------------------------------------------------

@app.command("sbom")
@with_cli_errors(console)
def sbom_cmd(
    tag: str = typer.Argument(help="Image tag to generate SBOM for"),
    fmt: str = typer.Option("spdx-json", "--format", "-f", help="SBOM format"),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Export an SBOM for a built artifact."""
    setup_cli(verbose=verbose)
    from stackwarden.catalog.store import CatalogStore
    from stackwarden.runtime.sbom import export_sbom

    catalog = get_catalog()
    record = catalog.get_artifact_by_tag(tag)
    if not record:
        console.print("[red]Artifact not found in catalog.[/red]")
        raise typer.Exit(1)

    path = export_sbom(tag, record.fingerprint, output_format=fmt)
    record.sbom_path = str(path)
    catalog.update_artifact(record)
    if output_json:
        console.print_json(json.dumps({"sbom_path": str(path), "tag": tag}))
        return

    console.print(f"[green]SBOM exported:[/green] {path}")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

@app.command()
def status(
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Show a summary of the artifact catalog."""
    setup_cli(verbose=verbose)

    catalog = get_catalog()
    all_records = catalog.search_artifacts()

    built = [r for r in all_records if r.status.value == "built"]
    stale = [r for r in all_records if r.status.value == "stale"]
    failed = [r for r in all_records if r.status.value == "failed"]
    building = [r for r in all_records if r.status.value == "building"]

    newest: dict[tuple[str, str], "ArtifactRecord"] = {}
    for r in built:
        key = (r.profile_id, r.stack_id)
        if key not in newest or (r.created_at and (newest[key].created_at is None or r.created_at > newest[key].created_at)):
            newest[key] = r

    if output_json:
        data = {
            "total": len(all_records),
            "built": len(built),
            "stale": len(stale),
            "failed": len(failed),
            "building": len(building),
            "newest": [
                {"profile": k[0], "stack": k[1], "tag": v.tag, "fingerprint": v.fingerprint[:16]}
                for k, v in sorted(newest.items())
            ],
        }
        console.print_json(json.dumps(data, indent=2, default=str))
        return

    console.print(Panel("[bold]StackWarden Status[/bold]"))
    console.print(f"  Total artifacts: {len(all_records)}")
    console.print(f"  [green]Built:[/green]    {len(built)}")
    console.print(f"  [dim]Stale:[/dim]    {len(stale)}")
    console.print(f"  [red]Failed:[/red]   {len(failed)}")
    if building:
        console.print(f"  [yellow]Building:[/yellow] {len(building)}")

    if newest:
        console.print(f"\n[bold]Newest per (profile, stack):[/bold]")
        table = Table()
        table.add_column("Profile", style="cyan")
        table.add_column("Stack", style="cyan")
        table.add_column("Tag")
        table.add_column("Fingerprint")
        for (pid, sid), rec in sorted(newest.items()):
            table.add_row(pid, sid, rec.tag, rec.fingerprint[:16] + "...")
        console.print(table)


# ---------------------------------------------------------------------------
# prune (top-level)
# ---------------------------------------------------------------------------

@app.command("prune")
def prune_cmd(
    stale: bool = typer.Option(False, "--stale", help="Prune stale artifacts"),
    failed: bool = typer.Option(False, "--failed", help="Prune failed artifacts"),
    all_unused: bool = typer.Option(False, "--all-unused", help="Prune all unused artifacts"),
    force: bool = typer.Option(
        False, "--force", help="Allow pruning newest stable artifacts"
    ),
    verbose: bool = _verbose_option,
    output_json: bool = _json_option,
) -> None:
    """Prune artifacts from the catalog and optionally remove images."""
    setup_cli(verbose=verbose)
    from stackwarden.catalog.store import CatalogStore
    from stackwarden.domain.enums import ArtifactStatus

    if not stale and not failed and not all_unused:
        stale = True
        failed = True

    catalog = get_catalog()
    pruned = 0
    image_remove_failures = 0

    try:
        docker: DockerClient | None = None
        from stackwarden.runtime.docker_client import DockerClient as DC
        docker = DC()
    except Exception as exc:
        log.debug("Docker unavailable during prune; proceeding without image deletes: %s", exc)

    if stale:
        records = catalog.search_artifacts(status="stale")
        for r in records:
            if docker:
                try:
                    docker.remove_image(r.tag)
                except Exception as exc:
                    image_remove_failures += 1
                    log.debug("Failed to remove stale image %s: %s", r.tag, exc)
        pruned += catalog.prune_by_status(ArtifactStatus.STALE)

    if failed:
        records = catalog.search_artifacts(status="failed")
        for r in records:
            if docker:
                try:
                    docker.remove_image(r.tag)
                except Exception as exc:
                    image_remove_failures += 1
                    log.debug("Failed to remove failed image %s: %s", r.tag, exc)
        pruned += catalog.prune_by_status(ArtifactStatus.FAILED)

    if all_unused:
        unused = catalog.find_unused(force=force)
        for r in unused:
            if docker:
                try:
                    docker.remove_image(r.tag)
                except Exception as exc:
                    image_remove_failures += 1
                    log.debug("Failed to remove unused image %s: %s", r.tag, exc)
            catalog.prune_artifact(r.id)
            pruned += 1
        if not force:
            protected = catalog.count_protected()
            if protected:
                console.print(
                    f"[dim]{protected} newest-stable artifact(s) protected. "
                    f"Use --force to include them.[/dim]"
                )

    result_data = {"pruned": pruned, "image_remove_failures": image_remove_failures}
    if output_json:
        console.print_json(json.dumps(result_data))
        return

    console.print(f"Pruned {pruned} artifact(s).")
    if image_remove_failures:
        console.print(f"[yellow]WARN[/yellow] {image_remove_failures} image delete(s) failed.")


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------

@app.command()
def doctor(
    verbose: bool = _verbose_option,
) -> None:
    """Run environment health checks."""
    setup_cli(verbose=verbose)
    checks_passed = 0
    checks_failed = 0

    def _ok(msg: str) -> None:
        nonlocal checks_passed
        checks_passed += 1
        console.print(f"  [green]OK[/green]  {msg}")

    def _fail(msg: str) -> None:
        nonlocal checks_failed
        checks_failed += 1
        console.print(f"  [red]FAIL[/red] {msg}")

    def _warn(msg: str) -> None:
        console.print(f"  [yellow]WARN[/yellow] {msg}")

    console.print(Panel("[bold]StackWarden Doctor[/bold]", subtitle=f"v{__version__}"))

    # 1. Docker daemon
    try:
        from stackwarden.runtime.docker_client import DockerClient
        docker = DockerClient()
        _ok("Docker daemon reachable")
    except Exception as exc:
        _fail(f"Docker daemon: {exc}")
        console.print("\n[red]Cannot proceed without Docker.[/red]")
        raise typer.Exit(1)

    # 2. Buildx
    from stackwarden.runtime.buildx import is_available
    bx_ok, bx_ver = is_available()
    if bx_ok:
        _ok(f"Buildx available: {bx_ver}")
    else:
        _fail(f"Buildx not available: {bx_ver}")

    # 3. nvidia-container-runtime
    if shutil.which("nvidia-container-runtime"):
        _ok("nvidia-container-runtime found")
    else:
        _warn("nvidia-container-runtime not found (needed for GPU profiles)")

    # 4. GPU visibility
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            gpus = [g.strip() for g in result.stdout.strip().split("\n") if g.strip()]
            _ok(f"GPU visible: {', '.join(gpus)}")
        else:
            _warn("nvidia-smi returned non-zero (no GPU visible)")
    except FileNotFoundError:
        _warn("nvidia-smi not found")
    except subprocess.TimeoutExpired:
        _warn("nvidia-smi timed out")

    # 5. Disk space (5GB threshold)
    try:
        info = docker.info()
        docker_root = info.get("DockerRootDir", "/var/lib/docker")
        usage = shutil.disk_usage(docker_root)
        free_gb = usage.free / (1024 ** 3)
        if free_gb > 5:
            _ok(f"Disk space: {free_gb:.1f} GB free on {docker_root}")
        else:
            _warn(f"Low disk space: {free_gb:.1f} GB free on {docker_root}")
    except Exception:
        _warn("Could not check disk space")

    # 6. NGC auth
    if os.environ.get("NGC_API_KEY"):
        _ok("NGC_API_KEY is set")
    else:
        _warn("NGC_API_KEY not set (needed for pulling NGC images)")

    # 7. Architecture consistency
    from stackwarden.config import list_profile_ids, load_profile
    from stackwarden.domain.enums import ContainerRuntime
    daemon_arch = docker.server_arch()
    arch_map = {"x86_64": "amd64", "aarch64": "arm64"}
    normalized_daemon = arch_map.get(daemon_arch, daemon_arch)
    for pid in list_profile_ids():
        try:
            p = load_profile(pid)
            if p.arch.value == normalized_daemon:
                _ok(f"Profile '{pid}' arch ({p.arch.value}) matches daemon ({normalized_daemon})")
            else:
                _warn(
                    f"Profile '{pid}' arch ({p.arch.value}) differs from daemon "
                    f"({normalized_daemon}) — cross-platform builds may be slow or fail"
                )
        except Exception as exc:
            _warn(f"Could not validate profile '{pid}' architecture: {exc}")

    # 8. Buildx builder active
    try:
        bx_ls = subprocess.run(
            ["docker", "buildx", "ls"],
            capture_output=True, text=True, timeout=10,
        )
        if bx_ls.returncode == 0 and "default" in bx_ls.stdout:
            _ok("Buildx default builder active")
        else:
            _warn("No active buildx builder found")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        _warn("Could not check buildx builders")

    # 9. Platform verification
    try:
        dinfo = docker.info()
        os_type = dinfo.get("OSType", "unknown")
        arch_info = dinfo.get("Architecture", "unknown")
        _ok(f"Platform: {os_type}/{arch_info}")
    except Exception:
        _warn("Could not verify platform from docker info")

    # 10. NVIDIA driver vs CUDA compatibility (gated)
    for pid in list_profile_ids():
        try:
            p = load_profile(pid)
            if p.container_runtime != ContainerRuntime.NVIDIA:
                continue
            drv_result = subprocess.run(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=10,
            )
            if drv_result.returncode != 0:
                continue
            driver_ver = drv_result.stdout.strip().split("\n")[0].strip()
            if driver_ver:
                cuda_desc = (
                    f"{p.cuda.major}.{p.cuda.minor}" if p.cuda else "unknown"
                )
                _ok(
                    f"Profile '{pid}': NVIDIA driver {driver_ver} "
                    f"(CUDA {cuda_desc})"
                )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        except Exception:
            pass

    # Summary
    console.print()
    if checks_failed:
        console.print(f"[red]{checks_failed} check(s) failed[/red], {checks_passed} passed.")
    else:
        console.print(f"[green]All {checks_passed} checks passed.[/green]")


@migrate_app.command("v1-to-v2")
def migrate_v1_to_v2(
    write: bool = typer.Option(False, "--write", help="Write changes in-place."),
    verbose: bool = _verbose_option,
) -> None:
    """Migrate profile/block/stack specs from schema_version=1 to =2."""
    setup_cli(verbose=verbose)
    from stackwarden.config import get_blocks_dir, get_profiles_dir, get_stacks_dir
    from stackwarden.domain.hardware_catalog import load_hardware_catalog

    import yaml

    converted = 0
    inspected = 0
    unresolved = 0
    catalog = load_hardware_catalog()
    targets = [get_profiles_dir(), get_blocks_dir(), get_stacks_dir()]
    for folder in targets:
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.yaml")):
            inspected += 1
            with open(path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            if not isinstance(data, dict):
                continue
            if int(data.get("schema_version", 1)) >= 2:
                continue

            if folder == get_profiles_dir():
                data["schema_version"] = 2
                data.pop("base_candidates", None)
                if "cuda" not in data:
                    data["cuda"] = None
                data.setdefault("host_facts", {})
                data.setdefault("capability_ranges", [])
                data.setdefault("labels", {})
                data.setdefault("tags", [])
                os_family = str(data.get("os_family") or data.get("os") or "").lower()
                os_version = str(data.get("os_version") or "").lower()
                gpu = data.get("gpu", {}) or {}
                gpu_vendor = str(gpu.get("vendor") or "").lower()
                gpu_family = str(gpu.get("family") or "").lower()
                os_family_id, _ = catalog.resolve("os_family", os_family)
                gpu_vendor_id, _ = catalog.resolve("gpu_vendor", gpu_vendor)
                gpu_family_id, _ = catalog.resolve("gpu_family", gpu_family)
                os_version_id, _ = catalog.resolve("os_version", os_version)
                if os_family and not os_family_id:
                    unresolved += 1
                if gpu_vendor and not gpu_vendor_id:
                    unresolved += 1
                if gpu_family and not gpu_family_id:
                    unresolved += 1
                if os_version and not os_version_id:
                    unresolved += 1
                if os_family_id:
                    data["os_family_id"] = os_family_id
                if os_version_id:
                    data["os_version_id"] = os_version_id
                if isinstance(gpu, dict):
                    if gpu_vendor_id:
                        gpu["vendor_id"] = gpu_vendor_id
                    if gpu_family_id:
                        gpu["family_id"] = gpu_family_id
                    data["gpu"] = gpu
            elif folder == get_blocks_dir():
                data["schema_version"] = 2
                data.setdefault("requires", {})
                data.setdefault("conflicts", [])
                data.setdefault("incompatible_with", [])
                data.setdefault("provides", {})
            else:
                data["schema_version"] = 2
                data.setdefault("blocks", [])
                data.setdefault("policy_overrides", {})

            converted += 1
            if write:
                atomic_write_spec(data, path)
                console.print(f"[green]migrated[/green] {path}")
            else:
                console.print(f"[yellow]would migrate[/yellow] {path}")

    mode = "written" if write else "preview"
    console.print(
        f"[cyan]Migration {mode} complete:[/cyan] inspected={inspected} converted={converted} unresolved={unresolved}"
    )


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

@app.command()
def init(
    verbose: bool = _verbose_option,
) -> None:
    """Initialize StackWarden directories and default configuration."""
    setup_cli(verbose=verbose)
    from stackwarden.paths import (
        get_artifacts_root,
        get_config_root,
        get_data_root,
        get_locks_root,
        get_logs_root,
        get_config_path,
    )
    from stackwarden.config import AppConfig

    dirs = [
        ("config", get_config_root()),
        ("data", get_data_root()),
        ("artifacts", get_artifacts_root()),
        ("logs", get_logs_root()),
        ("locks", get_locks_root()),
    ]

    for label, d in dirs:
        if d.exists():
            console.print(f"  [dim]exists[/dim]  {d}")
        else:
            d.mkdir(parents=True, exist_ok=True)
            console.print(f"  [green]created[/green] {d}")

    config_path = get_config_path()
    if config_path.exists():
        console.print(f"  [dim]exists[/dim]  {config_path}")
    else:
        _DEFAULT_CONFIG = (
            "# StackWarden configuration\n"
            "# See: stackwarden doctor\n"
            "\n"
            "# default_profile: x86_cuda\n"
            "# catalog_path: null\n"
            "# log_dir: null\n"
            "\n"
            "registry:\n"
            "  allow:\n"
            '    - "nvcr.io"\n'
            '    - "docker.io"\n'
            "  deny: []\n"
            "\n"
            "remote_catalog:\n"
            "  enabled: false\n"
            "  repo_url: null\n"
            '  branch: "main"\n'
            '  local_path: "~/.local/share/stackwarden/remote-catalog"\n'
            '  local_overrides_path: "~/.local/share/stackwarden/local-catalog"\n'
            "  auto_pull: true\n"
        )
        config_path.write_text(_DEFAULT_CONFIG)
        console.print(f"  [green]created[/green] {config_path}")

    cfg = AppConfig.load()
    console.print(f"\n[green]StackWarden initialized.[/green]")
    if cfg.default_profile:
        console.print(f"  Default profile: {cfg.default_profile}")
    console.print(f"\nRun [cyan]stackwarden doctor[/cyan] to verify your environment.")


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

@export_app.command("run")
def export_run(
    tag: str = typer.Argument(help="Image tag to export run command for"),
    gpus: Optional[str] = typer.Option(
        None,
        "--gpus",
        help="GPU allocation for docker run (defaults to 'all' for NVIDIA runtime).",
    ),
    verbose: bool = _verbose_option,
) -> None:
    """Print a docker run command for the given artifact."""
    setup_cli(verbose=verbose)

    catalog = get_catalog()
    record = catalog.get_artifact_by_tag(tag)
    if not record:
        console.print(f"[red]Artifact not found:[/red] {tag}")
        raise typer.Exit(1)

    runtime, ports = _artifact_runtime_and_ports(record)
    effective_gpus = gpus if gpus is not None else ("all" if runtime == "nvidia" else None)

    parts = ["docker", "run", "--rm", "-it"]
    if effective_gpus:
        if runtime and runtime != "nvidia":
            console.print(
                f"[yellow]WARN[/yellow] profile runtime is '{runtime}'; ignoring --gpus for export."
            )
        else:
            parts += ["--gpus", effective_gpus]

    for port in ports:
        parts += ["-p", f"{port}:{port}"]

    parts.append(tag)
    console.print(" ".join(parts))


@export_app.command("compose")
def export_compose(
    tag: str = typer.Argument(help="Image tag to export compose for"),
    gpus: Optional[str] = typer.Option(
        None,
        "--gpus",
        help="GPU allocation (defaults to 'all' for NVIDIA runtime).",
    ),
    verbose: bool = _verbose_option,
) -> None:
    """Print a docker-compose.yaml snippet for the given artifact."""
    setup_cli(verbose=verbose)
    import yaml

    catalog = get_catalog()
    record = catalog.get_artifact_by_tag(tag)
    if not record:
        console.print(f"[red]Artifact not found:[/red] {tag}")
        raise typer.Exit(1)

    runtime, ports = _artifact_runtime_and_ports(record)
    effective_gpus = gpus if gpus is not None else ("all" if runtime == "nvidia" else None)

    service_name = record.stack_id.replace("_", "-")
    service: dict = {
        "image": tag,
    }
    if runtime == "nvidia":
        service["runtime"] = "nvidia"

    if effective_gpus:
        if runtime and runtime != "nvidia":
            console.print(
                f"[yellow]WARN[/yellow] profile runtime is '{runtime}'; omitting GPU compose reservations."
            )
        else:
            service["deploy"] = {
                "resources": {
                    "reservations": {
                        "devices": [
                            {"driver": "nvidia", "count": effective_gpus, "capabilities": ["gpu"]}
                        ]
                    }
                }
            }
    if ports:
        service["ports"] = [f"{p}:{p}" for p in ports]

    compose = {
        "services": {service_name: service},
    }
    console.print(yaml.dump(compose, default_flow_style=False, sort_keys=False))


# ---------------------------------------------------------------------------
# wizard
# ---------------------------------------------------------------------------


@app.command()
def wizard(
    run: bool = typer.Option(False, "--run", help="Execute the plan after preview"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Hardware profile ID"),
    stack: Optional[str] = typer.Option(None, "--stack", "-s", help="Stack spec ID"),
    var: Optional[list[str]] = _var_option,
    defaults: bool = typer.Option(False, "--defaults", help="Accept all defaults without prompting"),
    immutable: bool = typer.Option(False, "--immutable", help="Fail on drift instead of rebuilding"),
    upgrade_base: bool = typer.Option(False, "--upgrade-base", help="Force fresh base pull"),
    no_hooks: bool = typer.Option(False, "--no-hooks", help="Skip post-build validation hooks"),
    rebuild: bool = typer.Option(False, "--rebuild", help="Force rebuild even if image exists"),
    explain: bool = typer.Option(False, "--explain", help="Show detailed decision rationale"),
    verify_after: bool = typer.Option(False, "--verify-after", help="Run verify after successful build"),
    output_json: bool = _json_option,
    verbose: bool = _verbose_option,
) -> None:
    """Interactive wizard to select profile, stack, and variants."""
    setup_cli(verbose=verbose)
    from stackwarden.config import AppConfig
    from stackwarden.domain.variants import parse_variants
    from stackwarden.ui.wizard import (
        WizardFlags,
        run_wizard,
        render_plan_human,
    )

    cfg = AppConfig.load()
    wiz_flags = WizardFlags(
        immutable=immutable,
        upgrade_base=upgrade_base,
        no_hooks=no_hooks,
        rebuild=rebuild,
        explain=explain,
    )
    var_overrides = parse_variants(var) if var else None

    try:
        result = run_wizard(
            profile_id=profile,
            stack_id=stack,
            var_overrides=var_overrides,
            defaults=defaults,
            flags=wiz_flags,
            default_profile=cfg.default_profile,
            console=console,
        )
    except (KeyboardInterrupt, SystemExit) as exc:
        code = getattr(exc, "code", 1) or 1
        raise typer.Exit(int(code))
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(exit_code_for(exc))

    if output_json and not run:
        console.print_json(result.model_dump_json(indent=2))
        return

    if not output_json:
        from stackwarden.resolvers.resolver import resolve
        from stackwarden.config import compatibility_strict_default, load_profile, load_stack

        p = load_profile(result.selection.profile_id)
        s = load_stack(result.selection.stack_id)
        plan = resolve(
            p, s,
            variants=result.selection.variants or None,
            explain=explain,
            strict_mode=compatibility_strict_default(),
        )
        render_plan_human(plan, console=console)

        if explain and plan.decision.rationale:
            _print_rationale(plan.decision.rationale)

        console.print(f"\n[bold]Command:[/bold]\n  {result.command}")

    should_run = run
    if not run and not output_json:
        from rich.prompt import Confirm
        should_run = Confirm.ask("\nRun now?", default=False)

    if should_run:
        from stackwarden.domain.ensure import ensure_internal

        try:
            sel = result.selection
            record, plan = ensure_internal(
                sel.profile_id,
                sel.stack_id,
                sel.variants or None,
                rebuild=sel.flags.rebuild,
                upgrade_base=sel.flags.upgrade_base,
                immutable=sel.flags.immutable,
                run_hooks=not sel.flags.no_hooks,
                explain=sel.flags.explain,
            )
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(exit_code_for(exc))

        result.executed = True
        result.tag = record.tag

        if output_json:
            console.print_json(result.model_dump_json(indent=2))
        else:
            console.print(f"\n[green]Image ready:[/green] {record.tag}")
            console.print(f"  Status: {record.status.value}")
            if record.image_id:
                console.print(f"  Image ID: {record.image_id[:19]}")
            if record.digest:
                console.print(f"  Digest: {record.digest}")

        if verify_after:
            try:
                from stackwarden.domain.verify import verify_artifact
                from stackwarden.runtime.docker_client import DockerClient

                docker = DockerClient()
                catalog = get_catalog()
                report = verify_artifact(record.tag, docker, catalog)
                if report.ok:
                    console.print("[green]PASS[/green] Post-build verification succeeded")
                else:
                    console.print("[red]FAIL[/red] Post-build verification failed")
                    for e in report.errors:
                        console.print(f"  - {e}")
            except Exception as exc:
                console.print(f"[yellow]Verify warning:[/yellow] {exc}")

        return

    if not output_json:
        console.print("\n[dim]No action taken. Copy the command above to run later.[/dim]")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _print_rationale(rationale) -> None:
    """Render a DecisionRationale to the console."""
    print_rationale(console, rationale)


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------

@app.command("help")
def help_cmd(
    topic: Optional[str] = typer.Argument(
        None,
        help="Topic: quickstart, env, troubleshooting, or a command name (e.g. ensure, plan)",
    ),
) -> None:
    """Show extended help, examples, environment variables, and links to documentation."""
    content = get_help_for_topic(topic)
    if content is not None:
        console.print(Panel(content.strip(), title="StackWarden Help", border_style="cyan"))
        return
    # Topic may be a command name; try to show its help
    if topic:
        from typer.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(app, [topic, "--help"])
        if result.exit_code == 0:
            console.print(result.output)
            return
        console.print(
            f"[yellow]Unknown topic or command:[/yellow] {topic}\n"
            "Try: stackwarden help quickstart | env | troubleshooting"
        )
    else:
        console.print(Panel(get_help_for_topic(None) or HELP_EPILOG, title="StackWarden Help", border_style="cyan"))


@app.command()
def version() -> None:
    """Show StackWarden version."""
    console.print(f"stackwarden {__version__}")


if __name__ == "__main__":
    app()
