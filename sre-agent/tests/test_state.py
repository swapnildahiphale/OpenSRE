"""Tests for state.py — GraphState schema and reducer functions."""

from state import AlertInput, GraphState, merge_dicts, take_latest


class TestMergeDicts:
    def test_merge_dicts_right_overwrites_left(self):
        left = {"a": 1, "b": 2}
        right = {"b": 99, "c": 3}
        result = merge_dicts(left, right)
        assert result == {"a": 1, "b": 99, "c": 3}

    def test_merge_dicts_empty_left(self):
        result = merge_dicts({}, {"x": 1})
        assert result == {"x": 1}

    def test_merge_dicts_empty_right(self):
        result = merge_dicts({"x": 1}, {})
        assert result == {"x": 1}

    def test_merge_dicts_both_empty(self):
        result = merge_dicts({}, {})
        assert result == {}

    def test_merge_dicts_does_not_mutate_left(self):
        left = {"a": 1}
        right = {"a": 2}
        merge_dicts(left, right)
        assert left == {"a": 1}


class TestTakeLatest:
    def test_returns_right_value(self):
        assert take_latest("old", "new") == "new"

    def test_returns_right_when_none(self):
        assert take_latest("old", None) is None

    def test_returns_right_when_left_is_none(self):
        assert take_latest(None, "new") == "new"

    def test_returns_right_for_integers(self):
        assert take_latest(1, 42) == 42


class TestAlertInput:
    def test_default_values(self):
        alert_input = AlertInput()
        assert alert_input.alert["name"] == "HighErrorRate"
        assert alert_input.alert["service"] == "payment-service"
        assert alert_input.alert["severity"] == "critical"
        assert alert_input.thread_id == "studio-test"

    def test_custom_alert(self):
        custom = {
            "name": "LowDiskSpace",
            "service": "storage-service",
            "severity": "warning",
        }
        alert_input = AlertInput(alert=custom)
        assert alert_input.alert == custom

    def test_custom_thread_id(self):
        alert_input = AlertInput(thread_id="my-thread-123")
        assert alert_input.thread_id == "my-thread-123"


class TestGraphState:
    def test_can_instantiate_as_dict(self):
        """GraphState is a TypedDict, so it should work as a regular dict."""
        state: GraphState = {
            "alert": {"name": "test"},
            "thread_id": "t1",
            "images": [],
            "memory_context": {},
            "kg_context": {},
            "team_config": {},
            "investigation_id": "inv-1",
            "agent_states": {},
            "messages": [],
            "hypotheses": [],
            "selected_agents": [],
            "conclusion": "",
            "structured_report": {},
            "iteration": 0,
            "max_iterations": 3,
            "max_react_loops": 25,
            "status": "running",
        }
        assert state["alert"]["name"] == "test"
        assert state["status"] == "running"
        assert isinstance(state, dict)

    def test_partial_dict_is_valid(self):
        """TypedDict doesn't enforce at runtime, partial dicts are fine."""
        state: GraphState = {"alert": {"name": "test"}, "status": "running"}
        assert state["status"] == "running"
