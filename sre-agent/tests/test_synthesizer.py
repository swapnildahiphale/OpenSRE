"""Tests for the synthesizer node."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import MagicMock, patch

import pytest


def _make_mock_llm(response_json: dict | str):
    """Create a mock LLM that returns a predefined response."""
    mock_llm = MagicMock()
    if isinstance(response_json, dict):
        content = json.dumps(response_json)
    else:
        content = response_json
    mock_response = MagicMock()
    mock_response.content = content
    mock_llm.invoke.return_value = mock_response
    return mock_llm


@pytest.fixture
def base_state():
    return {
        "alert": {"name": "HighLatency", "service": "cart-service"},
        "agent_states": {
            "kubernetes": {
                "status": "completed",
                "findings": "Found 2 pods in CrashLoopBackOff with OOM kills.",
                "react_loops": 5,
                "duration_seconds": 12.3,
            },
            "metrics": {
                "status": "completed",
                "findings": "Memory usage at 98% on cart-service nodes.",
                "react_loops": 3,
                "duration_seconds": 8.1,
            },
        },
        "iteration": 0,
        "max_iterations": 3,
        "team_config": {"agents": {}},
    }


class TestSynthesizer:
    """Tests for nodes.synthesizer.synthesizer."""

    @patch("nodes.synthesizer.build_llm")
    def test_sufficient_evidence_returns_completed(self, mock_build_llm, base_state):
        """When LLM says evidence is sufficient, returns status=completed."""
        synthesis = {
            "sufficient_evidence": True,
            "confidence": 0.9,
            "summary": "Root cause identified: OOM kills on cart-service",
            "gaps": [],
            "feedback": "",
        }
        mock_build_llm.return_value = _make_mock_llm(synthesis)

        from nodes.synthesizer import synthesizer

        result = synthesizer(base_state)

        assert result["status"] == "completed"
        assert any("OOM" in msg.get("content", "") for msg in result["messages"])

    @patch("nodes.synthesizer.build_llm")
    def test_insufficient_evidence_increments_iteration(
        self, mock_build_llm, base_state
    ):
        """When evidence is insufficient, increments iteration and returns running."""
        synthesis = {
            "sufficient_evidence": False,
            "confidence": 0.3,
            "summary": "Need more data on memory pressure",
            "gaps": ["Memory allocation details", "GC logs"],
            "feedback": "Check container memory limits and GC behavior",
        }
        mock_build_llm.return_value = _make_mock_llm(synthesis)

        from nodes.synthesizer import synthesizer

        result = synthesizer(base_state)

        assert result["status"] == "running"
        assert result["iteration"] == 1
        assert len(result["messages"]) > 0

    @patch("nodes.synthesizer.build_llm")
    def test_forces_conclusion_at_max_iterations(self, mock_build_llm, base_state):
        """At max_iterations - 1, forces status=completed even if LLM says insufficient."""
        base_state["iteration"] = 2  # max_iterations - 1 = 2

        synthesis = {
            "sufficient_evidence": False,  # LLM says insufficient
            "confidence": 0.4,
            "summary": "Partial findings",
            "gaps": ["Still need more data"],
            "feedback": "Would need another round",
        }
        mock_build_llm.return_value = _make_mock_llm(synthesis)

        from nodes.synthesizer import synthesizer

        result = synthesizer(base_state)

        assert result["status"] == "completed"

    @patch("nodes.synthesizer.build_llm")
    def test_handles_llm_failure_gracefully(self, mock_build_llm, base_state):
        """When LLM call fails, returns completed to proceed with available evidence."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("API error")
        mock_build_llm.return_value = mock_llm

        from nodes.synthesizer import synthesizer

        result = synthesizer(base_state)

        assert result["status"] == "completed"
        assert any(
            "error" in msg.get("content", "").lower() for msg in result["messages"]
        )

    @patch("nodes.synthesizer.build_llm")
    def test_appends_feedback_message_to_state(self, mock_build_llm, base_state):
        """When insufficient, appends a feedback message with guidance."""
        synthesis = {
            "sufficient_evidence": False,
            "confidence": 0.4,
            "summary": "Partial findings so far",
            "gaps": ["Need GC logs"],
            "feedback": "Focus on garbage collection behavior",
        }
        mock_build_llm.return_value = _make_mock_llm(synthesis)

        from nodes.synthesizer import synthesizer

        result = synthesizer(base_state)

        assert len(result["messages"]) > 0
        feedback_content = result["messages"][0]["content"]
        assert "Synthesizer Feedback" in feedback_content
        assert "garbage collection" in feedback_content.lower()

    @patch("nodes.synthesizer.build_llm")
    def test_handles_build_llm_failure(self, mock_build_llm, base_state):
        """When build_llm itself raises, still returns completed gracefully."""
        mock_build_llm.side_effect = RuntimeError("Config error")

        from nodes.synthesizer import synthesizer

        result = synthesizer(base_state)

        assert result["status"] == "completed"

    @patch("nodes.synthesizer.build_llm")
    def test_handles_unparseable_json_response(self, mock_build_llm, base_state):
        """When LLM returns non-JSON, still produces a result."""
        mock_build_llm.return_value = _make_mock_llm(
            "This is not JSON at all, just plain text analysis."
        )

        from nodes.synthesizer import synthesizer

        # iteration < max_iterations - 1, and parsed sufficient_evidence will be False
        # but the fallback handles it
        result = synthesizer(base_state)

        assert result["status"] in ("completed", "running")
