"""Tests for config.py extensions — get_skills_for_agent and build_llm."""

import os
from unittest.mock import patch

from config import (
    AgentConfig,
    MemoryConfig,
    ModelConfig,
    SkillsConfig,
    TeamConfig,
    build_llm,
    get_skills_for_agent,
)


def _make_team_config(agents=None, skills=None):
    """Helper to create a TeamConfig with defaults."""
    return TeamConfig(
        agents=agents or {},
        skills=skills or SkillsConfig(),
        memory=MemoryConfig(),
        business_context="",
        raw_config={},
    )


class TestGetSkillsForAgent:
    @patch("config.build_skill_name_map", return_value={})
    @patch("config.parse_enabled_skills_env", return_value=None)
    def test_no_agent_skills_returns_none(self, mock_env, mock_map):
        """When no agent has skill overrides and team config is wildcard, returns None (all allowed)."""
        tc = _make_team_config()
        result = get_skills_for_agent("planner", tc, "/fake/skills")
        assert result is None

    @patch(
        "config.build_skill_name_map", return_value={"infra-k8s": "kubernetes-debug"}
    )
    @patch("config.parse_enabled_skills_env", return_value=None)
    def test_agent_with_specific_skills(self, mock_env, mock_map):
        """When agent config has specific skill toggles, returns filtered set."""
        agents = {
            "investigator": AgentConfig(
                enabled=True,
                name="investigator",
                skills={"kubernetes-debug": True, "grafana-dashboards": False},
            )
        }
        tc = _make_team_config(agents=agents)
        result = get_skills_for_agent("investigator", tc, "/fake/skills")
        assert result is not None
        assert "kubernetes-debug" in result
        assert "grafana-dashboards" not in result

    @patch("config.build_skill_name_map", return_value={})
    @patch("config.parse_enabled_skills_env", return_value=None)
    def test_agent_with_all_false_skills_returns_none(self, mock_env, mock_map):
        """When agent has skills but all are False, returns None (safety fallback)."""
        agents = {
            "investigator": AgentConfig(
                enabled=True,
                name="investigator",
                skills={"kubernetes-debug": False},
            )
        }
        tc = _make_team_config(agents=agents)
        # No enabled_ids => agent_skills stays None => falls through to team-level
        result = get_skills_for_agent("investigator", tc, "/fake/skills")
        assert result is None

    @patch("config.build_skill_name_map", return_value={})
    def test_env_override_takes_priority(self, mock_map):
        """ENABLED_SKILLS env var overrides everything."""
        with patch("config.parse_enabled_skills_env", return_value={"my-skill"}):
            tc = _make_team_config()
            result = get_skills_for_agent("planner", tc, "/fake/skills")
            assert result == {"my-skill"}

    @patch("config.build_skill_name_map", return_value={})
    def test_team_level_enabled_list(self, mock_map):
        """Team-level skills.enabled list restricts skills."""
        with patch("config.parse_enabled_skills_env", return_value=None):
            tc = _make_team_config(
                skills=SkillsConfig(enabled=["skill-a", "skill-b"], disabled=[])
            )
            result = get_skills_for_agent("planner", tc, "/fake/skills")
            assert result is not None
            assert "skill-a" in result
            assert "skill-b" in result


class TestBuildLlm:
    @patch.dict(
        os.environ,
        {
            "LITELLM_BASE_URL": "http://test-litellm:4000/v1",
            "LITELLM_API_KEY": "test-key-123",
        },
    )
    @patch("langchain_openai.ChatOpenAI")
    def test_creates_chat_openai_with_correct_params(self, mock_cls):
        agent_config = AgentConfig(
            model=ModelConfig(name="claude-sonnet-4-20250514", temperature=0.7)
        )
        build_llm(agent_config)
        mock_cls.assert_called_once_with(
            base_url="http://test-litellm:4000/v1",
            api_key="test-key-123",
            model="claude-sonnet-4-20250514",
            temperature=0.7,
        )

    @patch.dict(
        os.environ,
        {
            "LITELLM_BASE_URL": "http://proxy:4000/v1",
            "LITELLM_API_KEY": "key-abc",
        },
    )
    @patch("langchain_openai.ChatOpenAI")
    def test_omits_none_params(self, mock_cls):
        """Temperature/max_tokens/top_p should be omitted when None."""
        agent_config = AgentConfig(model=ModelConfig(name="test-model"))
        build_llm(agent_config)
        call_kwargs = mock_cls.call_args[1]
        assert "temperature" not in call_kwargs
        assert "max_tokens" not in call_kwargs
        assert "top_p" not in call_kwargs

    @patch.dict(
        os.environ,
        {
            "LITELLM_BASE_URL": "http://proxy:4000/v1",
            "LITELLM_API_KEY": "key-abc",
        },
    )
    @patch("langchain_openai.ChatOpenAI")
    def test_includes_all_model_params(self, mock_cls):
        agent_config = AgentConfig(
            model=ModelConfig(name="gpt-4", temperature=0.5, max_tokens=1000, top_p=0.9)
        )
        build_llm(agent_config)
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["temperature"] == 0.5
        assert call_kwargs["max_tokens"] == 1000
        assert call_kwargs["top_p"] == 0.9

    @patch("langchain_openai.ChatOpenAI")
    def test_uses_fallback_env_vars(self, mock_cls):
        """When LITELLM_ vars not set, falls back to defaults."""
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("LITELLM_BASE_URL", "LITELLM_API_KEY", "OPENROUTER_API_KEY")
        }
        with patch.dict(os.environ, env, clear=True):
            agent_config = AgentConfig(model=ModelConfig(name="test"))
            build_llm(agent_config)
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["base_url"] == "http://litellm:4000/v1"
            assert call_kwargs["api_key"] == "sk-placeholder"
