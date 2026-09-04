"""Tests for the Jira Cloud Markdown -> ADF converter."""

import os
import sys

_SKILL_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".claude",
    "skills",
    "project-jira",
    "scripts",
)
sys.path.insert(0, _SKILL_SCRIPTS)

from markdown_to_adf import markdown_to_adf  # noqa: E402


def test_bold_paragraph_and_bullet_list():
    doc = markdown_to_adf("**Root cause**\n\n- one\n- two\n")
    assert doc == {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Root cause", "marks": [{"type": "strong"}]}
                ],
            },
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "one"}]}
                        ],
                    },
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "two"}]}
                        ],
                    },
                ],
            },
        ],
    }


def test_table_becomes_adf_table_with_header_row():
    doc = markdown_to_adf("| a | b |\n|---|---|\n| 1 | 2 |\n")
    table = doc["content"][0]
    assert table["type"] == "table"
    header_row, body_row = table["content"]
    assert [c["type"] for c in header_row["content"]] == ["tableHeader", "tableHeader"]
    assert [c["type"] for c in body_row["content"]] == ["tableCell", "tableCell"]


def test_fenced_code_block_keeps_language():
    doc = markdown_to_adf("```python\nprint(1)\n```\n")
    assert doc["content"] == [
        {
            "type": "codeBlock",
            "content": [{"type": "text", "text": "print(1)\n"}],
            "attrs": {"language": "python"},
        }
    ]


def test_inline_marks_codespan_link_emphasis_strong():
    doc = markdown_to_adf("See `x` and [link](http://e.com) and *it* and **b**.\n")
    texts = doc["content"][0]["content"]
    assert texts[1] == {"type": "text", "text": "x", "marks": [{"type": "code"}]}
    assert texts[3] == {
        "type": "text",
        "text": "link",
        "marks": [{"type": "link", "attrs": {"href": "http://e.com"}}],
    }
    assert texts[5] == {"type": "text", "text": "it", "marks": [{"type": "em"}]}
    assert texts[7] == {"type": "text", "text": "b", "marks": [{"type": "strong"}]}


def test_empty_input_returns_empty_paragraph_not_empty_doc():
    doc = markdown_to_adf("")
    assert doc == {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": []}]}


def test_plain_text_round_trips():
    doc = markdown_to_adf("just text\n")
    assert doc == {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "just text"}]}],
    }


def test_never_raises_on_malformed_input(monkeypatch):
    """A converter bug degrades to a flat paragraph - it never raises or empties."""
    import markdown_to_adf as mod

    def boom(_token):
        raise RuntimeError("simulated renderer bug")

    monkeypatch.setattr(mod, "_render_block", boom)
    doc = mod.markdown_to_adf("**anything**")
    assert doc == {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "**anything**"}]}],
    }


def test_make_text_body_uses_adf_converter_for_cloud(monkeypatch):
    monkeypatch.delenv("JIRA_API_VERSION", raising=False)  # default is "3" (Cloud)
    import jira_client

    body = jira_client.make_text_body("**bold**")
    assert body == {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "bold", "marks": [{"type": "strong"}]}]}
        ],
    }


def test_make_text_body_falls_back_to_flat_paragraph_on_converter_error(monkeypatch):
    monkeypatch.delenv("JIRA_API_VERSION", raising=False)
    import jira_client
    import markdown_to_adf as adf_mod

    def boom(_text):
        raise RuntimeError("simulated converter crash")

    monkeypatch.setattr(adf_mod, "markdown_to_adf", boom)
    body = jira_client.make_text_body("plain text")
    assert body == jira_client.make_adf_text("plain text")


def test_make_text_body_data_center_unchanged(monkeypatch):
    monkeypatch.setenv("JIRA_API_VERSION", "2")
    import jira_client

    assert jira_client.make_text_body("*bold wiki markup*") == "*bold wiki markup*"
