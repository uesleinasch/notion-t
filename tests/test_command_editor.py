from noterminal.commands import editor as editor_cmd


class FakeConsole:
    def __init__(self):
        self.printed = []
    def print(self, *a, **k):
        self.printed.append(" ".join(str(x) for x in a))


def _no_install_called(_cmd, _console):
    raise AssertionError("install_fn should not have been called")


def _ok_install(_cmd, _console):
    return True


def _fail_install(_cmd, _console):
    return False


def test_find_editor_known():
    ed = editor_cmd._find_editor("nvim")
    assert ed is not None
    assert ed.name == "nvim"
    assert ed.binary == "nvim"


def test_find_editor_case_insensitive():
    assert editor_cmd._find_editor("VIM").name == "vim"
    assert editor_cmd._find_editor("  Emacs  ").name == "emacs"


def test_find_editor_unknown_returns_none():
    assert editor_cmd._find_editor("foobar") is None


def test_matches_current_handles_empty_string():
    ed = editor_cmd._find_editor("nano")
    assert editor_cmd._matches_current(ed, "") is False


def test_matches_current_compares_first_token():
    emacs = editor_cmd._find_editor("emacs")
    assert editor_cmd._matches_current(emacs, "emacs -nw") is True
    assert editor_cmd._matches_current(emacs, "vim") is False


def test_build_install_cmd_apt_neovim():
    nvim = editor_cmd._find_editor("nvim")
    cmd = editor_cmd._build_install_cmd(nvim, "apt")
    assert cmd == ["sudo", "apt", "install", "-y", "neovim"]


def test_build_install_cmd_dnf_emacs_uses_nox_package():
    emacs = editor_cmd._find_editor("emacs")
    cmd = editor_cmd._build_install_cmd(emacs, "dnf")
    assert cmd == ["sudo", "dnf", "install", "-y", "emacs-nox"]


def test_build_install_cmd_brew_no_sudo():
    vim = editor_cmd._find_editor("vim")
    cmd = editor_cmd._build_install_cmd(vim, "brew")
    assert cmd[0] == "brew"
    assert "sudo" not in cmd


def test_build_install_cmd_unsupported_pkg_manager_returns_none():
    helix = editor_cmd._find_editor("helix")
    assert editor_cmd._build_install_cmd(helix, "apt") is None  # helix not in apt list


def test_run_arg_unknown_editor_returns_none(monkeypatch):
    console = FakeConsole()
    result = editor_cmd.run(
        current_command="nano",
        args=["foobar"],
        console=console,
        prompt_fn=lambda _: "",
        install_fn=_no_install_called,
    )
    assert result is None
    assert any("desconhecido" in line for line in console.printed)


def test_run_arg_already_current_returns_none(monkeypatch):
    monkeypatch.setattr(editor_cmd, "_is_installed", lambda ed: True)
    console = FakeConsole()
    result = editor_cmd.run(
        current_command="nano",
        args=["nano"],
        console=console,
        prompt_fn=lambda _: "",
        install_fn=_no_install_called,
    )
    assert result is None
    assert any("já é o editor atual" in line for line in console.printed)


def test_run_arg_installed_returns_command(monkeypatch):
    monkeypatch.setattr(editor_cmd, "_is_installed", lambda ed: True)
    console = FakeConsole()
    result = editor_cmd.run(
        current_command="nano",
        args=["vim"],
        console=console,
        prompt_fn=lambda _: "",
        install_fn=_no_install_called,
    )
    assert result == "vim"


def test_run_arg_not_installed_user_declines(monkeypatch):
    monkeypatch.setattr(editor_cmd, "_is_installed", lambda ed: False)
    monkeypatch.setattr(editor_cmd, "_detect_pkg_manager", lambda: "apt")
    console = FakeConsole()
    result = editor_cmd.run(
        current_command="nano",
        args=["nvim"],
        console=console,
        prompt_fn=lambda _: "n",
        install_fn=_no_install_called,
    )
    assert result is None
    assert any("cancelada" in line for line in console.printed)


def test_run_arg_not_installed_user_accepts_install_succeeds(monkeypatch):
    states = {"installed": False}
    monkeypatch.setattr(editor_cmd, "_is_installed", lambda ed: states["installed"])
    monkeypatch.setattr(editor_cmd, "_detect_pkg_manager", lambda: "apt")

    def install(cmd, console):
        states["installed"] = True  # binary now visible
        return True

    console = FakeConsole()
    result = editor_cmd.run(
        current_command="nano",
        args=["nvim"],
        console=console,
        prompt_fn=lambda _: "s",
        install_fn=install,
    )
    assert result == "nvim"


