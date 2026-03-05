"""Shared helpers for list commands."""

from __future__ import annotations

import json
from typing import Callable, TypeVar

from rich.console import Console
from rich.table import Table

T = TypeVar("T")


def format_source_label(origin: dict) -> str:
    """Format origin dict to a display string (e.g. 'local' or 'remote (owner)')."""
    source = str(origin.get("source") or "local")
    owner = str(origin.get("source_repo_owner") or "").strip()
    return f"{source} ({owner})" if source == "remote" and owner else source


def render_entity_list(
    console: Console,
    ids: list[str],
    load_fn: Callable[[str], T],
    origin_map: dict[str, dict],
    output_json: bool,
    to_json_item: Callable[[T, dict], dict],
    table_title: str,
    columns: list[tuple[str, str | None, Callable[[T, dict], str]]],
) -> None:
    """
    Render a list of entities as JSON or a Rich table.

    Args:
        console: Rich console for output
        ids: Entity IDs to list
        load_fn: Function to load entity by ID
        origin_map: Map of id -> origin dict
        output_json: If True, output JSON; else output table
        to_json_item: (entity, origin) -> dict for JSON output
        table_title: Table title
        columns: List of (header, style, get_cell) where get_cell(entity, origin) -> str
    """
    if output_json:
        items = [to_json_item(load_fn(i), origin_map.get(i) or {}) for i in ids]
        console.print_json(json.dumps(items))
        return

    table = Table(title=table_title)
    for header, style, _ in columns:
        table.add_column(header, style=style or "")
    for eid in ids:
        entity = load_fn(eid)
        origin = origin_map.get(eid) or {}
        row = [get_cell(entity, origin) for _, _, get_cell in columns]
        table.add_row(*row)
    console.print(table)
