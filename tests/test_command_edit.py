from pathlib import Path
from unittest.mock import MagicMock

import pytest

from noterminal.commands import edit as edit_cmd
from noterminal.notion_api import NetworkError, PageRef


@pytest.fixture
def fake_console():
    out = []
    class C:
        def print(self, *args, **kwargs):
            out.append(" ".join(str(a) for a in args))
    return C(), out


def _refs():
    return [
        PageRef(id="aaaa1111-2222-3333-4444-555566667777", title="Original", url="u"),
    ]


def test_edit_loads_existing_content_and_updates(monkeypatch, fake_console):
    console, out = fake_console
    api = MagicMock()
    api.get_page_blocks.return_value = [
        {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "old body"}]}}
    ]

    def fake_editor(path: Path, command: str | None) -> None:
        # User changes both title and body
        path.write_text("# Renamed\n\nnew body")
    monkeypatch.setattr(edit_cmd.new_cmd, "open_editor", fake_editor)

    result = edit_cmd.run(
        api=api,
        arg="1",
        last_listing=_refs(),
        editor_command="",
        console=console,
    )

    assert result is True
    api.update_page.assert_called_once()
    kwargs = api.update_page.call_args.kwargs
    assert kwargs["page_id"] == "aaaa1111-2222-3333-4444-555566667777"
    assert kwargs["title"] == "Renamed"
    assert any("Renamed" in line for line in out)


def test_edit_aborts_when_unchanged(monkeypatch, fake_console):
    console, out = fake_console
    api = MagicMock()
    api.get_page_blocks.return_value = [
        {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "body"}]}}
    ]

    def fake_editor(path, command):
        # User saves without modifying anything
        pass  # path already contains the initial content
    monkeypatch.setattr(edit_cmd.new_cmd, "open_editor", fake_editor)

    result = edit_cmd.run(
        api=api,
        arg="1",
        last_listing=_refs(),
        editor_command="",
        console=console,
    )

    assert result is False
    api.update_page.assert_not_called()
    assert any("cancelada" in line.lower() for line in out)


def test_edit_preserves_tempfile_on_api_failure(monkeypatch, fake_console):
    console, out = fake_console
    api = MagicMock()
    api.get_page_blocks.return_value = []
    api.update_page.side_effect = NetworkError("offline")

    captured: dict = {}
    def fake_editor(path: Path, command: str | None) -> None:
        path.write_text("# Renamed\n\nnew body")
        captured["path"] = path
    monkeypatch.setattr(edit_cmd.new_cmd, "open_editor", fake_editor)

    result = edit_cmd.run(
        api=api,
        arg="1",
        last_listing=_refs(),
        editor_command="",
        console=console,
    )

    assert result is False
    assert captured["path"].exists()
    assert any("preservado" in line.lower() for line in out)


def test_edit_unknown_arg_errors(fake_console):
    console, out = fake_console
    api = MagicMock()
    edit_cmd.run(
        api=api, arg="zzzz", last_listing=[], editor_command="", console=console
    )
    api.get_page_blocks.assert_not_called()
    api.update_page.assert_not_called()


def test_edit_fetches_title_when_not_in_listing(monkeypatch, fake_console):
    console, _ = fake_console
    api = MagicMock()
    api.get_page_metadata.return_value = ("Fetched title", "u")
    api.get_page_blocks.return_value = []

    def fake_editor(path: Path, command: str | None) -> None:
        # User adds body keeping the fetched title
        path.write_text("# Fetched title\n\nbody added")
    monkeypatch.setattr(edit_cmd.new_cmd, "open_editor", fake_editor)

    edit_cmd.run(
        api=api,
        arg="ffffffff-1111-2222-3333-444455556666",
        last_listing=[],
        editor_command="",
        console=console,
    )

    api.get_page_metadata.assert_called_once_with(
        "ffffffff-1111-2222-3333-444455556666"
    )
    api.update_page.assert_called_once()
