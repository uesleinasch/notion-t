"""Markdown <-> Notion blocks for the v1 feature set.

Supports: paragraphs, headings (#/##/###), bulleted (-) and numbered (1.) lists,
fenced code blocks (```), and inline **bold**, *italic*, `code`, [text](url).
Anything outside this subset falls back to a plain paragraph; the converter
never raises on malformed input.
"""
from __future__ import annotations

import re

MAX_TITLE_LEN = 200

_FENCE = re.compile(r"^```(.*)$")
_HEADING = re.compile(r"^(#{1,3})\s+(.*)$")
_BULLET = re.compile(r"^[-*]\s+(.*)$")
_NUMBERED = re.compile(r"^\d+\.\s+(.*)$")

_INLINE = re.compile(
    r"(\*\*([^*]+)\*\*"        # **bold**
    r"|\*([^*]+)\*"             # *italic*
    r"|`([^`]+)`"               # `code`
    r"|\[([^\]]+)\]\(([^)]+)\))"  # [text](url)
)


def _make_text(content: str, *, bold=False, italic=False, code=False, url: str | None = None) -> dict:
    rt: dict = {
        "type": "text",
        "text": {"content": content},
        "annotations": {
            "bold": bold,
            "italic": italic,
            "strikethrough": False,
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
        bold, italic, code, link_text, link_url = m.group(2, 3, 4, 5, 6)
        if bold is not None:
            out.append(_make_text(bold, bold=True))
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


def _code_block(language: str, content: str) -> dict:
    return {
        "object": "block",
        "type": "code",
        "code": {
            "language": language or "plain text",
            "rich_text": [_make_text(content)],
        },
    }


def to_blocks(md: str) -> list[dict]:
    if not md.strip():
        return []
    lines = md.splitlines()
    blocks: list[dict] = []
    paragraph_buf: list[str] = []

    def flush_paragraph():
        if paragraph_buf:
            blocks.append(_block("paragraph", " ".join(paragraph_buf).strip()))
            paragraph_buf.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        fence = _FENCE.match(line)
        if fence:
            flush_paragraph()
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
            i += 1
            continue
        h = _HEADING.match(line)
        if h:
            flush_paragraph()
            level = len(h.group(1))
            blocks.append(_block(f"heading_{level}", h.group(2).strip()))
            i += 1
            continue
        b = _BULLET.match(line)
        if b:
            flush_paragraph()
            blocks.append(_block("bulleted_list_item", b.group(1)))
            i += 1
            continue
        n = _NUMBERED.match(line)
        if n:
            flush_paragraph()
            blocks.append(_block("numbered_list_item", n.group(1)))
            i += 1
            continue
        paragraph_buf.append(line)
        i += 1
    flush_paragraph()
    return blocks


def _rich_text_plain(rich_text: list[dict]) -> str:
    return "".join(rt.get("plain_text", "") for rt in rich_text)


def from_blocks(blocks: list[dict]) -> str:
    out: list[str] = []
    for b in blocks:
        kind = b.get("type")
        body = b.get(kind, {})
        text = _rich_text_plain(body.get("rich_text", []))
        if kind == "paragraph":
            out.append(text)
        elif kind == "heading_1":
            out.append(f"# {text}")
        elif kind == "heading_2":
            out.append(f"## {text}")
        elif kind == "heading_3":
            out.append(f"### {text}")
        elif kind == "bulleted_list_item":
            out.append(f"- {text}")
        elif kind == "numbered_list_item":
            out.append(f"1. {text}")
        elif kind == "code":
            lang = body.get("language", "")
            out.append(f"```{lang}\n{text}\n```")
        else:
            out.append(text)
    return "\n\n".join(out)


def split_title(md: str) -> tuple[str, str]:
    """Return (title, body). Title is the first '# ...' heading or the first non-blank line."""
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
