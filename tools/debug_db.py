"""Quick diagnostic: dump what databases.retrieve returns for your configured DB.

Run from the repo root:
    .venv/bin/python tools/debug_db.py
"""
from __future__ import annotations

import json
import sys

from noterminal import config
from noterminal.notion_api import NotionAPI


def main() -> int:
    cfg = config.load()
    if cfg is None:
        print("nenhuma config carregada — rode `notion-t` primeiro pra fazer o setup.")
        return 1
    print(f"workspace: {cfg.workspace}")
    print(f"database_id: {cfg.database_id}")
    print()

    api = NotionAPI(token=cfg.token)

    # 1) Try as database
    print("=== databases.retrieve ===")
    try:
        db = api._client.databases.retrieve(database_id=cfg.database_id)
        print(json.dumps(db, indent=2, ensure_ascii=False)[:4000])
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")

    print()
    # 2) Try as page
    print("=== pages.retrieve (fallback) ===")
    try:
        page = api._client.pages.retrieve(page_id=cfg.database_id)
        print(json.dumps(page, indent=2, ensure_ascii=False)[:4000])
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
