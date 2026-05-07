from pathlib import Path
from unittest.mock import MagicMock

import pytest

from noterminal.commands import new
from noterminal.notion_api import CreatedPage, NetworkError


@pytest.fixture
def fake_console():
    out = []
    class C:
        def print(self, *args, **kwargs):
            out.append(" ".join(str(a) for a in args))
    return C(), out


def test_new_calls_editor_and_creates_page(monkeypatch, tmp_path, fake_console):
    console, out = fake_console
    api = MagicMock()
    api.create_page.return_value = CreatedPage(id="p1", url="https://notion.so/p1")

    def fake_editor(path: Path, command: str | None) -> None:
        path.write_text("# Title here\n\nbody")
    monkeypatch.setattr(new, "open_editor", fake_editor)

    result = new.run(
        api=api,
        database_id="db1",
        editor_command="",
        console=console,
    )

    assert result is True
    args = api.create_page.call_args.kwargs
    assert args["title"] == "Title here"
    assert args["database_id"] == "db1"
    assert any(b["type"] == "paragraph" for b in args["blocks"])
    assert any("Title here" in line or "p1" in line for line in out)


def test_new_aborts_when_template_unchanged(monkeypatch, fake_console):
    console, out = fake_console
    api = MagicMock()
    monkeypatch.setattr(new, "open_editor", lambda p, c: p.write_text(new.TEMPLATE))
    result = new.run(api=api, database_id="db1", editor_command="", console=console)
    assert result is False
    api.create_page.assert_not_called()
    assert any("descartada" in line for line in out)


def test_new_aborts_when_empty(monkeypatch, fake_console):
    console, out = fake_console
    api = MagicMock()
    monkeypatch.setattr(new, "open_editor", lambda p, c: p.write_text(""))
    result = new.run(api=api, database_id="db1", editor_command="", console=console)
    assert result is False
    api.create_page.assert_not_called()


def test_new_keeps_tempfile_visible_on_api_failure(monkeypatch, fake_console):
    console, out = fake_console
    api = MagicMock()
    api.create_page.side_effect = NetworkError("offline")

    captured: dict = {}
    def fake_editor(path: Path, command: str | None) -> None:
        path.write_text("# T\n\nbody")
        captured["path"] = path
    monkeypatch.setattr(new, "open_editor", fake_editor)

    result = new.run(api=api, database_id="db1", editor_command="", console=console)

    assert result is False
    assert any("conteúdo preservado" in line.lower() or "preservado" in line.lower() for line in out)
    assert captured["path"].exists()
    assert captured["path"].read_text().startswith("# T")
