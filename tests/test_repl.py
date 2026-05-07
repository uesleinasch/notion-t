from unittest.mock import MagicMock

from noterminal import repl
from noterminal.config import Config
from noterminal.notion_api import PageRef


def _cfg():
    return Config(token="t", workspace="w", database_id="db1",
                  editor_command="", list_size=10)


class FakeConsole:
    def __init__(self):
        self.printed = []
    def print(self, *a, **k):
        self.printed.append(" ".join(str(x) for x in a))


def test_repl_dispatches_help(monkeypatch):
    api = MagicMock()
    console = FakeConsole()
    state = repl.State(api=api, config=_cfg(), console=console, last_listing=[])

    lines = iter(["help", "exit"])
    repl.run(state, line_source=lambda prompt: next(lines))
    flat = "\n".join(console.printed)
    assert "new" in flat


def test_repl_list_updates_last_listing(monkeypatch):
    api = MagicMock()
    refs = [PageRef(id="p1", title="A", url="u", created_time="")]
    api.list_recent_pages.return_value = refs
    console = FakeConsole()
    state = repl.State(api=api, config=_cfg(), console=console, last_listing=[])

    lines = iter(["list 5", "exit"])
    repl.run(state, line_source=lambda prompt: next(lines))
    assert state.last_listing == refs
    api.list_recent_pages.assert_called_once_with(database_id="db1", page_size=5)


def test_repl_unknown_command_shows_hint():
    api = MagicMock()
    console = FakeConsole()
    state = repl.State(api=api, config=_cfg(), console=console, last_listing=[])

    lines = iter(["nosuchthing", "exit"])
    repl.run(state, line_source=lambda prompt: next(lines))
    flat = "\n".join(console.printed)
    assert "comando desconhecido" in flat.lower()
    assert "help" in flat


def test_repl_eof_exits():
    api = MagicMock()
    console = FakeConsole()
    state = repl.State(api=api, config=_cfg(), console=console, last_listing=[])

    def src(prompt):
        raise EOFError
    repl.run(state, line_source=src)


def test_repl_search_updates_last_listing():
    api = MagicMock()
    refs = [PageRef(id="p1", title="hit", url="u", created_time="")]
    api.search_in_database.return_value = refs
    console = FakeConsole()
    state = repl.State(api=api, config=_cfg(), console=console, last_listing=[])

    lines = iter(["search hi", "exit"])
    repl.run(state, line_source=lambda prompt: next(lines))
    assert state.last_listing == refs
