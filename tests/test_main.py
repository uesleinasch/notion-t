from unittest.mock import MagicMock, patch

from noterminal import __main__ as entry
from noterminal.config import Config


def _cfg():
    return Config(token="t", workspace="w", database_id="db1",
                  editor_command="", list_size=10)


def test_main_runs_wizard_on_missing_config(monkeypatch, tmp_path):
    monkeypatch.setattr(entry.config, "load", lambda: None)
    saved: list[Config] = []
    monkeypatch.setattr(entry.config, "save", lambda c: saved.append(c))
    monkeypatch.setattr(entry.setup_wizard, "run", lambda **k: _cfg())
    monkeypatch.setattr(entry, "_run_repl", lambda state: None)

    rc = entry.main()
    assert rc == 0
    assert saved and saved[0].database_id == "db1"


def test_main_skips_wizard_when_config_present(monkeypatch):
    monkeypatch.setattr(entry.config, "load", lambda: _cfg())
    called = {"wizard": False}
    monkeypatch.setattr(entry.setup_wizard, "run",
                        lambda **k: called.__setitem__("wizard", True) or _cfg())
    monkeypatch.setattr(entry, "_run_repl", lambda state: None)
    rc = entry.main()
    assert rc == 0
    assert called["wizard"] is False


def test_main_reruns_wizard_when_setup_requested(monkeypatch):
    monkeypatch.setattr(entry.config, "load", lambda: _cfg())
    saves: list[Config] = []
    monkeypatch.setattr(entry.config, "save", lambda c: saves.append(c))

    wizard_calls = {"n": 0}
    def fake_wizard(**k):
        wizard_calls["n"] += 1
        return _cfg()
    monkeypatch.setattr(entry.setup_wizard, "run", fake_wizard)

    repl_calls = {"n": 0}
    def fake_repl(state):
        repl_calls["n"] += 1
        if repl_calls["n"] == 1:
            state.setup_requested = True
    monkeypatch.setattr(entry, "_run_repl", fake_repl)

    rc = entry.main()
    assert rc == 0
    assert wizard_calls["n"] == 1
    assert repl_calls["n"] == 2
