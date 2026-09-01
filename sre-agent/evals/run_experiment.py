#!/usr/bin/env python3
"""Run the OpenSRE investigation suite as a Langfuse experiment.

    # everything, against the local stack
    python -m evals.run_experiment --run-name "sonnet-4.6 baseline"

    # one scenario while iterating on a prompt
    python -m evals.run_experiment --scenario cart-crashloop

    # deterministic checks only — no judge model calls, no Anthropic spend
    python -m evals.run_experiment --no-judge

Each run creates a dataset run in Langfuse, so runs can be compared side by side
in the UI. `--fail-under` makes the process exit non-zero when the headline
score regresses, which is what a CI gate keys on.
"""

import argparse
import sys

from langfuse import get_client

from .config import DATASET_NAME, JUDGE_MODEL, require_langfuse_credentials
from .evaluators import CODE_EVALUATORS, JUDGE_EVALUATORS, RUN_EVALUATORS
from .task import investigation_task

# The run-level score a CI gate reads.
GATE_SCORE = "avg_root_cause_correctness"


def _select_items(dataset, scenario: str | None, tier: int | None):
    """Filter dataset items down to the subset the caller asked for."""
    items = list(dataset.items)
    if scenario:
        items = [item for item in items if item.id == scenario]
        if not items:
            raise SystemExit(f"No dataset item named '{scenario}'")
    if tier is not None:
        items = [item for item in items if (item.metadata or {}).get("tier") == tier]
        if not items:
            raise SystemExit(f"No dataset items at tier {tier}")
    return items


def _fault_identity(fault: dict) -> tuple[str, str]:
    """Stable id for 'which injected fault this item assumes'.

    Two scenarios that share kind+target (or kind+flag) can run together —
    they are grading the same broken environment. Distinct identities cannot.
    """
    kind = str(fault.get("kind") or "none")
    marker = str(fault.get("target") or fault.get("flag") or "")
    return (kind, marker)


def _fault_groups(items) -> dict[tuple[str, str], list[str]]:
    """Map each distinct injected fault to the scenario names that assume it."""
    groups: dict[tuple[str, str], list[str]] = {}
    for item in items:
        fault = (item.metadata or {}).get("fault") or {}
        kind = fault.get("kind", "none")
        if kind == "none":
            continue
        groups.setdefault(_fault_identity(fault), []).append(item.id)
    return groups


def _check_fault_setup(items, allow_multi_fault: bool) -> None:
    """Refuse a run whose scenarios would invalidate each other.

    Nothing here injects faults — that is still manual (see the README). Each
    fault scenario therefore assumes its own fault, and only its own fault, is
    active. Running several *distinct* faults in one pass against one cluster
    means every scenario after the first is graded against an environment that
    also contains the previous faults, which produces confident, meaningless
    scores. Variants that share the same fault identity (for example a
    CrashLoopBackOff case and its red-herring twin) are safe together.
    """
    groups = _fault_groups(items)
    if len(groups) <= 1 or allow_multi_fault:
        return

    needing_faults = [name for names in groups.values() for name in names]
    raise SystemExit(
        f"{len(groups)} distinct injected faults are required by the selected "
        "scenarios, and this runner does not inject or clean up faults.\n\n"
        f"  {', '.join(needing_faults)}\n\n"
        "Run them one at a time with --scenario, injecting the fault beforehand "
        "(see scripts/eval_agent_performance.py for the otel-demo fault helpers).\n"
        "If your environment already handles fault setup per item, pass "
        "--allow-multi-fault."
    )


def _gate_value(result) -> float | None:
    """Read the headline run-level score out of an experiment result."""
    for evaluation in getattr(result, "run_evaluations", []) or []:
        if evaluation.name == GATE_SCORE and isinstance(evaluation.value, (int, float)):
            return float(evaluation.value)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DATASET_NAME, help="Langfuse dataset name")
    parser.add_argument("--run-name", default=None, help="Name for this dataset run")
    parser.add_argument(
        "--scenario", default=None, help="Run a single scenario by name"
    )
    parser.add_argument(
        "--tier", type=int, default=None, help="Run one difficulty tier"
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Skip LLM-as-a-judge evaluators (deterministic checks only)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help=(
            "Scenarios to investigate in parallel. Keep at 1 when scenarios share "
            "a cluster — concurrent fault injection makes results uninterpretable."
        ),
    )
    parser.add_argument(
        "--allow-multi-fault",
        action="store_true",
        help=(
            "Run several fault scenarios in one pass. Only correct if something "
            "outside this runner injects and clears each fault per item."
        ),
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help=f"Exit non-zero if {GATE_SCORE} falls below this value",
    )
    args = parser.parse_args()

    require_langfuse_credentials()
    langfuse = get_client()
    dataset = langfuse.get_dataset(args.dataset)

    evaluators = list(CODE_EVALUATORS)
    if not args.no_judge:
        evaluators += JUDGE_EVALUATORS

    items = _select_items(dataset, args.scenario, args.tier)
    _check_fault_setup(items, args.allow_multi_fault)

    print(
        f"Running {len(items)} of {len(dataset.items)} scenario(s) from '{args.dataset}'"
    )
    print(f"Judge: {'disabled' if args.no_judge else JUDGE_MODEL}\n")

    experiment_kwargs = dict(
        name="OpenSRE investigation suite",
        run_name=args.run_name,
        description="Agent investigates each scenario end to end via POST /investigate",
        task=investigation_task,
        evaluators=evaluators,
        run_evaluators=RUN_EVALUATORS,
        max_concurrency=args.concurrency,
        # Recorded on the run so a regression can be traced back to what changed.
        metadata={
            "judge_model": "none" if args.no_judge else JUDGE_MODEL,
            "scenario_filter": args.scenario or "all",
            "tier_filter": "all" if args.tier is None else str(args.tier),
        },
    )

    if len(items) == len(dataset.items):
        result = dataset.run_experiment(**experiment_kwargs)
    else:
        # DatasetClient.run_experiment always runs the whole dataset, so a
        # filtered run goes through the client with an explicit item list. These
        # are still Langfuse DatasetItems, so the SDK creates a dataset run for
        # them and the results stay comparable with a full run.
        result = langfuse.run_experiment(data=items, **experiment_kwargs)

    # Per-item scores are the point of a small suite — they tell you *which*
    # scenario regressed, which the run-level averages alone cannot.
    print(result.format(include_item_results=True))

    # Short-lived process: flush before exit or the last scores never ship.
    langfuse.flush()

    if args.fail_under is None:
        return 0

    score = _gate_value(result)
    if score is None:
        print(f"\nFAIL: {GATE_SCORE} was not produced, cannot evaluate the gate.")
        return 1
    if score < args.fail_under:
        print(
            f"\nFAIL: {GATE_SCORE} {score:.2f} is below the {args.fail_under:.2f} gate."
        )
        return 1

    print(f"\nPASS: {GATE_SCORE} {score:.2f} meets the {args.fail_under:.2f} gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
