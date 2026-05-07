from noterminal.commands import help as help_cmd


class FakeConsole:
    def __init__(self):
        self.printed = []
    def print(self, *a, **k):
        self.printed.append(" ".join(str(x) for x in a))


def test_help_lists_all_commands():
    console = FakeConsole()
    help_cmd.run(console=console)
    text = "\n".join(console.printed)
    for cmd in ("new", "list", "open", "search", "setup", "help", "exit"):
        assert cmd in text
