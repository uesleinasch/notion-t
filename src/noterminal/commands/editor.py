"""`editor` command — choose/install the editor used by `new` and `edit`.

The chosen string is persisted into `editor.command` of `config.toml`. Helix
is registered as `hx` (its real binary name); emacs runs in terminal mode
via `emacs -nw`.
"""
from __future__ import annotations

import shlex
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable, Protocol


class _Console(Protocol):
    def print(self, *args, **kwargs) -> None: ...


@dataclass(frozen=True)
class _Editor:
    name: str
    description: str
    binary: str
    command: str
    packages: dict[str, str]


KNOWN_EDITORS: list[_Editor] = [
    _Editor(
        "nano", "padrão simples e amigável", "nano", "nano",
        {"apt": "nano", "dnf": "nano", "pacman": "nano",
         "brew": "nano", "zypper": "nano", "apk": "nano"},
    ),
    _Editor(
        "vim", "Vi IMproved", "vim", "vim",
        {"apt": "vim", "dnf": "vim-enhanced", "pacman": "vim",
         "brew": "vim", "zypper": "vim", "apk": "vim"},
    ),
    _Editor(
        "nvim", "Neovim — Vim modernizado", "nvim", "nvim",
        {"apt": "neovim", "dnf": "neovim", "pacman": "neovim",
         "brew": "neovim", "zypper": "neovim", "apk": "neovim"},
    ),
    _Editor(
        "micro", "moderno, mouse e atalhos comuns", "micro", "micro",
        {"apt": "micro", "dnf": "micro", "pacman": "micro",
         "brew": "micro", "zypper": "micro", "apk": "micro"},
    ),
    _Editor(
        "helix", "modal pós-Vim (binário 'hx')", "hx", "hx",
        {"dnf": "helix", "pacman": "helix", "brew": "helix"},
    ),
    _Editor(
        "emacs", "GNU Emacs em modo terminal", "emacs", "emacs -nw",
        {"apt": "emacs-nox", "dnf": "emacs-nox", "pacman": "emacs",
         "brew": "emacs", "zypper": "emacs"},
    ),
]


_PKG_MANAGERS = ("apt", "dnf", "pacman", "brew", "zypper", "apk")

_INSTALL_PREFIX: dict[str, list[str]] = {
    "apt": ["sudo", "apt", "install", "-y"],
    "dnf": ["sudo", "dnf", "install", "-y"],
    "pacman": ["sudo", "pacman", "-S", "--noconfirm"],
    "brew": ["brew", "install"],
    "zypper": ["sudo", "zypper", "install", "-y"],
    "apk": ["sudo", "apk", "add"],
}


def _find_editor(name: str) -> _Editor | None:
    name = name.strip().lower()
    for ed in KNOWN_EDITORS:
        if ed.name == name:
            return ed
    return None


def _is_installed(ed: _Editor) -> bool:
    return shutil.which(ed.binary) is not None


def _detect_pkg_manager() -> str | None:
    for pm in _PKG_MANAGERS:
        if shutil.which(pm):
            return pm
    return None


def _build_install_cmd(ed: _Editor, pm: str) -> list[str] | None:
    pkg = ed.packages.get(pm)
    if not pkg:
        return None
    return _INSTALL_PREFIX[pm] + [pkg]


def _default_prompt(message: str) -> str:
    return input(message)


def _default_install(cmd: list[str], console: _Console) -> bool:
    console.print(f"[dim]$ {' '.join(cmd)}[/dim]")
    try:
        result = subprocess.run(cmd)
    except (FileNotFoundError, KeyboardInterrupt) as e:
        console.print(f"[red]instalação interrompida:[/red] {e}")
        return False
    return result.returncode == 0


def _matches_current(ed: _Editor, current: str) -> bool:
    """True if `current` resolves to the same binary as `ed`."""
    if not current:
        return False
    try:
        first = shlex.split(current)[0]
    except (ValueError, IndexError):
        return False
    return first == ed.binary


def _confirm_install(
    ed: _Editor,
    console: _Console,
    prompt_fn: Callable[[str], str],
    install_fn: Callable[[list[str], _Console], bool],
) -> bool:
    """Returns True if the editor ends up installed and ready to use."""
    if _is_installed(ed):
        return True
    pm = _detect_pkg_manager()
    install_cmd = _build_install_cmd(ed, pm) if pm else None
    console.print(f"[yellow]'{ed.name}' não está instalado.[/yellow]")
    if not install_cmd:
        console.print(
            "  [dim]nenhum gerenciador de pacote conhecido detectado, "
            "ou pacote indisponível para este gerenciador. instale manualmente.[/dim]"
        )
        return False
    console.print(f"  comando: [dim]{' '.join(install_cmd)}[/dim]")
    answer = prompt_fn("instalar agora? [s/N] ").strip().lower()
    if answer not in ("s", "sim", "y", "yes"):
        console.print("[dim]instalação cancelada.[/dim]")
        return False
    if not install_fn(install_cmd, console):
        console.print("[red]falha na instalação.[/red]")
        return False
    if not _is_installed(ed):
        console.print(
            "[yellow]instalação reportou sucesso mas o binário não está no PATH.[/yellow]"
        )
        return False
    console.print(f"[green]✓[/green] {ed.name} instalado")
    return True


def _show_menu(current: str, console: _Console) -> None:
    if current:
        console.print(f"editor atual: [cyan]{current}[/cyan]\n")
    else:
        console.print("editor atual: [dim](usando $EDITOR ou nano como fallback)[/dim]\n")
    console.print("[bold]editores disponíveis:[/bold]")
    for i, ed in enumerate(KNOWN_EDITORS, 1):
        status = (
            "[green]instalado[/green]"
            if _is_installed(ed)
            else "[dim]não instalado[/dim]"
        )
        marker = " [yellow]← atual[/yellow]" if _matches_current(ed, current) else ""
        console.print(
            f"  [{i}] {ed.name:<6} — {ed.description} ({status}){marker}"
        )
    console.print("  [0] cancelar")


def run(
    *,
    current_command: str,
    args: list[str],
    console: _Console,
    prompt_fn: Callable[[str], str] = _default_prompt,
    install_fn: Callable[[list[str], _Console], bool] = _default_install,
) -> str | None:
    """Returns the new editor command string if changed, else None."""
    if args:
        ed = _find_editor(args[0])
        if ed is None:
            console.print(
                f"[red]editor desconhecido:[/red] {args[0]}. "
                "rode [cyan]editor[/cyan] sem args para listar."
            )
            return None
        if _matches_current(ed, current_command):
            console.print(f"[dim]'{ed.name}' já é o editor atual.[/dim]")
            return None
        if not _confirm_install(ed, console, prompt_fn, install_fn):
            return None
        return ed.command

    _show_menu(current_command, console)
    answer = prompt_fn("escolha> ").strip()
    if not answer or answer == "0":
        console.print("[dim]nenhuma mudança.[/dim]")
        return None
    if not answer.isdigit() or not (1 <= int(answer) <= len(KNOWN_EDITORS)):
        console.print("[red]escolha inválida.[/red]")
        return None
    ed = KNOWN_EDITORS[int(answer) - 1]
    if _matches_current(ed, current_command):
        console.print(f"[dim]'{ed.name}' já é o editor atual.[/dim]")
        return None
    if not _confirm_install(ed, console, prompt_fn, install_fn):
        return None
    return ed.command
