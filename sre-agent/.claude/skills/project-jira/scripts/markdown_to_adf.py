"""Convert Markdown to Atlassian Document Format (ADF) for Jira Cloud comments/descriptions.

Parses Markdown via mistune's AST mode (renderer=None) and walks the token
tree into ADF nodes. Unknown/unhandled token types degrade to a plain text
run instead of raising or vanishing - a converter bug should never drop
content or crash the caller.
"""

import mistune

_INLINE_MARK_TYPES = {
    "strong": "strong",
    "emphasis": "em",
}


def _render_inline_children(children, marks):
    nodes = []
    for child in children or []:
        nodes.extend(_render_inline(child, marks))
    return nodes


def _render_inline(token, marks):
    """Render one inline mistune token into a list of ADF inline nodes,
    threading `marks` (the ADF mark dicts already applied by enclosing
    strong/emphasis/link tokens) down to leaf text/codespan nodes."""
    ttype = token.get("type")

    if ttype == "text":
        raw = token.get("raw", "")
        if not raw:
            return []
        node = {"type": "text", "text": raw}
        if marks:
            node["marks"] = list(marks)
        return [node]

    if ttype == "codespan":
        return [{"type": "text", "text": token.get("raw", ""), "marks": [*marks, {"type": "code"}]}]

    if ttype in ("strong", "emphasis"):
        mark = {"type": _INLINE_MARK_TYPES[ttype]}
        return _render_inline_children(token.get("children"), [*marks, mark])

    if ttype == "link":
        url = token.get("attrs", {}).get("url", "")
        mark = {"type": "link", "attrs": {"href": url}}
        return _render_inline_children(token.get("children"), [*marks, mark])

    if ttype in ("linebreak", "softbreak"):
        return [{"type": "text", "text": " "}]

    if ttype == "image":
        # ADF has a mediaSingle/media node for real embeds; degrade to a
        # plain text run instead of a full media-upload flow.
        url = token.get("attrs", {}).get("url", "")
        alt = token.get("alt") or url
        return [{"type": "text", "text": f"{alt} ({url})" if url else alt}]

    # Unknown inline token: recurse into children as plain text, or fall
    # back to raw text - never drop the content.
    if token.get("children"):
        return _render_inline_children(token.get("children"), marks)
    raw = token.get("raw", "")
    return [{"type": "text", "text": raw}] if raw else []


def _paragraph_from_inline(children):
    # ADF forbids empty-string text nodes - an empty paragraph is
    # {"content": []}, not a text node with "".
    return {"type": "paragraph", "content": _render_inline_children(children, [])}


def _render_list_item(token):
    # ADF listItem content must be block nodes; mistune wraps list item
    # inline content in a "block_text" token - treat it as one paragraph.
    blocks = []
    for child in token.get("children", []):
        if child.get("type") == "block_text":
            blocks.append(_paragraph_from_inline(child.get("children")))
        else:
            blocks.extend(_render_block(child))
    if not blocks:
        blocks = [_paragraph_from_inline([])]
    return {"type": "listItem", "content": blocks}


def _render_table_cell(token):
    is_header = token.get("attrs", {}).get("head", False)
    node_type = "tableHeader" if is_header else "tableCell"
    return {
        "type": node_type,
        "attrs": {},
        "content": [_paragraph_from_inline(token.get("children"))],
    }


def _render_table(token):
    # mistune's table AST nests header cells directly under table_head
    # (no intermediate row) and body rows under table_body/table_row.
    rows = []
    for section in token.get("children", []):
        section_type = section.get("type")
        if section_type == "table_head":
            cells = [_render_table_cell(c) for c in section.get("children", [])]
            rows.append({"type": "tableRow", "content": cells})
        elif section_type == "table_body":
            for row in section.get("children", []):
                cells = [_render_table_cell(c) for c in row.get("children", [])]
                rows.append({"type": "tableRow", "content": cells})
    return {"type": "table", "content": rows}


def _render_block(token):
    """Render one block-level mistune token into a list of ADF block nodes."""
    ttype = token.get("type")

    if ttype == "paragraph":
        return [_paragraph_from_inline(token.get("children"))]

    if ttype == "heading":
        level = token.get("attrs", {}).get("level", 1)
        content = _render_inline_children(token.get("children"), [])
        return [{"type": "heading", "attrs": {"level": level}, "content": content}]

    if ttype == "block_code":
        code = token.get("raw", "")
        node = {"type": "codeBlock", "content": [{"type": "text", "text": code}]}
        info = token.get("attrs", {}).get("info")
        if info:
            node["attrs"] = {"language": info.strip().split()[0]}
        return [node]

    if ttype == "list":
        ordered = token.get("attrs", {}).get("ordered", False)
        items = [_render_list_item(item) for item in token.get("children", [])]
        return [{"type": "orderedList" if ordered else "bulletList", "content": items}]

    if ttype == "table":
        return [_render_table(token)]

    if ttype == "block_quote":
        blocks = []
        for child in token.get("children", []):
            blocks.extend(_render_block(child))
        return [{"type": "blockquote", "content": blocks or [_paragraph_from_inline([])]}]

    if ttype == "thematic_break":
        return [{"type": "rule"}]

    if ttype == "blank_line":
        return []

    # Unknown block token: recurse into children if present, else render
    # any raw text as a plain paragraph - never drop, never raise.
    if token.get("children"):
        blocks = []
        for child in token.get("children", []):
            blocks.extend(_render_block(child))
        return blocks
    raw = token.get("raw", "")
    if raw:
        return [{"type": "paragraph", "content": [{"type": "text", "text": raw}]}]
    return []


_md_ast = mistune.create_markdown(renderer=None, plugins=["table", "strikethrough"])


def markdown_to_adf(text: str) -> dict:
    """Convert Markdown text to an Atlassian Document Format (ADF) document.

    On any parse/render failure, falls back to a single flat paragraph
    containing the raw text - the same degraded-but-safe shape Jira Cloud
    comments already get today. A converter bug never raises out to the
    caller and never produces an empty document.
    """
    if not text:
        return {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": []}]}

    try:
        tokens = _md_ast(text)
        content = []
        for token in tokens:
            content.extend(_render_block(token))
        if not content:
            content = [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]
        return {"type": "doc", "version": 1, "content": content}
    except Exception:
        return {
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
        }
