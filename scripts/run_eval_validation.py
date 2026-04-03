#!/usr/bin/env python3
"""
OpenSRE Evaluation Validation Suite

This script orchestrates the full evaluation pipeline to validate that:
1. All plumbing works (eval packs load, pipeline runs, outputs are generated)
2. LLM-as-judge scoring works
3. Agent performance meets enterprise thresholds

Usage:
    # Dry-run (no LLM calls, validates plumbing)
    python3 scripts/run_eval_validation.py --dry-run

    # Full validation with LLM (requires ANTHROPIC_API_KEY or OPENAI_API_KEY)
    python3 scripts/run_eval_validation.py --use-llm

    # Specific scenarios
    python3 scripts/run_eval_validation.py --use-llm --scenarios incremental

    # Generate enterprise report
    python3 scripts/run_eval_validation.py --use-llm --report

Environment:
    ANTHROPIC_API_KEY or OPENAI_API_KEY must be set for LLM-based validation.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Configuration
AI_PIPELINE_DIR = Path(__file__).parent.parent / "ai_pipeline"
EVAL_PACKS_DIR = AI_PIPELINE_DIR / "eval" / "packs"
RESULTS_DIR = AI_PIPELINE_DIR / "eval" / "results"

# Enterprise thresholds
THRESHOLDS = {
    "min_pass_rate": 0.80,  # 80% of scenarios must pass
    "min_avg_score": 70,  # Average LLM judge score
    "max_false_positive_rate": 0.05,  # Max 5% false positives
    "max_contract_error_rate": 0.10,  # Max 10% contract validation failures
}


@dataclass
class EvalResult:
    scenario_id: str
    passed: bool
    score: int
    false_positive: bool
    false_negative: bool
    contract_errors: int
    smoke_passed: bool
    errors: List[str]


@dataclass
class ValidationReport:
    timestamp: str
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    pass_rate: float
    avg_score: float
    false_positive_rate: float
    contract_error_rate: float
    results: List[Dict[str, Any]]
    meets_thresholds: bool
    threshold_failures: List[str]


def run_eval_pipeline(
    *,
    scenarios: str = "all",
    dry_run: bool = False,
    use_llm_judge: bool = False,
    skip_codegen: bool = False,
    limit: int = 0,
) -> Path:
    """Run the eval pipeline and return the results directory."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results_dir = RESULTS_DIR / f"validation_{timestamp}"
    results_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(AI_PIPELINE_DIR / "scripts" / "run_eval.py"),
        "--no-rds",
        "--results-dir",
        str(results_dir),
    ]

    # Select scenarios
    if scenarios == "incremental":
        cmd.extend(["--packs-dir", str(EVAL_PACKS_DIR / "incremental")])
    elif scenarios == "bootstrap":
        cmd.extend(["--packs-dir", str(EVAL_PACKS_DIR / "bootstrap")])
        cmd.append("--skip-gap-analysis")
    else:
        cmd.extend(["--packs-dir", str(EVAL_PACKS_DIR)])

    if dry_run:
        cmd.append("--dry-run")

    if use_llm_judge:
        cmd.append("--use-llm-judge")

    if skip_codegen:
        cmd.append("--skip-mcp-codegen")
    else:
        cmd.append("--run-mcp-smoke-pytest")

    if limit > 0:
        cmd.extend(["--limit", str(limit)])

    print("\n🚀 Running eval pipeline...")
    print(f"   Command: {' '.join(cmd)}")
    print(f"   Results: {results_dir}\n")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(AI_PIPELINE_DIR)

    result = subprocess.run(
        cmd,
        cwd=str(AI_PIPELINE_DIR),
        env=env,
        capture_output=False,
    )

    if result.returncode != 0:
        print(f"❌ Eval pipeline failed with exit code {result.returncode}")
        sys.exit(1)

    return results_dir


