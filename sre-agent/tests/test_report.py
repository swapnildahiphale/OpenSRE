# sre-agent/tests/test_report.py
"""Tests for structured_report extraction from agent result text — Task 6."""

from report import extract_structured_report


def test_extracts_fenced_json_block():
    text = 'Summary.\n\n```json\n{"root_cause": "bad deploy", "confidence": 0.8, "services": ["api"]}\n```\n'
    rep = extract_structured_report(text)
    assert rep["root_cause"] == "bad deploy"
    assert rep["confidence"] == 0.8


def test_returns_none_when_absent_or_malformed():
    assert extract_structured_report("no json here") is None
    assert extract_structured_report("```json\n{not valid}\n```") is None


from report import clean_and_extract


def test_clean_and_extract_strips_fence_when_valid():
    text = '**Headline**\n\nbody text\n\n```json\n{"title": "x"}\n```\n'
    display_text, structured = clean_and_extract(text)
    assert structured == {"title": "x"}
    assert display_text == "**Headline**\n\nbody text"
    assert "```json" not in display_text


def test_clean_and_extract_leaves_text_unchanged_when_absent():
    text = "no json here"
    display_text, structured = clean_and_extract(text)
    assert structured is None
    assert display_text == text


def test_clean_and_extract_leaves_fence_visible_when_malformed():
    text = "**Headline**\n\n```json\n{not valid}\n```\n"
    display_text, structured = clean_and_extract(text)
    assert structured is None
    assert display_text == text  # never strip a fence that didn't actually parse
