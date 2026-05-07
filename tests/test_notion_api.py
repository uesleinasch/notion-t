from unittest.mock import MagicMock

import pytest
from notion_client.errors import APIResponseError, RequestTimeoutError

from noterminal import notion_api
from noterminal.notion_api import (
    AuthError,
    NotFoundOrForbiddenError,
    NotionError,
    NotionAPI,
    RateLimitError,
    NetworkError,
)


def make_api(client):
    return NotionAPI(client=client)


def _api_error(status):
    err = APIResponseError.__new__(APIResponseError)
    err.status = status
    err.code = "x"
    err.body = {"message": "boom"}
    return err


def test_validate_token_returns_workspace_name():
    client = MagicMock()
    client.users.me.return_value = {
        "bot": {"workspace_name": "Ueslei Pessoal"}
    }
    api = make_api(client)
    assert api.validate_token() == "Ueslei Pessoal"


def test_validate_token_unauthorized_raises_auth_error():
    client = MagicMock()
    client.users.me.side_effect = _api_error(401)
    api = make_api(client)
    with pytest.raises(AuthError):
        api.validate_token()


def test_create_database_passes_correct_schema():
    client = MagicMock()
    client.databases.create.return_value = {"id": "db123"}
    api = make_api(client)

    db_id = api.create_quick_notes_database(parent_page_id="page-abc")

    assert db_id == "db123"
    args = client.databases.create.call_args.kwargs
    assert args["parent"] == {"type": "page_id", "page_id": "page-abc"}
    assert "Title" in args["properties"]
    assert args["properties"]["Title"] == {"title": {}}
    assert args["properties"]["Created"] == {"created_time": {}}
    assert "Tags" in args["properties"]
    assert args["properties"]["Tags"]["multi_select"] == {"options": []}


def test_create_page_sends_title_and_blocks():
    client = MagicMock()
    client.databases.retrieve.return_value = {
        "properties": {"Title": {"type": "title"}}
    }
    client.pages.create.return_value = {
        "id": "page-1",
        "url": "https://notion.so/page-1",
    }
    api = make_api(client)

    blocks = [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}}]
    result = api.create_page(database_id="db1", title="My note", blocks=blocks)

    assert result.id == "page-1"
    assert result.url == "https://notion.so/page-1"
    args = client.pages.create.call_args.kwargs
    assert args["parent"] == {"database_id": "db1"}
    assert args["properties"]["Title"]["title"][0]["text"]["content"] == "My note"
    assert args["children"] == blocks


def test_create_page_uses_actual_title_property_name():
    client = MagicMock()
    client.databases.retrieve.return_value = {
        "properties": {
            "Name": {"type": "title"},
            "Status": {"type": "select"},
        }
    }
    client.pages.create.return_value = {
        "id": "p1",
        "url": "https://notion.so/p1",
    }
    api = make_api(client)

    api.create_page(database_id="db1", title="hello", blocks=[])

    args = client.pages.create.call_args.kwargs
    assert "Name" in args["properties"]
    assert "Title" not in args["properties"]
    assert args["properties"]["Name"]["title"][0]["text"]["content"] == "hello"


def test_create_page_caches_title_property_lookup():
    client = MagicMock()
    # Include a date prop so auto-add doesn't run and bust the cache.
    client.databases.retrieve.return_value = {
        "properties": {
            "Tarefa": {"type": "title"},
            "Criado": {"type": "date"},
        }
    }
    client.pages.create.return_value = {"id": "p1", "url": "u"}
    api = make_api(client)

    api.create_page(database_id="db1", title="a", blocks=[])
    api.create_page(database_id="db1", title="b", blocks=[])

    assert client.databases.retrieve.call_count == 1


def test_create_page_populates_date_property_when_present():
    client = MagicMock()
    client.databases.retrieve.return_value = {
        "properties": {
            "Title": {"type": "title"},
            "Criado": {"type": "date"},
        }
    }
    client.pages.create.return_value = {"id": "p1", "url": "u"}
    api = make_api(client)

    api.create_page(database_id="db1", title="x", blocks=[])

    args = client.pages.create.call_args.kwargs
    assert "Criado" in args["properties"]
    date_value = args["properties"]["Criado"]["date"]
    assert "start" in date_value
    # ISO 8601 with timezone offset
    assert "T" in date_value["start"] and ("+" in date_value["start"] or "Z" in date_value["start"])


