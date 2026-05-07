"""notion-t entry point."""
from __future__ import annotations

import sys

from rich.console import Console

from . import config as config_mod
from . import setup_wizard
from .notion_api import NotionAPI
from .repl import State, run as repl_run

config = config_mod  # alias for tests that monkeypatch entry.config


def _run_repl(state: State) -> None:
    repl_run(state)


def main() -> int:
    console = Console()
    cfg = config.load()
    if cfg is None:
        try:
            cfg = setup_wizard.run()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]setup cancelado.[/dim]")
            return 1
        config.save(cfg)

    while True:
        api = NotionAPI(token=cfg.token)
        state = State(api=api, config=cfg, console=console)
        _run_repl(state)
        if not state.setup_requested:
            return 0
        try:
            cfg = setup_wizard.run()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]setup cancelado.[/dim]")
            return 1
        config.save(cfg)


if __name__ == "__main__":
    sys.exit(main())
