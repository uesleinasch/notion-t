"""`list` command — show the N most recent pages in the configured database."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from rich.table import Table

from ..notion_api import NotionAPI, PageRef


class _Console(Protocol):
    def print(self, *args, **kwargs) -> None: ...


def _humanize(iso: str) -> str:
    if not iso:
        return ""
    try:
        when = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    now = datetime.now(timezone.utc)
    delta = now - when
    secs = int(delta.total_seconds())
    if secs < 60:
        return "agora"
    if secs < 3600:
        return f"há {secs // 60}min"
    if secs < 86400:
        return f"há {secs // 3600}h"
    if secs < 7 * 86400:
        return f"há {secs // 86400}d"
    return when.strftime("%d %b").lower()


def run(*, api: NotionAPI, database_id: str, page_size: int, console: _Console) -> list[PageRef]:
    refs = api.list_recent_pages(database_id=database_id, page_size=page_size)
    if not refs:
        console.print("[dim]nenhuma nota ainda — use `new` para criar a primeira.[/dim]")
        return refs

    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("#", style="dim", width=3)
    table.add_column("Título")
    table.add_column("Criado", style="dim")
    for i, r in enumerate(refs, start=1):
        table.add_row(str(i), r.title, _humanize(r.created_time))
    console.print(table)
    return refs