def test_create_page_skips_unrecognized_date_property_names():
    """Date properties with unrelated names (e.g. 'Due') are not auto-filled."""
    client = MagicMock()
    client.databases.retrieve.return_value = {
        "properties": {
            "Title": {"type": "title"},
            "Due": {"type": "date"},
        }
    }
    client.pages.create.return_value = {"id": "p1", "url": "u"}
    api = make_api(client)

    api.create_page(database_id="db1", title="x", blocks=[])

    args = client.pages.create.call_args.kwargs
    assert "Due" not in args["properties"]


def test_create_page_auto_adds_date_property_when_missing_classic():
    """When the classic DB has no date prop, create_page must add 'Criado' first."""
    client = MagicMock()
    # First retrieve → no date prop. Second (after cache bust) → has it.
    client.databases.retrieve.side_effect = [
        {"properties": {"Title": {"type": "title"}}},
        {"properties": {"Title": {"type": "title"}, "Criado": {"type": "date"}}},
    ]
    client.pages.create.return_value = {"id": "p1", "url": "u"}
    api = make_api(client)

    api.create_page(database_id="db1", title="x", blocks=[])

    # Schema was patched with the new property
    client.databases.update.assert_called_once_with(
        database_id="db1",
        properties={"Criado": {"date": {}}},
    )
    # And the page was created with the new prop populated
    args = client.pages.create.call_args.kwargs
    assert "Criado" in args["properties"]
    assert "start" in args["properties"]["Criado"]["date"]


def test_create_page_auto_adds_date_property_when_missing_multi_source():
    client = MagicMock()
    # databases.retrieve → multi-source shell, called twice (cache busted after patch)
    client.databases.retrieve.side_effect = [
        {"object": "database", "data_sources": [{"id": "ds1"}]},
        {"object": "database", "data_sources": [{"id": "ds1"}]},
    ]
    # Sequence of `request` calls: GET ds (no date), PATCH ds, GET ds (with date)
    client.request.side_effect = [
        {"properties": {"Title": {"type": "title"}}},
        {"object": "data_source", "id": "ds1"},
        {"properties": {"Title": {"type": "title"}, "Criado": {"type": "date"}}},
    ]
    client.pages.create.return_value = {"id": "p1", "url": "u"}
    api = make_api(client)

    api.create_page(database_id="db1", title="x", blocks=[])

    # PATCH was sent to the data source endpoint
    patch_call = client.request.call_args_list[1]
    assert patch_call.kwargs == {
        "path": "data_sources/ds1",
        "method": "PATCH",
        "body": {"properties": {"Criado": {"date": {}}}},
    }
    # Page parent uses data_source_id and date prop is populated
    args = client.pages.create.call_args.kwargs
    assert args["parent"] == {"data_source_id": "ds1"}
    assert "Criado" in args["properties"]


def test_create_page_skips_created_time_property():
    """Notion auto-fills `created_time` props; we must not try to set them."""
    client = MagicMock()
    client.databases.retrieve.return_value = {
        "properties": {
            "Title": {"type": "title"},
            "Created": {"type": "created_time"},
        }
    }
    client.pages.create.return_value = {"id": "p1", "url": "u"}
    api = make_api(client)

    api.create_page(database_id="db1", title="x", blocks=[])

    args = client.pages.create.call_args.kwargs
    assert "Created" not in args["properties"]


def test_create_page_handles_multi_source_database():
    """New Notion DBs return data_sources[] with no top-level properties."""
    client = MagicMock()
    client.databases.retrieve.return_value = {
        "object": "database",
        "data_sources": [{"id": "ds1", "name": "Quick Notes"}],
    }
    # Include a date prop so auto-add doesn't run.
    client.request.return_value = {
        "properties": {
            "Title": {"type": "title"},
            "Criado": {"type": "date"},
        }
    }
    client.pages.create.return_value = {"id": "p1", "url": "u"}
    api = make_api(client)

    api.create_page(database_id="db1", title="hello", blocks=[])

    # Data source schema fetched (single GET, no PATCH)
    client.request.assert_called_once_with(path="data_sources/ds1", method="GET")
    # Page parent uses data_source_id (not database_id)
    args = client.pages.create.call_args.kwargs
    assert args["parent"] == {"data_source_id": "ds1"}
    assert args["properties"]["Title"]["title"][0]["text"]["content"] == "hello"


