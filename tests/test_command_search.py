from unittest.mock import MagicMock

from noterminal.commands import search as search_cmd
from noterminal.notion_api import PageRef


class FakeConsole:
    def __init__(self):
        self.printed = []
    def print(self, *a, **k):
        self.printed.append(a)


def test_search_calls_api_with_query_and_database():
    api = MagicMock()
    api.search_in_database.return_value = [
        PageRef(id="p1", title="hit", url="u", created_time="")
    ]
    result = search_cmd.run(api=api, database_id="db1", query="hit", console=FakeConsole())
    api.search_in_database.assert_called_once_with(database_id="db1", query="hit")
    assert result and result[0].title == "hit"


def test_search_with_no_results_prints_message():
    api = MagicMock()
    api.search_in_database.return_value = []
    console = FakeConsole()
    result = search_cmd.run(api=api, database_id="db1", query="x", console=console)
    assert result == []
    flat = " ".join(str(x) for args in console.printed for x in args)
    assert "sem resultados" in flat.lower()
