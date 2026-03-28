"""End-to-end tests for the LangGraph investigation graph.

Tests the full graph flow with mocked LLM and external dependencies.
Verifies that the graph assembles correctly and data flows through all nodes.
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
    """Mimics langchain_core.messages.AIMessage."""

    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


PLANNER_RESPONSE = json.dumps(
    {
        "hypotheses": [
            {
                "hypothesis": "High error rate caused by OOM in payment pods",
                "priority": "high",
                "agents_to_test": ["kubernetes"],
            }
        ],
        "selected_agents": ["kubernetes"],
        "reasoning": "Kubernetes investigation needed for pod-level issues",
    }
)

SUBAGENT_FINDINGS = (
    "Found pod payment-service-abc123 restarting due to OOMKilled. "
    "Memory limit 512Mi exceeded. Last restart 5 minutes ago."
)

SYNTHESIZER_SUFFICIENT = json.dumps(
    {
        "sufficient_evidence": True,
        "confidence": 0.85,
        "summary": "Root cause identified: OOMKilled pods in payment-service",
        "gaps": [],
        "feedback": "",
    }
)

WRITEUP_RESPONSE = (
    "# Incident Report: Payment Service High Error Rate\n\n"
    "Root cause: payment-service pods OOMKilled due to 512Mi memory limit.\n\n"
    "```json\n"
    + json.dumps(
        {
            "title": "Payment Service OOMKill",
            "severity": "critical",
            "services": ["payment-service"],
            "root_cause": "OOM due to insufficient memory limits",
            "findings": [
                {
                    "category": "Kubernetes",
                    "detail": "OOMKilled pods",
                    "evidence": "kubectl logs",
                }
            ],
            "action_items": [
                {
                    "priority": "high",
                    "action": "Increase memory limit to 1Gi",
                    "owner": "platform",
                }
            ],
            "resolution_status": "mitigated",
        }
    )
    + "\n```"
)


class MockLLM:
    """Mock LLM that returns deterministic responses based on the calling node.

    Identifies the caller by inspecting the system prompt content.
    """

    def invoke(self, messages, **kwargs):
        system = ""
        for msg in messages:
            if hasattr(msg, "content"):
                system += msg.content + " "

        # Order matters: check specific keywords before generic ones
        if "Planner" in system and "hypotheses" in system.lower():
            return MockAIMessage(content=PLANNER_RESPONSE)
        elif "Writeup" in system and "JSON Report Schema" in system:
            return MockAIMessage(content=WRITEUP_RESPONSE)
        elif "Synthesizer" in system and "sufficient_evidence" in system.lower():
            return MockAIMessage(content=SYNTHESIZER_SUFFICIENT)
        elif "investigation agent" in system.lower():
            return MockAIMessage(content=SUBAGENT_FINDINGS)
        elif "Planner" in system:
            return MockAIMessage(content=PLANNER_RESPONSE)
        elif "Writeup" in system:
            return MockAIMessage(content=WRITEUP_RESPONSE)
        elif "Synthesizer" in system:
            return MockAIMessage(content=SYNTHESIZER_SUFFICIENT)
        return MockAIMessage(content="OK")

    def bind_tools(self, tools):
        """Return self -- mock LLM never produces tool calls."""
        return self


MOCK_TEAM_CONFIG_RAW = {
    "agents": {
        "planner": {
            "prompt": {"system": ""},
            "model": {"name": "test-model"},
            "max_iterations": 3,
        },
        "investigation": {
            "sub_agents": {"kubernetes": True, "metrics": True},
        },
        "writeup": {
            "prompt": {"system": ""},
            "model": {"name": "test-model"},
        },
    },
    "skills": {"enabled": ["*"]},
}


TEST_ALERT = {
    "name": "HighErrorRate",
    "service": "payment-service",
    "severity": "critical",
    "timestamp": "2026-03-18T10:00:00Z",
    "description": "Payment service error rate above 5% for 10 minutes",
}


def _mock_load_team_config():
    """Return a mock TeamConfig with .raw_config."""
    mock_config = MagicMock()
    mock_config.raw_config = MOCK_TEAM_CONFIG_RAW
    return mock_config


def _build_graph_with_mocks():
    """Build the investigation graph with all external deps mocked."""
    from graph import build_graph

    checkpointer = MemorySaver()
    graph = build_graph(checkpointer=checkpointer)
    return graph, checkpointer


# ---------------------------------------------------------------------------
# Patches applied to every test
# ---------------------------------------------------------------------------


def _common_patches():
    """Return a list of patch context managers for all external deps."""
    return [
        patch(
            "nodes.init_context.load_team_config", side_effect=_mock_load_team_config
        ),
        patch("nodes.planner.build_llm", return_value=MockLLM()),
        patch("nodes.synthesizer.build_llm", return_value=MockLLM()),
        patch("nodes.writeup.build_llm", return_value=MockLLM()),
        patch("nodes.subagent_executor.build_llm", return_value=MockLLM()),
        patch("nodes.subagent_executor.resolve_tools", return_value=[]),
        patch(
            "nodes.subagent_executor.get_skill_catalog",
            return_value="No skills loaded.",
        ),
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


class TestGraphFullFlow:
    """Test the complete investigation graph end-to-end."""

    def test_graph_full_flow(self):
        """Invoke graph with a test alert and verify it produces conclusion + structured_report."""
        patches = _common_patches()
        for p in patches:
            p.start()

        try:
            # Need to reimport graph module after patches so the module-level
            # make_subagent_executor() picks up the mocked dependencies.
            # But since patches target the nodes' namespace, the existing
            # compiled graph should work.
            graph, _ = _build_graph_with_mocks()

            config = {"configurable": {"thread_id": "test-full-flow"}}
            initial_state = {
                "alert": TEST_ALERT,
                "thread_id": "test-full-flow",
                "images": [],
            }

            result = graph.invoke(initial_state, config=config)

            # --- Assertions ---
            assert result is not None, "Graph returned None"

            # Must have a conclusion (markdown report)
            conclusion = result.get("conclusion", "")
            assert len(conclusion) > 0, "No conclusion produced"

            # Must have a structured report
            structured_report = result.get("structured_report", {})
            assert isinstance(
                structured_report, dict
            ), "structured_report is not a dict"
            assert "title" in structured_report, "structured_report missing 'title'"
            assert (
                "severity" in structured_report
            ), "structured_report missing 'severity'"

            # Status should be completed
            assert (
                result.get("status") == "completed"
            ), f"Expected completed, got {result.get('status')}"

            # Investigation ID was generated
            assert result.get("investigation_id"), "No investigation_id"

            # Agent states should contain kubernetes results
            agent_states = result.get("agent_states", {})
            assert (
                "kubernetes" in agent_states
            ), f"kubernetes not in agent_states: {list(agent_states.keys())}"
            assert agent_states["kubernetes"]["status"] == "completed"

        finally:
            for p in patches:
                p.stop()

    def test_graph_handles_empty_alert(self):
        """Verify the graph completes even with an empty alert dict."""
        patches = _common_patches()
        for p in patches:
            p.start()

        try:
            graph, _ = _build_graph_with_mocks()

            config = {"configurable": {"thread_id": "test-empty-alert"}}
            initial_state = {
                "alert": {},
                "thread_id": "test-empty-alert",
                "images": [],
            }

            result = graph.invoke(initial_state, config=config)

            # Graph should still complete (nodes handle empty alert gracefully)
            assert result is not None, "Graph returned None"
            # Should have a conclusion (even if generic)
            assert result.get("conclusion") is not None, "No conclusion field"

        finally:
            for p in patches:
                p.stop()

    def test_graph_topology_has_all_nodes(self):
        """Verify the graph contains all expected nodes."""
        patches = _common_patches()
        for p in patches:
            p.start()

        try:
            graph, _ = _build_graph_with_mocks()

            # LangGraph compiled graph exposes node names via .get_graph()
            graph_def = graph.get_graph()
            node_ids = {node.id for node in graph_def.nodes.values()}

            expected_nodes = {
                "init_context",
                "memory_lookup",
                "kg_context",
                "planner",
                "subagent",
                "synthesizer_node",
                "writeup_node",
                "memory_store",
            }

            for node in expected_nodes:
                assert (
                    node in node_ids
                ), f"Missing node '{node}' in graph. Found: {node_ids}"

        finally:
            for p in patches:
                p.stop()

    def test_graph_preserves_alert_in_state(self):
        """Verify alert data survives through the entire graph."""
        patches = _common_patches()
        for p in patches:
            p.start()

        try:
            graph, _ = _build_graph_with_mocks()

            config = {"configurable": {"thread_id": "test-alert-preserved"}}
            initial_state = {
                "alert": TEST_ALERT,
                "thread_id": "test-alert-preserved",
                "images": [],
            }

            result = graph.invoke(initial_state, config=config)

            assert (
                result.get("alert") == TEST_ALERT
            ), "Alert was modified during graph execution"

        finally:
            for p in patches:
                p.stop()
