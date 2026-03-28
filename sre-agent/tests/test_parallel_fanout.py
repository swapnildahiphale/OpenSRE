"""Tests for the Send() fan-out mechanism and subagent parallelism.

Verifies that:
- Multiple subagents receive correct payloads via Send()
- Agent states merge correctly via merge_dicts reducer
- Empty selected_agents skips to synthesizer
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
from unittest.mock import MagicMock, patch

from langgraph.checkpoint.memory import MemorySaver

# ---------------------------------------------------------------------------
# Mock LLM infrastructure
# ---------------------------------------------------------------------------


class MockAIMessage:
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


MOCK_TEAM_CONFIG_RAW = {
    "agents": {
        "planner": {
            "prompt": {"system": ""},
            "model": {"name": "test"},
            "max_iterations": 1,
        },
        "investigation": {
            "sub_agents": {"kubernetes": True, "metrics": True, "log_analysis": True},
        },
        "writeup": {"prompt": {"system": ""}, "model": {"name": "test"}},
    },
    "skills": {"enabled": ["*"]},
}

TEST_ALERT = {
    "name": "HighLatency",
    "service": "api-gateway",
    "severity": "warning",
    "description": "P99 latency above 2s for 15 minutes",
}


def _mock_load_team_config():
    mock_config = MagicMock()
    mock_config.raw_config = MOCK_TEAM_CONFIG_RAW
    return mock_config


class StructuredOutputMock:
    """Mock for llm.with_structured_output() that returns Pydantic model instances."""

    def __init__(self, parent_llm, schema_cls):
        self._parent = parent_llm
        self._schema_cls = schema_cls

    def invoke(self, messages, **kwargs):
        # Get the raw response from parent
        raw = self._parent.invoke(messages, **kwargs)
        # Parse JSON content into the Pydantic model
        data = json.loads(raw.content)
        return self._schema_cls(**data)


class FanoutMockLLM:
    """Mock LLM that selects multiple subagents and tracks per-agent calls."""

    def __init__(self, agents_to_select=None):
        self._agents_to_select = agents_to_select or ["kubernetes", "metrics"]
        self._subagent_calls = {}

    def invoke(self, messages, **kwargs):
        system = ""
        for msg in messages:
            if hasattr(msg, "content"):
                system += msg.content + " "

        # Order matters: check specific keywords before generic "investigation"
        if "Planner" in system and "hypotheses" in system.lower():
            return MockAIMessage(
                content=json.dumps(
                    {
                        "hypotheses": [
                            {
                                "hypothesis": "Network latency spike",
                                "priority": "high",
                                "agents_to_test": self._agents_to_select,
                            },
                        ],
                        "selected_agents": self._agents_to_select,
                        "reasoning": "Multi-agent investigation needed",
                    }
                )
            )
        elif "Writeup" in system and "JSON Report Schema" in system:
            return MockAIMessage(
                content=(
                    "# Latency Investigation Report\n\n"
                    "Multiple agents confirmed latency issues.\n\n"
                    "```json\n"
                    + json.dumps(
                        {
                            "title": "API Gateway Latency Spike",
                            "severity": "warning",
                            "services": ["api-gateway"],
                            "root_cause": "Network congestion",
                            "findings": [],
                            "action_items": [],
                            "resolution_status": "investigating",
                        }
                    )
                    + "\n```"
                )
            )
        elif "Synthesizer" in system and "sufficient_evidence" in system.lower():
            return MockAIMessage(
                content=json.dumps(
                    {
                        "sufficient_evidence": True,
                        "confidence": 0.85,
                        "summary": "Combined evidence from multiple agents confirms latency issue",
                        "gaps": [],
                        "feedback": "",
                    }
                )
            )
        elif "investigation agent" in system.lower():
            # Determine which agent this is from the system prompt
            agent_id = "unknown"
            for agent_name in ["kubernetes", "metrics", "log_analysis"]:
                if agent_name in system.lower():
                    agent_id = agent_name
                    break
            self._subagent_calls[agent_id] = self._subagent_calls.get(agent_id, 0) + 1
            return MockAIMessage(
                content=f"[{agent_id}] Found relevant evidence for latency spike in api-gateway."
            )
        elif "Planner" in system:
            return MockAIMessage(
                content=json.dumps(
                    {
                        "hypotheses": [
                            {
                                "hypothesis": "Fallback",
                                "priority": "high",
                                "agents_to_test": self._agents_to_select,
                            }
                        ],
                        "selected_agents": self._agents_to_select,
                        "reasoning": "Fallback plan",
                    }
                )
            )
        return MockAIMessage(content="OK")

    def bind_tools(self, tools):
        return self

    def with_structured_output(self, schema_cls):
        return StructuredOutputMock(self, schema_cls)


def _build_patches(mock_llm):
    return [
        patch(
            "nodes.init_context.load_team_config", side_effect=_mock_load_team_config
        ),
        patch("nodes.planner.build_llm", return_value=mock_llm),
        patch("nodes.synthesizer.build_llm", return_value=mock_llm),
        patch("nodes.writeup.build_llm", return_value=mock_llm),
        patch("nodes.subagent_executor.build_llm", return_value=mock_llm),
        patch("nodes.subagent_executor.resolve_tools", return_value=[]),
        patch("nodes.subagent_executor.get_skill_catalog", return_value=""),
        patch("nodes.subagent_executor.get_skills_for_agent", return_value=["*"]),
        patch(
            "nodes.memory_lookup.enhance_investigation_with_memory",
            side_effect=lambda prompt, **kw: prompt,
        ),
        patch(
            "tools.neo4j_semantic_layer.KubernetesGraphTools",
            side_effect=ImportError("Neo4j not available"),
        ),
        patch("nodes.memory_store.store_investigation_result", return_value=None),
    ]


class TestParallelFanout:
    """Tests for Send() fan-out to multiple subagents."""

    def test_multiple_subagents_receive_correct_payloads(self):
        """Verify that when planner selects multiple agents, each receives a Send()."""
        mock_llm = FanoutMockLLM(agents_to_select=["kubernetes", "metrics"])
        patches = _build_patches(mock_llm)
        for p in patches:
            p.start()

        try:
            from graph import build_graph

            graph = build_graph(checkpointer=MemorySaver())
            config = {"configurable": {"thread_id": "test-fanout-payloads"}}

            result = graph.invoke(
                {
                    "alert": TEST_ALERT,
                    "thread_id": "test-fanout-payloads",
                    "images": [],
                },
                config=config,
            )

            # Both agents should appear in agent_states
            agent_states = result.get("agent_states", {})
            assert (
                "kubernetes" in agent_states
            ), f"kubernetes not in agent_states: {list(agent_states.keys())}"
            assert (
                "metrics" in agent_states
            ), f"metrics not in agent_states: {list(agent_states.keys())}"

            # Each agent should have completed
            for agent_id in ["kubernetes", "metrics"]:
                assert (
                    agent_states[agent_id]["status"] == "completed"
                ), f"{agent_id} status: {agent_states[agent_id]['status']}"
                assert agent_states[agent_id]["findings"], f"{agent_id} has no findings"

        finally:
            for p in patches:
                p.stop()

    def test_agent_states_merge_correctly(self):
        """Verify merge_dicts reducer combines results from multiple subagents.

        Each subagent returns {agent_states: {agent_id: {...}}}.
        The merge_dicts reducer should shallow-merge these into a single dict.
        """
        mock_llm = FanoutMockLLM(
            agents_to_select=["kubernetes", "metrics", "log_analysis"]
        )
        patches = _build_patches(mock_llm)
        for p in patches:
            p.start()

        try:
            from graph import build_graph

            graph = build_graph(checkpointer=MemorySaver())
            config = {"configurable": {"thread_id": "test-merge"}}

            result = graph.invoke(
                {"alert": TEST_ALERT, "thread_id": "test-merge", "images": []},
                config=config,
            )

            agent_states = result.get("agent_states", {})

            # All three agents should be present after merge
            assert (
                len(agent_states) >= 3
            ), f"Expected >= 3 agent states after merge, got {len(agent_states)}: {list(agent_states.keys())}"

            # Each should have its own findings (not overwritten by others)
            for agent_id in ["kubernetes", "metrics", "log_analysis"]:
                assert (
                    agent_id in agent_states
                ), f"{agent_id} missing from merged states"
                findings = agent_states[agent_id].get("findings", "")
                assert len(findings) > 0, f"{agent_id} has empty findings"

        finally:
            for p in patches:
                p.stop()

    def test_empty_selected_agents_skips_to_synthesizer(self):
        """When planner selects no agents, graph should skip to synthesizer.

        The _route_to_subagents function sends directly to synthesizer_node
        when selected_agents is empty.
        """
        # Create a mock LLM that returns empty selected_agents
        mock_llm = FanoutMockLLM(agents_to_select=[])
        patches = _build_patches(mock_llm)
        for p in patches:
            p.start()

        try:
            from graph import build_graph

            graph = build_graph(checkpointer=MemorySaver())
            config = {"configurable": {"thread_id": "test-empty-agents"}}

            result = graph.invoke(
                {"alert": TEST_ALERT, "thread_id": "test-empty-agents", "images": []},
                config=config,
            )

            # Graph should still complete without hanging
            assert (
                result.get("status") == "completed"
            ), f"Expected completed status, got {result.get('status')}"

            # Should still produce conclusion and report
            assert result.get("conclusion"), "No conclusion with empty agents"
            assert isinstance(
                result.get("structured_report"), dict
            ), "structured_report should be a dict"

        finally:
            for p in patches:
                p.stop()


class TestRoutingFunctions:
    """Unit tests for the graph routing functions (no graph invocation needed)."""

    def test_route_after_init_returns_both_context_nodes(self):
        """_route_after_init should always return memory_lookup and kg_context."""
        from graph import _route_after_init

        result = _route_after_init({})
        assert "memory_lookup" in result
        assert "kg_context" in result
        assert len(result) == 2

    def test_route_to_subagents_creates_sends(self):
        """_route_to_subagents should create one Send per selected agent."""
        from graph import _route_to_subagents

        state = {
            "selected_agents": ["kubernetes", "metrics"],
            "alert": TEST_ALERT,
            "hypotheses": [],
            "team_config": {},
            "max_react_loops": 5,
            "thread_id": "test",
            "memory_context": {},
            "kg_context": {},
        }

        sends = _route_to_subagents(state)
        assert len(sends) == 2, f"Expected 2 Send objects, got {len(sends)}"

        # Verify each Send targets the "subagent" node
        for send in sends:
            assert send.node == "subagent", f"Send targets {send.node}, not 'subagent'"

    def test_route_to_subagents_empty_sends_to_synthesizer(self):
        """With no selected agents, should send to synthesizer_node."""
        from graph import _route_to_subagents

        state = {"selected_agents": []}
        sends = _route_to_subagents(state)

        assert len(sends) == 1
        assert sends[0].node == "synthesizer_node"

    def test_route_after_synthesis_completed(self):
        """Completed status routes to writeup."""
        from graph import _route_after_synthesis

        result = _route_after_synthesis(
            {"status": "completed", "iteration": 0, "max_iterations": 3}
        )
        assert result == "writeup_node"

    def test_route_after_synthesis_running(self):
        """Running status routes back to planner."""
        from graph import _route_after_synthesis

        result = _route_after_synthesis(
            {"status": "running", "iteration": 1, "max_iterations": 3}
        )
        assert result == "planner"

    def test_route_after_synthesis_max_iterations_forces_writeup(self):
        """At max iterations, always routes to writeup regardless of status."""
        from graph import _route_after_synthesis

        result = _route_after_synthesis(
            {"status": "running", "iteration": 3, "max_iterations": 3}
        )
        assert result == "writeup_node"


class TestMergeDicts:
    """Unit tests for the merge_dicts reducer used by agent_states."""

    def test_merge_dicts_combines_disjoint_keys(self):
        from state import merge_dicts

        left = {"kubernetes": {"status": "completed"}}
        right = {"metrics": {"status": "completed"}}
        merged = merge_dicts(left, right)

        assert "kubernetes" in merged
        assert "metrics" in merged

    def test_merge_dicts_right_overwrites_left(self):
        from state import merge_dicts

        left = {"kubernetes": {"status": "running"}}
        right = {"kubernetes": {"status": "completed"}}
        merged = merge_dicts(left, right)

        assert merged["kubernetes"]["status"] == "completed"

    def test_merge_dicts_empty_left(self):
        from state import merge_dicts

        merged = merge_dicts({}, {"kubernetes": {"status": "completed"}})
        assert merged == {"kubernetes": {"status": "completed"}}

    def test_merge_dicts_empty_right(self):
        from state import merge_dicts

        left = {"kubernetes": {"status": "completed"}}
        merged = merge_dicts(left, {})
        assert merged == left
