"""List subcommand implementations (profiles, stacks, layers)."""

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
    """Register list profiles, stacks, layers. Returns list command callables."""

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
                "layers": list(getattr(s, "layers", []) or []),
                "source": o.get("source"),
                "source_path": o.get("source_path"),
                "source_repo_url": o.get("source_repo_url"),
                "source_repo_owner": o.get("source_repo_owner"),
            }

        columns = [
            ("ID", "cyan", lambda s, o: s.id),
            ("Display Name", None, lambda s, o: s.display_name),
            ("Source", None, lambda s, o: format_source_label(o)),
            ("Layers", None, lambda s, o: str(len(getattr(s, "layers", []) or []))),
        ]
        render_entity_list(
            console, ids, load_stack, origin_map,
            output_json, to_json, "Stack Specs", columns,
        )

    @list_app.command("layers")
    def list_layers(
        verbose: bool = verbose_option,
        output_json: bool = json_option,
    ) -> None:
        """List available stack layers."""
        setup_fn(verbose)
        from stackwarden.config import get_layer_origins, list_layer_ids, load_layer

        ids = list_layer_ids()
        origin_map = get_layer_origins(ids)

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
            console, ids, load_layer, origin_map,
            output_json, to_json, "Stack Layers", columns,
        )

    return list_profiles, list_stacks, list_layers
