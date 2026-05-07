"""`help` command — print available commands."""
from __future__ import annotations

from typing import Protocol


class _Console(Protocol):
    def print(self, *args, **kwargs) -> None: ...


HELP_TEXT = """[bold]Comandos disponíveis:[/bold]
  [cyan]new[/cyan]              cria uma nota nova (abre o editor)
  [cyan]list[/cyan] [N]         lista as N notas mais recentes (default 10)
  [cyan]open[/cyan] <id|N>      abre/visualiza uma nota (id, id-curto ou índice da última list)
  [cyan]<N>[/cyan]              atalho: depois de `list` ou `search`, digite só o número
  [cyan]edit[/cyan] <id|N>      abre a nota no $EDITOR para edição
  [cyan]search[/cyan] <termo>   busca notas no database
  [cyan]setup[/cyan]            reconfigura token / database
  [cyan]help[/cyan]             mostra esta ajuda
  [cyan]exit[/cyan] / [cyan]quit[/cyan] / Ctrl-D   sai do notion-t
"""


def run(*, console: _Console) -> None:
    console.print(HELP_TEXT)
