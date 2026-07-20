"""
Task 4: resolve_agent_tools — neutralise LangGraph tool names so agents get full SDK tools.

TDD test: written first (red), then config.py implementation makes it green.
"""

from config import ToolsConfig, resolve_agent_tools


class TestResolveAgentTools:
    """resolve_agent_tools(tools_cfg) -> list[str] | None"""

    def test_langgraph_names_return_none(self):
        """Bogus LangGraph names (docker_ps, think) must yield None (wildcard)."""
        result = resolve_agent_tools(ToolsConfig(enabled=["docker_ps", "think"]))
        assert result is None

    def test_explicit_wildcard_returns_none(self):
        """['*'] must yield None (full tools)."""
        result = resolve_agent_tools(ToolsConfig(enabled=["*"]))
        assert result is None

    def test_real_sdk_tools_honored(self):
        """A non-empty subset of valid SDK tool names must be returned as-is."""
        result = resolve_agent_tools(ToolsConfig(enabled=["Bash", "Read"]))
        assert result == ["Bash", "Read"]

    def test_empty_enabled_returns_none(self):
        """Empty list must yield None (wildcard/no restriction)."""
        result = resolve_agent_tools(ToolsConfig(enabled=[]))
        assert result is None

    def test_single_valid_sdk_tool_honored(self):
        """A single valid SDK tool name must be returned."""
        result = resolve_agent_tools(ToolsConfig(enabled=["Bash"]))
        assert result == ["Bash"]

    def test_mix_of_sdk_and_langgraph_returns_none(self):
        """A mix of valid SDK names and LangGraph names must yield None (not partial)."""
        result = resolve_agent_tools(ToolsConfig(enabled=["Bash", "docker_ps"]))
        assert result is None

    def test_all_sdk_tools_honored(self):
        """The full set of valid SDK tool names must be returned."""
        all_tools = [
            "Read",
            "Write",
            "Edit",
            "Bash",
            "Glob",
            "Grep",
            "WebSearch",
            "WebFetch",
            "AskUserQuestion",
            "Task",
        ]
        result = resolve_agent_tools(ToolsConfig(enabled=all_tools))
        assert result == all_tools

    def test_task_is_valid(self):
        """Task is a valid SDK tool name and must be honored."""
        result = resolve_agent_tools(ToolsConfig(enabled=["Task"]))
        assert result == ["Task"]

    def test_skill_is_no_longer_a_valid_tool_name(self):
        """ "Skill" was dropped from allowed_tools in favor of ClaudeAgentOptions.skills
        (deprecated per SDK 0.1.77+); an explicit "Skill" entry is now an unknown
        name and falls through to None (full default), same as a LangGraph leftover.
        """
        result = resolve_agent_tools(ToolsConfig(enabled=["Skill", "Task"]))
        assert result is None
