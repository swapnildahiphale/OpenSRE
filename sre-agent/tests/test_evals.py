#!/usr/bin/env python3
"""Tests for the Langfuse eval harness in sre-agent/evals/.

These cover the parts that must be right before an experiment is trustworthy:
the scenario file is well-formed, the deterministic evaluators score what they
claim to, and the judge refuses to invent a score when its output is unusable.

Run: cd sre-agent && uv run python -m pytest tests/test_evals.py -v
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from evals.evaluators.code import (  # noqa: E402
    expected_tools_used,
    no_unsafe_mutations,
    red_herring_avoided,
    report_completeness,
    required_evidence,
    within_latency_budget,
)
from evals.evaluators.judge import (
    evidence_grounded,
    root_cause_correctness,
)  # noqa: E402
from evals.evaluators.run_level import (  # noqa: E402
    avg_root_cause_correctness,
    safety_pass_rate,
)
from evals.run_experiment import _check_fault_setup  # noqa: E402
from evals.sync_dataset import load_scenarios  # noqa: E402
from evals.task import _event_payload, run_investigation  # noqa: E402

# ---------------------------------------------------------------------------
# Test doubles matching the shapes Langfuse passes to run evaluators
# ---------------------------------------------------------------------------


class FakeEvaluation:
    def __init__(self, name, value):
        self.name = name
        self.value = value


class FakeItemResult:
    def __init__(self, evaluations):
        self.evaluations = evaluations


def make_output(report="", trajectory=None, duration=10.0):
    return {
        "report": report,
        "trajectory": trajectory or [],
        "duration_seconds": duration,
    }


# ---------------------------------------------------------------------------
# scenarios.yaml
# ---------------------------------------------------------------------------


class TestScenarios:
    def test_scenarios_are_well_formed(self):
        """A healthy control plus a reference root cause per item is required
        before the judge or a latency gate can mean anything."""
        scenarios = load_scenarios()
        assert len(scenarios) >= 5
        faults = []
        for scenario in scenarios:
            assert scenario["expected_output"]["root_cause"].strip()
            assert scenario["input"]["prompt"].strip()
            assert scenario["metadata"]["latency_budget_seconds"] > 0
            evidence = scenario["metadata"].get("required_evidence") or []
            for token in evidence:
                assert str(token).strip()
            faults.append(scenario["metadata"]["fault"]["kind"])
        assert "none" in faults
        names = [s["name"] for s in scenarios]
        assert "cart-crashloop-red-herring" in names


# ---------------------------------------------------------------------------
# Deterministic evaluators
# ---------------------------------------------------------------------------


class TestReportCompleteness:
    def test_full_report_scores_one(self):
        report = (
            "Root cause: cart pods crash on startup. "
            "Evidence: CrashLoopBackOff events. "
            "Impact: checkout affected. "
            "Recommendation: roll back the deployment."
        )
        assert report_completeness(output=make_output(report)).value == 1.0

    def test_empty_report_scores_zero(self):
        result = report_completeness(output=make_output(""))
        assert result.value == 0.0
        assert "no report" in result.comment.lower()

    def test_partial_report_scores_fraction(self):
        result = report_completeness(output=make_output("Root cause: something broke."))
        assert 0.0 < result.value < 1.0


class TestExpectedToolsUsed:
    def test_matches_tool_named_inside_a_bash_input(self):
        """Skills call their helpers via Bash, so the match must look at inputs."""
        trajectory = [
            {
                "name": "Bash",
                "input": {"command": "python get_events.py cart -n otel-demo"},
            }
        ]
        result = expected_tools_used(
            output=make_output(trajectory=trajectory),
            metadata={"expected_tools": ["get_events"]},
        )
        assert result.value == 1.0

    def test_missing_tool_scores_zero_and_names_it(self):
        result = expected_tools_used(
            output=make_output(trajectory=[{"name": "Read", "input": {}}]),
            metadata={"expected_tools": ["get_events"]},
        )
        assert result.value == 0.0
        assert "get_events" in result.comment

    def test_no_expectation_is_unscored_not_zero(self):
        # Return None (not Evaluation(value=None)): Langfuse create_score
        # rejects a null numeric value.
        result = expected_tools_used(
            output=make_output(), metadata={"expected_tools": []}
        )
        assert result is None


class TestRequiredEvidence:
    def test_all_tokens_present_scores_one(self):
        result = required_evidence(
            output=make_output("Pods are in CrashLoopBackOff after a bad command."),
            metadata={"required_evidence": ["CrashLoopBackOff"]},
        )
        assert result.value == 1.0

    def test_missing_token_scores_zero(self):
        result = required_evidence(
            output=make_output("Cart is unhealthy."),
            metadata={"required_evidence": ["CrashLoopBackOff"]},
        )
        assert result.value == 0.0
        assert "CrashLoopBackOff" in result.comment

    def test_absent_list_is_unscored(self):
        assert required_evidence(output=make_output("x"), metadata={}) is None


class TestRedHerringAvoided:
    def test_correct_dismissal_passes(self):
        report = (
            "Root cause: cart is in CrashLoopBackOff from a bad container "
            "command. Ad CPU is unrelated."
        )
        result = red_herring_avoided(
            output=make_output(report),
            metadata={
                "forbidden_claims": ["ad service cpu is the root cause"],
                "ruling_out": ["CrashLoopBackOff"],
            },
        )
        assert result.value == 1.0

    def test_blaming_the_decoy_fails(self):
        result = red_herring_avoided(
            output=make_output("Ad service CPU is the root cause of the cart outage."),
            metadata={
                "forbidden_claims": ["ad service cpu is the root cause"],
                "ruling_out": ["CrashLoopBackOff"],
            },
        )
        assert result.value == 0.0
        assert "decoy" in result.comment.lower()

    def test_absent_constraints_are_unscored(self):
        assert red_herring_avoided(output=make_output("x"), metadata={}) is None


class TestNoUnsafeMutations:
    def test_read_only_investigation_passes(self):
        trajectory = [{"name": "Bash", "input": {"command": "kubectl get pods"}}]
        assert (
            no_unsafe_mutations(output=make_output(trajectory=trajectory)).value == 1.0
        )

    def test_real_delete_fails(self):
        trajectory = [
            {"name": "Bash", "input": {"command": "kubectl delete pod cart-abc"}}
        ]
        result = no_unsafe_mutations(output=make_output(trajectory=trajectory))
        assert result.value == 0.0

    def test_dry_run_mutation_passes(self):
        """Remediation skills are expected to simulate before acting."""
        trajectory = [
            {
                "name": "Bash",
                "input": {"command": "python restart_pod.py cart --dry-run"},
            }
        ]
        assert (
            no_unsafe_mutations(output=make_output(trajectory=trajectory)).value == 1.0
        )

    def test_merely_mentioning_a_command_is_not_a_mutation(self):
        """Prose naming a command must not read as having run it."""
        trajectory = [
            {"name": "Bash", "input": {"command": 'echo "do not kubectl delete pods"'}}
        ]
        assert (
            no_unsafe_mutations(output=make_output(trajectory=trajectory)).value == 1.0
        )

    def test_mutation_after_a_shell_separator_is_caught(self):
        """Chained commands are still commands."""
        trajectory = [
            {
                "name": "Bash",
                "input": {"command": "kubectl get pods && kubectl delete pod cart-abc"},
            }
        ]
        assert (
            no_unsafe_mutations(output=make_output(trajectory=trajectory)).value == 0.0
        )


class TestLatencyBudget:
    def test_within_budget(self):
        result = within_latency_budget(
            output=make_output(duration=50.0),
            metadata={"latency_budget_seconds": 120},
        )
        assert result.value == 1.0

    def test_over_budget(self):
        result = within_latency_budget(
            output=make_output(duration=200.0),
            metadata={"latency_budget_seconds": 120},
        )
        assert result.value == 0.0

    def test_no_budget_is_unscored(self):
        assert within_latency_budget(output=make_output(), metadata={}) is None


# ---------------------------------------------------------------------------
# LLM-as-a-judge evaluators
# ---------------------------------------------------------------------------


class TestRootCauseJudge:
    @pytest.mark.parametrize(
        "label,expected",
        [("CORRECT", 1.0), ("PARTIAL", 0.5)],
    )
    def test_label_maps_to_score(self, label, expected):
        with patch(
            "evals.evaluators.judge._ask_judge",
            return_value={"label": label, "reason": "mapped"},
        ):
            result = root_cause_correctness(
                output=make_output("cart is in CrashLoopBackOff"),
                expected_output={"root_cause": "cart pods crash on startup"},
            )
        assert result.value == expected

    def test_invalid_label_is_unscored_not_a_failure(self):
        """A broken judge must not be recorded as a failing investigation."""
        with patch(
            "evals.evaluators.judge._ask_judge", return_value={"label": "MAYBE"}
        ):
            result = root_cause_correctness(
                output=make_output("something"),
                expected_output={"root_cause": "cart pods crash"},
            )
        assert result is None

    def test_judge_failure_is_unscored(self):
        with patch("evals.evaluators.judge._ask_judge", return_value={}):
            result = root_cause_correctness(
                output=make_output("something"),
                expected_output={"root_cause": "cart pods crash"},
            )
        assert result is None

    def test_empty_report_scores_zero_without_calling_the_judge(self):
        with patch("evals.evaluators.judge._ask_judge") as judge:
            result = root_cause_correctness(
                output=make_output(""), expected_output={"root_cause": "x"}
            )
        judge.assert_not_called()
        assert result.value == 0.0


class TestGroundednessJudge:
    def test_valid_score_passes_through(self):
        with patch(
            "evals.evaluators.judge._ask_judge",
            return_value={"score": 0.75, "reason": "mostly cited"},
        ):
            result = evidence_grounded(output=make_output("report text"))
        assert result.value == 0.75

    @pytest.mark.parametrize("bad", [1.5, -0.1, "high", None])
    def test_out_of_range_scores_are_rejected(self, bad):
        with patch("evals.evaluators.judge._ask_judge", return_value={"score": bad}):
            result = evidence_grounded(output=make_output("report text"))
        assert result is None


# ---------------------------------------------------------------------------
# Run-level aggregation
# ---------------------------------------------------------------------------


class TestRunEvaluators:
    def test_average_skips_unscored_items(self):
        """Unscored items lower confidence, they must not drag the average down."""
        item_results = [
            FakeItemResult([FakeEvaluation("root_cause_correctness", 1.0)]),
            FakeItemResult([FakeEvaluation("root_cause_correctness", 0.0)]),
            FakeItemResult([FakeEvaluation("root_cause_correctness", None)]),
        ]
        result = avg_root_cause_correctness(item_results=item_results)
        assert result.value == 0.5
        assert "2 scored item" in result.comment

    def test_average_with_no_scores_is_none(self):
        result = avg_root_cause_correctness(item_results=[])
        assert result is None

    def test_safety_pass_rate_counts_failures(self):
        item_results = [
            FakeItemResult([FakeEvaluation("no_unsafe_mutations", 1.0)]),
            FakeItemResult([FakeEvaluation("no_unsafe_mutations", 0.0)]),
        ]
        result = safety_pass_rate(item_results=item_results)
        assert result.value == 0.5
        assert "1 unsafe run" in result.comment


# ---------------------------------------------------------------------------
# SSE parsing
# ---------------------------------------------------------------------------


class TestEventPayload:
    def test_parses_data_line(self):
        assert _event_payload('data: {"type": "result"}') == {"type": "result"}

    @pytest.mark.parametrize(
        "line", ["", "event: ping", "data: [DONE]", "data: not-json"]
    )
    def test_ignores_non_events(self, line):
        assert _event_payload(line) is None


# ---------------------------------------------------------------------------
# Talking to the agent
# ---------------------------------------------------------------------------


class FakeItem:
    """Stands in for a Langfuse DatasetItem."""

    def __init__(self, item_id, metadata):
        self.id = item_id
        self.metadata = metadata


def _fault(kind, **extra):
    return {"fault": {"kind": kind, **extra}}


class TestFaultSetupGuard:
    """Nothing injects faults yet, so a multi-fault run would be meaningless."""

    def test_single_fault_scenario_is_allowed(self):
        _check_fault_setup([FakeItem("cart", _fault("pod-crash"))], False)

    def test_many_fault_free_scenarios_are_allowed(self):
        items = [FakeItem(f"c{i}", _fault("none")) for i in range(3)]
        _check_fault_setup(items, False)

    def test_multiple_fault_scenarios_are_refused(self):
        items = [
            FakeItem("cart-crashloop", _fault("pod-crash")),
            FakeItem("payment-unreachable", _fault("flagd")),
        ]
        with pytest.raises(SystemExit) as excinfo:
            _check_fault_setup(items, False)
        # The message has to name the scenarios, or the operator cannot act on it.
        assert "cart-crashloop" in str(excinfo.value)
        assert "--scenario" in str(excinfo.value)

    def test_override_allows_multi_fault(self):
        items = [
            FakeItem("cart-crashloop", _fault("pod-crash")),
            FakeItem("payment-unreachable", _fault("flagd")),
        ]
        _check_fault_setup(items, True)

    def test_same_fault_variants_are_allowed_together(self):
        """A CrashLoopBackOff case and its red-herring twin share one injection."""
        items = [
            FakeItem("cart-crashloop", _fault("pod-crash", target="cart")),
            FakeItem("cart-crashloop-red-herring", _fault("pod-crash", target="cart")),
        ]
        _check_fault_setup(items, False)


class TestRunInvestigation:
    """The task must degrade to a scored failure, never abort the experiment."""

    def _response(self, lines):
        response = MagicMock()
        response.iter_lines.return_value = iter(lines)
        response.raise_for_status.return_value = None
        return response

    def test_parses_a_full_investigation(self):
        lines = [
            'data: {"type":"tool_start","thread_id":"t1","data":'
            '{"name":"Bash","input":{"command":"python get_events.py cart"}}}',
            'data: {"type":"tool_start","thread_id":"t1","data":'
            '{"name":"Skill","input":{"skill":"infrastructure-kubernetes"}}}',
            'data: {"type":"result","thread_id":"t1","data":'
            '{"text":"Root cause: bad command","success":true}}',
        ]
        with patch("evals.task.get_team_token", return_value="tok"):
            with patch("evals.task.requests.post", return_value=self._response(lines)):
                result = run_investigation("why is cart down?")

        assert result["report"] == "Root cause: bad command"
        assert result["succeeded"] is True
        assert result["thread_id"] == "t1"
        assert len(result["trajectory"]) == 2
        assert result["skills"] == ["infrastructure-kubernetes"]
        assert result["error"] is None

    def test_error_event_is_captured(self):
        lines = ['data: {"type":"error","thread_id":"t1","data":{"message":"boom"}}']
        with patch("evals.task.get_team_token", return_value="tok"):
            with patch("evals.task.requests.post", return_value=self._response(lines)):
                result = run_investigation("why is cart down?")

        assert result["error"] == "boom"
        assert result["succeeded"] is False

    def test_timeout_becomes_a_scored_failure(self):
        import requests

        with patch("evals.task.get_team_token", return_value="tok"):
            with patch(
                "evals.task.requests.post",
                side_effect=requests.exceptions.Timeout(),
            ):
                result = run_investigation("why is cart down?", timeout=5)

        assert result["succeeded"] is False
        assert "did not respond within 5s" in result["error"]

    def test_mid_stream_disconnect_becomes_a_scored_failure(self):
        """iter_lines() can raise partway through a long investigation."""
        import requests

        def explode():
            yield 'data: {"type":"tool_start","thread_id":"t1","data":{"name":"Bash"}}'
            raise requests.exceptions.ChunkedEncodingError("connection reset")

        response = MagicMock()
        response.iter_lines.return_value = explode()
        response.raise_for_status.return_value = None

        with patch("evals.task.get_team_token", return_value="tok"):
            with patch("evals.task.requests.post", return_value=response):
                result = run_investigation("why is cart down?")

        assert result["succeeded"] is False
        assert "Transport error" in result["error"]
        # Partial trajectory is still returned so the failure can be diagnosed.
        assert len(result["trajectory"]) == 1
