"""`delete` command — archive a note (Notion's recoverable delete)."""
from __future__ import annotations

from typing import Callable, Protocol

from ..notion_api import NotionAPI, NotionError, PageRef
from . import open as open_cmd


class _Console(Protocol):
    def print(self, *args, **kwargs) -> None: ...


def _default_confirm(prompt: str) -> str:
    return input(prompt)


def run(
    *,
    api: NotionAPI,
    arg: str,
    last_listing: list[PageRef],
    console: _Console,
    confirm: Callable[[str], str] = _default_confirm,
) -> str | None:
    """Returns the deleted page id on success, None otherwise."""
    page_id = open_cmd._resolve(arg, last_listing)
    if page_id is None:
        console.print(
            f"[red]não consegui resolver[/red] '{arg}' — passe um índice de "
            f"`list`, um id curto, ou o id completo."
        )
        return None

    matched = next((r for r in last_listing if r.id == page_id), None)
    label = matched.title if matched else page_id[:8]

    try:
        answer = confirm(f'deletar "{label}"? [y/N] ').strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[dim]cancelado.[/dim]")
        return None

    if answer not in ("y", "yes", "s", "sim"):
        console.print("[dim]cancelado.[/dim]")
        return None

    try:
        api.delete_page(page_id)
    except NotionError as e:
        console.print(f"[red]falha ao deletar:[/red] {e}")
        return None

    console.print(f'[green]✓[/green] "{label}" deletado (recuperável na lixeira do Notion)')
    return page_id
