from unittest.mock import MagicMock

from noterminal.commands import list as list_cmd
from noterminal.notion_api import PageRef


class FakeConsole:
    def __init__(self):
        self.printed = []
    def print(self, *args, **kwargs):
        self.printed.append(args)


def test_list_returns_pages_and_prints_table():
    console = FakeConsole()
    api = MagicMock()
    refs = [
        PageRef(id="p1", title="A", url="u1", created_time="2026-05-07T10:00:00Z"),
        PageRef(id="p2", title="B", url="u2", created_time="2026-05-06T10:00:00Z"),
    ]
    api.list_recent_pages.return_value = refs

    result = list_cmd.run(api=api, database_id="db1", page_size=10, console=console)

    assert result == refs
    api.list_recent_pages.assert_called_once_with(database_id="db1", page_size=10)
    assert console.printed  # something rendered


def test_list_empty_db_prints_message():
    console = FakeConsole()
    api = MagicMock()
    api.list_recent_pages.return_value = []
    result = list_cmd.run(api=api, database_id="db1", page_size=10, console=console)
    assert result == []
    flat = " ".join(str(x) for args in console.printed for x in args)
    assert "nenhuma nota" in flat.lower()
