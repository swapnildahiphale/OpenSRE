"""Tests for the planner-synthesizer feedback loop.

Verifies that the graph correctly loops back from synthesizer to planner
when evidence is insufficient, and respects max_iterations.
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


PLANNER_RESPONSE = json.dumps(
    {
        "hypotheses": [
            {
                "hypothesis": "OOM in pods",
                "priority": "high",
                "agents_to_test": ["kubernetes"],
            }
        ],
        "selected_agents": ["kubernetes"],
        "reasoning": "Investigate kubernetes",
    }
)

SYNTHESIZER_INSUFFICIENT = json.dumps(
    {
        "sufficient_evidence": False,
        "confidence": 0.3,
        "summary": "Not enough evidence yet",
        "gaps": ["Need to check metrics", "Need log analysis"],
        "feedback": "Check prometheus metrics for error rate spike pattern",
    }
)

SYNTHESIZER_SUFFICIENT = json.dumps(
    {
        "sufficient_evidence": True,
        "confidence": 0.9,
        "summary": "Root cause confirmed: OOM in payment pods",
        "gaps": [],
        "feedback": "",
    }
)

SUBAGENT_FINDINGS = "Found elevated error rates in payment-service pods."

WRITEUP_RESPONSE = (
    "# Report\n\n"
    "Root cause found.\n\n"
    "```json\n"
    + json.dumps(
        {
            "title": "Test Report",
            "severity": "critical",
            "services": ["payment-service"],
            "root_cause": "OOM",
            "findings": [],
            "action_items": [],
            "resolution_status": "resolved",
        }
    )
    + "\n```"
)


MOCK_TEAM_CONFIG_RAW = {
    "agents": {
        "planner": {
            "prompt": {"system": ""},
            "model": {"name": "test"},
            "max_iterations": 3,
        },
        "investigation": {"sub_agents": {"kubernetes": True}},
        "writeup": {"prompt": {"system": ""}, "model": {"name": "test"}},
    },
    "skills": {"enabled": ["*"]},
}


TEST_ALERT = {
    "name": "HighErrorRate",
    "service": "payment-service",
    "severity": "critical",
    "description": "Error rate above 5%",
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
        raw = self._parent.invoke(messages, **kwargs)
        data = json.loads(raw.content)
        return self._schema_cls(**data)


class LoopingMockLLM:
    """Mock LLM that returns insufficient evidence on first synth call, sufficient on second.

    Tracks call counts per node type to provide different responses across iterations.
    """

    def __init__(self, insufficient_count=1):
        self._synth_calls = 0
        self._planner_calls = 0
        self._insufficient_count = insufficient_count

    def invoke(self, messages, **kwargs):
        system = ""
        for msg in messages:
            if hasattr(msg, "content"):
                system += msg.content + " "

        # Order matters: check specific keywords before generic "investigation"
        if "Planner" in system and "hypotheses" in system.lower():
            self._planner_calls += 1
            return MockAIMessage(content=PLANNER_RESPONSE)
        elif "Writeup" in system and "JSON Report Schema" in system:
            return MockAIMessage(content=WRITEUP_RESPONSE)
        elif "Synthesizer" in system and "sufficient_evidence" in system.lower():
            self._synth_calls += 1
            if self._synth_calls <= self._insufficient_count:
                return MockAIMessage(content=SYNTHESIZER_INSUFFICIENT)
            return MockAIMessage(content=SYNTHESIZER_SUFFICIENT)
        elif "investigation agent" in system.lower():
            return MockAIMessage(content=SUBAGENT_FINDINGS)
        elif "Planner" in system:
            self._planner_calls += 1
            return MockAIMessage(content=PLANNER_RESPONSE)
        elif "Writeup" in system:
            return MockAIMessage(content=WRITEUP_RESPONSE)
        elif "Synthesizer" in system:
            self._synth_calls += 1
            return MockAIMessage(content=SYNTHESIZER_SUFFICIENT)
        return MockAIMessage(content="OK")

    def bind_tools(self, tools):
        return self

    def with_structured_output(self, schema_cls):
        return StructuredOutputMock(self, schema_cls)

    @property
    def planner_call_count(self):
        return self._planner_calls

    @property
    def synth_call_count(self):
        return self._synth_calls


def _build_patches(mock_llm):
    """Build the common patches using a shared mock LLM instance."""
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


class TestFeedbackLoop:
    """Tests for the planner <-> synthesizer feedback loop."""

    def test_loop_iterates_when_insufficient(self):
        """When synthesizer returns insufficient evidence, planner runs again."""
        mock_llm = LoopingMockLLM(insufficient_count=1)
        patches = _build_patches(mock_llm)
        for p in patches:
            p.start()

        try:
            from graph import build_graph

            graph = build_graph(checkpointer=MemorySaver())
            config = {"configurable": {"thread_id": "test-loop-iterate"}}

            result = graph.invoke(
                {"alert": TEST_ALERT, "thread_id": "test-loop-iterate", "images": []},
                config=config,
            )

            # Planner should have been called at least twice
            # (once for initial plan, once after insufficient feedback)
            assert (
                mock_llm.planner_call_count >= 2
            ), f"Expected planner to be called >= 2 times, got {mock_llm.planner_call_count}"

            # Synthesizer should have been called at least twice
            assert (
                mock_llm.synth_call_count >= 2
            ), f"Expected synthesizer to be called >= 2 times, got {mock_llm.synth_call_count}"

            # Should still complete successfully
            assert result.get("status") == "completed"
            assert result.get("conclusion"), "No conclusion produced after loop"

        finally:
            for p in patches:
                p.stop()

    def test_loop_stops_at_max_iterations(self):
        """Verify max_iterations is enforced -- graph stops even if evidence is always insufficient."""
        # Set insufficient_count very high so synthesizer never says "sufficient"
        mock_llm = LoopingMockLLM(insufficient_count=100)
        patches = _build_patches(mock_llm)
        for p in patches:
            p.start()

        try:
            from graph import build_graph

            graph = build_graph(checkpointer=MemorySaver())
            config = {"configurable": {"thread_id": "test-max-iter"}}

            result = graph.invoke(
                {"alert": TEST_ALERT, "thread_id": "test-max-iter", "images": []},
                config=config,
            )

            # max_iterations is 3 in team config
            # The synthesizer forces completion at iteration >= max_iterations - 1
            # and the routing function also enforces the cap.
            # Planner should not exceed max_iterations calls.
            assert (
                mock_llm.planner_call_count <= 3
            ), f"Planner called {mock_llm.planner_call_count} times, exceeds max_iterations=3"

            # Graph must still produce a final report
            assert (
                result.get("status") == "completed"
            ), f"Status: {result.get('status')}"
            assert result.get("conclusion"), "No conclusion despite forced completion"
            assert isinstance(
                result.get("structured_report"), dict
            ), "structured_report should be a dict"

        finally:
            for p in patches:
                p.stop()

    def test_feedback_message_reaches_planner(self):
        """Verify synthesizer feedback appears in state messages for the planner."""
        mock_llm = LoopingMockLLM(insufficient_count=1)
        patches = _build_patches(mock_llm)
        for p in patches:
            p.start()

        try:
            from graph import build_graph

            graph = build_graph(checkpointer=MemorySaver())
            config = {"configurable": {"thread_id": "test-feedback-msg"}}

            result = graph.invoke(
                {"alert": TEST_ALERT, "thread_id": "test-feedback-msg", "images": []},
                config=config,
            )

            # Messages should contain synthesizer feedback
            messages = result.get("messages", [])
            assert len(messages) > 0, "No messages in final state"

            # Find a synthesizer feedback message
            synth_messages = [
                m
                for m in messages
                if isinstance(m, dict) and m.get("role") == "synthesizer"
            ]
            assert len(synth_messages) >= 1, (
                f"Expected at least 1 synthesizer message, found {len(synth_messages)}. "
                f"All messages: {messages}"
            )

            # The insufficient feedback should reference the gaps
            feedback_found = any(
                "Not enough evidence" in m.get("content", "")
                or "Synthesizer Feedback" in m.get("content", "")
                for m in synth_messages
            )
            assert (
                feedback_found
            ), f"Synthesizer feedback content not found in messages: {synth_messages}"

        finally:
            for p in patches:
                p.stop()

    def test_iteration_counter_increments(self):
        """Verify the iteration counter increments correctly through the loop."""
        mock_llm = LoopingMockLLM(insufficient_count=1)
        patches = _build_patches(mock_llm)
        for p in patches:
            p.start()

        try:
            from graph import build_graph

            graph = build_graph(checkpointer=MemorySaver())
            config = {"configurable": {"thread_id": "test-iter-count"}}

            result = graph.invoke(
                {"alert": TEST_ALERT, "thread_id": "test-iter-count", "images": []},
                config=config,
            )

            # After 1 insufficient + 1 sufficient, iteration should be >= 1
            iteration = result.get("iteration", 0)
            assert iteration >= 1, f"Expected iteration >= 1, got {iteration}"

        finally:
            for p in patches:
                p.stop()
