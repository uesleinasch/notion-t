"""`search` command — Notion search filtered by configured database."""
from __future__ import annotations

from typing import Protocol

from rich.table import Table

from ..notion_api import NotionAPI, PageRef


class _Console(Protocol):
    def print(self, *args, **kwargs) -> None: ...


def run(*, api: NotionAPI, database_id: str, query: str, console: _Console) -> list[PageRef]:
    refs = api.search_in_database(database_id=database_id, query=query)
    if not refs:
        console.print("[dim]sem resultados.[/dim]")
        return refs
    from .list import _humanize  # reuse the same time formatter
    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("#", style="dim", width=3)
    table.add_column("Título")
    table.add_column("Criado", style="dim")
    for i, r in enumerate(refs, start=1):
        table.add_row(str(i), r.title, _humanize(r.created_time))
    console.print(table)
    return refs
