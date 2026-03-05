"""List subcommand implementations (profiles, stacks, blocks)."""

from __future__ import annotations

from typing import Callable

import typer

from stackwarden.cli_shared.list_helpers import format_source_label, render_entity_list


def register_list_commands(
    list_app: typer.Typer,
    *,
    verbose_option: typer.Option,
    json_option: typer.Option,
    setup_fn: Callable[[bool], None],
    console,
) -> tuple[Callable[..., None], Callable[..., None], Callable[..., None]]:
    """Register list profiles, stacks, blocks. Returns (list_profiles, list_stacks, list_blocks)."""

    @list_app.command("profiles")
    def list_profiles(
        verbose: bool = verbose_option,
        output_json: bool = json_option,
    ) -> None:
        """List available hardware profiles."""
        setup_fn(verbose)
        from stackwarden.config import get_profile_origins, list_profile_ids, load_profile

        ids = list_profile_ids()
        origin_map = get_profile_origins(ids)

        def to_json(p, o):
            return {
                "id": p.id,
                "display_name": p.display_name,
                "arch": p.arch.value,
                "source": o.get("source"),
                "source_path": o.get("source_path"),
                "source_repo_url": o.get("source_repo_url"),
                "source_repo_owner": o.get("source_repo_owner"),
            }

        columns = [
            ("ID", "cyan", lambda p, o: p.id),
            ("Display Name", None, lambda p, o: p.display_name),
            ("Source", None, lambda p, o: format_source_label(o)),
            ("Arch", None, lambda p, o: p.arch.value),
        ]
        render_entity_list(
            console, ids, load_profile, origin_map,
            output_json, to_json, "Hardware Profiles", columns,
        )

    @list_app.command("stacks")
    def list_stacks(
        verbose: bool = verbose_option,
        output_json: bool = json_option,
    ) -> None:
        """List available stack specs."""
        setup_fn(verbose)
        from stackwarden.config import get_stack_origins, list_stack_ids, load_stack

        ids = list_stack_ids()
        origin_map = get_stack_origins(ids)

        def to_json(s, o):
            return {
                "id": s.id,
                "display_name": s.display_name,
                "blocks": list(getattr(s, "blocks", []) or []),
                "source": o.get("source"),
                "source_path": o.get("source_path"),
                "source_repo_url": o.get("source_repo_url"),
                "source_repo_owner": o.get("source_repo_owner"),
            }

        columns = [
            ("ID", "cyan", lambda s, o: s.id),
            ("Display Name", None, lambda s, o: s.display_name),
            ("Source", None, lambda s, o: format_source_label(o)),
            ("Blocks", None, lambda s, o: str(len(getattr(s, "blocks", []) or []))),
        ]
        render_entity_list(
            console, ids, load_stack, origin_map,
            output_json, to_json, "Stack Specs", columns,
        )

    @list_app.command("blocks")
    def list_blocks(
        verbose: bool = verbose_option,
        output_json: bool = json_option,
    ) -> None:
        """List available stack blocks."""
        setup_fn(verbose)
        from stackwarden.config import get_block_origins, list_block_ids, load_block

        ids = list_block_ids()
        origin_map = get_block_origins(ids)

        def to_json(b, o):
            return {
                "id": b.id,
                "display_name": b.display_name,
                "tags": b.tags,
                "source": o.get("source"),
                "source_path": o.get("source_path"),
                "source_repo_url": o.get("source_repo_url"),
                "source_repo_owner": o.get("source_repo_owner"),
            }

        columns = [
            ("ID", "cyan", lambda b, o: b.id),
            ("Display Name", None, lambda b, o: b.display_name),
            ("Source", None, lambda b, o: format_source_label(o)),
            ("Tags", None, lambda b, o: ", ".join(b.tags)),
        ]
        render_entity_list(
            console, ids, load_block, origin_map,
            output_json, to_json, "Stack Blocks", columns,
        )

    return list_profiles, list_stacks, list_blocks
