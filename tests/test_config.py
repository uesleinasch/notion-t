import os
import stat
from pathlib import Path

import pytest

from noterminal import config


@pytest.fixture
def tmp_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_config_path_uses_xdg(tmp_home):
    expected = tmp_home / "xdg" / "noterminal" / "config.toml"
    assert config.config_path() == expected


def test_load_returns_none_when_missing(tmp_home):
    assert config.load() is None


def test_save_then_load_roundtrip(tmp_home):
    cfg = config.Config(
        token="ntn_x",
        workspace="W",
        database_id="db_1",
        editor_command="",
        list_size=10,
    )
    config.save(cfg)
    loaded = config.load()
    assert loaded == cfg


def test_save_writes_chmod_600(tmp_home):
    cfg = config.Config(
        token="ntn_x", workspace="W", database_id="db_1",
        editor_command="", list_size=10,
    )
    config.save(cfg)
    mode = stat.S_IMODE(os.stat(config.config_path()).st_mode)
    assert mode == 0o600


def test_load_corrupted_returns_none_and_backs_up(tmp_home):
    config.config_path().parent.mkdir(parents=True, exist_ok=True)
    config.config_path().write_text("not valid toml = = =")
    assert config.load() is None
    assert config.config_path().with_suffix(".toml.bak").exists()


def test_load_missing_field_returns_none_and_backs_up(tmp_home):
    config.config_path().parent.mkdir(parents=True, exist_ok=True)
    config.config_path().write_text('schema_version = 1\n[notion]\ntoken = "x"\n')
    assert config.load() is None
    assert config.config_path().with_suffix(".toml.bak").exists()


def test_unknown_schema_version_returns_none(tmp_home):
    config.config_path().parent.mkdir(parents=True, exist_ok=True)
    config.config_path().write_text(
        'schema_version = 99\n'
        '[notion]\ntoken = "x"\nworkspace = "W"\ndatabase_id = "d"\n'
        '[editor]\ncommand = ""\n'
        '[display]\nlist_size = 10\n'
    )
    assert config.load() is None
    assert config.config_path().with_suffix(".toml.bak").exists()