def test_run_arg_install_succeeds_but_binary_still_missing(monkeypatch):
    monkeypatch.setattr(editor_cmd, "_is_installed", lambda ed: False)
    monkeypatch.setattr(editor_cmd, "_detect_pkg_manager", lambda: "apt")
    console = FakeConsole()
    result = editor_cmd.run(
        current_command="nano",
        args=["nvim"],
        console=console,
        prompt_fn=lambda _: "s",
        install_fn=_ok_install,  # claims success but _is_installed still False
    )
    assert result is None
    assert any("não está no PATH" in line for line in console.printed)


def test_run_arg_install_fails(monkeypatch):
    monkeypatch.setattr(editor_cmd, "_is_installed", lambda ed: False)
    monkeypatch.setattr(editor_cmd, "_detect_pkg_manager", lambda: "apt")
    console = FakeConsole()
    result = editor_cmd.run(
        current_command="nano",
        args=["nvim"],
        console=console,
        prompt_fn=lambda _: "s",
        install_fn=_fail_install,
    )
    assert result is None
    assert any("falha" in line.lower() for line in console.printed)


def test_run_arg_no_pkg_manager_detected(monkeypatch):
    monkeypatch.setattr(editor_cmd, "_is_installed", lambda ed: False)
    monkeypatch.setattr(editor_cmd, "_detect_pkg_manager", lambda: None)
    console = FakeConsole()
    result = editor_cmd.run(
        current_command="nano",
        args=["nvim"],
        console=console,
        prompt_fn=lambda _: "s",
        install_fn=_no_install_called,
    )
    assert result is None
    assert any("manualmente" in line for line in console.printed)


def test_run_interactive_lists_all_known_editors(monkeypatch):
    monkeypatch.setattr(editor_cmd, "_is_installed", lambda ed: ed.name == "nano")
    console = FakeConsole()
    result = editor_cmd.run(
        current_command="nano",
        args=[],
        console=console,
        prompt_fn=lambda _: "0",  # cancel
        install_fn=_no_install_called,
    )
    assert result is None
    text = "\n".join(console.printed)
    for ed in editor_cmd.KNOWN_EDITORS:
        assert ed.name in text


def test_run_interactive_select_installed_editor(monkeypatch):
    monkeypatch.setattr(editor_cmd, "_is_installed", lambda ed: True)
    console = FakeConsole()
    # nvim is at index 3 (1-based) in KNOWN_EDITORS: nano, vim, nvim
    result = editor_cmd.run(
        current_command="nano",
        args=[],
        console=console,
        prompt_fn=lambda _: "3",
        install_fn=_no_install_called,
    )
    assert result == "nvim"


def test_run_interactive_invalid_choice(monkeypatch):
    console = FakeConsole()
    result = editor_cmd.run(
        current_command="nano",
        args=[],
        console=console,
        prompt_fn=lambda _: "999",
        install_fn=_no_install_called,
    )
    assert result is None
    assert any("inválida" in line for line in console.printed)


def test_run_interactive_non_numeric_choice(monkeypatch):
    console = FakeConsole()
    result = editor_cmd.run(
        current_command="nano",
        args=[],
        console=console,
        prompt_fn=lambda _: "abc",
        install_fn=_no_install_called,
    )
    assert result is None


def test_run_interactive_cancel_returns_none(monkeypatch):
    console = FakeConsole()
    result = editor_cmd.run(
        current_command="nano",
        args=[],
        console=console,
        prompt_fn=lambda _: "0",
        install_fn=_no_install_called,
    )
    assert result is None


def test_run_interactive_empty_input_returns_none(monkeypatch):
    console = FakeConsole()
    result = editor_cmd.run(
        current_command="",
        args=[],
        console=console,
        prompt_fn=lambda _: "",
        install_fn=_no_install_called,
    )
    assert result is None


def test_run_interactive_marks_current_editor(monkeypatch):
    monkeypatch.setattr(editor_cmd, "_is_installed", lambda ed: True)
    console = FakeConsole()
    editor_cmd.run(
        current_command="vim",
        args=[],
        console=console,
        prompt_fn=lambda _: "0",
        install_fn=_no_install_called,
    )
    text = "\n".join(console.printed)
    assert "← atual" in text


def test_run_interactive_select_same_as_current_returns_none(monkeypatch):
    monkeypatch.setattr(editor_cmd, "_is_installed", lambda ed: True)
    console = FakeConsole()
    result = editor_cmd.run(
        current_command="nano",
        args=[],
        console=console,
        prompt_fn=lambda _: "1",  # nano is index 1
        install_fn=_no_install_called,
    )
    assert result is None
