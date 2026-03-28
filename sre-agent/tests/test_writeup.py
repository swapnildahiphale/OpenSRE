"""Tests for the writeup node."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import MagicMock, patch

import pytest


def _make_mock_llm(response_text: str):
    """Create a mock LLM that returns a predefined text response."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = response_text
    mock_llm.invoke.return_value = mock_response
    return mock_llm


@pytest.fixture
def base_state():
    return {
        "alert": {
            "name": "HighLatency",
            "service": "cart-service",
            "severity": "warning",
        },
        "agent_states": {
            "kubernetes": {
                "findings": "2 pods in CrashLoopBackOff. OOM kills detected.",
            },
            "metrics": {
                "findings": "Memory usage at 98%. CPU normal.",
            },
        },
        "hypotheses": [{"hypothesis": "Memory leak in cart-service"}],
        "messages": [{"role": "synthesizer", "content": "Evidence sufficient."}],
        "team_config": {"agents": {}},
    }


SAMPLE_WRITEUP_RESPONSE = """# Incident Report: Cart Service High Latency

## Summary
Cart service experienced high latency due to memory exhaustion causing OOM kills.

## Root Cause
Memory leak in the cart-service application causing pods to hit memory limits.

## Impact
- 2 pods in CrashLoopBackOff
- Memory usage at 98%

```json
{
    "title": "Cart Service OOM-Induced High Latency",
    "severity": "warning",
    "services": ["cart-service"],
    "root_cause": "Memory leak causing OOM kills",
    "timeline": [
        {"time": "14:00", "event": "Memory usage began climbing"},
        {"time": "14:30", "event": "First OOM kill"}
    ],
    "findings": [
        {"category": "Kubernetes", "detail": "2 pods in CrashLoopBackOff", "evidence": "kubectl output"}
    ],
    "action_items": [
        {"priority": "high", "action": "Increase memory limits", "owner": "platform-team"},
        {"priority": "medium", "action": "Fix memory leak", "owner": "cart-team"}
    ],
    "resolution_status": "mitigated"
}
```
"""


class TestWriteup:
    """Tests for nodes.writeup.writeup."""

    @patch("nodes.writeup.build_llm")
    def test_generates_conclusion_and_structured_report(
        self, mock_build_llm, base_state
    ):
        """Writeup generates both conclusion text and structured_report dict."""
        mock_build_llm.return_value = _make_mock_llm(SAMPLE_WRITEUP_RESPONSE)

        from nodes.writeup import writeup

        result = writeup(base_state)

        assert "conclusion" in result
        assert "structured_report" in result
        assert len(result["conclusion"]) > 0
        assert isinstance(result["structured_report"], dict)

    @patch("nodes.writeup.build_llm")
    def test_structured_report_has_required_fields(self, mock_build_llm, base_state):
        """Structured report contains title, severity, and services fields."""
        mock_build_llm.return_value = _make_mock_llm(SAMPLE_WRITEUP_RESPONSE)

        from nodes.writeup import writeup

        result = writeup(base_state)
        report = result["structured_report"]

        assert "title" in report
        assert "severity" in report
        assert "affected_services" in report
        assert report["title"] == "Cart Service OOM-Induced High Latency"
        assert report["severity"] == "warning"
        assert "cart-service" in report["affected_services"]

    @patch("nodes.writeup.build_llm")
    def test_handles_llm_failure_gracefully(self, mock_build_llm, base_state):
        """When LLM fails, returns fallback conclusion and report."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("API error")
        mock_build_llm.return_value = mock_llm

        from nodes.writeup import writeup

        result = writeup(base_state)

        assert "conclusion" in result
        assert "failed" in result["conclusion"].lower()
        assert "structured_report" in result
        assert result["structured_report"]["severity"] == "warning"
        assert "error" in result["structured_report"]

    @patch("nodes.writeup.build_llm")
    def test_extracts_json_from_markdown_code_block(self, mock_build_llm, base_state):
        """JSON is correctly extracted from markdown ```json code block."""
        response = 'Some narrative text.\n\n```json\n{"title": "Test", "severity": "info", "services": ["svc"]}\n```'
        mock_build_llm.return_value = _make_mock_llm(response)

        from nodes.writeup import writeup

        result = writeup(base_state)

        assert result["structured_report"]["title"] == "Test"
        assert result["structured_report"]["severity"] == "info"
        assert "svc" in result["structured_report"]["affected_services"]

    @patch("nodes.writeup.build_llm")
    def test_conclusion_excludes_json_block(self, mock_build_llm, base_state):
        """The conclusion (narrative) text does not include the JSON block."""
        mock_build_llm.return_value = _make_mock_llm(SAMPLE_WRITEUP_RESPONSE)

        from nodes.writeup import writeup

        result = writeup(base_state)

        # Conclusion should be the markdown before the JSON block
        assert "```json" not in result["conclusion"]
        assert "Incident Report" in result["conclusion"]

    @patch("nodes.writeup.build_llm")
    def test_handles_response_without_json_block(self, mock_build_llm, base_state):
        """When LLM response has no JSON block, falls back to alert-based report."""
        response = "This is just a narrative report without any JSON."
        mock_build_llm.return_value = _make_mock_llm(response)

        from nodes.writeup import writeup

        result = writeup(base_state)

        assert result["conclusion"] == response
        # structured_report should be empty dict (no JSON found)
        assert isinstance(result["structured_report"], dict)

    @patch("nodes.writeup.build_llm")
    def test_build_llm_failure_returns_fallback(self, mock_build_llm, base_state):
        """When build_llm itself raises, returns error-based fallback."""
        mock_build_llm.side_effect = RuntimeError("Config missing")

        from nodes.writeup import writeup

        result = writeup(base_state)

        assert (
            "failed" in result["conclusion"].lower()
            or "Config missing" in result["conclusion"]
        )
        assert result["structured_report"]["resolution_status"] == "investigating"
