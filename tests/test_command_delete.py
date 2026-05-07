from unittest.mock import MagicMock

import pytest

from noterminal.commands import delete as delete_cmd
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
        PageRef(id="aaaa1111-2222-3333-4444-555566667777", title="A", url="u1"),
        PageRef(id="bbbb1111-2222-3333-4444-555566667777", title="B", url="u2"),
    ]


def test_delete_archives_after_yes_confirmation(fake_console):
    console, out = fake_console
    api = MagicMock()
    deleted = delete_cmd.run(
        api=api,
        arg="2",
        last_listing=_refs(),
        console=console,
        confirm=lambda _: "y",
    )
    assert deleted == "bbbb1111-2222-3333-4444-555566667777"
    api.delete_page.assert_called_once_with("bbbb1111-2222-3333-4444-555566667777")
    assert any("deletado" in line.lower() for line in out)


def test_delete_accepts_portuguese_yes(fake_console):
    console, _ = fake_console
    api = MagicMock()
    deleted = delete_cmd.run(
        api=api,
        arg="1",
        last_listing=_refs(),
        console=console,
        confirm=lambda _: "sim",
    )
    assert deleted is not None
    api.delete_page.assert_called_once()


def test_delete_cancelled_when_no(fake_console):
    console, out = fake_console
    api = MagicMock()
    deleted = delete_cmd.run(
        api=api,
        arg="1",
        last_listing=_refs(),
        console=console,
        confirm=lambda _: "n",
    )
    assert deleted is None
    api.delete_page.assert_not_called()
    assert any("cancelado" in line.lower() for line in out)


def test_delete_cancelled_when_empty_response(fake_console):
    console, _ = fake_console
    api = MagicMock()
    deleted = delete_cmd.run(
        api=api,
        arg="1",
        last_listing=_refs(),
        console=console,
        confirm=lambda _: "",
    )
    assert deleted is None
    api.delete_page.assert_not_called()


def test_delete_cancelled_on_eof(fake_console):
    console, out = fake_console
    api = MagicMock()

    def raise_eof(_):
        raise EOFError

    deleted = delete_cmd.run(
        api=api,
        arg="1",
        last_listing=_refs(),
        console=console,
        confirm=raise_eof,
    )
    assert deleted is None
    api.delete_page.assert_not_called()
    assert any("cancelado" in line.lower() for line in out)


def test_delete_unknown_arg(fake_console):
    console, out = fake_console
    api = MagicMock()
    deleted = delete_cmd.run(
        api=api,
        arg="zzzz",
        last_listing=[],
        console=console,
        confirm=lambda _: "y",
    )
    assert deleted is None
    api.delete_page.assert_not_called()


def test_delete_api_failure_returns_none(fake_console):
    console, out = fake_console
    api = MagicMock()
    api.delete_page.side_effect = NetworkError("offline")
    deleted = delete_cmd.run(
        api=api,
        arg="1",
        last_listing=_refs(),
        console=console,
        confirm=lambda _: "y",
    )
    assert deleted is None
    assert any("falha" in line.lower() for line in out)
