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


def test_repl_setup_sets_flag_and_exits():
    api = MagicMock()
    console = FakeConsole()
    state = repl.State(api=api, config=_cfg(), console=console, last_listing=[])

    lines = iter(["setup"])
    repl.run(state, line_source=lambda prompt: next(lines))
    assert state.setup_requested is True


def test_repl_open_without_arg_prints_usage():
    api = MagicMock()
    console = FakeConsole()
    state = repl.State(api=api, config=_cfg(), console=console, last_listing=[])

    lines = iter(["open", "exit"])
    repl.run(state, line_source=lambda prompt: next(lines))
    flat = "\n".join(console.printed).lower()
    assert "uso" in flat and "open" in flat


def test_repl_search_without_arg_prints_usage():
    api = MagicMock()
    console = FakeConsole()
    state = repl.State(api=api, config=_cfg(), console=console, last_listing=[])

    lines = iter(["search", "exit"])
    repl.run(state, line_source=lambda prompt: next(lines))
    flat = "\n".join(console.printed).lower()
    assert "uso" in flat and "search" in flat


def test_repl_notion_error_in_list_is_caught():
    from noterminal.notion_api import NetworkError
    api = MagicMock()
    api.list_recent_pages.side_effect = NetworkError("offline")
    console = FakeConsole()
    state = repl.State(api=api, config=_cfg(), console=console, last_listing=[])

    lines = iter(["list", "exit"])
    repl.run(state, line_source=lambda prompt: next(lines))
    flat = "\n".join(console.printed).lower()
    assert "erro" in flat and "offline" in flat


def test_repl_empty_line_continues_loop():
    api = MagicMock()
    console = FakeConsole()
    state = repl.State(api=api, config=_cfg(), console=console, last_listing=[])

    lines = iter(["", "   ", "exit"])
    repl.run(state, line_source=lambda prompt: next(lines))
    # If the empty/whitespace lines didn't continue, we'd exit before consuming "exit"
    # and the iter would have raised StopIteration instead of completing.


def test_repl_numeric_shortcut_opens_note_from_listing():
    api = MagicMock()
    api.get_page_blocks.return_value = []
    console = FakeConsole()
    refs = [
        PageRef(id="aaaa1111-2222-3333-4444-555566667777", title="A", url="u1"),
        PageRef(id="bbbb1111-2222-3333-4444-555566667777", title="B", url="u2"),
    ]
    state = repl.State(api=api, config=_cfg(), console=console, last_listing=refs)

    lines = iter(["2", "exit"])
    repl.run(state, line_source=lambda prompt: next(lines))

    api.get_page_blocks.assert_called_once_with(
        "bbbb1111-2222-3333-4444-555566667777"
    )


def test_repl_clear_calls_console_clear():
    api = MagicMock()

    class ConsoleWithClear:
        def __init__(self):
            self.printed = []
            self.cleared = 0
        def print(self, *a, **k):
            self.printed.append(" ".join(str(x) for x in a))
        def clear(self):
            self.cleared += 1

    console = ConsoleWithClear()
    state = repl.State(api=api, config=_cfg(), console=console, last_listing=[])

    lines = iter(["clear", "cls", "exit"])
    repl.run(state, line_source=lambda prompt: next(lines))
    assert console.cleared == 2


def test_repl_clear_falls_back_to_ansi_when_console_has_no_clear():
    api = MagicMock()
    console = FakeConsole()  # no .clear() method
    state = repl.State(api=api, config=_cfg(), console=console, last_listing=[])

    lines = iter(["clear", "exit"])
    repl.run(state, line_source=lambda prompt: next(lines))
    flat = "".join(console.printed)
    assert "\x1b[2J" in flat


def test_repl_numeric_shortcut_without_listing_shows_hint():
    api = MagicMock()
    console = FakeConsole()
    state = repl.State(api=api, config=_cfg(), console=console, last_listing=[])

    lines = iter(["3", "exit"])
    repl.run(state, line_source=lambda prompt: next(lines))

    flat = "\n".join(console.printed).lower()
    assert "list" in flat or "search" in flat
    api.get_page_blocks.assert_not_called()


def test_repl_editor_persists_new_choice(monkeypatch, tmp_path):
    from noterminal import config as config_mod
    from noterminal.commands import editor as editor_cmd

    # Pretend everything is installed so editor cmd just returns a value.
    monkeypatch.setattr(editor_cmd, "_is_installed", lambda ed: True)
    monkeypatch.setattr(config_mod, "config_path", lambda: tmp_path / "config.toml")

    saved = {}

    def fake_save(cfg):
        saved["cfg"] = cfg

    monkeypatch.setattr(config_mod, "save", fake_save)

    api = MagicMock()
    console = FakeConsole()
    state = repl.State(api=api, config=_cfg(), console=console, last_listing=[])

    lines = iter(["editor vim", "exit"])
    repl.run(state, line_source=lambda prompt: next(lines))

    assert saved["cfg"].editor_command == "vim"
    assert state.config.editor_command == "vim"


def test_repl_editor_no_change_does_not_save(monkeypatch):
    from noterminal import config as config_mod
    from noterminal.commands import editor as editor_cmd

    monkeypatch.setattr(editor_cmd, "_is_installed", lambda ed: True)

    saved = {"called": False}

    def fake_save(cfg):
        saved["called"] = True

    monkeypatch.setattr(config_mod, "save", fake_save)

    api = MagicMock()
    console = FakeConsole()
    cfg = Config(token="t", workspace="w", database_id="db1",
                 editor_command="nano", list_size=10)
    state = repl.State(api=api, config=cfg, console=console, last_listing=[])

    lines = iter(["editor nano", "exit"])
    repl.run(state, line_source=lambda prompt: next(lines))

    assert saved["called"] is False
    assert state.config.editor_command == "nano"
