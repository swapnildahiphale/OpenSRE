"""Tests for the planner node."""

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
def sample_state():
    return {
        "alert": {
            "name": "HighLatency",
            "service": "cart-service",
            "severity": "warning",
        },
        "memory_context": {},
        "kg_context": {},
        "team_config": {
            "agents": {
                "investigation": {
                    "sub_agents": {
                        "kubernetes": True,
                        "metrics": True,
                        "log_analysis": True,
                        "github": False,
                    }
                }
            }
        },
        "iteration": 0,
        "messages": [],
    }


@pytest.fixture
def mock_langchain():
    """Mock langchain_core.messages to avoid import errors."""
    mock_mod = MagicMock()
    mock_mod.SystemMessage = MagicMock
    mock_mod.HumanMessage = MagicMock
    return mock_mod


class TestPlanner:
    """Tests for nodes.planner.planner."""

    @patch("nodes.planner.build_llm")
    def test_generates_hypotheses_and_selected_agents(
        self, mock_build_llm, sample_state
    ):
        """Planner returns hypotheses and selected_agents from LLM response."""
        plan_response = {
            "hypotheses": [
                {
                    "hypothesis": "Memory leak in cart-service",
                    "priority": "high",
                    "agents_to_test": ["kubernetes", "metrics"],
                }
            ],
            "selected_agents": ["kubernetes", "metrics"],
            "reasoning": "Latency spike suggests resource issue",
        }
        mock_build_llm.return_value = _make_mock_llm(plan_response)

        from nodes.planner import planner

        result = planner(sample_state)

        assert len(result["hypotheses"]) == 1
        assert result["hypotheses"][0]["hypothesis"] == "Memory leak in cart-service"
        assert "kubernetes" in result["selected_agents"]
        assert "metrics" in result["selected_agents"]
        assert result["iteration"] == 0

    @patch("nodes.planner.build_llm")
    def test_uses_available_agents_from_team_config(self, mock_build_llm, sample_state):
        """Planner only uses enabled agents from team_config sub_agents."""
        plan_response = {
            "hypotheses": [
                {
                    "hypothesis": "test",
                    "priority": "high",
                    "agents_to_test": ["kubernetes"],
                }
            ],
            "selected_agents": ["kubernetes", "github"],  # github is disabled
            "reasoning": "test",
        }
        mock_build_llm.return_value = _make_mock_llm(plan_response)

        from nodes.planner import planner

        result = planner(sample_state)

        # github should be filtered out since it's disabled
        assert "github" not in result["selected_agents"]
        assert "kubernetes" in result["selected_agents"]

    @patch("nodes.planner.build_llm")
    def test_handles_llm_failure_gracefully(self, mock_build_llm, sample_state):
        """When build_llm raises, returns fallback plan with available agents."""
        mock_build_llm.side_effect = RuntimeError("LLM service unavailable")

        from nodes.planner import planner

        result = planner(sample_state)

        assert len(result["hypotheses"]) >= 1
        assert "LLM unavailable" in result["hypotheses"][0]["hypothesis"]
        # Fallback should include all available agents
        assert set(result["selected_agents"]) == {
            "kubernetes",
            "metrics",
            "log_analysis",
        }

    @patch("nodes.planner.build_llm")
    def test_includes_feedback_on_iteration_gt_0(self, mock_build_llm, sample_state):
        """On iteration > 0, feedback messages are included in the prompt."""
        sample_state["iteration"] = 1
        sample_state["messages"] = [
            {"role": "synthesizer", "content": "Need more metrics data"}
        ]

        plan_response = {
            "hypotheses": [
                {
                    "hypothesis": "Refined hypothesis",
                    "priority": "high",
                    "agents_to_test": ["metrics"],
                }
            ],
            "selected_agents": ["metrics"],
            "reasoning": "Focusing on metrics based on feedback",
        }
        mock_llm = _make_mock_llm(plan_response)
        mock_build_llm.return_value = mock_llm

        from nodes.planner import planner

        result = planner(sample_state)

        # Verify the LLM was called with feedback in the prompt
        call_args = mock_llm.invoke.call_args[0][0]
        # The second message (HumanMessage) should contain the feedback
        human_msg_content = call_args[1].content
        assert "Previous Feedback" in human_msg_content
        assert "Need more metrics data" in human_msg_content

    @patch("nodes.planner.build_llm")
    def test_filters_selected_agents_to_only_available(
        self, mock_build_llm, sample_state
    ):
        """LLM may suggest agents not in the available list; they get filtered."""
        plan_response = {
            "hypotheses": [
                {
                    "hypothesis": "test",
                    "priority": "high",
                    "agents_to_test": ["kubernetes"],
                }
            ],
            "selected_agents": ["kubernetes", "nonexistent_agent", "aws"],
            "reasoning": "test",
        }
        mock_build_llm.return_value = _make_mock_llm(plan_response)

        from nodes.planner import planner

        result = planner(sample_state)

        # Only kubernetes is in the available list
        assert "nonexistent_agent" not in result["selected_agents"]
        assert "aws" not in result["selected_agents"]
        assert "kubernetes" in result["selected_agents"]

    @patch("nodes.planner.build_llm")
    def test_fallback_agents_when_none_configured(self, mock_build_llm):
        """When no sub_agents configured, uses fallback agent list."""
        state = {
            "alert": {"name": "test"},
            "team_config": {"agents": {}},
            "iteration": 0,
            "messages": [],
        }
        plan_response = {
            "hypotheses": [
                {
                    "hypothesis": "test",
                    "priority": "high",
                    "agents_to_test": ["kubernetes"],
                }
            ],
            "selected_agents": ["kubernetes", "metrics"],
            "reasoning": "test",
        }
        mock_build_llm.return_value = _make_mock_llm(plan_response)

        from nodes.planner import planner

        result = planner(state)

        # Should use fallback agents
        assert len(result["selected_agents"]) >= 1

    @patch("nodes.planner.build_llm")
    def test_llm_invoke_failure_returns_fallback(self, mock_build_llm, sample_state):
        """When LLM invoke raises (not build_llm), returns fallback plan."""
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("API error")
        mock_build_llm.return_value = mock_llm

        from nodes.planner import planner

        result = planner(sample_state)

        assert len(result["hypotheses"]) >= 1
        assert (
            "error" in result["hypotheses"][0]["hypothesis"].lower()
            or "Fallback" in result["hypotheses"][0]["hypothesis"]
        )
        assert len(result["selected_agents"]) > 0
