"""
Tests for dependency validation.

Tests:
- Can't disable integration if tool depends on it
- Can't disable tool if agent uses it
- Can't disable sub-agent if agent uses it
- Can't disable MCP if agent uses it
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.dependency_validator import (
    validate_config_change,
    validate_integration_dependencies,
    validate_mcp_dependencies,
    validate_subagent_dependencies,
    validate_tool_dependencies,
)


class TestIntegrationDependencies:
    """Test integration → tool dependency validation."""

    def test_cannot_disable_integration_with_dependent_tool(self):
        """Test that disabling integration with dependent tool fails."""
        effective_config = {
            "tools": {
                "grafana_query_prometheus": {
                    "enabled": True,
                    "requires_integration": "grafana",
                }
            },
            "integrations": {"grafana": {"enabled": False}},  # Trying to disable
        }

        error = validate_integration_dependencies(
            effective_config, "grafana", False  # new_enabled_state
        )

        assert error is not None
        assert "grafana_query_prometheus" in error.dependents
        assert "Cannot disable integration 'grafana'" in error.message

    def test_can_disable_integration_with_no_dependents(self):
        """Test that disabling integration with no dependents is allowed."""
        effective_config = {
            "tools": {
                "grafana_query_prometheus": {
                    "enabled": False,  # Tool already disabled
                    "requires_integration": "grafana",
                }
            },
            "integrations": {"grafana": {"enabled": False}},
        }

        error = validate_integration_dependencies(effective_config, "grafana", False)

        assert error is None

    def test_enabling_integration_always_allowed(self):
        """Test that enabling integration is always allowed."""
        effective_config = {"integrations": {"grafana": {"enabled": True}}}

        error = validate_integration_dependencies(
            effective_config, "grafana", True  # Enabling
        )

        assert error is None


class TestToolDependencies:
    """Test tool → agent dependency validation."""

    def test_cannot_disable_tool_used_by_agent(self):
        """Test that disabling tool used by agent fails."""
        effective_config = {
            "agents": {
                "planner": {"enabled": True, "tools": {"think": True, "llm_call": True}}
            },
            "tools": {"think": {"enabled": False}},  # Trying to disable
        }

        error = validate_tool_dependencies(effective_config, "think", False)

        assert error is not None
        assert "planner" in error.dependents
        assert "Cannot disable tool 'think'" in error.message

    def test_can_disable_tool_not_used(self):
        """Test that disabling unused tool is allowed."""
        effective_config = {
            "agents": {
                "planner": {"enabled": True, "tools": {"think": True, "llm_call": True}}
            },
            "tools": {"web_search": {"enabled": False}},
        }

        error = validate_tool_dependencies(effective_config, "web_search", False)

        assert error is None

    def test_special_wildcard_tool(self):
        """Test that wildcard tool (*) means all tools are used."""
        effective_config = {
            "agents": {
                "investigation": {
                    "enabled": True,
                    "tools": {"*": True},  # All tools enabled
                }
            },
            "tools": {"any_tool": {"enabled": False}},
        }

        error = validate_tool_dependencies(effective_config, "any_tool", False)

        # Should fail because agent uses all tools
        assert error is not None
        assert "investigation" in error.dependents


class TestSubAgentDependencies:
    """Test sub-agent → agent dependency validation."""

    def test_cannot_disable_subagent_used_by_agent(self):
        """Test that disabling sub-agent used by agent fails."""
        effective_config = {
            "agents": {
                "planner": {
                    "enabled": True,
                    "sub_agents": {"investigation": True, "k8s": True},
                },
                "investigation": {"enabled": False},  # Trying to disable
            }
        }

        error = validate_subagent_dependencies(effective_config, "investigation", False)

        assert error is not None
        assert "planner" in error.dependents
        assert "Cannot disable agent 'investigation'" in error.message

    def test_can_disable_subagent_not_used(self):
        """Test that disabling unused sub-agent is allowed."""
        effective_config = {
            "agents": {
                "planner": {"enabled": True, "sub_agents": {"investigation": True}},
                "k8s": {"enabled": False},  # Not used by planner
            }
        }

        error = validate_subagent_dependencies(effective_config, "k8s", False)

        assert error is None

    def test_disabled_agent_doesnt_block(self):
        """Test that disabled agent using sub-agent doesn't block."""
        effective_config = {
            "agents": {
                "planner": {
                    "enabled": False,  # Agent is disabled
                    "sub_agents": {"investigation": True},
                },
                "investigation": {"enabled": False},
            }
        }

        error = validate_subagent_dependencies(effective_config, "investigation", False)

        # Should be allowed because planner is disabled
        assert error is None


