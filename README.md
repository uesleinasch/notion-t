# notion-t

Interactive terminal CLI for quick Notion notes.

## Install

```
pipx install .
```

## First run

```
notion-t
```

The setup wizard will prompt for your Notion integration token and ask
where notes should live (existing database or new "Quick Notes" database
inside a parent page you choose).

## Commands inside the REPL

- `new` — opens `$EDITOR` on a markdown template; first `# heading` becomes the title
- `list [N]` — last N notes (default 10)
- `open <id|N>` — render a note (id, short id, or index from the last `list`)
- `search <term>` — Notion search filtered to your database
- `setup` — reconfigure token / database
- `help`, `exit` / `quit` / Ctrl-D

## Config

Stored at `~/.config/noterminal/config.toml` (chmod 600).

## Development

```
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```
