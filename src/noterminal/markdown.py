"""Markdown <-> Notion blocks.

`from_blocks` is a lossy display path used by `open` — inline annotations are
dropped and Notion only returns top-level children, so nested list items
written via `to_blocks` won't reappear when the page is re-opened.
"""
from __future__ import annotations

import re

MAX_TITLE_LEN = 200

_FENCE = re.compile(r"^```(.*)$")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET = re.compile(r"^([ \t]*)[-*+]\s+(.*)$")
_NUMBERED = re.compile(r"^([ \t]*)\d+\.\s+(.*)$")
_TODO = re.compile(r"^([ \t]*)[-*+]\s+\[([ xX])\]\s*(.*)$")
_QUOTE = re.compile(r"^>\s?(.*)$")
_HR = re.compile(r"^[ \t]*(?:-[ \t]*){3,}$|^[ \t]*(?:\*[ \t]*){3,}$|^[ \t]*(?:_[ \t]*){3,}$")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")

_INLINE = re.compile(
    r"(\*\*([^*]+)\*\*"           # **bold**
    r"|~~([^~]+)~~"                # ~~strike~~
    r"|\*([^*]+)\*"                # *italic*
    r"|`([^`]+)`"                  # `code`
    r"|\[([^\]]+)\]\(([^)]+)\))"   # [text](url)
)

_NOTION_LANGUAGES = frozenset({
    "abap", "abc", "agda", "arduino", "ascii art", "assembly", "bash", "basic",
    "bnf", "c", "c#", "c++", "clojure", "coffeescript", "coq", "css", "dart",
    "dhall", "diff", "docker", "ebnf", "elixir", "elm", "erlang", "f#", "flow",
    "fortran", "gherkin", "glsl", "go", "graphql", "groovy", "haskell", "hcl",
    "html", "idris", "java", "javascript", "json", "julia", "kotlin", "latex",
    "less", "lisp", "livescript", "llvm ir", "lua", "makefile", "markdown",
    "markup", "matlab", "mathematica", "mermaid", "nix", "notion formula",
    "objective-c", "ocaml", "pascal", "perl", "php", "plain text", "powershell",
    "prolog", "protobuf", "purescript", "python", "r", "racket", "reason",
    "ruby", "rust", "sass", "scala", "scheme", "scss", "shell", "smalltalk",
    "solidity", "sql", "swift", "toml", "typescript", "vb.net", "verilog",
    "vhdl", "visual basic", "webassembly", "xml", "yaml", "java/c/c++/c#",
})

_LANG_ALIASES = {
    "cs": "c#", "csharp": "c#",
    "cpp": "c++", "cplusplus": "c++",
    "fs": "f#", "fsharp": "f#",
    "objc": "objective-c", "objectivec": "objective-c",
    "vb": "vb.net", "visualbasic": "visual basic",
    "js": "javascript", "jsx": "javascript", "node": "javascript",
    "ts": "typescript", "tsx": "typescript",
    "py": "python", "py3": "python", "python3": "python",
    "rs": "rust",
    "rb": "ruby",
    "sh": "shell", "zsh": "shell", "bash-script": "bash",
    "yml": "yaml",
    "md": "markdown",
    "tf": "hcl", "terraform": "hcl",
    "dockerfile": "docker",
    "text": "plain text", "txt": "plain text", "plaintext": "plain text",
    "asm": "assembly",
    "wat": "webassembly", "wasm": "webassembly",
    "tex": "latex",
    "ps1": "powershell", "pwsh": "powershell",
    "make": "makefile", "mk": "makefile",
    "ino": "arduino",
    "kt": "kotlin", "kts": "kotlin",
    "html5": "html",
    "css3": "css",
    "proto": "protobuf",
    "pl": "perl",
    "rkt": "racket",
    "ml": "ocaml",
    "hs": "haskell",
    "ex": "elixir", "exs": "elixir",
    "erl": "erlang",
    "lua-script": "lua",
    "graphql-schema": "graphql", "gql": "graphql",
    "sol": "solidity",
}


def _normalize_language(lang: str) -> str:
    """Map a fenced-code language tag to a Notion-supported value.

    Unknown languages fall back to ``"plain text"`` silently — the alternative
    (raising) would break note creation for any markdown the user pastes from
    elsewhere.
    """
    if not isinstance(lang, str):
        return "plain text"
    key = lang.strip().lower()
    if not key:
        return "plain text"
    if key in _NOTION_LANGUAGES:
        return key
    return _LANG_ALIASES.get(key, "plain text")


