"""Convert Markdown to a list of Adaptive Card body elements.

Uses mistune's AST mode (renderer=None). Adaptive Card TextBlocks already
render **bold**/*italic*/links natively, so inline markdown is left as-is
inside each TextBlock's `text` field; only block-level structure (headings,
lists, tables, code fences) needs actual conversion, since Adaptive Cards
have no native equivalent for those.

On any parse failure, falls back to a single TextBlock with the raw,
unconverted text - never an empty or partial block list.
"""

import mistune

_md_ast = mistune.create_markdown(renderer=None, plugins=["table", "strikethrough"])


def _inline_markdown(children) -> str:
    """Re-serialize inline children back to Markdown text - Adaptive Card
    TextBlocks render **bold**/*italic*/`code`/[text](url) natively, so
    these are reassembled rather than stripped or converted."""
    parts = []
    for token in children or []:
        ttype = token.get("type")
        if ttype == "text":
            parts.append(token.get("raw", ""))
        elif ttype == "strong":
            parts.append(f"**{_inline_markdown(token.get('children'))}**")
        elif ttype == "emphasis":
            parts.append(f"*{_inline_markdown(token.get('children'))}*")
        elif ttype == "codespan":
            parts.append(f"`{token.get('raw', '')}`")
        elif ttype == "link":
            url = token.get("attrs", {}).get("url", "")
            parts.append(f"[{_inline_markdown(token.get('children'))}]({url})")
        elif ttype in ("linebreak", "softbreak"):
            parts.append(" ")
        elif token.get("children"):
            parts.append(_inline_markdown(token.get("children")))
        else:
            parts.append(token.get("raw", ""))
    return "".join(parts)


def _text_block(text: str, **kwargs) -> dict:
    block = {"type": "TextBlock", "text": text, "wrap": True}
    block.update(kwargs)
    return block


def _flatten_table(token) -> list:
    """Flatten a table into one TextBlock per row - Adaptive Cards have no
    Table element supported consistently across Teams clients, so rows
    render as plain 'col1 | col2' text (mirrors slack-bot/table_converter.py's
    flattening approach)."""
    blocks = []
    for section in token.get("children", []):
        if section.get("type") == "table_head":
            cells = section.get("children", [])
            line = " | ".join(_inline_markdown(c.get("children")) for c in cells)
            blocks.append(_text_block(f"**{line}**"))
        elif section.get("type") == "table_body":
            for row in section.get("children", []):
                cells = row.get("children", [])
                line = " | ".join(_inline_markdown(c.get("children")) for c in cells)
                blocks.append(_text_block(line))
    return blocks


def _render_block(token) -> list:
    ttype = token.get("type")

    if ttype == "paragraph":
        text = _inline_markdown(token.get("children"))
        return [_text_block(text)] if text else []

    if ttype == "heading":
        level = token.get("attrs", {}).get("level", 1)
        text = _inline_markdown(token.get("children"))
        size = "Large" if level == 1 else "Medium" if level <= 3 else "Default"
        return [_text_block(text, weight="Bolder", size=size)]

    if ttype == "block_code":
        return [_text_block(token.get("raw", "").rstrip("\n"), fontType="Monospace")]

    if ttype == "list":
        ordered = token.get("attrs", {}).get("ordered", False)
        blocks = []
        for i, item in enumerate(token.get("children", []), start=1):
            text = ""
            for child in item.get("children", []):
                if child.get("type") == "block_text":
                    text = _inline_markdown(child.get("children"))
            prefix = f"{i}. " if ordered else "• "
            blocks.append(_text_block(f"{prefix}{text}", spacing="None"))
        return blocks

    if ttype == "table":
        return _flatten_table(token)

    if ttype == "block_quote":
        blocks = []
        for child in token.get("children", []):
            blocks.extend(_render_block(child))
        return blocks

    if ttype == "thematic_break":
        return [_text_block("---")]

    if ttype == "blank_line":
        return []

    if token.get("children"):
        blocks = []
        for child in token.get("children", []):
            blocks.extend(_render_block(child))
        return blocks

    raw = token.get("raw", "")
    return [_text_block(raw)] if raw else []


def markdown_to_adaptive_blocks(text: str) -> list:
    """Convert Markdown text to a list of Adaptive Card body elements.

    On any parse/render failure, or if the input produces no blocks at
    all, falls back to a single TextBlock containing the original raw
    text - never an empty list, never a partial block list.
    """
    if not text:
        return [_text_block("_No summary returned._")]
    try:
        tokens = _md_ast(text)
        blocks = []
        for token in tokens:
            blocks.extend(_render_block(token))
        return blocks if blocks else [_text_block(text)]
    except Exception:
        return [_text_block(text)]
