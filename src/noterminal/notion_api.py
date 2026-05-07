"""Thin wrapper over `notion-client`.

This module is the only place in the codebase that imports the Notion SDK.
Errors from the SDK are translated into a small hierarchy of `NotionError`
subclasses so callers can show friendly messages without coupling to the
SDK's exception types.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from notion_client import Client
from notion_client.errors import APIResponseError, RequestTimeoutError


class NotionError(Exception):
    pass


class AuthError(NotionError):
    pass


class NotFoundOrForbiddenError(NotionError):
    pass


class RateLimitError(NotionError):
    pass


class NetworkError(NotionError):
    pass


@dataclass(frozen=True)
class PageRef:
    id: str
    title: str
    url: str
    created_time: str = ""


@dataclass(frozen=True)
class CreatedPage:
    id: str
    url: str


def _extract_title(properties: dict[str, Any]) -> str:
    title_prop = properties.get("Title") or properties.get("title") or {}
    parts = title_prop.get("title", [])
    return "".join(p.get("plain_text", "") for p in parts) or "(sem título)"


def _translate(err: Exception) -> NotionError:
    if isinstance(err, RequestTimeoutError):
        return NetworkError(str(err))
    if isinstance(err, APIResponseError):
        status = getattr(err, "status", None)
        if status == 401:
            return AuthError("token inválido ou revogado")
        if status in (403, 404):
            return NotFoundOrForbiddenError(
                "recurso inacessível — verifique se a integração tem acesso à página/database"
            )
        if status == 429:
            return RateLimitError("rate limit do Notion atingido")
    return NetworkError(str(err))


class NotionAPI:
    """Narrow wrapper exposing only what notion-t needs."""

    def __init__(self, *, token: str | None = None, client: Client | None = None) -> None:
        if client is None:
            if token is None:
                raise ValueError("either token or client must be provided")
            client = Client(auth=token)
        self._client = client

    def validate_token(self) -> str:
        try:
            me = self._client.users.me()
        except (APIResponseError, RequestTimeoutError) as e:
            raise _translate(e) from e
        return (me.get("bot") or {}).get("workspace_name", "")

    def create_quick_notes_database(self, *, parent_page_id: str) -> str:
        try:
            resp = self._client.databases.create(
                parent={"type": "page_id", "page_id": parent_page_id},
                title=[{"type": "text", "text": {"content": "Quick Notes"}}],
                properties={
                    "Title": {"title": {}},
                    "Created": {"created_time": {}},
                    "Tags": {"multi_select": {"options": []}},
                },
            )
        except (APIResponseError, RequestTimeoutError) as e:
            raise _translate(e) from e
        return resp["id"]

    def create_page(self, *, database_id: str, title: str, blocks: list[dict]) -> CreatedPage:
        try:
            resp = self._client.pages.create(
                parent={"database_id": database_id},
                properties={
                    "Title": {
                        "title": [{"type": "text", "text": {"content": title}}]
                    }
                },
                children=blocks,
            )
        except (APIResponseError, RequestTimeoutError) as e:
            raise _translate(e) from e
        return CreatedPage(id=resp["id"], url=resp["url"])

    def list_recent_pages(self, *, database_id: str, page_size: int = 10) -> list[PageRef]:
        try:
            resp = self._client.databases.query(
                database_id=database_id,
                page_size=page_size,
                sorts=[{"property": "Created", "direction": "descending"}],
            )
        except (APIResponseError, RequestTimeoutError) as e:
            raise _translate(e) from e
        return [
            PageRef(
                id=p["id"],
                title=_extract_title(p.get("properties", {})),
                url=p.get("url", ""),
                created_time=p.get("created_time", ""),
            )
            for p in resp.get("results", [])
        ]

    def get_page_blocks(self, page_id: str) -> list[dict]:
        all_blocks: list[dict] = []
        cursor: str | None = None
        while True:
            try:
                kwargs: dict[str, Any] = {"block_id": page_id, "page_size": 100}
                if cursor:
                    kwargs["start_cursor"] = cursor
                resp = self._client.blocks.children.list(**kwargs)
            except (APIResponseError, RequestTimeoutError) as e:
                raise _translate(e) from e
            all_blocks.extend(resp.get("results", []))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
            if not cursor:
                break  # API contract violated; avoid infinite loop
        return all_blocks

    def search_in_database(self, *, database_id: str, query: str) -> list[PageRef]:
        results: list[PageRef] = []
        cursor: str | None = None
        while True:
            try:
                kwargs: dict[str, Any] = {
                    "query": query,
                    "filter": {"property": "object", "value": "page"},
                }
                if cursor:
                    kwargs["start_cursor"] = cursor
                resp = self._client.search(**kwargs)
            except (APIResponseError, RequestTimeoutError) as e:
                raise _translate(e) from e
            for p in resp.get("results", []):
                parent = p.get("parent", {})
                if parent.get("type") != "database_id":
                    continue
                if parent.get("database_id") != database_id:
                    continue
                results.append(
                    PageRef(
                        id=p["id"],
                        title=_extract_title(p.get("properties", {})),
                        url=p.get("url", ""),
                        created_time=p.get("created_time", ""),
                    )
                )
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
            if not cursor:
                break
        return results

    def with_retry(self, fn, *, attempts: int = 3, base_delay: float = 0.5):
        """Invoke `fn()` retrying on RateLimitError with exponential backoff."""
        last: Exception | None = None
        for i in range(attempts):
            try:
                return fn()
            except RateLimitError as e:
                last = e
                if i < attempts - 1:
                    time.sleep(base_delay * (2 ** i))
        assert last is not None
        raise last
