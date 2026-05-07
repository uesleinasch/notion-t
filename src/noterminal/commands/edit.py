"""`edit` command — open an existing note in $EDITOR and save changes."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Protocol

from .. import markdown as md
from ..notion_api import NotionAPI, NotionError, PageRef
from . import new as new_cmd
from . import open as open_cmd


class _Console(Protocol):
    def print(self, *args, **kwargs) -> None: ...


def run(
    *,
    api: NotionAPI,
    arg: str,
    last_listing: list[PageRef],
    editor_command: str,
    console: _Console,
) -> bool:
    """Returns True if the page was updated, False otherwise."""
    page_id = open_cmd._resolve(arg, last_listing)
    if page_id is None:
        console.print(
            f"[red]não consegui resolver[/red] '{arg}' — passe um índice de "
            f"`list`, um id curto, ou o id completo."
        )
        return False

    matched = next((r for r in last_listing if r.id == page_id), None)
    title = matched.title if matched else None
    try:
        if not title:
            title, _ = api.get_page_metadata(page_id)
        blocks = api.get_page_blocks(page_id)
    except NotionError as e:
        console.print(f"[red]erro ao carregar nota:[/red] {e}")
        return False

    body = md.from_blocks(blocks)
    initial = f"# {title}\n\n{body}\n" if body.strip() else f"# {title}\n\n"

    fd, raw_path = tempfile.mkstemp(prefix="notion-t-edit-", suffix=".md")
    os.close(fd)
    path = Path(raw_path)
    try:
        path.write_text(initial, encoding="utf-8")
        new_cmd.open_editor(path, editor_command)
        text = path.read_text(encoding="utf-8")
        if not text.strip() or text == initial:
            console.print("[yellow]edição cancelada (sem mudanças).[/yellow]")
            return False

        new_title, new_body = md.split_title(text)
        if not new_title:
            console.print("[yellow]edição abortada (sem título na primeira linha).[/yellow]")
            return False

        new_blocks = md.to_blocks(new_body)
        try:
            api.update_page(page_id=page_id, title=new_title, blocks=new_blocks)
        except NotionError as e:
            console.print(f"[red]falha ao atualizar nota:[/red] {e}")
            console.print(f"[yellow]conteúdo preservado em:[/yellow] {path}")
            return False

        console.print(f'[green]✓[/green] "{new_title}" atualizado')
        path.unlink(missing_ok=True)
        return True
    except Exception:
        console.print(f"[yellow]conteúdo preservado em:[/yellow] {path}")
        raise