class TestMCPDependencies:
    """Test MCP → agent dependency validation."""

    def test_cannot_disable_mcp_used_by_agent(self):
        """Test that disabling MCP used by agent fails."""
        effective_config = {
            "agents": {"planner": {"enabled": True, "mcps": {"github-mcp": True}}},
            "mcp_servers": {"github-mcp": {"enabled": False}},  # Trying to disable
        }

        error = validate_mcp_dependencies(effective_config, "github-mcp", False)

        assert error is not None
        assert "planner" in error.dependents
        assert "Cannot disable MCP 'github-mcp'" in error.message

    def test_can_disable_mcp_not_used(self):
        """Test that disabling unused MCP is allowed."""
        effective_config = {
            "agents": {"planner": {"enabled": True, "mcps": {}}},
            "mcp_servers": {"github-mcp": {"enabled": False}},
        }

        error = validate_mcp_dependencies(effective_config, "github-mcp", False)

        assert error is None


class TestFullConfigValidation:
    """Test full config validation with multiple changes."""

    def test_validate_multiple_changes(self):
        """Test validation with multiple changes in one patch."""
        effective_config = {
            "agents": {
                "planner": {
                    "enabled": True,
                    "tools": {"think": True, "web_search": True},
                    "sub_agents": {"investigation": True},
                    "mcps": {"github-mcp": True},
                },
                "investigation": {"enabled": False},  # Trying to disable
            },
            "tools": {
                "think": {
                    "enabled": False,  # Trying to disable
                    "requires_integration": None,
                },
                "grafana_query_prometheus": {
                    "enabled": True,
                    "requires_integration": "grafana",
                },
            },
            "integrations": {"grafana": {"enabled": False}},  # Trying to disable
            "mcp_servers": {"github-mcp": {"enabled": False}},  # Trying to disable
        }

        patch = {
            "agents": {"investigation": {"enabled": False}},
            "tools": {"think": {"enabled": False}},
            "integrations": {"grafana": {"enabled": False}},
            "mcp_servers": {"github-mcp": {"enabled": False}},
        }

        errors = validate_config_change(effective_config, patch)

        # Should have 4 errors (one for each dependency violation)
        assert len(errors) == 4

        # Check that all expected errors are present
        error_messages = [str(err) for err in errors]
        assert any(
            "investigation" in msg and "sub-agent" in msg for msg in error_messages
        )
        assert any("think" in msg and "tool" in msg for msg in error_messages)
        assert any("grafana" in msg and "integration" in msg for msg in error_messages)
        assert any("github-mcp" in msg and "MCP" in msg for msg in error_messages)

    def test_validate_safe_changes(self):
        """Test that safe changes pass validation."""
        effective_config = {
            "agents": {"planner": {"enabled": True, "tools": {"think": True}}},
            "tools": {"think": {"enabled": True}, "unused_tool": {"enabled": False}},
        }

        patch = {"tools": {"unused_tool": {"enabled": False}}}

        errors = validate_config_change(effective_config, patch)

        # Should have no errors
        assert len(errors) == 0

    def test_correct_order_of_operations(self):
        """Test that disabling dependents first allows disabling dependencies."""
        # This is conceptual - in practice, this would be two separate API calls

        # First, disable the tool in agent
        config_after_step1 = {
            "agents": {
                "planner": {
                    "enabled": True,
                    "tools": {
                        # think removed
                    },
                }
            },
            "tools": {"think": {"enabled": True}},
        }

        patch_step1 = {
            "agents": {"planner": {"tools": {"think": False}}}  # Remove from agent
        }

        errors1 = validate_config_change(config_after_step1, patch_step1)
        assert len(errors1) == 0  # Should succeed

        # Then, disable the tool itself
        config_after_step2 = {
            "agents": {"planner": {"enabled": True, "tools": {"think": False}}},
            "tools": {"think": {"enabled": False}},
        }

        patch_step2 = {"tools": {"think": {"enabled": False}}}

        errors2 = validate_config_change(config_after_step2, patch_step2)
        assert len(errors2) == 0  # Should also succeed
