from noterminal import markdown


def _rt(b):
    return b[b["type"]]["rich_text"]


def test_empty_markdown_yields_no_blocks():
    assert markdown.to_blocks("") == []


def test_paragraph():
    blocks = markdown.to_blocks("hello world")
    assert len(blocks) == 1
    assert blocks[0]["type"] == "paragraph"
    assert _rt(blocks[0])[0]["text"]["content"] == "hello world"


def test_headings_levels_1_2_3():
    md = "# H1\n## H2\n### H3"
    blocks = markdown.to_blocks(md)
    assert [b["type"] for b in blocks] == ["heading_1", "heading_2", "heading_3"]
    assert _rt(blocks[0])[0]["text"]["content"] == "H1"
    assert _rt(blocks[2])[0]["text"]["content"] == "H3"


def test_heading_4_supported_natively():
    blocks = markdown.to_blocks("#### H4")
    assert blocks[0]["type"] == "heading_4"
    assert _rt(blocks[0])[0]["text"]["content"] == "H4"


def test_heading_5_falls_back_to_paragraph_with_bold():
    blocks = markdown.to_blocks("##### H5")
    assert blocks[0]["type"] == "paragraph"
    rt = _rt(blocks[0])
    assert rt[0]["text"]["content"] == "H5"
    assert rt[0]["annotations"]["bold"] is True


def test_heading_6_falls_back_to_paragraph_with_bold():
    blocks = markdown.to_blocks("###### H6")
    assert blocks[0]["type"] == "paragraph"
    assert _rt(blocks[0])[0]["annotations"]["bold"] is True


def test_bulleted_list():
    md = "- a\n- b\n- c"
    blocks = markdown.to_blocks(md)
    assert all(b["type"] == "bulleted_list_item" for b in blocks)
    assert [_rt(b)[0]["text"]["content"] for b in blocks] == ["a", "b", "c"]


def test_numbered_list():
    md = "1. one\n2. two"
    blocks = markdown.to_blocks(md)
    assert all(b["type"] == "numbered_list_item" for b in blocks)
    assert [_rt(b)[0]["text"]["content"] for b in blocks] == ["one", "two"]


def test_nested_bulleted_list_with_two_spaces():
    md = "- top\n  - child\n  - sibling"
    blocks = markdown.to_blocks(md)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "bulleted_list_item"
    children = blocks[0]["bulleted_list_item"]["children"]
    assert len(children) == 2
    assert [_rt(c)[0]["text"]["content"] for c in children] == ["child", "sibling"]


def test_nested_list_with_tab_indent():
    md = "- top\n\t- child"
    blocks = markdown.to_blocks(md)
    children = blocks[0]["bulleted_list_item"]["children"]
    assert len(children) == 1
    assert _rt(children[0])[0]["text"]["content"] == "child"


def test_nested_mixed_bullet_and_numbered():
    md = "- top\n  1. one\n  2. two"
    blocks = markdown.to_blocks(md)
    children = blocks[0]["bulleted_list_item"]["children"]
    assert [c["type"] for c in children] == ["numbered_list_item", "numbered_list_item"]


def test_three_level_nesting():
    md = "- a\n  - b\n    - c"
    blocks = markdown.to_blocks(md)
    a = blocks[0]
    b = a["bulleted_list_item"]["children"][0]
    c = b["bulleted_list_item"]["children"][0]
    assert _rt(c)[0]["text"]["content"] == "c"


def test_top_level_list_item_with_no_children_has_no_children_key():
    blocks = markdown.to_blocks("- only")
    assert "children" not in blocks[0]["bulleted_list_item"]


def test_code_fence_with_language():
    md = "```python\nprint('hi')\n```"
    blocks = markdown.to_blocks(md)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "code"
    assert blocks[0]["code"]["language"] == "python"
    assert _rt(blocks[0])[0]["text"]["content"] == "print('hi')"


def test_code_fence_without_language_defaults_to_plain_text():
    md = "```\nfoo\n```"
    blocks = markdown.to_blocks(md)
    assert blocks[0]["code"]["language"] == "plain text"


