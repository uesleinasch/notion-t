"""`open` command — render a note's content to the terminal."""
from __future__ import annotations

import re
from typing import Protocol

from rich.markdown import Markdown
from rich.rule import Rule

from .. import markdown as md
from ..notion_api import NotionAPI, NotionError, PageRef


class _Console(Protocol):
    def print(self, *args, **kwargs) -> None: ...


_FULL_ID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_HEX32 = re.compile(r"^[0-9a-fA-F]{32}$")
_SHORT = re.compile(r"^[0-9a-fA-F]{4,16}$")


def _resolve(arg: str, last_listing: list[PageRef]) -> str | None:
    arg = arg.strip()
    if arg.isdigit():
        idx = int(arg) - 1
        if 0 <= idx < len(last_listing):
            return last_listing[idx].id
        return None
    if _FULL_ID.match(arg):
        return arg
    if _HEX32.match(arg):
        return f"{arg[0:8]}-{arg[8:12]}-{arg[12:16]}-{arg[16:20]}-{arg[20:32]}"
    if _SHORT.match(arg):
        for ref in last_listing:
            if ref.id.replace("-", "").lower().startswith(arg.lower()):
                return ref.id
    return None


def run(*, api: NotionAPI, arg: str, last_listing: list[PageRef], console: _Console) -> None:
    page_id = _resolve(arg, last_listing)
    if page_id is None:
        console.print(
            f"[red]não consegui resolver[/red] '{arg}' — passe um índice de `list`, um id curto, ou o id completo."
        )
        return
    try:
        blocks = api.get_page_blocks(page_id)
    except NotionError as e:
        console.print(f"[red]erro ao abrir nota:[/red] {e}")
        return

    matched = next((r for r in last_listing if r.id == page_id), None)
    body = md.from_blocks(blocks)

    parts: list[str] = []
    if matched and matched.title:
        parts.append(f"# {matched.title}")
    if body.strip():
        parts.append(body)
    elif not parts:
        parts.append("*(nota vazia)*")

    console.print(Markdown("\n\n".join(parts)))
    console.print(Rule(style="dim"))

    url = (
        matched.url
        if matched and matched.url
        else f"https://www.notion.so/{page_id.replace('-', '')}"
    )
    console.print(f"[dim]{url}[/dim]")