def _make_text(
    content: str,
    *,
    bold: bool = False,
    italic: bool = False,
    code: bool = False,
    strikethrough: bool = False,
    url: str | None = None,
) -> dict:
    rt: dict = {
        "type": "text",
        "text": {"content": content},
        "annotations": {
            "bold": bold,
            "italic": italic,
            "strikethrough": strikethrough,
            "underline": False,
            "code": code,
            "color": "default",
        },
        "plain_text": content,
    }
    if url:
        rt["text"]["link"] = {"url": url}
        rt["href"] = url
    return rt


def _parse_inline(line: str) -> list[dict]:
    out: list[dict] = []
    pos = 0
    for m in _INLINE.finditer(line):
        if m.start() > pos:
            out.append(_make_text(line[pos:m.start()]))
        bold, strike, italic, code, link_text, link_url = m.group(2, 3, 4, 5, 6, 7)
        if bold is not None:
            out.append(_make_text(bold, bold=True))
        elif strike is not None:
            out.append(_make_text(strike, strikethrough=True))
        elif italic is not None:
            out.append(_make_text(italic, italic=True))
        elif code is not None:
            out.append(_make_text(code, code=True))
        else:
            out.append(_make_text(link_text, url=link_url))
        pos = m.end()
    if pos < len(line):
        out.append(_make_text(line[pos:]))
    if not out:
        out.append(_make_text(""))
    return out


def _block(kind: str, text: str) -> dict:
    return {"object": "block", "type": kind, kind: {"rich_text": _parse_inline(text)}}


def _paragraph_bold(text: str) -> dict:
    rt = _parse_inline(text)
    for t in rt:
        t["annotations"]["bold"] = True
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": rt}}


def _code_block(language: str, content: str) -> dict:
    return {
        "object": "block",
        "type": "code",
        "code": {
            "language": _normalize_language(language),
            "rich_text": [_make_text(content)],
        },
    }


def _quote_block(text: str) -> dict:
    return {"object": "block", "type": "quote", "quote": {"rich_text": _parse_inline(text)}}


def _divider_block() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _todo_block(text: str, checked: bool) -> dict:
    return {
        "object": "block",
        "type": "to_do",
        "to_do": {"rich_text": _parse_inline(text), "checked": checked},
    }


def _split_table_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _is_table_separator(line: str) -> bool:
    if not _TABLE_ROW.match(line):
        return False
    cells = _split_table_row(line)
    if not cells:
        return False
    return all(re.match(r"^:?-{3,}:?$", c) for c in cells)


def _table_block(rows: list[list[str]]) -> dict:
    width = max((len(r) for r in rows), default=0)
    table_rows: list[dict] = []
    for row in rows:
        cells = [_parse_inline(c) for c in row]
        while len(cells) < width:
            cells.append([])
        table_rows.append({
            "object": "block",
            "type": "table_row",
            "table_row": {"cells": cells},
        })
    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": width,
            "has_column_header": True,
            "has_row_header": False,
            "children": table_rows,
        },
    }


def _indent_level(indent: str) -> int:
    """Tab = 1 level, 2 spaces = 1 level. Mixed allowed; remainder ignored."""
    return indent.count("\t") + indent.count(" ") // 2


