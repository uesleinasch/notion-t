from unittest.mock import MagicMock

import pytest

from noterminal import setup_wizard
from noterminal.config import Config


def test_extract_id_from_url_with_dashes():
    url = "https://www.notion.so/page-Title-2c5a8e3a4d4b4f8a8e3a4d4b4f8a8e3a"
    assert setup_wizard.extract_id(url) == "2c5a8e3a-4d4b-4f8a-8e3a-4d4b4f8a8e3a"


def test_extract_id_passes_through_already_dashed():
    raw = "2c5a8e3a-4d4b-4f8a-8e3a-4d4b4f8a8e3a"
    assert setup_wizard.extract_id(raw) == raw


def test_extract_id_rejects_garbage():
    with pytest.raises(ValueError):
        setup_wizard.extract_id("not a url")


def test_run_full_flow_creating_database(monkeypatch):
    api = MagicMock()
    api.validate_token.return_value = "WS"
    api.create_quick_notes_database.return_value = "db123"

    inputs = iter([
        "ntn_secret",                                   # token
        "2",                                            # create new
        "https://www.notion.so/Inbox-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",  # parent page URL
    ])
    monkeypatch.setattr(setup_wizard, "_prompt_secret", lambda *_: next(inputs))
    monkeypatch.setattr(setup_wizard, "_prompt", lambda *_: next(inputs))

    cfg = setup_wizard.run(api_factory=lambda token: api)

    assert cfg == Config(
        token="ntn_secret",
        workspace="WS",
        database_id="db123",
        editor_command="",
        list_size=10,
    )
    api.validate_token.assert_called_once()
    api.create_quick_notes_database.assert_called_once()


def test_run_full_flow_using_existing_database(monkeypatch):
    api = MagicMock()
    api.validate_token.return_value = "WS"

    inputs = iter([
        "ntn_secret",
        "1",
        "https://www.notion.so/db-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    ])
    monkeypatch.setattr(setup_wizard, "_prompt_secret", lambda *_: next(inputs))
    monkeypatch.setattr(setup_wizard, "_prompt", lambda *_: next(inputs))

    cfg = setup_wizard.run(api_factory=lambda token: api)

    assert cfg.database_id == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    api.create_quick_notes_database.assert_not_called()


def test_invalid_token_re_prompts(monkeypatch):
    from noterminal.notion_api import AuthError

    bad_api = MagicMock()
    bad_api.validate_token.side_effect = AuthError("nope")
    good_api = MagicMock()
    good_api.validate_token.return_value = "WS"

    apis = iter([bad_api, good_api])
    inputs = iter([
        "ntn_bad",
        "ntn_good",
        "1",
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    ])
    monkeypatch.setattr(setup_wizard, "_prompt_secret", lambda *_: next(inputs))
    monkeypatch.setattr(setup_wizard, "_prompt", lambda *_: next(inputs))

    cfg = setup_wizard.run(api_factory=lambda token: next(apis))
    assert cfg.token == "ntn_good"
