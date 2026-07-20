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
