from unittest.mock import MagicMock

from noterminal.commands import open as open_cmd
from noterminal.notion_api import PageRef


class FakeConsole:
    def __init__(self):
        self.printed = []
    def print(self, *args, **kwargs):
        self.printed.append(args)


def _refs():
    return [
        PageRef(id="aaaa1111-2222-3333-4444-555566667777", title="A", url="u1"),
        PageRef(id="bbbb1111-2222-3333-4444-555566667777", title="B", url="u2"),
    ]


def test_open_resolves_index_from_last_listing():
    api = MagicMock()
    api.get_page_blocks.return_value = [
        {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "hi"}]}}
    ]
    console = FakeConsole()
    open_cmd.run(api=api, arg="2", last_listing=_refs(), console=console)
    api.get_page_blocks.assert_called_once_with("bbbb1111-2222-3333-4444-555566667777")


def test_open_resolves_short_id():
    api = MagicMock()
    api.get_page_blocks.return_value = []
    console = FakeConsole()
    open_cmd.run(api=api, arg="aaaa1111", last_listing=_refs(), console=console)
    api.get_page_blocks.assert_called_once_with("aaaa1111-2222-3333-4444-555566667777")


def test_open_passes_full_id_through():
    api = MagicMock()
    api.get_page_blocks.return_value = []
    console = FakeConsole()
    open_cmd.run(
        api=api,
        arg="ffffffff-1111-2222-3333-444455556666",
        last_listing=[],
        console=console,
    )
    api.get_page_blocks.assert_called_once_with("ffffffff-1111-2222-3333-444455556666")


def test_open_unknown_short_id_with_no_listing_errors():
    api = MagicMock()
    console = FakeConsole()
    open_cmd.run(api=api, arg="zzzz", last_listing=[], console=console)
    api.get_page_blocks.assert_not_called()
    flat = " ".join(str(x) for args in console.printed for x in args)
    assert "não consegui resolver" in flat.lower()
