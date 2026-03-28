"""Tests for nodes/init_context.py — entry node of the investigation graph."""

import os
import uuid
from unittest.mock import patch

from config import MemoryConfig, SkillsConfig, TeamConfig
from nodes.init_context import init_context


def _mock_team_config(**overrides):
    """Create a mock TeamConfig with defaults."""
    tc = TeamConfig(
        agents={},
        skills=SkillsConfig(),
        memory=MemoryConfig(),
        business_context="",
        raw_config=overrides.get("raw_config", {}),
    )
    return tc


class TestInitContext:
    @patch("nodes.init_context.load_team_config")
    def test_valid_alert_returns_populated_state(self, mock_load):
        mock_load.return_value = _mock_team_config()
        state = {
            "alert": {"name": "HighErrorRate", "service": "api"},
            "thread_id": "t1",
        }
        result = init_context(state)

        assert result["status"] == "running"
        assert result["iteration"] == 0
        assert result["thread_id"] == "t1"
        assert "investigation_id" in result
        assert result["agent_states"] == {}
        assert result["messages"] == []
        assert result["hypotheses"] == []
        assert result["selected_agents"] == []

    @patch("nodes.init_context.load_team_config")
    def test_empty_alert_returns_error(self, mock_load):
        mock_load.return_value = _mock_team_config()
        state = {"alert": {}}
        result = init_context(state)

        assert result["status"] == "error"
        assert "No alert data" in result["conclusion"]

    @patch("nodes.init_context.load_team_config")
    def test_missing_alert_returns_error(self, mock_load):
        mock_load.return_value = _mock_team_config()
        state = {}
        result = init_context(state)

        assert result["status"] == "error"

    @patch("nodes.init_context.load_team_config")
    def test_investigation_id_is_uuid(self, mock_load):
        mock_load.return_value = _mock_team_config()
        state = {"alert": {"name": "test"}}
        result = init_context(state)

        # Should be a valid UUID
        parsed = uuid.UUID(result["investigation_id"])
        assert str(parsed) == result["investigation_id"]

    @patch("nodes.init_context.load_team_config")
    def test_default_max_iterations_is_3(self, mock_load):
        mock_load.return_value = _mock_team_config()
        state = {"alert": {"name": "test"}}
        result = init_context(state)

        assert result["max_iterations"] == 3

    @patch("nodes.init_context.load_team_config")
    def test_max_iterations_from_config(self, mock_load):
        mock_load.return_value = _mock_team_config(
            raw_config={"agents": {"planner": {"max_iterations": 5}}}
        )
        state = {"alert": {"name": "test"}}
        result = init_context(state)

        assert result["max_iterations"] == 5

    @patch.dict(os.environ, {"SUBAGENT_MAX_REACT_LOOPS": "50"})
    @patch("nodes.init_context.load_team_config")
    def test_max_react_loops_from_env(self, mock_load):
        mock_load.return_value = _mock_team_config()
        state = {"alert": {"name": "test"}}
        result = init_context(state)

        assert result["max_react_loops"] == 50

    @patch.dict(os.environ, {}, clear=False)
    @patch("nodes.init_context.load_team_config")
    def test_default_max_react_loops(self, mock_load):
        mock_load.return_value = _mock_team_config()
        # Remove env var if present
        os.environ.pop("SUBAGENT_MAX_REACT_LOOPS", None)
        state = {"alert": {"name": "test"}}
        result = init_context(state)

        assert result["max_react_loops"] == 25

    @patch(
        "nodes.init_context.load_team_config",
        side_effect=Exception("connection refused"),
    )
    def test_config_failure_uses_defaults(self, mock_load):
        state = {"alert": {"name": "test"}}
        result = init_context(state)

        # Should still succeed with defaults
        assert result["status"] == "running"
        assert result["max_iterations"] == 3
        assert result["team_config"] == {}

    @patch("nodes.init_context.load_team_config")
    def test_images_passed_through(self, mock_load):
        mock_load.return_value = _mock_team_config()
        images = [{"url": "http://example.com/img.png"}]
        state = {"alert": {"name": "test"}, "images": images}
        result = init_context(state)

        assert result["images"] == images

    @patch("nodes.init_context.load_team_config")
    def test_empty_images_default(self, mock_load):
        mock_load.return_value = _mock_team_config()
        state = {"alert": {"name": "test"}}
        result = init_context(state)

        assert result["images"] == []
