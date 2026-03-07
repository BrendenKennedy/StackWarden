"""Low-risk command registration helpers."""

from __future__ import annotations


def command_map() -> dict[str, tuple[str, ...]]:
    return {
        "listing": ("list_profiles", "list_stacks", "list_layers"),
        "entity_read": (
            "profiles_list_cmd",
            "profiles_show_cmd",
            "stacks_list_cmd",
            "stacks_show_cmd",
            "layers_list_cmd",
            "layers_show_cmd",
        ),
        "export": ("export_run", "export_compose"),
        "version": ("version",),
    }