def to_blocks(md: str) -> list[dict]:
    if not isinstance(md, str) or not md.strip():
        return []
    lines = md.splitlines()
    blocks: list[dict] = []
    paragraph_buf: list[str] = []
    quote_buf: list[str] = []
    list_stack: list[dict] = []  # entries: {"level": int, "append": callable}

    def flush_paragraph() -> None:
        if paragraph_buf:
            blocks.append(_block("paragraph", " ".join(paragraph_buf).strip()))
            paragraph_buf.clear()

    def flush_quote() -> None:
        if quote_buf:
            blocks.append(_quote_block("\n".join(quote_buf)))
            quote_buf.clear()

    def flush_lists() -> None:
        list_stack.clear()

    def flush_all() -> None:
        flush_paragraph()
        flush_quote()
        flush_lists()

    def list_parent_append(level: int):
        while list_stack and list_stack[-1]["level"] >= level:
            list_stack.pop()
        if list_stack:
            return list_stack[-1]["append"]
        return blocks.append

    def push_list_item(level: int, item: dict) -> None:
        body = item[item["type"]]

        def append_child(child: dict, _body=body) -> None:
            _body.setdefault("children", []).append(child)

        list_stack.append({"level": level, "append": append_child})

    def emit_list_item(item: dict, level: int) -> None:
        flush_paragraph()
        flush_quote()
        list_parent_append(level)(item)
        push_list_item(level, item)

    i = 0
    while i < len(lines):
        line = lines[i]

        fence = _FENCE.match(line)
        if fence:
            flush_all()
            lang = fence.group(1).strip()
            i += 1
            code_lines: list[str] = []
            while i < len(lines) and not _FENCE.match(lines[i]):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence (or EOF)
            blocks.append(_code_block(lang, "\n".join(code_lines)))
            continue

        if not line.strip():
            flush_paragraph()
            flush_quote()
            flush_lists()
            i += 1
            continue

        if _HR.match(line):
            flush_all()
            blocks.append(_divider_block())
            i += 1
            continue

        if (
            _TABLE_ROW.match(line)
            and i + 1 < len(lines)
            and _is_table_separator(lines[i + 1])
        ):
            flush_all()
            header = _split_table_row(line)
            i += 2  # skip header + separator
            data_rows: list[list[str]] = []
            while i < len(lines) and _TABLE_ROW.match(lines[i]) and not _is_table_separator(lines[i]):
                data_rows.append(_split_table_row(lines[i]))
                i += 1
            blocks.append(_table_block([header] + data_rows))
            continue

        h = _HEADING.match(line)
        if h:
            flush_all()
            level = len(h.group(1))
            text = h.group(2).strip()
            if level <= 4:
                blocks.append(_block(f"heading_{level}", text))
            else:
                blocks.append(_paragraph_bold(text))
            i += 1
            continue

        t = _TODO.match(line)
        if t:
            level = _indent_level(t.group(1))
            checked = t.group(2).lower() == "x"
            emit_list_item(_todo_block(t.group(3), checked), level)
            i += 1
            continue

        # _BULLET also matches todo lines; _TODO above must run first.
        b = _BULLET.match(line)
        if b:
            level = _indent_level(b.group(1))
            emit_list_item(_block("bulleted_list_item", b.group(2)), level)
            i += 1
            continue

        n = _NUMBERED.match(line)
        if n:
            level = _indent_level(n.group(1))
            emit_list_item(_block("numbered_list_item", n.group(2)), level)
            i += 1
            continue

        q = _QUOTE.match(line)
        if q:
            flush_paragraph()
            flush_lists()
            quote_buf.append(q.group(1))
            i += 1
            continue

        flush_quote()
        flush_lists()
        paragraph_buf.append(line)
        i += 1

    flush_all()
    return blocks


def _rich_text_plain(rich_text: list[dict]) -> str:
    return "".join(rt.get("plain_text", "") for rt in rich_text)


def _render_table(block: dict) -> str:
    body = block.get("table", {})
    width = body.get("table_width", 0)
    rows = body.get("children", [])
    if not rows or not width:
        return ""
    lines: list[str] = []
    for r in rows:
        cells = r.get("table_row", {}).get("cells", [])
        texts = [_rich_text_plain(c) for c in cells]
        while len(texts) < width:
            texts.append("")
        lines.append("| " + " | ".join(texts) + " |")
    if body.get("has_column_header"):
        sep = "| " + " | ".join(["---"] * width) + " |"
        lines.insert(1, sep)
    return "\n".join(lines)


def from_blocks(blocks: list[dict]) -> str:
    out: list[str] = []
    for b in blocks:
        kind = b.get("type")
        body = b.get(kind, {})
        if kind == "divider":
            out.append("---")
            continue
        if kind == "table":
            rendered = _render_table(b)
            if rendered:
                out.append(rendered)
            continue
        text = _rich_text_plain(body.get("rich_text", []))
        if kind == "paragraph":
            out.append(text)
        elif kind == "heading_1":
            out.append(f"# {text}")
        elif kind == "heading_2":
            out.append(f"## {text}")
        elif kind == "heading_3":
            out.append(f"### {text}")
        elif kind == "heading_4":
            out.append(f"#### {text}")
        elif kind == "bulleted_list_item":
            out.append(f"- {text}")
        elif kind == "numbered_list_item":
            out.append(f"1. {text}")
        elif kind == "to_do":
            mark = "x" if body.get("checked") else " "
            out.append(f"- [{mark}] {text}")
        elif kind == "quote":
            out.append("\n".join(f"> {ln}" for ln in text.split("\n")))
        elif kind == "code":
            lang = body.get("language", "")
            out.append(f"```{lang}\n{text}\n```")
        else:
            out.append(text)
    return "\n\n".join(out)


def split_title(md: str) -> tuple[str, str]:
    """Return (title, body). Title is the first '# ...' heading or the first non-blank line."""
    if not isinstance(md, str):
        return "", ""
    lines = md.splitlines()
    title = ""
    title_idx: int | None = None
    for idx, line in enumerate(lines):
        if not line.strip():
            continue
        h = _HEADING.match(line)
        if h and len(h.group(1)) == 1:
            title = h.group(2).strip()
            title_idx = idx
            break
        title = line.strip()
        title_idx = idx
        break
    if title_idx is None:
        return "", md
    body = "\n".join(lines[title_idx + 1:])
    if len(title) > MAX_TITLE_LEN:
        title = title[:MAX_TITLE_LEN]
    return title, body