def test_code_fence_csharp_alias_maps_to_c_sharp():
    blocks = markdown.to_blocks("```csharp\nvar x = 1;\n```")
    assert blocks[0]["code"]["language"] == "c#"


def test_code_fence_terraform_alias_maps_to_hcl():
    blocks = markdown.to_blocks("```terraform\nresource \"x\" \"y\" {}\n```")
    assert blocks[0]["code"]["language"] == "hcl"


def test_code_fence_unknown_language_falls_back_to_plain_text():
    blocks = markdown.to_blocks("```foobar-lang\ncontent\n```")
    assert blocks[0]["code"]["language"] == "plain text"


def test_code_fence_canonical_language_passes_through():
    blocks = markdown.to_blocks("```c#\nint x = 1;\n```")
    assert blocks[0]["code"]["language"] == "c#"


def test_code_fence_common_aliases():
    cases = {
        "js": "javascript",
        "ts": "typescript",
        "py": "python",
        "rs": "rust",
        "yml": "yaml",
        "dockerfile": "docker",
        "tf": "hcl",
        "cpp": "c++",
        "fs": "f#",
        "objc": "objective-c",
        "vb": "vb.net",
    }
    for alias, expected in cases.items():
        blocks = markdown.to_blocks(f"```{alias}\nx\n```")
        assert blocks[0]["code"]["language"] == expected, alias


def test_inline_bold_italic_code_link():
    md = "this is **bold** and *italic* and `code` and [link](https://x.y)"
    blocks = markdown.to_blocks(md)
    rt = _rt(blocks[0])
    contents = [r["text"]["content"] for r in rt]
    assert "bold" in contents
    assert "italic" in contents
    assert "code" in contents
    annotations = {r["text"]["content"]: r["annotations"] for r in rt}
    assert annotations["bold"]["bold"] is True
    assert annotations["italic"]["italic"] is True
    assert annotations["code"]["code"] is True
    link_rt = next(r for r in rt if r["text"]["content"] == "link")
    assert link_rt["text"]["link"] == {"url": "https://x.y"}


def test_inline_strikethrough():
    blocks = markdown.to_blocks("foo ~~deleted~~ bar")
    rt = _rt(blocks[0])
    strike = next(r for r in rt if r["text"]["content"] == "deleted")
    assert strike["annotations"]["strikethrough"] is True


def test_blank_lines_separate_paragraphs():
    md = "first\n\nsecond"
    blocks = markdown.to_blocks(md)
    assert len(blocks) == 2
    assert _rt(blocks[0])[0]["text"]["content"] == "first"
    assert _rt(blocks[1])[0]["text"]["content"] == "second"


def test_horizontal_rule_dashes():
    blocks = markdown.to_blocks("a\n\n---\n\nb")
    types = [b["type"] for b in blocks]
    assert types == ["paragraph", "divider", "paragraph"]


def test_horizontal_rule_stars():
    blocks = markdown.to_blocks("***")
    assert blocks[0]["type"] == "divider"


def test_horizontal_rule_underscores():
    blocks = markdown.to_blocks("___")
    assert blocks[0]["type"] == "divider"


def test_blockquote_single_line():
    blocks = markdown.to_blocks("> a quote")
    assert blocks[0]["type"] == "quote"
    assert _rt(blocks[0])[0]["text"]["content"] == "a quote"


def test_blockquote_consecutive_lines_merge():
    blocks = markdown.to_blocks("> line one\n> line two")
    assert len(blocks) == 1
    assert blocks[0]["type"] == "quote"
    assert _rt(blocks[0])[0]["text"]["content"] == "line one\nline two"


def test_blockquote_preserves_inline_formatting():
    blocks = markdown.to_blocks("> **bold** quote")
    rt = _rt(blocks[0])
    bold = next(r for r in rt if r["text"]["content"] == "bold")
    assert bold["annotations"]["bold"] is True


