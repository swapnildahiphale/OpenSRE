"""Tests for the memory_store node."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch

import pytest


@pytest.fixture
def base_state():
    return {
        "alert": {
            "name": "HighLatency",
            "service": "cart-service",
            "description": "P99 > 5s",
        },
        "conclusion": "Root cause identified: OOM kills on cart-service pods due to memory leak. "
        * 5,
        "thread_id": "thread-123",
        "investigation_id": "inv-456",
        "status": "completed",
        "agent_states": {
            "kubernetes": {
                "evidence": [
                    {"tool": "run_script", "args": {"command": "kubectl get pods"}},
                    {"tool": "load_skill", "args": {"name": "k8s-debug"}},
                ],
            },
            "metrics": {
                "evidence": [
                    {"tool": "run_script", "args": {"command": "promql query"}},
                ],
            },
        },
    }


class TestMemoryStore:
    """Tests for nodes.memory_store.memory_store."""

    @patch("nodes.memory_store.store_investigation_result")
    def test_stores_episode_when_conclusion_long_enough(self, mock_store, base_state):
        """Stores episode when conclusion exceeds 50 chars."""
        from nodes.memory_store import memory_store

        result = memory_store(base_state)

        mock_store.assert_called_once()
        call_kwargs = mock_store.call_args
        # Verify key arguments
        assert (
            call_kwargs.kwargs.get("thread_id")
            or call_kwargs[1].get("thread_id")
            or (len(call_kwargs[0]) > 0 if call_kwargs[0] else False)
            or "thread_id" in str(call_kwargs)
        )

        # Check it was called with right params
        args, kwargs = mock_store.call_args
        assert kwargs["thread_id"] == "thread-123"
        assert kwargs["result_text"] == base_state["conclusion"]
        assert kwargs["success"] is True
        assert kwargs["agent_run_id"] == "inv-456"

    @patch("nodes.memory_store.store_investigation_result")
    def test_skips_storage_when_conclusion_too_short(self, mock_store):
        """Skips episode storage when conclusion is under 50 chars."""
        state = {
            "alert": {"name": "test"},
            "conclusion": "Short.",
            "thread_id": "t1",
            "investigation_id": "i1",
            "agent_states": {},
        }

        from nodes.memory_store import memory_store

        result = memory_store(state)

        mock_store.assert_not_called()
        assert result == {}

    @patch("nodes.memory_store.store_investigation_result")
    def test_skips_storage_when_conclusion_empty(self, mock_store):
        """Skips storage when conclusion is empty string."""
        state = {
            "alert": {"name": "test"},
            "conclusion": "",
            "thread_id": "t1",
            "investigation_id": "i1",
            "agent_states": {},
        }

        from nodes.memory_store import memory_store

        result = memory_store(state)

        mock_store.assert_not_called()

    @patch("nodes.memory_store.store_investigation_result")
    def test_handles_storage_failure_gracefully(self, mock_store, base_state):
        """When store_investigation_result raises, node returns empty dict without crashing."""
        mock_store.side_effect = RuntimeError("Config service down")

        from nodes.memory_store import memory_store

        result = memory_store(base_state)

        # Should not raise, just returns empty dict
        assert result == {}

    @patch("nodes.memory_store.store_investigation_result")
    def test_builds_tool_calls_data_from_agent_states(self, mock_store, base_state):
        """Tool calls data is built from evidence entries in agent_states."""
        from nodes.memory_store import memory_store

        memory_store(base_state)

        args, kwargs = mock_store.call_args
        tool_calls = kwargs["tool_calls_data"]

        # Should have 3 tool calls (2 from kubernetes + 1 from metrics)
        assert len(tool_calls) == 3
        assert tool_calls[0]["tool_name"] == "run_script"
        assert tool_calls[1]["tool_name"] == "load_skill"
        assert tool_calls[2]["tool_name"] == "run_script"

    @patch("nodes.memory_store.store_investigation_result")
    def test_builds_prompt_from_alert(self, mock_store, base_state):
        """Prompt passed to store is built from alert name and description."""
        from nodes.memory_store import memory_store

        memory_store(base_state)

        args, kwargs = mock_store.call_args
        assert "HighLatency" in kwargs["prompt"]
        assert "P99 > 5s" in kwargs["prompt"]

    @patch("nodes.memory_store.store_investigation_result")
    def test_passes_service_and_alert_type(self, mock_store, base_state):
        """service_name and alert_type are passed from alert dict."""
        from nodes.memory_store import memory_store

        memory_store(base_state)

        args, kwargs = mock_store.call_args
        assert kwargs["service_name"] == "cart-service"
        assert kwargs["alert_type"] == "HighLatency"
