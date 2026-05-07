"""Thin wrapper over `notion-client`.

This module is the only place in the codebase that imports the Notion SDK.
Errors from the SDK are translated into a small hierarchy of `NotionError`
subclasses so callers can show friendly messages without coupling to the
SDK's exception types.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
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


@dataclass(frozen=True)
class _DBMeta:
    """Resolved schema info for a database, tolerant of multi-source layout."""
    is_multi_source: bool
    data_source_id: str | None  # only set if multi-source
    title_property: str
    date_property: str | None  # user-fillable creation date, if database has one


_CREATED_DATE_NAMES = {"created", "criado", "data", "date", "created at", "created time"}
DEFAULT_DATE_PROP_NAME = "Criado"


def _find_creation_date_prop(properties: dict[str, Any]) -> str | None:
    """Return a property name suitable for the creation date, or None.

    Only matches properties of type `date` (we never overwrite `created_time`,
    which Notion auto-populates and is read-only). Match is conservative:
    name must be in `_CREATED_DATE_NAMES` (case-insensitive).
    """
    for name, prop in properties.items():
        if not isinstance(prop, dict) or prop.get("type") != "date":
            continue
        if name.strip().lower() in _CREATED_DATE_NAMES:
            return name
    return None


def _extract_title(properties: dict[str, Any]) -> str:
    for prop in properties.values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            parts = prop.get("title", [])
            text = "".join(p.get("plain_text", "") for p in parts)
            if text:
                return text
    return "(sem título)"


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
        self._db_meta_cache: dict[str, _DBMeta] = {}

    def _find_title_prop(self, properties: dict[str, Any]) -> str | None:
        for name, prop in properties.items():
            if isinstance(prop, dict) and prop.get("type") == "title":
                return name
        return None

    def _resolve_db_meta(self, database_id: str) -> _DBMeta:
        """Resolve the title property name and detect multi-source layout.

        Notion has two database shapes in flight:
        - Classic: `databases.retrieve` returns properties inline
        - Multi-source: top-level has `data_sources: [{id, name}]` and
          properties live on each data source (fetched via the data sources
          endpoint). New databases default to this layout.
        """
        cached = self._db_meta_cache.get(database_id)
        if cached:
            return cached
        try:
            db = self._client.databases.retrieve(database_id=database_id)
        except (APIResponseError, RequestTimeoutError) as e:
            raise _translate(e) from e

        # Classic layout: properties at the top level.
        props = db.get("properties") or {}
        title_name = self._find_title_prop(props)
        if title_name:
            meta = _DBMeta(
                is_multi_source=False,
                data_source_id=None,
                title_property=title_name,
                date_property=_find_creation_date_prop(props),
            )
            self._db_meta_cache[database_id] = meta
            return meta

        # Multi-source layout: fetch the first data source for its schema.
        data_sources = db.get("data_sources") or []
        if data_sources:
            ds_id = data_sources[0].get("id")
            if ds_id:
                try:
                    ds = self._client.request(
                        path=f"data_sources/{ds_id}", method="GET"
                    )
                except (APIResponseError, RequestTimeoutError) as e:
                    raise _translate(e) from e
                ds_props = (ds or {}).get("properties") or {}
                title_name = self._find_title_prop(ds_props)
                if title_name:
                    meta = _DBMeta(
                        is_multi_source=True,
                        data_source_id=ds_id,
                        title_property=title_name,
                        date_property=_find_creation_date_prop(ds_props),
                    )
                    self._db_meta_cache[database_id] = meta
                    return meta

        kind = db.get("object", "?")
        prop_summary = (
            ", ".join(f"{n}({(p or {}).get('type', '?')})" for n, p in props.items())
            or "(nenhuma)"
        )
        raise NotionError(
            f"database {database_id} não tem propriedade do tipo 'title'. "
            f"objeto retornado: {kind}; propriedades: [{prop_summary}]. "
            f"verifique se você colou a URL do database (não de uma página) "
            f"em `setup`."
        )

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

    def _ensure_date_property(self, database_id: str) -> _DBMeta:
        """Add a default `date` property to the schema if none exists."""
        meta = self._resolve_db_meta(database_id)
        if meta.date_property:
            return meta
        body = {"properties": {DEFAULT_DATE_PROP_NAME: {"date": {}}}}
        try:
            if meta.is_multi_source and meta.data_source_id:
                self._client.request(
                    path=f"data_sources/{meta.data_source_id}",
                    method="PATCH",
                    body=body,
                )
            else:
                self._client.databases.update(database_id=database_id, **body)
        except (APIResponseError, RequestTimeoutError) as e:
            raise _translate(e) from e
        self._db_meta_cache.pop(database_id, None)
        return self._resolve_db_meta(database_id)

    def create_page(self, *, database_id: str, title: str, blocks: list[dict]) -> CreatedPage:
        meta = self._ensure_date_property(database_id)
        parent: dict[str, str] = (
            {"data_source_id": meta.data_source_id}
            if meta.is_multi_source and meta.data_source_id
            else {"database_id": database_id}
        )
        properties: dict[str, Any] = {
            meta.title_property: {
                "title": [{"type": "text", "text": {"content": title}}]
            }
        }
        if meta.date_property:
            now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
            properties[meta.date_property] = {"date": {"start": now_iso}}
        try:
            resp = self._client.pages.create(
                parent=parent,
                properties=properties,
                children=blocks,
            )
        except (APIResponseError, RequestTimeoutError) as e:
            raise _translate(e) from e
        return CreatedPage(id=resp["id"], url=resp["url"])

    def list_recent_pages(self, *, database_id: str, page_size: int = 10) -> list[PageRef]:
        meta = self._resolve_db_meta(database_id)
        sorts = [{"timestamp": "created_time", "direction": "descending"}]
        try:
            if meta.is_multi_source and meta.data_source_id:
                resp = self._client.request(
                    path=f"data_sources/{meta.data_source_id}/query",
                    method="POST",
                    body={"page_size": page_size, "sorts": sorts},
                )
            else:
                resp = self._client.databases.query(
                    database_id=database_id,
                    page_size=page_size,
                    sorts=sorts,
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

    def get_page_metadata(self, page_id: str) -> tuple[str, str]:
        """Return (title, url) for a page."""
        try:
            page = self._client.pages.retrieve(page_id=page_id)
        except (APIResponseError, RequestTimeoutError) as e:
            raise _translate(e) from e
        return _extract_title(page.get("properties") or {}), page.get("url", "")

    def update_page(self, *, page_id: str, title: str, blocks: list[dict]) -> None:
        """Update a page's title and replace its body blocks.

        Block replacement is non-atomic: existing children are deleted (Notion
        archives them) and the new blocks are appended. If a delete fails
        partway through, earlier deletes have already happened — caller should
        preserve the source markdown until this returns successfully.
        """
        try:
            page = self._client.pages.retrieve(page_id=page_id)
        except (APIResponseError, RequestTimeoutError) as e:
            raise _translate(e) from e
        title_prop: str | None = None
        for name, prop in (page.get("properties") or {}).items():
            if isinstance(prop, dict) and prop.get("type") == "title":
                title_prop = name
                break
        if not title_prop:
            raise NotionError(f"page {page_id} não tem propriedade do tipo 'title'")

        try:
            self._client.pages.update(
                page_id=page_id,
                properties={
                    title_prop: {
                        "title": [{"type": "text", "text": {"content": title}}]
                    }
                },
            )
        except (APIResponseError, RequestTimeoutError) as e:
            raise _translate(e) from e

        existing = self.get_page_blocks(page_id)
        for blk in existing:
            blk_id = blk.get("id")
            if not blk_id:
                continue
            try:
                self._client.blocks.delete(block_id=blk_id)
            except (APIResponseError, RequestTimeoutError) as e:
                raise _translate(e) from e

        if blocks:
            try:
                self._client.blocks.children.append(block_id=page_id, children=blocks)
            except (APIResponseError, RequestTimeoutError) as e:
                raise _translate(e) from e

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
        meta = self._resolve_db_meta(database_id)
        if meta.is_multi_source and meta.data_source_id:
            target_parent_type = "data_source_id"
            target_parent_id = meta.data_source_id
        else:
            target_parent_type = "database_id"
            target_parent_id = database_id
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
                if parent.get("type") != target_parent_type:
                    continue
                if parent.get(target_parent_type) != target_parent_id:
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
