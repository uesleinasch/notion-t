"""First-run wizard: token + database setup.

Prompts the user, validates the token through `NotionAPI.validate_token`,
and either accepts an existing database id or creates a new "Quick Notes"
database inside a parent page chosen by the user.
"""
from __future__ import annotations

import getpass
import re
from typing import Callable

from .config import Config
from .notion_api import (
    AuthError,
    NotFoundOrForbiddenError,
    NotionAPI,
    NotionError,
)

_HEX32 = re.compile(r"(?<![0-9a-fA-F])([0-9a-fA-F]{32})(?![0-9a-fA-F])")
_DASHED = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def extract_id(value: str) -> str:
    value = value.strip()
    if _DASHED.match(value):
        return value
    # Strip query string and fragment before searching so ?v=... doesn't confuse the match
    clean = re.split(r"[?#]", value)[0]
    m = _HEX32.search(clean)
    if not m:
        raise ValueError("não consegui encontrar um id Notion válido em: " + value)
    h = m.group(1)
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def _prompt(message: str) -> str:
    return input(message)


def _prompt_secret(message: str) -> str:
    return getpass.getpass(message)


def run(*, api_factory: Callable[[str], NotionAPI] = lambda t: NotionAPI(token=t)) -> Config:
    print("notion-t — primeiro acesso detectado.\n")
    print("1) Crie uma integração interna em https://www.notion.so/my-integrations")
    print("   Compartilhe a página/database alvo com a integração antes de continuar.\n")

    api: NotionAPI
    token: str
    workspace: str
    while True:
        token = _prompt_secret("token (cola aqui, não será exibido)> ").strip()
        if not token:
            print("  ✗ token vazio, tente novamente.")
            continue
        try:
            api = api_factory(token)
            workspace = api.validate_token() or "(workspace sem nome)"
        except AuthError:
            print("  ✗ token inválido. Tente outro.\n")
            continue
        except NotionError as e:
            print(f"  ✗ erro ao validar: {e}\n")
            continue
        print(f"  ✓ token validado (workspace: \"{workspace}\")\n")
        break

    print("2) Onde devem ficar suas notas?")
    print("   [1] Usar database existente")
    print("   [2] Criar database \"Quick Notes\" agora")
    while True:
        choice = _prompt("escolha> ").strip()
        if choice in ("1", "2"):
            break
        print("  escolha 1 ou 2.")

    if choice == "1":
        while True:
            raw = _prompt("URL ou ID do database> ").strip()
            try:
                database_id = extract_id(raw)
                break
            except ValueError as e:
                print(f"  ✗ {e}")
    else:
        while True:
            raw = _prompt("URL da página pai (onde criar)> ").strip()
            try:
                parent_id = extract_id(raw)
            except ValueError as e:
                print(f"  ✗ {e}")
                continue
            try:
                database_id = api.create_quick_notes_database(parent_page_id=parent_id)
            except NotFoundOrForbiddenError:
                print(
                    "  ✗ a integração não tem acesso à página. Vá na página → "
                    "⋯ → Connections → adicione sua integração e tente de novo."
                )
                continue
            except NotionError as e:
                print(f"  ✗ erro ao criar database: {e}")
                continue
            print(f"  ✓ database criado (id: {database_id})\n")
            break

    return Config(
        token=token,
        workspace=workspace,
        database_id=database_id,
        editor_command="",
        list_size=10,
    )