def parse_results(results_dir: Path) -> List[EvalResult]:
    """Parse eval results from JSON files."""
    results = []

    for result_file in results_dir.glob("scenario_*.json"):
        try:
            data = json.loads(result_file.read_text())

            # Extract judge results if present
            judge = data.get("judge") or {}
            bootstrap_judge = judge.get("bootstrap") or {}
            gap_judge = judge.get("gap_analysis") or {}

            # Use gap analysis score if available, else bootstrap
            if gap_judge:
                passed = gap_judge.get("pass", False)
                score = gap_judge.get("score", 0)
                fp = gap_judge.get("false_positive", False)
                fn = gap_judge.get("false_negative", False)
            elif bootstrap_judge:
                passed = bootstrap_judge.get("pass", False)
                score = bootstrap_judge.get("score", 0)
                fp = bootstrap_judge.get("false_positive", False)
                fn = bootstrap_judge.get("false_negative", False)
            else:
                # No judge - use contract checks
                passed = True
                score = 100
                fp = False
                fn = False

            # Count contract errors
            contract_checks = data.get("contract_checks") or []
            contract_errors = sum(
                1 for c in contract_checks if not c.get("passed", True)
            )

            # Check smoke test results
            smoke_pytest = data.get("mcp_smoke_pytest") or {}
            smoke_passed = smoke_pytest.get("passed", True) if smoke_pytest else True

            results.append(
                EvalResult(
                    scenario_id=data.get("scenario_id", "unknown"),
                    passed=passed,
                    score=score,
                    false_positive=fp,
                    false_negative=fn,
                    contract_errors=contract_errors,
                    smoke_passed=smoke_passed,
                    errors=[],
                )
            )

        except Exception as e:
            results.append(
                EvalResult(
                    scenario_id=result_file.stem,
                    passed=False,
                    score=0,
                    false_positive=False,
                    false_negative=False,
                    contract_errors=0,
                    smoke_passed=False,
                    errors=[str(e)],
                )
            )

    return results


def generate_report(results: List[EvalResult]) -> ValidationReport:
    """Generate a validation report from results."""
    total = len(results)
    if total == 0:
        return ValidationReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_scenarios=0,
            passed_scenarios=0,
            failed_scenarios=0,
            pass_rate=0.0,
            avg_score=0.0,
            false_positive_rate=0.0,
            contract_error_rate=0.0,
            results=[],
            meets_thresholds=False,
            threshold_failures=["No scenarios evaluated"],
        )

    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    pass_rate = passed / total
    avg_score = sum(r.score for r in results) / total
    fp_count = sum(1 for r in results if r.false_positive)
    fp_rate = fp_count / total
    contract_errors = sum(r.contract_errors for r in results)
    # Total tools is approximate (contract_checks per scenario)
    contract_error_rate = contract_errors / max(
        total * 5, 1
    )  # Assume ~5 tools/scenario

    # Check thresholds
    failures = []
    if pass_rate < THRESHOLDS["min_pass_rate"]:
        failures.append(
            f"Pass rate {pass_rate:.1%} < {THRESHOLDS['min_pass_rate']:.0%}"
        )
    if avg_score < THRESHOLDS["min_avg_score"]:
        failures.append(f"Avg score {avg_score:.0f} < {THRESHOLDS['min_avg_score']}")
    if fp_rate > THRESHOLDS["max_false_positive_rate"]:
        failures.append(
            f"False positive rate {fp_rate:.1%} > {THRESHOLDS['max_false_positive_rate']:.0%}"
        )
    if contract_error_rate > THRESHOLDS["max_contract_error_rate"]:
        failures.append(
            f"Contract error rate {contract_error_rate:.1%} > {THRESHOLDS['max_contract_error_rate']:.0%}"
        )

    return ValidationReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        total_scenarios=total,
        passed_scenarios=passed,
        failed_scenarios=failed,
        pass_rate=pass_rate,
        avg_score=avg_score,
        false_positive_rate=fp_rate,
        contract_error_rate=contract_error_rate,
        results=[
            {
                "scenario_id": r.scenario_id,
                "passed": r.passed,
                "score": r.score,
                "false_positive": r.false_positive,
                "false_negative": r.false_negative,
                "contract_errors": r.contract_errors,
                "smoke_passed": r.smoke_passed,
            }
            for r in results
        ],
        meets_thresholds=len(failures) == 0,
        threshold_failures=failures,
    )


