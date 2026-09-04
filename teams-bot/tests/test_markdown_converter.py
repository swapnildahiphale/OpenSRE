"""Tests for the Markdown -> Adaptive Card block converter."""

from markdown_converter import markdown_to_adaptive_blocks


def test_final_report_shape_renders_bold_labels_and_bullets():
    text = (
        "**Root cause headline**\n\n"
        "**Scope:** affected thing\n\n"
        "**Timeline:**\n"
        "- 10:00 UTC - event one\n"
        "- 10:05 UTC - event two\n"
    )
    blocks = markdown_to_adaptive_blocks(text)
    assert blocks == [
        {"type": "TextBlock", "text": "**Root cause headline**", "wrap": True},
        {"type": "TextBlock", "text": "**Scope:** affected thing", "wrap": True},
        {"type": "TextBlock", "text": "**Timeline:**", "wrap": True},
        {"type": "TextBlock", "text": "• 10:00 UTC - event one", "wrap": True, "spacing": "None"},
        {"type": "TextBlock", "text": "• 10:05 UTC - event two", "wrap": True, "spacing": "None"},
    ]


def test_heading_becomes_bold_text_block():
    blocks = markdown_to_adaptive_blocks("## Section\n")
    assert blocks == [
        {"type": "TextBlock", "text": "Section", "wrap": True, "weight": "Bolder", "size": "Medium"}
    ]


def test_table_flattens_to_pipe_separated_rows():
    blocks = markdown_to_adaptive_blocks("| a | b |\n|---|---|\n| 1 | 2 |\n")
    assert blocks == [
        {"type": "TextBlock", "text": "**a | b**", "wrap": True},
        {"type": "TextBlock", "text": "1 | 2", "wrap": True},
    ]


def test_code_fence_becomes_monospace_block_without_trailing_newline():
    blocks = markdown_to_adaptive_blocks("```\nraw output\n```\n")
    assert blocks == [
        {"type": "TextBlock", "text": "raw output", "wrap": True, "fontType": "Monospace"}
    ]


def test_ordered_list_numbers_items():
    blocks = markdown_to_adaptive_blocks("1. first\n2. second\n")
    assert blocks == [
        {"type": "TextBlock", "text": "1. first", "wrap": True, "spacing": "None"},
        {"type": "TextBlock", "text": "2. second", "wrap": True, "spacing": "None"},
    ]


def test_empty_input_returns_placeholder_block():
    assert markdown_to_adaptive_blocks("") == [
        {"type": "TextBlock", "text": "_No summary returned._", "wrap": True}
    ]


def test_never_returns_empty_list_on_converter_failure(monkeypatch):
    import markdown_converter as mod

    def boom(_token):
        raise RuntimeError("simulated renderer bug")

    monkeypatch.setattr(mod, "_render_block", boom)
    blocks = mod.markdown_to_adaptive_blocks("**anything**")
    assert blocks == [{"type": "TextBlock", "text": "**anything**", "wrap": True}]
