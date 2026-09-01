#!/usr/bin/env python3
"""
Tests for the observability backend abstraction in agent.py.

Tests backend detection, initialization, and helper functions for
Laminar, Langfuse, and disabled ("none") modes.

Run: cd sre-agent && uv run python -m pytest tests/test_observability.py -v
"""

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Helpers to reset module state between tests
# ---------------------------------------------------------------------------


def _reset_observability():
    """Reset the observability module state so each test starts clean."""
    import agent

    agent._observability_backend = "none"
    agent._observability_initialized = False
    agent._Laminar = None
    agent._observe = None
    agent._langfuse_client = None
    agent._langfuse_propagate_attributes = None
    agent._langfuse_session_metadata.clear()
    agent._langfuse_tool_spans.clear()


# ---------------------------------------------------------------------------
# Backend detection tests
# ---------------------------------------------------------------------------


class TestDetectBackend:
    """Tests for _detect_observability_backend()."""

    def setup_method(self):
        _reset_observability()

    def test_explicit_laminar(self):
        from agent import _detect_observability_backend

        with patch.dict(os.environ, {"OBSERVABILITY_BACKEND": "laminar"}, clear=False):
            assert _detect_observability_backend() == "laminar"

    def test_explicit_langfuse(self):
        from agent import _detect_observability_backend

        with patch.dict(os.environ, {"OBSERVABILITY_BACKEND": "langfuse"}, clear=False):
            assert _detect_observability_backend() == "langfuse"

    def test_explicit_none(self):
        from agent import _detect_observability_backend

        with patch.dict(os.environ, {"OBSERVABILITY_BACKEND": "none"}, clear=False):
            assert _detect_observability_backend() == "none"

    def test_explicit_case_insensitive(self):
        from agent import _detect_observability_backend

        with patch.dict(os.environ, {"OBSERVABILITY_BACKEND": "LAMINAR"}, clear=False):
            assert _detect_observability_backend() == "laminar"

    def test_autodetect_laminar_from_key(self):
        from agent import _detect_observability_backend

        env = {"LMNR_PROJECT_API_KEY": "test-key"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("OBSERVABILITY_BACKEND", None)
            assert _detect_observability_backend() == "laminar"

    def test_autodetect_langfuse_from_keys(self):
        from agent import _detect_observability_backend

        env = {
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("OBSERVABILITY_BACKEND", None)
            os.environ.pop("LMNR_PROJECT_API_KEY", None)
            assert _detect_observability_backend() == "langfuse"

    def test_autodetect_langfuse_needs_both_keys(self):
        from agent import _detect_observability_backend

        env = {"LANGFUSE_PUBLIC_KEY": "pk-test"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("OBSERVABILITY_BACKEND", None)
            os.environ.pop("LMNR_PROJECT_API_KEY", None)
            os.environ.pop("LANGFUSE_SECRET_KEY", None)
            assert _detect_observability_backend() == "none"

    def test_no_config_returns_none(self):
        from agent import _detect_observability_backend

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OBSERVABILITY_BACKEND", None)
            os.environ.pop("LMNR_PROJECT_API_KEY", None)
            os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
            os.environ.pop("LANGFUSE_SECRET_KEY", None)
            assert _detect_observability_backend() == "none"

    def test_explicit_overrides_autodetect(self):
        """Explicit OBSERVABILITY_BACKEND takes priority over credential env vars."""
        from agent import _detect_observability_backend

        env = {
            "OBSERVABILITY_BACKEND": "none",
            "LMNR_PROJECT_API_KEY": "test-key",
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test",
        }
        with patch.dict(os.environ, env, clear=False):
            assert _detect_observability_backend() == "none"

    def test_laminar_priority_over_langfuse(self):
        """When both credential sets exist, Laminar wins (checked first)."""
        from agent import _detect_observability_backend

        env = {
            "LMNR_PROJECT_API_KEY": "test-key",
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test",
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("OBSERVABILITY_BACKEND", None)
            assert _detect_observability_backend() == "laminar"


# ---------------------------------------------------------------------------
# Initialization tests
# ---------------------------------------------------------------------------


class TestInitObservability:
    """Tests for init_observability()."""

    def setup_method(self):
        _reset_observability()

    def test_init_none_backend(self):
        import agent

        with patch.dict(os.environ, {"OBSERVABILITY_BACKEND": "none"}, clear=False):
            agent._observability_initialized = False
            agent.init_observability()
            assert agent._observability_backend == "none"
            assert agent._observability_initialized is True

    def test_init_laminar_success(self):
        import agent

        mock_laminar = MagicMock()
        mock_observe = MagicMock()

        with patch.dict(
            os.environ,
            {
                "OBSERVABILITY_BACKEND": "laminar",
                "LMNR_PROJECT_API_KEY": "test-key",
            },
            clear=False,
        ):
            with patch.dict(
                "sys.modules",
                {"lmnr": MagicMock(Laminar=mock_laminar, observe=mock_observe)},
            ):
                agent._observability_initialized = False
                agent.init_observability()
                assert agent._observability_backend == "laminar"
                assert agent._observability_initialized is True

    def test_init_laminar_import_failure_falls_back_to_none(self):
        import agent

        with patch.dict(
            os.environ,
            {
                "OBSERVABILITY_BACKEND": "laminar",
                "LMNR_PROJECT_API_KEY": "test-key",
            },
            clear=False,
        ):
            # Force ImportError by removing lmnr from sys.modules and patching import
            with patch("builtins.__import__", side_effect=ImportError("no lmnr")):
                agent._observability_initialized = False
                agent.init_observability()
                assert agent._observability_backend == "none"

    def test_init_langfuse_wires_client_and_propagate_attributes(self):
        """v4 uses get_client/propagate_attributes; both must land on module state.

        A missing `global` once left propagate_attributes None, so the turn
        wrapper silently skipped export.
        """
        import agent

        mock_get_client = MagicMock()
        mock_propagate = MagicMock()

        with patch.dict(
            os.environ,
            {
                "OBSERVABILITY_BACKEND": "langfuse",
                "LANGFUSE_PUBLIC_KEY": "pk-test",
                "LANGFUSE_SECRET_KEY": "sk-test",
                "LANGFUSE_HOST": "https://test.langfuse.com",
            },
            clear=False,
        ):
            with patch.dict(
                "sys.modules",
                {
                    "langfuse": MagicMock(
                        get_client=mock_get_client,
                        propagate_attributes=mock_propagate,
                    )
                },
            ):
                agent._observability_initialized = False
                agent.init_observability()

                assert agent._observability_backend == "langfuse"
                assert agent._observability_initialized is True
                assert agent._langfuse_client is not None
                assert agent._langfuse_propagate_attributes is mock_propagate
                mock_get_client.assert_called_once()

    def test_init_langfuse_import_failure_falls_back_to_none(self):
        import agent

        with patch.dict(
            os.environ,
            {
                "OBSERVABILITY_BACKEND": "langfuse",
                "LANGFUSE_PUBLIC_KEY": "pk-test",
                "LANGFUSE_SECRET_KEY": "sk-test",
            },
            clear=False,
        ):
            with patch("builtins.__import__", side_effect=ImportError("no langfuse")):
                agent._observability_initialized = False
                agent.init_observability()
                assert agent._observability_backend == "none"

    def test_idempotent(self):
        """Calling init_observability() twice doesn't re-initialize."""
        import agent

        with patch.dict(os.environ, {"OBSERVABILITY_BACKEND": "none"}, clear=False):
            agent._observability_initialized = False
            agent.init_observability()
            assert agent._observability_initialized is True

            # Change env, but init should be a no-op
            with patch.dict(
                os.environ, {"OBSERVABILITY_BACKEND": "laminar"}, clear=False
            ):
                agent.init_observability()
                assert agent._observability_backend == "none"  # Still none


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    """Tests for observability_set_session, observability_set_tags, observability_observe."""

    def setup_method(self):
        _reset_observability()

    def test_set_session_noop_when_disabled(self):
        import agent

        agent._observability_backend = "none"
        # Should not raise
        agent.observability_set_session("thread-123", {"env": "test"})

    def test_set_session_calls_laminar(self):
        import agent

        mock_laminar = MagicMock()
        agent._observability_backend = "laminar"
        agent._Laminar = mock_laminar

        agent.observability_set_session("thread-123", {"env": "staging"})

        mock_laminar.set_trace_session_id.assert_called_once_with("thread-123")
        mock_laminar.set_trace_metadata.assert_called_once_with({"env": "staging"})

    def test_set_session_laminar_no_metadata(self):
        import agent

        mock_laminar = MagicMock()
        agent._observability_backend = "laminar"
        agent._Laminar = mock_laminar

        agent.observability_set_session("thread-123")

        mock_laminar.set_trace_session_id.assert_called_once_with("thread-123")
        mock_laminar.set_trace_metadata.assert_not_called()

    def test_set_tags_noop_when_disabled(self):
        import agent

        agent._observability_backend = "none"
        agent.observability_set_tags(["success"])  # Should not raise

    def test_set_tags_calls_laminar(self):
        import agent

        mock_laminar = MagicMock()
        agent._observability_backend = "laminar"
        agent._Laminar = mock_laminar

        agent.observability_set_tags(["error", "timeout"])

        mock_laminar.set_span_tags.assert_called_once_with(["error", "timeout"])

    def test_observe_returns_identity_when_disabled(self):
        import agent

        agent._observability_backend = "none"

        decorator = agent.observability_observe()

        async def my_func():
            return 42

        # Identity decorator should return the same function
        assert decorator(my_func) is my_func

    def test_observe_returns_laminar_decorator(self):
        import agent

        mock_observe = MagicMock(return_value=lambda fn: fn)
        agent._observability_backend = "laminar"
        agent._observe = mock_observe

        agent.observability_observe()
        mock_observe.assert_called_once()


# ---------------------------------------------------------------------------
# Langfuse-specific wiring
# ---------------------------------------------------------------------------


class TestLangfuseHostEnv:
    """LANGFUSE_HOST (chart/.env) and LANGFUSE_BASE_URL (SDK v4) must agree."""

    def setup_method(self):
        _reset_observability()

    def test_host_is_copied_to_base_url(self):
        from agent import _sync_langfuse_host_env

        env = {"LANGFUSE_HOST": "https://lf.internal"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("LANGFUSE_BASE_URL", None)
            assert _sync_langfuse_host_env() == "https://lf.internal"
            assert os.environ["LANGFUSE_BASE_URL"] == "https://lf.internal"

    def test_base_url_is_copied_to_host(self):
        from agent import _sync_langfuse_host_env

        env = {"LANGFUSE_BASE_URL": "https://lf.example"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("LANGFUSE_HOST", None)
            assert _sync_langfuse_host_env() == "https://lf.example"
            assert os.environ["LANGFUSE_HOST"] == "https://lf.example"

    def test_defaults_to_us_cloud(self):
        from agent import _sync_langfuse_host_env

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LANGFUSE_HOST", None)
            os.environ.pop("LANGFUSE_BASE_URL", None)
            assert _sync_langfuse_host_env() == "https://us.cloud.langfuse.com"


class TestLangfuseHelpers:
    """Session metadata, outcome tags and flush for the Langfuse backend."""

    def setup_method(self):
        _reset_observability()

    def test_set_session_stashes_metadata_for_the_turn(self):
        import agent

        agent._observability_backend = "langfuse"
        agent._langfuse_client = MagicMock()

        agent.observability_set_session("thread-123", {"environment": "local"})

        assert agent._langfuse_session_metadata["thread-123"] == {
            "environment": "local"
        }

    def test_update_metadata_merges_without_wiping_existing_keys(self):
        """agent_run_id is per turn; replacing the dict would drop environment."""
        import agent

        agent._observability_backend = "langfuse"
        agent._langfuse_client = MagicMock()

        agent.observability_set_session(
            "thread-123", {"environment": "local", "thread_id": "thread-123"}
        )
        agent.observability_update_metadata("thread-123", agent_run_id="abc123def456")

        assert agent._langfuse_session_metadata["thread-123"] == {
            "environment": "local",
            "thread_id": "thread-123",
            "agent_run_id": "abc123def456",
        }

    def test_update_metadata_overwrites_agent_run_id_on_follow_up(self):
        import agent

        agent._observability_backend = "langfuse"
        agent._langfuse_client = MagicMock()

        agent.observability_set_session("thread-123", {"environment": "local"})
        agent.observability_update_metadata("thread-123", agent_run_id="run-1")
        agent.observability_update_metadata("thread-123", agent_run_id="run-2")

        assert agent._langfuse_session_metadata["thread-123"]["agent_run_id"] == "run-2"
        assert agent._langfuse_session_metadata["thread-123"]["environment"] == "local"

    def test_update_metadata_on_unknown_thread_starts_a_dict(self):
        import agent

        agent._observability_backend = "langfuse"
        agent._langfuse_client = MagicMock()

        agent.observability_update_metadata("thread-new", agent_run_id="run-1")

        assert agent._langfuse_session_metadata["thread-new"] == {
            "agent_run_id": "run-1"
        }

    def test_set_tags_writes_the_trace_tag_span_attribute(self):
        """Outcome is known only at turn end, so tags go on the still-open span."""
        import agent

        agent._observability_backend = "langfuse"
        agent._langfuse_client = MagicMock()

        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
            agent.observability_set_tags(["success"])

        mock_span.set_attribute.assert_called_once_with(
            "langfuse.trace.tags", ["success"]
        )

    def test_set_tags_skips_a_span_that_is_not_recording(self):
        import agent

        agent._observability_backend = "langfuse"
        agent._langfuse_client = MagicMock()

        mock_span = MagicMock()
        mock_span.is_recording.return_value = False
        with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
            agent.observability_set_tags(["success"])

        mock_span.set_attribute.assert_not_called()

    def test_tag_failure_does_not_propagate(self):
        """Telemetry must never break an investigation."""
        import agent

        agent._observability_backend = "langfuse"
        agent._langfuse_client = MagicMock()

        with patch(
            "opentelemetry.trace.get_current_span",
            side_effect=RuntimeError("no active span"),
        ):
            agent.observability_set_tags(["error"])  # should not raise

    def test_end_session_drops_this_thread_state_only(self):
        """Session state must not accumulate for the life of the process."""
        import agent

        agent._observability_backend = "langfuse"
        agent._langfuse_client = MagicMock()

        agent.observability_set_session("thread-a", {"environment": "local"})
        agent.observability_set_session("thread-b", {"environment": "local"})
        agent.observability_end_session("thread-a")

        assert list(agent._langfuse_session_metadata) == ["thread-b"]

    def test_flush_calls_client(self):
        import agent

        mock_client = MagicMock()
        agent._observability_backend = "langfuse"
        agent._langfuse_client = mock_client

        agent.observability_flush()

        mock_client.flush.assert_called_once()


class TestLangfuseToolSpans:
    """PreToolUse/PostToolUse spans, keyed by (thread_id, tool_use_id)."""

    def setup_method(self):
        _reset_observability()

    def _enable(self):
        import agent

        agent._observability_backend = "langfuse"
        mock_client = MagicMock()
        agent._langfuse_client = mock_client
        return agent, mock_client

    def test_start_opens_a_tool_span(self):
        agent, mock_client = self._enable()

        agent.observability_tool_start(
            "thread-a",
            "Bash",
            {"command": "kubectl get pods"},
            "toolu_1",
            agent_type="k8s",
            depth=1,
        )

        mock_client.start_observation.assert_called_once_with(
            as_type="tool",
            name="Bash",
            input={"command": "kubectl get pods"},
            metadata={"agent_type": "k8s", "depth": 1},
        )
        assert ("thread-a", "toolu_1") in agent._langfuse_tool_spans

    def test_end_closes_the_matching_span(self):
        agent, mock_client = self._enable()
        mock_span = MagicMock()
        mock_client.start_observation.return_value = mock_span

        agent.observability_tool_start("thread-a", "Bash", {}, "toolu_1")
        agent.observability_tool_end("thread-a", "toolu_1", output="3 pods")

        mock_span.update.assert_called_once_with(
            output="3 pods", level="DEFAULT", status_message=None
        )
        mock_span.end.assert_called_once()
        assert agent._langfuse_tool_spans == {}

    def test_failed_tool_records_the_error(self):
        agent, mock_client = self._enable()
        mock_span = MagicMock()
        mock_client.start_observation.return_value = mock_span

        agent.observability_tool_start("thread-a", "Bash", {}, "toolu_1")
        agent.observability_tool_end(
            "thread-a", "toolu_1", success=False, error="exit 1"
        )

        mock_span.update.assert_called_once_with(
            output="exit 1", level="ERROR", status_message="exit 1"
        )

    def test_tool_without_an_id_is_skipped(self):
        """Without a tool_use_id there is no way to match the closing event."""
        agent, mock_client = self._enable()

        agent.observability_tool_start("thread-a", "Bash", {}, None)

        mock_client.start_observation.assert_not_called()

    def test_end_without_a_matching_start_is_a_noop(self):
        agent, _ = self._enable()
        agent.observability_tool_end("thread-a", "never-started")  # should not raise

    def test_turn_end_closes_spans_left_open(self):
        """A timeout can end a turn with tools still in flight."""
        agent, mock_client = self._enable()
        mock_span = MagicMock()
        mock_client.start_observation.return_value = mock_span

        agent.observability_tool_start("thread-a", "Bash", {}, "toolu_1")
        agent.observability_close_open_tool_spans("thread-a")

        assert agent._langfuse_tool_spans == {}
        mock_span.end.assert_called_once()
        assert mock_span.update.call_args.kwargs["level"] == "ERROR"

    def test_turn_end_leaves_other_investigations_alone(self):
        """One investigation ending must not close another's in-flight spans.

        server_simple.py runs many InteractiveAgentSessions concurrently in one
        process, so a process-global span registry would let thread B's turn end
        close thread A's open tool spans and corrupt A's trace.
        """
        agent, mock_client = self._enable()
        span_a, span_b = MagicMock(), MagicMock()
        mock_client.start_observation.side_effect = [span_a, span_b]

        agent.observability_tool_start("thread-a", "Bash", {}, "toolu_1")
        agent.observability_tool_start("thread-b", "Bash", {}, "toolu_2")

        agent.observability_close_open_tool_spans("thread-b")

        span_b.end.assert_called_once()
        span_a.end.assert_not_called()
        assert list(agent._langfuse_tool_spans) == [("thread-a", "toolu_1")]

    def test_same_tool_use_id_in_two_investigations_does_not_collide(self):
        agent, mock_client = self._enable()
        span_a, span_b = MagicMock(), MagicMock()
        mock_client.start_observation.side_effect = [span_a, span_b]

        agent.observability_tool_start("thread-a", "Bash", {}, "toolu_dup")
        agent.observability_tool_start("thread-b", "Bash", {}, "toolu_dup")
        agent.observability_tool_end("thread-a", "toolu_dup", output="done")

        span_a.end.assert_called_once()
        span_b.end.assert_not_called()


class TestLangfuseGenerationCost:
    """Nested llm generations carry the usage/cost Langfuse actually prices."""

    def setup_method(self):
        _reset_observability()

    def _enable(self):
        import agent

        agent._observability_backend = "langfuse"
        mock_client = MagicMock()
        mock_gen = MagicMock()
        mock_client.start_observation.return_value = mock_gen
        agent._langfuse_client = mock_client
        return agent, mock_client, mock_gen

    @staticmethod
    def _result(**kwargs):
        defaults = {
            "subtype": "success",
            "duration_ms": 1000,
            "duration_api_ms": 800,
            "is_error": False,
            "num_turns": 1,
            "session_id": "sess-1",
            "total_cost_usd": None,
            "usage": None,
            "model_usage": None,
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_model_usage_emits_a_generation_with_model_tokens_and_cost(self):
        agent, mock_client, mock_gen = self._enable()
        message = self._result(
            model_usage={
                "claude-sonnet-4-6": {
                    "inputTokens": 10,
                    "outputTokens": 20,
                    "cacheReadInputTokens": 100,
                    "cacheCreationInputTokens": 5,
                    "costUSD": 0.0123,
                }
            },
            total_cost_usd=0.0123,
        )

        agent.observability_record_generation(message)

        mock_client.start_observation.assert_called_once_with(
            as_type="generation",
            name="llm",
            model="claude-sonnet-4-6",
        )
        mock_gen.update.assert_called_once_with(
            usage_details={
                "input": 10,
                "output": 20,
                "cache_read_input_tokens": 100,
                "cache_creation_input_tokens": 5,
            },
            cost_details={"total": 0.0123},
        )
        mock_gen.end.assert_called_once()

    def test_model_usage_emits_one_generation_per_model(self):
        """Root + subagents often run different models in one turn."""
        agent, mock_client, _ = self._enable()
        message = self._result(
            model_usage={
                "claude-opus-4-6": {
                    "inputTokens": 3,
                    "outputTokens": 8,
                    "costUSD": 0.04,
                },
                "claude-sonnet-4-6": {
                    "inputTokens": 40,
                    "outputTokens": 12,
                    "costUSD": 0.01,
                },
            }
        )

        agent.observability_record_generation(message)

        models = [
            call.kwargs["model"]
            for call in mock_client.start_observation.call_args_list
        ]
        assert models == ["claude-opus-4-6", "claude-sonnet-4-6"]

    def test_falls_back_to_usage_and_total_cost_when_model_usage_missing(self):
        agent, mock_client, mock_gen = self._enable()
        message = self._result(
            usage={
                "input_tokens": 33,
                "output_tokens": 904,
                "cache_creation_input_tokens": 50,
                "cache_read_input_tokens": 200,
                "server_tool_use": {"web_search_requests": 0},
                "service_tier": "standard",
            },
            total_cost_usd=0.18,
        )

        agent.observability_record_generation(
            message, fallback_model="claude-sonnet-4-6"
        )

        mock_client.start_observation.assert_called_once_with(
            as_type="generation",
            name="llm",
            model="claude-sonnet-4-6",
        )
        update_kwargs = mock_gen.update.call_args.kwargs
        assert update_kwargs["usage_details"] == {
            "input": 33,
            "output": 904,
            "cache_creation_input_tokens": 50,
            "cache_read_input_tokens": 200,
        }
        assert "server_tool_use" not in update_kwargs["usage_details"]
        assert "service_tier" not in update_kwargs["usage_details"]
        assert update_kwargs["cost_details"] == {"total": 0.18}

    def test_skips_when_there_is_no_usage_and_no_cost(self):
        agent, mock_client, _ = self._enable()

        agent.observability_record_generation(self._result())

        mock_client.start_observation.assert_not_called()

    def test_none_message_is_a_noop(self):
        agent, mock_client, _ = self._enable()

        agent.observability_record_generation(None)

        mock_client.start_observation.assert_not_called()


class TestLangfuseDisabledBackend:
    """When the backend is off, helpers must not raise or open spans."""

    def setup_method(self):
        _reset_observability()

    def test_helpers_are_noops(self):
        import agent

        agent._observability_backend = "none"
        agent.observability_flush()
        agent.observability_tool_start("thread-a", "Bash", {}, "toolu_1")
        agent.observability_record_generation(
            SimpleNamespace(total_cost_usd=0.01, usage={"input_tokens": 1})
        )
        assert agent._langfuse_tool_spans == {}


class TestLangfuseAsyncGenWrapper:
    """execute() is an async generator, which @observe() cannot wrap."""

    def setup_method(self):
        _reset_observability()

    @staticmethod
    def _event(event_type, **data):
        return SimpleNamespace(type=event_type, data=data)

    def _session_emitting(self, events, thread_id="thread-abc"):
        class FakeSession:
            def __init__(self):
                self.thread_id = thread_id

            async def execute(self, prompt):
                for event in events:
                    yield event

        return FakeSession()

    def _passthrough_session(self, thread_id="thread-abc"):
        """Yields prompt-shaped strings so we can assert the wrapper re-yields."""

        class FakeSession:
            def __init__(self):
                self.thread_id = thread_id

            async def execute(self, prompt):
                yield f"event-1:{prompt}"
                yield "event-2"

        return FakeSession()

    def _run(self, agent, session, prompt="why is cart down?"):
        import asyncio

        wrapped = agent._langfuse_observe_async_gen(type(session).execute)

        async def drain():
            return [event async for event in wrapped(session, prompt)]

        return asyncio.run(drain())

    def _enable_langfuse(self):
        import agent

        mock_client = MagicMock()
        agent._observability_backend = "langfuse"
        agent._langfuse_client = mock_client
        agent._langfuse_propagate_attributes = MagicMock()
        mock_span = MagicMock()
        mock_client.start_as_current_observation.return_value.__enter__.return_value = (
            mock_span
        )
        return agent, mock_client, mock_span

    def test_events_pass_through_and_span_wraps_the_turn(self):
        agent, mock_client, _ = self._enable_langfuse()
        agent._langfuse_session_metadata["thread-abc"] = {"environment": "local"}

        events = self._run(agent, self._passthrough_session())

        assert events == ["event-1:why is cart down?", "event-2"]
        mock_client.start_as_current_observation.assert_called_once_with(
            as_type="span", name="investigation-turn", input="why is cart down?"
        )
        agent._langfuse_propagate_attributes.assert_called_once_with(
            metadata={"environment": "local"},
            trace_name="investigation",
            session_id="thread-abc",
        )
        assert agent.observability_observe() is agent._langfuse_observe_async_gen

    @pytest.mark.parametrize(
        "event_type,data,output",
        [
            (
                "result",
                {"text": "Root cause: bad container command"},
                "Root cause: bad container command",
            ),
            (
                "error",
                {"message": "Investigation stopped after 10 minutes"},
                "Investigation stopped after 10 minutes",
            ),
        ],
    )
    def test_terminal_event_sets_span_output(self, event_type, data, output):
        agent, _, mock_span = self._enable_langfuse()
        events = [
            self._event("thought", text="checking events"),
            self._event(event_type, **data),
        ]

        self._run(agent, self._session_emitting(events))

        mock_span.update.assert_called_once_with(output=output)

    def test_turn_forwards_agent_run_id_in_metadata(self):
        """OpenSRE URL hex must land on the Langfuse trace so cost can be mapped."""
        agent, _, _ = self._enable_langfuse()
        agent._langfuse_session_metadata["thread-abc"] = {
            "environment": "local",
            "thread_id": "thread-abc",
            "agent_run_id": "7b42f5a78f704106a9693c6bd7691d2c",
        }

        self._run(agent, self._session_emitting([]), prompt="pong")

        assert (
            agent._langfuse_propagate_attributes.call_args.kwargs["metadata"][
                "agent_run_id"
            ]
            == "7b42f5a78f704106a9693c6bd7691d2c"
        )

    def test_passes_through_when_client_is_missing(self):
        """A torn-down backend must not stop the investigation."""
        import agent

        agent._observability_backend = "langfuse"
        agent._langfuse_client = None

        events = self._run(agent, self._passthrough_session(), prompt="hi")

        assert events == ["event-1:hi", "event-2"]


# ---------------------------------------------------------------------------
# Helm template rendering test (requires helm CLI)
# ---------------------------------------------------------------------------


class TestHelmTemplate:
    """Test Helm chart renders correctly for each backend."""

    @pytest.fixture(autouse=True)
    def check_helm(self):
        import shutil

        if not shutil.which("helm"):
            pytest.skip("helm CLI not available")

    def _render(self, set_values: list[str]) -> str:
        import subprocess

        chart_path = str(Path(__file__).parent.parent.parent / "charts" / "opensre")
        cmd = [
            "helm",
            "template",
            "test",
            chart_path,
            "--show-only",
            "templates/agent.yaml",
            # Required globals to satisfy chart validation
            "--set",
            "global.configService.url=http://test:8080",
            "--set",
            "services.agent.image=test:latest",
        ]
        for sv in set_values:
            cmd.extend(["--set", sv])
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            pytest.fail(f"helm template failed: {result.stderr}")
        return result.stdout

    def test_backend_none_no_observability_env(self):
        output = self._render(["services.agent.agentObservability.backend=none"])
        assert "OBSERVABILITY_BACKEND" not in output

    def test_backend_langfuse(self):
        output = self._render(
            [
                "services.agent.agentObservability.backend=langfuse",
                "services.agent.agentObservability.langfuse.secretName=my-secret",
                "services.agent.agentObservability.langfuse.publicKeyKey=pk",
                "services.agent.agentObservability.langfuse.secretKeyKey=sk",
            ]
        )
        assert "OBSERVABILITY_BACKEND" in output
        assert "langfuse" in output
        assert "LANGFUSE_HOST" in output
        assert "LANGFUSE_PUBLIC_KEY" in output
        assert "LANGFUSE_SECRET_KEY" in output

    def test_backend_laminar(self):
        output = self._render(
            [
                "services.agent.agentObservability.backend=laminar",
                "services.agent.agentObservability.laminar.secretName=my-laminar",
                "services.agent.agentObservability.laminar.apiKeyKey=key",
            ]
        )
        assert "OBSERVABILITY_BACKEND" in output
        assert "laminar" in output
        assert "LMNR_PROJECT_API_KEY" in output
        assert "LANGFUSE" not in output