def test_list_recent_pages_uses_data_source_query_for_multi_source():
    client = MagicMock()
    client.databases.retrieve.return_value = {
        "object": "database",
        "data_sources": [{"id": "ds1", "name": "Quick Notes"}],
    }
    # First request: schema. Second request: query.
    client.request.side_effect = [
        {"properties": {"Name": {"type": "title"}}},
        {"results": [
            {
                "id": "p1",
                "url": "u",
                "created_time": "2026-05-07T10:00:00Z",
                "properties": {"Name": {"type": "title", "title": [{"plain_text": "A"}]}},
            }
        ]},
    ]
    api = make_api(client)

    refs = api.list_recent_pages(database_id="db1", page_size=5)

    assert len(refs) == 1 and refs[0].title == "A"
    second_call = client.request.call_args_list[1]
    assert second_call.kwargs["path"] == "data_sources/ds1/query"
    assert second_call.kwargs["method"] == "POST"
    assert second_call.kwargs["body"]["page_size"] == 5
    # Classic query endpoint NOT used
    client.databases.query.assert_not_called()


def test_search_filters_by_data_source_for_multi_source():
    client = MagicMock()
    client.databases.retrieve.return_value = {
        "object": "database",
        "data_sources": [{"id": "ds1", "name": "x"}],
    }
    client.request.return_value = {"properties": {"T": {"type": "title"}}}
    client.search.return_value = {
        "results": [
            {
                "id": "p1",
                "object": "page",
                "url": "u1",
                "parent": {"type": "data_source_id", "data_source_id": "ds1"},
                "properties": {"T": {"type": "title", "title": [{"plain_text": "match"}]}},
            },
            {
                "id": "p2",
                "object": "page",
                "url": "u2",
                "parent": {"type": "data_source_id", "data_source_id": "OTHER"},
                "properties": {"T": {"type": "title", "title": [{"plain_text": "miss"}]}},
            },
            {
                "id": "p3",
                "object": "page",
                "url": "u3",
                "parent": {"type": "database_id", "database_id": "db1"},  # classic-shaped result
                "properties": {"T": {"type": "title", "title": [{"plain_text": "ignore"}]}},
            },
        ]
    }
    api = make_api(client)

    refs = api.search_in_database(database_id="db1", query="x")

    assert [r.id for r in refs] == ["p1"]


def test_create_page_raises_when_database_has_no_title_property():
    client = MagicMock()
    client.databases.retrieve.return_value = {
        "properties": {"Status": {"type": "select"}}
    }
    api = make_api(client)
    with pytest.raises(NotionError):
        api.create_page(database_id="db1", title="x", blocks=[])


def test_query_database_returns_page_refs():
    client = MagicMock()
    client.databases.retrieve.return_value = {
        "properties": {"Title": {"type": "title"}}
    }
    client.databases.query.return_value = {
        "results": [
            {
                "id": "p1",
                "url": "https://notion.so/p1",
                "created_time": "2026-05-07T10:00:00Z",
                "properties": {
                    "Title": {"type": "title", "title": [{"plain_text": "Note A"}]},
                },
            }
        ]
    }
    api = make_api(client)

    refs = api.list_recent_pages(database_id="db1", page_size=10)

    assert len(refs) == 1
    assert refs[0].id == "p1"
    assert refs[0].title == "Note A"
    assert refs[0].url == "https://notion.so/p1"
    args = client.databases.query.call_args.kwargs
    assert args["database_id"] == "db1"
    assert args["page_size"] == 10
    assert args["sorts"] == [
        {"timestamp": "created_time", "direction": "descending"}
    ]