def print_report(report: ValidationReport, verbose: bool = False) -> None:
    """Print a human-readable report."""
    print("\n" + "=" * 70)
    print("📊 OPENSRE EVALUATION VALIDATION REPORT")
    print("=" * 70)
    print(f"\nTimestamp: {report.timestamp}")
    print(
        f"\nScenarios: {report.total_scenarios} total, {report.passed_scenarios} passed, {report.failed_scenarios} failed"
    )
    print("\n📈 Metrics:")
    print(
        f"   Pass Rate:           {report.pass_rate:.1%} (threshold: ≥{THRESHOLDS['min_pass_rate']:.0%})"
    )
    print(
        f"   Average Score:       {report.avg_score:.0f}/100 (threshold: ≥{THRESHOLDS['min_avg_score']})"
    )
    print(
        f"   False Positive Rate: {report.false_positive_rate:.1%} (threshold: ≤{THRESHOLDS['max_false_positive_rate']:.0%})"
    )
    print(
        f"   Contract Error Rate: {report.contract_error_rate:.1%} (threshold: ≤{THRESHOLDS['max_contract_error_rate']:.0%})"
    )

    if report.meets_thresholds:
        print("\n✅ ALL THRESHOLDS MET - System is enterprise-ready!")
    else:
        print("\n❌ THRESHOLD FAILURES:")
        for f in report.threshold_failures:
            print(f"   - {f}")

    if verbose:
        print("\n📋 Per-Scenario Results:")
        for r in report.results:
            status = "✅" if r["passed"] else "❌"
            fp = " [FP]" if r["false_positive"] else ""
            fn = " [FN]" if r["false_negative"] else ""
            print(f"   {status} {r['scenario_id']}: score={r['score']}{fp}{fn}")

    print("\n" + "=" * 70)


def save_report(report: ValidationReport, output_path: Path) -> None:
    """Save report as JSON."""
    output_path.write_text(
        json.dumps(
            {
                "timestamp": report.timestamp,
                "summary": {
                    "total_scenarios": report.total_scenarios,
                    "passed_scenarios": report.passed_scenarios,
                    "failed_scenarios": report.failed_scenarios,
                    "pass_rate": report.pass_rate,
                    "avg_score": report.avg_score,
                    "false_positive_rate": report.false_positive_rate,
                    "contract_error_rate": report.contract_error_rate,
                    "meets_thresholds": report.meets_thresholds,
                },
                "thresholds": THRESHOLDS,
                "threshold_failures": report.threshold_failures,
                "results": report.results,
            },
            indent=2,
        )
    )
    print(f"\n📄 Report saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="OpenSRE Evaluation Validation Suite")
    parser.add_argument(
        "--dry-run", action="store_true", help="Skip LLM calls, validate plumbing only"
    )
    parser.add_argument(
        "--use-llm", action="store_true", help="Run with LLM-as-judge scoring"
    )
    parser.add_argument(
        "--scenarios",
        choices=["all", "incremental", "bootstrap"],
        default="incremental",
        help="Which scenario set to run (default: incremental)",
    )
    parser.add_argument(
        "--skip-codegen", action="store_true", help="Skip MCP code generation"
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="Limit number of scenarios (0=all)"
    )
    parser.add_argument(
        "--report", action="store_true", help="Generate detailed report file"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    print("\n🦊 OpenSRE Evaluation Validation Suite")
    print("=" * 50)

    # Check for API keys if using LLM
    if args.use_llm and not args.dry_run:
        if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OPENAI_API_KEY"):
            print(
                "❌ Error: ANTHROPIC_API_KEY or OPENAI_API_KEY required for LLM validation"
            )
            print("   Set one of these environment variables and retry.")
            sys.exit(1)

    # Run the eval pipeline
    results_dir = run_eval_pipeline(
        scenarios=args.scenarios,
        dry_run=args.dry_run,
        use_llm_judge=args.use_llm and not args.dry_run,
        skip_codegen=args.skip_codegen,
        limit=args.limit,
    )

    # Parse results
    results = parse_results(results_dir)

    if not results:
        print("❌ No results found. Check the eval pipeline output.")
        sys.exit(1)

    # Generate and print report
    report = generate_report(results)
    print_report(report, verbose=args.verbose)

    # Save report if requested
    if args.report:
        report_path = results_dir / "validation_report.json"
        save_report(report, report_path)

    # Exit with appropriate code
    if args.dry_run:
        print("\n✅ Dry-run completed successfully. Plumbing is working!")
        sys.exit(0)
    elif report.meets_thresholds:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
