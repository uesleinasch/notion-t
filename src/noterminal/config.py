"""Config persistence for notion-t.

Stores user token, workspace name, database id, and display preferences
in a TOML file at the XDG config path with mode 0600. A `schema_version`
field allows safe migration on future updates.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

import tomli_w

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Config:
    token: str
    workspace: str
    database_id: str
    editor_command: str
    list_size: int


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.environ.get("HOME", str(Path.home())), ".config"
    )
    return Path(base) / "noterminal" / "config.toml"


def _backup_corrupted(path: Path) -> None:
    backup = path.with_suffix(".toml.bak")
    try:
        path.replace(backup)
    except OSError:
        pass


def load() -> Config | None:
    path = config_path()
    if not path.exists():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        if data.get("schema_version") != SCHEMA_VERSION:
            _backup_corrupted(path)
            return None
        return Config(
            token=data["notion"]["token"],
            workspace=data["notion"]["workspace"],
            database_id=data["notion"]["database_id"],
            editor_command=data["editor"]["command"],
            list_size=int(data["display"]["list_size"]),
        )
    except (tomllib.TOMLDecodeError, KeyError, TypeError, ValueError):
        _backup_corrupted(path)
        return None


def save(cfg: Config) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "notion": {
            "token": cfg.token,
            "workspace": cfg.workspace,
            "database_id": cfg.database_id,
        },
        "editor": {"command": cfg.editor_command},
        "display": {"list_size": cfg.list_size},
    }
    tmp = path.with_suffix(".toml.tmp")
    tmp.write_bytes(tomli_w.dumps(payload).encode("utf-8"))
    os.chmod(tmp, 0o600)
    tmp.replace(path)
