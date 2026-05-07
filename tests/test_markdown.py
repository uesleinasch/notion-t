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


def test_blank_lines_separate_paragraphs():
    md = "first\n\nsecond"
    blocks = markdown.to_blocks(md)
    assert len(blocks) == 2
    assert _rt(blocks[0])[0]["text"]["content"] == "first"
    assert _rt(blocks[1])[0]["text"]["content"] == "second"


def test_unknown_construct_falls_back_to_paragraph():
    md = "> this is a quote we don't support"
    blocks = markdown.to_blocks(md)
    assert blocks[0]["type"] == "paragraph"
    assert "> this is a quote" in _rt(blocks[0])[0]["text"]["content"]


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
