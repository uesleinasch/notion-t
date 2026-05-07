"""`new` command — open an editor, send the resulting note to Notion."""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

from .. import markdown as md
from ..notion_api import NotionAPI, NotionError


TEMPLATE = """# Título da nota aqui

Conteúdo em markdown...
"""


class _Console(Protocol):
    def print(self, *args, **kwargs) -> None: ...


def _resolve_editor(editor_command: str) -> list[str]:
    if editor_command.strip():
        return shlex.split(editor_command)
    env = os.environ.get("EDITOR", "").strip()
    if env:
        return shlex.split(env)
    for candidate in ("nano", "vi"):
        if shutil.which(candidate):
            return [candidate]
    raise RuntimeError("nenhum editor encontrado — defina $EDITOR ou config.editor.command")


def open_editor(path: Path, editor_command: str) -> None:
    cmd = _resolve_editor(editor_command) + [str(path)]
    subprocess.run(cmd, check=False)


def run(*, api: NotionAPI, database_id: str, editor_command: str, console: _Console) -> bool:
    """Returns True if a page was created, False otherwise."""
    fd, raw_path = tempfile.mkstemp(prefix="notion-t-", suffix=".md")
    os.close(fd)
    path = Path(raw_path)
    try:
        path.write_text(TEMPLATE, encoding="utf-8")
        open_editor(path, editor_command)
        text = path.read_text(encoding="utf-8")
        if not text.strip() or text == TEMPLATE:
            console.print("[yellow]nota descartada (sem conteúdo).[/yellow]")
            return False

        title, body = md.split_title(text)
        if not title:
            console.print("[yellow]nota descartada (sem título na primeira linha).[/yellow]")
            return False

        blocks = md.to_blocks(body)
        try:
            created = api.create_page(database_id=database_id, title=title, blocks=blocks)
        except NotionError as e:
            console.print(f"[red]falha ao enviar para o Notion:[/red] {e}")
            console.print(
                f"[yellow]conteúdo preservado em:[/yellow] {path}"
            )
            # don't unlink — let the user recover
            return False

        console.print(f'[green]✓[/green] "{title}" criado [dim]({created.url})[/dim]')
        path.unlink(missing_ok=True)
        return True
    except Exception:
        console.print(f"[yellow]conteúdo preservado em:[/yellow] {path}")
        raise
