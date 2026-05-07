"""Interactive REPL — prompt, dispatch, shared session state."""
from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Callable, Protocol

from .commands import help as help_cmd
from .commands import list as list_cmd
from .commands import new as new_cmd
from .commands import open as open_cmd
from .commands import search as search_cmd
from .config import Config
from .notion_api import NotionAPI, NotionError, PageRef


class _Console(Protocol):
    def print(self, *args, **kwargs) -> None: ...


@dataclass
class State:
    api: NotionAPI
    config: Config
    console: _Console
    last_listing: list[PageRef] = field(default_factory=list)
    setup_requested: bool = False


def _default_line_source(prompt: str) -> str:
    # Lazy import keeps prompt_toolkit out of the test path.
    if not hasattr(_default_line_source, "_session"):
        import os

        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import WordCompleter
        from prompt_toolkit.history import FileHistory

        histfile = os.path.expanduser("~/.local/share/noterminal/history")
        os.makedirs(os.path.dirname(histfile), exist_ok=True)
        completer = WordCompleter(
            ["new", "list", "open", "search", "setup", "help", "exit", "quit"],
            ignore_case=True,
        )
        _default_line_source._session = PromptSession(
            history=FileHistory(histfile), completer=completer
        )
    return _default_line_source._session.prompt(prompt)


def _dispatch(state: State, line: str) -> bool:
    """Return False to keep looping, True to exit."""
    if not line.strip():
        return False
    try:
        parts = shlex.split(line)
    except ValueError:
        parts = line.split()
    cmd, *args = parts
    cmd = cmd.lower()

    if cmd in ("exit", "quit"):
        return True
    if cmd.isdigit():
        if not state.last_listing:
            state.console.print(
                "[dim]rode `list` ou `search` antes de digitar um número.[/dim]"
            )
            return False
        open_cmd.run(
            api=state.api,
            arg=cmd,
            last_listing=state.last_listing,
            console=state.console,
        )
        return False
    if cmd == "help":
        help_cmd.run(console=state.console)
        return False
    if cmd == "new":
        try:
            new_cmd.run(
                api=state.api,
                database_id=state.config.database_id,
                editor_command=state.config.editor_command,
                console=state.console,
            )
        except NotionError as e:
            state.console.print(f"[red]erro:[/red] {e}")
        return False
    if cmd == "list":
        size = state.config.list_size
        if args and args[0].isdigit():
            size = int(args[0])
        try:
            state.last_listing = list_cmd.run(
                api=state.api,
                database_id=state.config.database_id,
                page_size=size,
                console=state.console,
            )
        except NotionError as e:
            state.console.print(f"[red]erro:[/red] {e}")
        return False
    if cmd == "open":
        if not args:
            state.console.print("uso: [cyan]open <id|N>[/cyan]")
            return False
        open_cmd.run(
            api=state.api,
            arg=args[0],
            last_listing=state.last_listing,
            console=state.console,
        )
        return False
    if cmd == "search":
        if not args:
            state.console.print("uso: [cyan]search <termo>[/cyan]")
            return False
        try:
            state.last_listing = search_cmd.run(
                api=state.api,
                database_id=state.config.database_id,
                query=" ".join(args),
                console=state.console,
            )
        except NotionError as e:
            state.console.print(f"[red]erro:[/red] {e}")
        return False
    if cmd == "setup":
        state.setup_requested = True
        return True

    state.console.print(
        f"[red]comando desconhecido:[/red] {cmd}. digite [cyan]help[/cyan]."
    )
    return False


def run(state: State, *, line_source: Callable[[str], str] = _default_line_source) -> None:
    state.console.print(
        f"[bold]notion-t[/bold] — workspace [cyan]{state.config.workspace}[/cyan]. "
        "digite [cyan]help[/cyan] para começar."
    )
    while True:
        try:
            line = line_source("> ")
        except (EOFError, KeyboardInterrupt):
            state.console.print("")
            return
        if _dispatch(state, line):
            return