def test_blockquote_separated_by_blank_line_creates_two_blocks():
    blocks = markdown.to_blocks("> a\n\n> b")
    assert [b["type"] for b in blocks] == ["quote", "quote"]


def test_todo_unchecked():
    blocks = markdown.to_blocks("- [ ] task")
    assert blocks[0]["type"] == "to_do"
    assert blocks[0]["to_do"]["checked"] is False
    assert _rt(blocks[0])[0]["text"]["content"] == "task"


def test_todo_checked():
    blocks = markdown.to_blocks("- [x] done")
    assert blocks[0]["type"] == "to_do"
    assert blocks[0]["to_do"]["checked"] is True


def test_todo_uppercase_x_also_checked():
    blocks = markdown.to_blocks("- [X] done")
    assert blocks[0]["to_do"]["checked"] is True


def test_todo_with_no_trailing_text():
    blocks = markdown.to_blocks("- [ ]")
    assert blocks[0]["type"] == "to_do"
    assert blocks[0]["to_do"]["checked"] is False
    assert _rt(blocks[0])[0]["text"]["content"] == ""


def test_todo_checked_with_no_trailing_text():
    blocks = markdown.to_blocks("- [x]")
    assert blocks[0]["type"] == "to_do"
    assert blocks[0]["to_do"]["checked"] is True


def test_todo_nested_under_bullet():
    md = "- parent\n  - [ ] child task"
    blocks = markdown.to_blocks(md)
    children = blocks[0]["bulleted_list_item"]["children"]
    assert children[0]["type"] == "to_do"


def test_table_basic():
    md = "| h1 | h2 |\n|---|---|\n| a | b |\n| c | d |"
    blocks = markdown.to_blocks(md)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "table"
    body = blocks[0]["table"]
    assert body["table_width"] == 2
    assert body["has_column_header"] is True
    rows = body["children"]
    assert len(rows) == 3  # header + 2 data
    header_cells = rows[0]["table_row"]["cells"]
    assert header_cells[0][0]["text"]["content"] == "h1"
    data_cells = rows[1]["table_row"]["cells"]
    assert data_cells[1][0]["text"]["content"] == "b"


def test_table_irregular_rows_padded_with_empty_cells():
    md = "| a | b | c |\n|---|---|---|\n| x | y |\n| 1 | 2 | 3 | 4 |"
    blocks = markdown.to_blocks(md)
    body = blocks[0]["table"]
    assert body["table_width"] == 4  # widest row wins
    rows = body["children"]
    short_row = rows[1]["table_row"]["cells"]
    assert len(short_row) == 4
    assert short_row[2] == []  # padded
    assert short_row[3] == []


def test_table_with_alignment_separator():
    md = "| a | b |\n|:---|---:|\n| 1 | 2 |"
    blocks = markdown.to_blocks(md)
    assert blocks[0]["type"] == "table"


def test_table_without_separator_falls_back_to_paragraph():
    md = "| a | b |\n| c | d |"
    blocks = markdown.to_blocks(md)
    assert blocks[0]["type"] == "paragraph"


def test_unsupported_construct_falls_back_to_paragraph():
    md = "@@@ some weird marker @@@"
    blocks = markdown.to_blocks(md)
    assert blocks[0]["type"] == "paragraph"
    assert "@@@" in _rt(blocks[0])[0]["text"]["content"]


def test_blocks_to_markdown_paragraph():
    blocks = [{
        "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "plain_text": "hello"}]},
    }]
    assert markdown.from_blocks(blocks) == "hello"


def test_blocks_to_markdown_heading_and_lists():
    blocks = [
        {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "H"}]}},
        {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"plain_text": "a"}]}},
        {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"plain_text": "b"}]}},
        {"type": "numbered_list_item", "numbered_list_item": {"rich_text": [{"plain_text": "one"}]}},
        {"type": "code", "code": {"language": "python", "rich_text": [{"plain_text": "x = 1"}]}},
    ]
    md = markdown.from_blocks(blocks)
    assert "# H" in md
    assert "- a" in md
    assert "- b" in md
    assert "1. one" in md
    assert "```python" in md
    assert "x = 1" in md


