"""Tests for the subagent_executor node."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage


def _make_ai_message(content="", tool_calls=None):
    """Create a mock AIMessage."""
    msg = MagicMock(spec=AIMessage)
    msg.content = content
    msg.tool_calls = tool_calls or []
    return msg


@pytest.fixture
def base_state():
    return {
        "agent_id": "kubernetes",
        "alert": {"name": "HighLatency", "service": "cart-service"},
        "hypotheses": [{"hypothesis": "Pod crash loop", "priority": "high"}],
        "team_config": {"agents": {}},
        "max_react_loops": 3,
    }


class TestSubagentExecutor:
    """Tests for nodes.subagent_executor.make_subagent_executor."""

    def test_make_subagent_executor_returns_callable(self):
        """make_subagent_executor returns a callable function."""
        from nodes.subagent_executor import make_subagent_executor

        executor = make_subagent_executor()
        assert callable(executor)

    @patch("nodes.subagent_executor.get_skill_catalog", return_value="")
    @patch("nodes.subagent_executor.resolve_tools", return_value=[])
    @patch("nodes.subagent_executor.get_skills_for_agent", return_value=None)
    @patch("nodes.subagent_executor.build_llm")
    def test_executor_runs_react_loop_and_returns_agent_states(
        self,
        mock_build_llm,
        mock_get_skills,
        mock_resolve_tools,
        mock_catalog,
        base_state,
    ):
        """Executor runs ReAct loop and returns findings in agent_states."""
        # LLM returns a tool call, then a final response
        tool_call_msg = _make_ai_message(
            content="",
            tool_calls=[
                {
                    "name": "run_script",
                    "args": {"command": "kubectl get pods"},
                    "id": "tc1",
                }
            ],
        )
        final_msg = _make_ai_message(content="Found 2 pods in CrashLoopBackOff")

        mock_llm = MagicMock()
        mock_llm_with_tools = MagicMock()
        mock_llm_with_tools.invoke.side_effect = [tool_call_msg, final_msg]
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        mock_build_llm.return_value = mock_llm

        from nodes.subagent_executor import make_subagent_executor

        executor = make_subagent_executor()
        result = executor(base_state)

        assert "agent_states" in result
        agent_state = result["agent_states"]["kubernetes"]
        assert agent_state["status"] == "completed"
        assert "CrashLoopBackOff" in agent_state["findings"]
        assert agent_state["react_loops"] > 0

    @patch("nodes.subagent_executor.get_skill_catalog", return_value="")
    @patch("nodes.subagent_executor.resolve_tools", return_value=[])
    @patch("nodes.subagent_executor.get_skills_for_agent", return_value=None)
    @patch("nodes.subagent_executor.build_llm")
    def test_executor_respects_max_react_loops(
        self,
        mock_build_llm,
        mock_get_skills,
        mock_resolve_tools,
        mock_catalog,
        base_state,
    ):
        """Executor stops after max_react_loops iterations."""
        base_state["max_react_loops"] = 2

        # LLM always returns tool calls (never finishes)
        tool_call_msg = _make_ai_message(
            content="",
            tool_calls=[
                {"name": "run_script", "args": {"command": "test"}, "id": "tc1"}
            ],
        )

        mock_llm = MagicMock()
        mock_llm_with_tools = MagicMock()
        mock_llm_with_tools.invoke.return_value = tool_call_msg
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        mock_build_llm.return_value = mock_llm

        from nodes.subagent_executor import make_subagent_executor

        executor = make_subagent_executor()
        result = executor(base_state)

        agent_state = result["agent_states"]["kubernetes"]
        # Should have at most max_react_loops entries
        assert agent_state["react_loops"] <= 2

    @patch("nodes.subagent_executor.get_skill_catalog", return_value="")
    @patch("nodes.subagent_executor.resolve_tools", return_value=[])
    @patch("nodes.subagent_executor.get_skills_for_agent", return_value=None)
    @patch("nodes.subagent_executor.build_llm")
    def test_executor_handles_llm_failure(
        self,
        mock_build_llm,
        mock_get_skills,
        mock_resolve_tools,
        mock_catalog,
        base_state,
    ):
        """When build_llm raises, executor returns error state."""
        mock_build_llm.side_effect = RuntimeError("LLM unavailable")

        from nodes.subagent_executor import make_subagent_executor

        executor = make_subagent_executor()
        result = executor(base_state)

        agent_state = result["agent_states"]["kubernetes"]
        assert agent_state["status"] == "error"
        assert "Failed to initialize" in agent_state["findings"]
        assert agent_state["confidence"] == 0.0

    @patch("nodes.subagent_executor.get_skill_catalog", return_value="")
    @patch("nodes.subagent_executor.resolve_tools", return_value=[])
    @patch("nodes.subagent_executor.get_skills_for_agent", return_value=None)
    @patch("nodes.subagent_executor.build_llm")
    def test_executor_returns_findings_from_last_ai_message(
        self,
        mock_build_llm,
        mock_get_skills,
        mock_resolve_tools,
        mock_catalog,
        base_state,
    ):
        """Findings come from the last AIMessage without tool_calls."""
        final_msg = _make_ai_message(content="Root cause: OOM kill on redis pod")

        mock_llm = MagicMock()
        mock_llm_with_tools = MagicMock()
        mock_llm_with_tools.invoke.return_value = final_msg
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        mock_build_llm.return_value = mock_llm

        from nodes.subagent_executor import make_subagent_executor

        executor = make_subagent_executor()
        result = executor(base_state)

        agent_state = result["agent_states"]["kubernetes"]
        assert agent_state["findings"] == "Root cause: OOM kill on redis pod"

    @patch("nodes.subagent_executor.get_skill_catalog", return_value="")
    @patch("nodes.subagent_executor.resolve_tools", return_value=[])
    @patch("nodes.subagent_executor.get_skills_for_agent", return_value=None)
    @patch("nodes.subagent_executor.build_llm")
    def test_executor_handles_loop_exception(
        self,
        mock_build_llm,
        mock_get_skills,
        mock_resolve_tools,
        mock_catalog,
        base_state,
    ):
        """When LLM invoke raises during the loop, executor breaks and returns."""
        mock_llm = MagicMock()
        mock_llm_with_tools = MagicMock()
        mock_llm_with_tools.invoke.side_effect = RuntimeError("API timeout")
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        # Forced summary also fails (no messages to summarize)
        mock_llm.invoke.side_effect = RuntimeError("API timeout")
        mock_build_llm.return_value = mock_llm

        from nodes.subagent_executor import make_subagent_executor

        executor = make_subagent_executor()
        result = executor(base_state)

        agent_state = result["agent_states"]["kubernetes"]
        assert agent_state["status"] == "completed"
        # Should have a fallback findings message
        assert (
            "kubernetes" in agent_state["findings"].lower()
            or "did not produce" in agent_state["findings"]
        )

    @patch("nodes.subagent_executor.get_skill_catalog", return_value="")
    @patch("nodes.subagent_executor.resolve_tools", return_value=[])
    @patch("nodes.subagent_executor.get_skills_for_agent", return_value=None)
    @patch("nodes.subagent_executor.build_llm")
    def test_forced_summary_preferred_over_tool_call_content_on_max_loops(
        self,
        mock_build_llm,
        mock_get_skills,
        mock_resolve_tools,
        mock_catalog,
        base_state,
    ):
        """On max-loop exit, forced summary fires even if AIMessages have content with tool_calls."""
        base_state["max_react_loops"] = 2

        # Every AIMessage has both content AND tool_calls — reasoning text, not findings
        msg_with_content = _make_ai_message(
            content="Let me check the pods next.",
            tool_calls=[
                {
                    "name": "run_script",
                    "args": {"command": "kubectl get pods"},
                    "id": "tc1",
                }
            ],
        )

        # Forced summary produces actual findings
        summary_msg = _make_ai_message(
            content="cartservice has 0/0 replicas, deployment scaled to zero."
        )

        mock_llm = MagicMock()
        mock_llm_with_tools = MagicMock()
        mock_llm_with_tools.invoke.return_value = msg_with_content
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        # Forced summary via bare LLM
        mock_llm.invoke.return_value = summary_msg
        mock_build_llm.return_value = mock_llm

        from nodes.subagent_executor import make_subagent_executor

        executor = make_subagent_executor()
        result = executor(base_state)

        agent_state = result["agent_states"]["kubernetes"]
        # Forced summary should be used instead of reasoning text
        assert "0/0 replicas" in agent_state["findings"]
        assert "Let me check" not in agent_state["findings"]
        mock_llm.invoke.assert_called_once()

    @patch("nodes.subagent_executor.get_skill_catalog", return_value="")
    @patch("nodes.subagent_executor.resolve_tools", return_value=[])
    @patch("nodes.subagent_executor.get_skills_for_agent", return_value=None)
    @patch("nodes.subagent_executor.build_llm")
    def test_forced_summary_on_max_loops(
        self,
        mock_build_llm,
        mock_get_skills,
        mock_resolve_tools,
        mock_catalog,
        base_state,
    ):
        """Tier 3: When hitting max loops with no extractable content, forced summary fires."""
        base_state["max_react_loops"] = 2

        # AIMessages have tool_calls but NO content (empty string)
        tool_call_msg = _make_ai_message(
            content="",
            tool_calls=[
                {"name": "run_script", "args": {"command": "test"}, "id": "tc1"}
            ],
        )

        # Forced summary response from bare LLM
        summary_msg = _make_ai_message(
            content="Summary: cartservice scaled to 0 replicas causing 503 errors."
        )

        mock_llm = MagicMock()
        mock_llm_with_tools = MagicMock()
        mock_llm_with_tools.invoke.return_value = tool_call_msg
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        # The bare llm.invoke is called for forced summary
        mock_llm.invoke.return_value = summary_msg
        mock_build_llm.return_value = mock_llm

        from nodes.subagent_executor import make_subagent_executor

        executor = make_subagent_executor()
        result = executor(base_state)

        agent_state = result["agent_states"]["kubernetes"]
        assert "cartservice scaled to 0" in agent_state["findings"]
        # Verify bare LLM was called (forced summary)
        mock_llm.invoke.assert_called_once()

    @patch("nodes.subagent_executor.get_skill_catalog", return_value="")
    @patch("nodes.subagent_executor.resolve_tools", return_value=[])
    @patch("nodes.subagent_executor.get_skills_for_agent", return_value=None)
    @patch("nodes.subagent_executor.build_llm")
    def test_forced_summary_failure_falls_back(
        self,
        mock_build_llm,
        mock_get_skills,
        mock_resolve_tools,
        mock_catalog,
        base_state,
    ):
        """If forced summary LLM call fails, falls back to generic message."""
        base_state["max_react_loops"] = 2

        # AIMessages have tool_calls but NO content
        tool_call_msg = _make_ai_message(
            content="",
            tool_calls=[
                {"name": "run_script", "args": {"command": "test"}, "id": "tc1"}
            ],
        )

        mock_llm = MagicMock()
        mock_llm_with_tools = MagicMock()
        mock_llm_with_tools.invoke.return_value = tool_call_msg
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        # Forced summary fails
        mock_llm.invoke.side_effect = RuntimeError("API quota exceeded")
        mock_build_llm.return_value = mock_llm

        from nodes.subagent_executor import make_subagent_executor

        executor = make_subagent_executor()
        result = executor(base_state)

        agent_state = result["agent_states"]["kubernetes"]
        # Should fall back to generic message
        assert "did not produce a final summary" in agent_state["findings"]

    @patch("nodes.subagent_executor.get_skill_catalog", return_value="")
    @patch("nodes.subagent_executor.resolve_tools", return_value=[])
    @patch("nodes.subagent_executor.get_skills_for_agent", return_value=None)
    @patch("nodes.subagent_executor.build_llm")
    def test_reflection_checkpoint_injected(
        self,
        mock_build_llm,
        mock_get_skills,
        mock_resolve_tools,
        mock_catalog,
        base_state,
    ):
        """After 5 tool calls, a REFLECTION CHECKPOINT HumanMessage is injected."""
        base_state["max_react_loops"] = 10

        # LLM returns 5 tool calls in sequence, then a final response
        tool_call_msgs = []
        for i in range(5):
            tool_call_msgs.append(
                _make_ai_message(
                    content="",
                    tool_calls=[
                        {
                            "name": "run_script",
                            "args": {"command": f"cmd_{i}"},
                            "id": f"tc{i}",
                        }
                    ],
                )
            )
        final_msg = _make_ai_message(content="Investigation complete after reflection")

        mock_llm = MagicMock()
        mock_llm_with_tools = MagicMock()
        mock_llm_with_tools.invoke.side_effect = tool_call_msgs + [final_msg]
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        mock_build_llm.return_value = mock_llm

        from nodes.subagent_executor import make_subagent_executor

        executor = make_subagent_executor()
        result = executor(base_state)

        # Check that a REFLECTION CHECKPOINT message was injected
        invoke_calls = mock_llm_with_tools.invoke.call_args_list
        # The messages list passed to the 6th invoke (after 5 tool calls) should contain reflection
        # We check all messages passed to any invoke after the 5th tool call
        reflection_found = False
        for call_args in invoke_calls:
            msgs = call_args[0][0]  # First positional arg is messages list
            for msg in msgs:
                if (
                    isinstance(msg, HumanMessage)
                    and "REFLECTION CHECKPOINT" in msg.content
                ):
                    reflection_found = True
                    break
        assert (
            reflection_found
        ), "REFLECTION CHECKPOINT not found in messages after 5 tool calls"

    @patch("nodes.subagent_executor.get_skill_catalog", return_value="")
    @patch("nodes.subagent_executor.resolve_tools", return_value=[])
    @patch("nodes.subagent_executor.get_skills_for_agent", return_value=None)
    @patch("nodes.subagent_executor.build_llm")
    def test_duplicate_tool_calls_skipped(
        self,
        mock_build_llm,
        mock_get_skills,
        mock_resolve_tools,
        mock_catalog,
        base_state,
    ):
        """Identical tool calls return DUPLICATE ToolMessage and don't re-execute."""
        base_state["max_react_loops"] = 5

        # LLM returns the same tool call twice, then a final response
        dup_call = {
            "name": "run_script",
            "args": {"command": "kubectl get pods"},
            "id": "tc1",
        }
        msg1 = _make_ai_message(content="", tool_calls=[dup_call])
        dup_call2 = {
            "name": "run_script",
            "args": {"command": "kubectl get pods"},
            "id": "tc2",
        }
        msg2 = _make_ai_message(content="", tool_calls=[dup_call2])
        final_msg = _make_ai_message(content="Done investigating")

        mock_llm = MagicMock()
        mock_llm_with_tools = MagicMock()
        mock_llm_with_tools.invoke.side_effect = [msg1, msg2, final_msg]
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        mock_build_llm.return_value = mock_llm

        from nodes.subagent_executor import make_subagent_executor

        executor = make_subagent_executor()
        result = executor(base_state)

        agent_state = result["agent_states"]["kubernetes"]
        # Should have one tool_call and one duplicate_skipped in timeline
        tool_calls = [
            e for e in agent_state["evidence"] if e.get("action") == "tool_call"
        ]
        assert (
            len(tool_calls) == 1
        ), f"Expected 1 actual tool call, got {len(tool_calls)}"

        # Check react_timeline for duplicate_skipped via the full return
        # The evidence field only includes tool_call actions, so check findings instead
        assert agent_state["findings"] == "Done investigating"

    @patch("nodes.subagent_executor.get_skill_catalog", return_value="")
    @patch("nodes.subagent_executor.resolve_tools", return_value=[])
    @patch("nodes.subagent_executor.get_skills_for_agent", return_value=None)
    @patch("nodes.subagent_executor.build_llm")
    def test_kg_context_injected_in_system_prompt(
        self,
        mock_build_llm,
        mock_get_skills,
        mock_resolve_tools,
        mock_catalog,
        base_state,
    ):
        """When kg_context is available, system prompt contains Service Topology section."""
        base_state["kg_context"] = {
            "available": True,
            "service_name": "cart-service",
            "service_info": {
                "resolved_name": "cartservice",
                "deployment": {
                    "namespace": "otel-demo",
                    "replicas": 1,
                    "image": "ghcr.io/open-telemetry/demo:cartservice",
                    "language": "dotnet",
                    "port": 8080,
                },
                "upstream_dependents": [{"service": "frontend", "via": "gRPC"}],
                "downstream_dependencies": [{"service": "redis-cart", "via": "TCP"}],
                "blast_radius": {"upstream_count": 3},
            },
        }

        final_msg = _make_ai_message(content="Found issue with cartservice")
        mock_llm = MagicMock()
        mock_llm_with_tools = MagicMock()
        mock_llm_with_tools.invoke.return_value = final_msg
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        mock_build_llm.return_value = mock_llm

        from nodes.subagent_executor import make_subagent_executor

        executor = make_subagent_executor()
        executor(base_state)

        # Check the system prompt passed to LLM
        call_args = mock_llm_with_tools.invoke.call_args_list[0]
        messages = call_args[0][0]
        system_content = messages[0].content
        assert "Service Topology" in system_content
        assert "cartservice" in system_content
        assert "frontend" in system_content
        assert "redis-cart" in system_content

    @patch("nodes.subagent_executor.get_skill_catalog", return_value="")
    @patch("nodes.subagent_executor.resolve_tools", return_value=[])
    @patch("nodes.subagent_executor.get_skills_for_agent", return_value=None)
    @patch("nodes.subagent_executor.build_llm")
    def test_kg_context_unavailable_graceful(
        self,
        mock_build_llm,
        mock_get_skills,
        mock_resolve_tools,
        mock_catalog,
        base_state,
    ):
        """When kg_context is unavailable, prompt contains graceful fallback."""
        base_state["kg_context"] = {"available": False}

        final_msg = _make_ai_message(content="Investigated without topology")
        mock_llm = MagicMock()
        mock_llm_with_tools = MagicMock()
        mock_llm_with_tools.invoke.return_value = final_msg
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        mock_build_llm.return_value = mock_llm

        from nodes.subagent_executor import make_subagent_executor

        executor = make_subagent_executor()
        executor(base_state)

        call_args = mock_llm_with_tools.invoke.call_args_list[0]
        messages = call_args[0][0]
        system_content = messages[0].content
        assert "No service topology available" in system_content

    @patch("nodes.subagent_executor.get_skill_catalog", return_value="")
    @patch("nodes.subagent_executor.resolve_tools", return_value=[])
    @patch("nodes.subagent_executor.get_skills_for_agent", return_value=None)
    @patch("nodes.subagent_executor.build_llm")
    def test_kg_context_agent_type_formatting(
        self, mock_build_llm, mock_get_skills, mock_resolve_tools, mock_catalog
    ):
        """Different agent types get tailored KG context formatting."""
        kg_context = {
            "available": True,
            "service_name": "cart-service",
            "service_info": {
                "resolved_name": "cartservice",
                "deployment": {
                    "namespace": "otel-demo",
                    "replicas": 1,
                    "image": "ghcr.io/demo:cart",
                    "language": "dotnet",
                    "port": 8080,
                },
                "upstream_dependents": [{"service": "frontend", "via": "gRPC"}],
                "downstream_dependencies": [{"service": "redis-cart", "via": "TCP"}],
                "blast_radius": {"upstream_count": 3},
            },
        }

        final_msg = _make_ai_message(content="Done")
        mock_llm = MagicMock()
        mock_llm_with_tools = MagicMock()
        mock_llm_with_tools.invoke.return_value = final_msg
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        mock_build_llm.return_value = mock_llm

        from nodes.subagent_executor import make_subagent_executor

        executor = make_subagent_executor()

        # K8s agent should get Upstream/Downstream sections with blast radius
        k8s_state = {
            "agent_id": "kubernetes",
            "alert": {"name": "HighLatency"},
            "hypotheses": [],
            "team_config": {"agents": {}},
            "max_react_loops": 1,
            "kg_context": kg_context,
        }
        executor(k8s_state)
        k8s_prompt = mock_llm_with_tools.invoke.call_args_list[0][0][0][0].content
        assert "Upstream (services that CALL this service)" in k8s_prompt
        assert "Downstream (services this service CALLS)" in k8s_prompt
        assert "Blast radius: 3" in k8s_prompt
        assert "Image:" in k8s_prompt

        mock_llm_with_tools.invoke.reset_mock()

        # Metrics agent should get related services for correlation
        metrics_state = {
            "agent_id": "metrics",
            "alert": {"name": "HighLatency"},
            "hypotheses": [],
            "team_config": {"agents": {}},
            "max_react_loops": 1,
            "kg_context": kg_context,
        }
        executor(metrics_state)
        metrics_prompt = mock_llm_with_tools.invoke.call_args_list[0][0][0][0].content
        assert "Related services for metric correlation" in metrics_prompt
        assert "frontend" in metrics_prompt
        assert "Upstream (services that CALL" not in metrics_prompt

        mock_llm_with_tools.invoke.reset_mock()

        # Log analysis agent should get service names for log searching
        log_state = {
            "agent_id": "log_analysis",
            "alert": {"name": "HighLatency"},
            "hypotheses": [],
            "team_config": {"agents": {}},
            "max_react_loops": 1,
            "kg_context": kg_context,
        }
        executor(log_state)
        log_prompt = mock_llm_with_tools.invoke.call_args_list[0][0][0][0].content
        assert "Related service names (search in logs)" in log_prompt
        assert "These service names may appear in error messages" in log_prompt

    @patch("nodes.subagent_executor.get_skill_catalog", return_value="")
    @patch("nodes.subagent_executor.resolve_tools", return_value=[])
    @patch("nodes.subagent_executor.get_skills_for_agent", return_value=None)
    @patch("nodes.subagent_executor.build_llm")
    def test_duplicate_detection_different_args_allowed(
        self,
        mock_build_llm,
        mock_get_skills,
        mock_resolve_tools,
        mock_catalog,
        base_state,
    ):
        """Same tool with different args is NOT flagged as duplicate."""
        base_state["max_react_loops"] = 5

        call1 = {
            "name": "run_script",
            "args": {"command": "kubectl get pods"},
            "id": "tc1",
        }
        call2 = {
            "name": "run_script",
            "args": {"command": "kubectl get nodes"},
            "id": "tc2",
        }
        msg1 = _make_ai_message(content="", tool_calls=[call1])
        msg2 = _make_ai_message(content="", tool_calls=[call2])
        final_msg = _make_ai_message(content="Both calls succeeded")

        mock_llm = MagicMock()
        mock_llm_with_tools = MagicMock()
        mock_llm_with_tools.invoke.side_effect = [msg1, msg2, final_msg]
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        mock_build_llm.return_value = mock_llm

        from nodes.subagent_executor import make_subagent_executor

        executor = make_subagent_executor()
        result = executor(base_state)

        agent_state = result["agent_states"]["kubernetes"]
        tool_calls = [
            e for e in agent_state["evidence"] if e.get("action") == "tool_call"
        ]
        assert (
            len(tool_calls) == 2
        ), f"Expected 2 tool calls (different args), got {len(tool_calls)}"
