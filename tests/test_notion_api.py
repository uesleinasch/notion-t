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


def test_query_database_returns_page_refs():
    client = MagicMock()
    client.databases.query.return_value = {
        "results": [
            {
                "id": "p1",
                "url": "https://notion.so/p1",
                "created_time": "2026-05-07T10:00:00Z",
                "properties": {
                    "Title": {"title": [{"plain_text": "Note A"}]},
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
        {"property": "Created", "direction": "descending"}
    ]


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
    client.search.return_value = {
        "results": [
            {
                "id": "p1",
                "object": "page",
                "url": "https://notion.so/p1",
                "parent": {"type": "database_id", "database_id": "db1"},
                "properties": {"Title": {"title": [{"plain_text": "hit"}]}},
            },
            {
                "id": "p2",
                "object": "page",
                "url": "https://notion.so/p2",
                "parent": {"type": "database_id", "database_id": "OTHER"},
                "properties": {"Title": {"title": [{"plain_text": "miss"}]}},
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