def test_blocks_to_markdown_renders_heading_4_quote_divider_todo():
    blocks = [
        {"type": "heading_4", "heading_4": {"rich_text": [{"plain_text": "h4"}]}},
        {"type": "divider", "divider": {}},
        {"type": "quote", "quote": {"rich_text": [{"plain_text": "wisdom"}]}},
        {"type": "to_do", "to_do": {"rich_text": [{"plain_text": "task"}], "checked": True}},
        {"type": "to_do", "to_do": {"rich_text": [{"plain_text": "todo"}], "checked": False}},
    ]
    md = markdown.from_blocks(blocks)
    assert "#### h4" in md
    assert "---" in md
    assert "> wisdom" in md
    assert "- [x] task" in md
    assert "- [ ] todo" in md


def test_blocks_to_markdown_renders_table():
    table = {
        "type": "table",
        "table": {
            "table_width": 2,
            "has_column_header": True,
            "has_row_header": False,
            "children": [
                {"type": "table_row", "table_row": {"cells": [
                    [{"plain_text": "A"}], [{"plain_text": "B"}],
                ]}},
                {"type": "table_row", "table_row": {"cells": [
                    [{"plain_text": "1"}], [{"plain_text": "2"}],
                ]}},
            ],
        },
    }
    md = markdown.from_blocks([table])
    assert "| A | B |" in md
    assert "| --- | --- |" in md
    assert "| 1 | 2 |" in md


def test_extract_title_uses_first_h1_line():
    md = "# Real title\n\nbody line"
    title, body = markdown.split_title(md)
    assert title == "Real title"
    assert body.strip() == "body line"


def test_extract_title_falls_back_to_first_nonblank_line():
    md = "no heading here\nmore text"
    title, body = markdown.split_title(md)
    assert title == "no heading here"
    assert body.strip() == "more text"


def test_extract_title_truncates_to_max_length():
    md = "# " + "x" * 300
    title, _ = markdown.split_title(md)
    assert len(title) <= 200


def test_to_blocks_returns_empty_for_non_string():
    assert markdown.to_blocks(None) == []  # type: ignore[arg-type]
    assert markdown.to_blocks(123) == []  # type: ignore[arg-type]


def test_split_title_safe_for_non_string():
    assert markdown.split_title(None) == ("", "")  # type: ignore[arg-type]


def test_rich_markdown_from_user_report_does_not_raise_and_normalizes_csharp():
    """Smoke test: the exact rich markdown from the bug report converts
    cleanly, code fence languages are valid, and headings 4 are supported."""
    md = (
        "# Title\n\n"
        "**Date:** 2026-05-08\n\n"
        "## Section\n\n"
        "1. first\n"
        "2. second\n\n"
        "- a bullet\n"
        "  - nested bullet\n\n"
        "> a quote line\n"
        "> still quote\n\n"
        "---\n\n"
        "| col1 | col2 |\n"
        "|---|---|\n"
        "| a | b |\n\n"
        "```csharp\nvar x = 1;\n```\n\n"
        "```terraform\nresource \"x\" \"y\" {}\n```\n\n"
        "#### Heading 4\n\n"
        "Some ~~deleted~~ text and `inline code`.\n"
    )
    blocks = markdown.to_blocks(md)
    code_blocks = [b for b in blocks if b["type"] == "code"]
    languages = {b["code"]["language"] for b in code_blocks}
    assert "c#" in languages
    assert "hcl" in languages
    valid_langs = markdown._NOTION_LANGUAGES
    for b in code_blocks:
        assert b["code"]["language"] in valid_langs
    assert any(b["type"] == "heading_4" for b in blocks)
    assert any(b["type"] == "table" for b in blocks)
    assert any(b["type"] == "divider" for b in blocks)
    assert any(b["type"] == "quote" for b in blocks)