def test_extract_title_finds_property_by_type_not_name():
    """A DB with title prop named 'Tarefa' (not 'Title') should still resolve."""
    client = MagicMock()
    client.databases.retrieve.return_value = {
        "properties": {"Tarefa": {"type": "title"}}
    }
    client.databases.query.return_value = {
        "results": [
            {
                "id": "p1",
                "url": "u",
                "created_time": "2026-05-07T10:00:00Z",
                "properties": {
                    "Status": {"type": "select", "select": {"name": "todo"}},
                    "Tarefa": {"type": "title", "title": [{"plain_text": "do thing"}]},
                },
            }
        ]
    }
    api = make_api(client)
    refs = api.list_recent_pages(database_id="db1")
    assert refs[0].title == "do thing"


def test_get_page_blocks_paginates():
    client = MagicMock()
    client.blocks.children.list.side_effect = [
        {"results": [{"id": "b1"}], "has_more": True, "next_cursor": "c1"},
        {"results": [{"id": "b2"}], "has_more": False, "next_cursor": None},
    ]
    api = make_api(client)

    blocks = api.get_page_blocks("p1")

    assert [b["id"] for b in blocks] == ["b1", "b2"]
    assert client.blocks.children.list.call_count == 2


def test_search_filters_by_database():
    client = MagicMock()
    client.databases.retrieve.return_value = {
        "properties": {"Title": {"type": "title"}}
    }
    client.search.return_value = {
        "results": [
            {
                "id": "p1",
                "object": "page",
                "url": "https://notion.so/p1",
                "parent": {"type": "database_id", "database_id": "db1"},
                "properties": {"Title": {"type": "title", "title": [{"plain_text": "hit"}]}},
            },
            {
                "id": "p2",
                "object": "page",
                "url": "https://notion.so/p2",
                "parent": {"type": "database_id", "database_id": "OTHER"},
                "properties": {"Title": {"type": "title", "title": [{"plain_text": "miss"}]}},
            },
        ]
    }
    api = make_api(client)

    refs = api.search_in_database(database_id="db1", query="hit")

    assert [r.id for r in refs] == ["p1"]


def test_403_maps_to_not_found_or_forbidden():
    client = MagicMock()
    client.databases.create.side_effect = _api_error(403)
    api = make_api(client)
    with pytest.raises(NotFoundOrForbiddenError):
        api.create_quick_notes_database(parent_page_id="x")


def test_404_maps_to_not_found_or_forbidden():
    client = MagicMock()
    client.databases.create.side_effect = _api_error(404)
    api = make_api(client)
    with pytest.raises(NotFoundOrForbiddenError):
        api.create_quick_notes_database(parent_page_id="x")


def test_429_maps_to_rate_limit():
    client = MagicMock()
    client.databases.create.side_effect = _api_error(429)
    api = make_api(client)
    with pytest.raises(RateLimitError):
        api.create_quick_notes_database(parent_page_id="x")


def test_timeout_maps_to_network_error():
    client = MagicMock()
    client.users.me.side_effect = RequestTimeoutError("timeout")
    api = make_api(client)
    with pytest.raises(NetworkError):
        api.validate_token()


def test_with_retry_returns_immediately_on_success(monkeypatch):
    monkeypatch.setattr(notion_api.time, "sleep", lambda *_: None)
    api = make_api(MagicMock())
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        return "ok"

    assert api.with_retry(fn) == "ok"
    assert calls["n"] == 1


def test_with_retry_retries_on_rate_limit_then_succeeds(monkeypatch):
    monkeypatch.setattr(notion_api.time, "sleep", lambda *_: None)
    api = make_api(MagicMock())
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 2:
            raise RateLimitError("slow down")
        return "ok"

    assert api.with_retry(fn, attempts=3, base_delay=0.0) == "ok"
    assert calls["n"] == 2


def test_with_retry_exhausts_attempts_and_reraises(monkeypatch):
    monkeypatch.setattr(notion_api.time, "sleep", lambda *_: None)
    api = make_api(MagicMock())
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise RateLimitError("nope")

    with pytest.raises(RateLimitError):
        api.with_retry(fn, attempts=3, base_delay=0.0)
    assert calls["n"] == 3
