#!/usr/bin/env python3
"""
OpenSRE Agent Performance Evaluation

This script tests the agent's ability to diagnose and investigate incidents.
It sends simulated incident scenarios to the agent and validates the responses.

Usage:
    # Local agent (port-forward or local run)
    python3 scripts/run_agent_eval.py --agent-url http://localhost:8080

    # Against deployed agent
    python3 scripts/run_agent_eval.py --agent-url http://agent.opensre.internal:8080

Test Scenarios:
1. Basic Kubernetes diagnosis (pods, events, logs)
2. Service dependency analysis
3. Metrics interpretation
4. Log analysis
5. Root cause identification
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Test scenarios that don't require real infrastructure
SCENARIOS = [
    {
        "id": "basic_pods",
        "description": "Basic pod status query",
        "agent": "investigation_agent",
        "message": "List all pods in the kube-system namespace and their status",
        "expected_keywords": ["pod", "status", "running", "kube-system"],
        "timeout": 60,
    },
    {
        "id": "diagnostic_question",
        "description": "Diagnostic reasoning",
        "agent": "planner",
        "message": "A user reports that checkout is slow. What are the top 5 things I should check first?",
        "expected_keywords": ["latency", "metrics", "logs", "dependencies", "check"],
        "timeout": 60,
    },
    {
        "id": "incident_triage",
        "description": "Incident triage steps",
        "agent": "planner",
        "message": "We're seeing 5xx errors from the payment service. Walk me through how to triage this.",
        "expected_keywords": ["error", "rate", "logs", "traces", "downstream"],
        "timeout": 60,
    },
]


@dataclass
class TestResult:
    scenario_id: str
    passed: bool
    response_time_ms: float
    keywords_found: List[str]
    keywords_missing: List[str]
    output_preview: str
    error: Optional[str]


def call_agent(
    base_url: str,
    agent: str,
    message: str,
    timeout: int = 60,
) -> Dict[str, Any]:
    """Call the agent API."""
    import requests

    url = f"{base_url.rstrip('/')}/agents/{agent}/run"

    try:
        response = requests.post(
            url,
            json={
                "message": message,
                "timeout": timeout,
                "max_turns": 50,
            },
            timeout=timeout + 30,
        )

        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"HTTP {response.status_code}: {response.text[:200]}"}

    except Exception as e:
        return {"error": str(e)}


def validate_response(
    result: Dict[str, Any],
    expected_keywords: List[str],
) -> tuple[bool, List[str], List[str]]:
    """Check if response contains expected keywords."""
    if not result.get("success", False):
        return False, [], expected_keywords

    output = result.get("output", "")
    if isinstance(output, dict):
        output = json.dumps(output)
    output_lower = str(output).lower()

    found = []
    missing = []

    for kw in expected_keywords:
        if kw.lower() in output_lower:
            found.append(kw)
        else:
            missing.append(kw)

    # Pass if we found at least half the keywords
    passed = len(found) >= len(expected_keywords) / 2

    return passed, found, missing


def run_scenario(base_url: str, scenario: Dict[str, Any]) -> TestResult:
    """Run a single test scenario."""
    print(f"\n  📋 {scenario['id']}: {scenario['description']}")

    start_time = time.time()
    result = call_agent(
        base_url=base_url,
        agent=scenario["agent"],
        message=scenario["message"],
        timeout=scenario["timeout"],
    )
    elapsed_ms = (time.time() - start_time) * 1000

    if "error" in result:
        return TestResult(
            scenario_id=scenario["id"],
            passed=False,
            response_time_ms=elapsed_ms,
            keywords_found=[],
            keywords_missing=scenario["expected_keywords"],
            output_preview="",
            error=result["error"],
        )

    passed, found, missing = validate_response(result, scenario["expected_keywords"])

    output = result.get("output", "")
    if isinstance(output, dict):
        output = json.dumps(output)
    preview = str(output)[:200] + "..." if len(str(output)) > 200 else str(output)

    return TestResult(
        scenario_id=scenario["id"],
        passed=passed,
        response_time_ms=elapsed_ms,
        keywords_found=found,
        keywords_missing=missing,
        output_preview=preview,
        error=None,
    )


def run_all_scenarios(base_url: str) -> List[TestResult]:
    """Run all test scenarios."""
    results = []

    for scenario in SCENARIOS:
        result = run_scenario(base_url, scenario)
        results.append(result)

        if result.passed:
            print(f"     ✅ PASSED ({result.response_time_ms:.0f}ms)")
        else:
            print(
                f"     ❌ FAILED: {result.error or f'missing keywords: {result.keywords_missing}'}"
            )

    return results


def print_summary(results: List[TestResult]) -> bool:
    """Print summary and return success status."""
    print("\n" + "=" * 60)
    print("📊 AGENT EVALUATION SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    pass_rate = passed / total if total > 0 else 0
    avg_time = sum(r.response_time_ms for r in results) / total if total > 0 else 0

    print(f"\nResults: {passed}/{total} scenarios passed ({pass_rate:.0%})")
    print(f"Average response time: {avg_time:.0f}ms")

    if pass_rate >= 0.8:
        print("\n✅ AGENT EVALUATION PASSED")
        return True
    else:
        print("\n❌ AGENT EVALUATION FAILED")
        print("\nFailed scenarios:")
        for r in results:
            if not r.passed:
                print(f"  - {r.scenario_id}: {r.error or 'missing keywords'}")
        return False


def main():
    parser = argparse.ArgumentParser(description="OpenSRE Agent Evaluation")
    parser.add_argument(
        "--agent-url",
        default="http://localhost:8080",
        help="Agent API URL",
    )
    parser.add_argument(
        "--scenario",
        help="Run specific scenario by ID",
    )
    parser.add_argument(
        "--output",
        help="Output file for results JSON",
    )

    args = parser.parse_args()

    print("\n🦊 OpenSRE Agent Evaluation")
    print("=" * 50)
    print(f"Agent URL: {args.agent_url}")

    # Check connectivity
    try:
        import requests

        response = requests.get(f"{args.agent_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Agent is reachable")
        else:
            print(f"⚠️ Agent returned {response.status_code}")
    except Exception as e:
        print(f"❌ Cannot reach agent: {e}")
        print("\nMake sure the agent is running and accessible.")
        print(
            "For local testing, run: kubectl port-forward svc/opensre-agent 8080:8080"
        )
        sys.exit(1)

    # Run scenarios
    print("\n🧪 Running evaluation scenarios...")

    if args.scenario:
        scenarios = [s for s in SCENARIOS if s["id"] == args.scenario]
        if not scenarios:
            print(f"❌ Unknown scenario: {args.scenario}")
            print(f"   Available: {[s['id'] for s in SCENARIOS]}")
            sys.exit(1)
        results = [run_scenario(args.agent_url, scenarios[0])]
    else:
        results = run_all_scenarios(args.agent_url)

    # Save results
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent_url": args.agent_url,
                    "results": [
                        {
                            "scenario_id": r.scenario_id,
                            "passed": r.passed,
                            "response_time_ms": r.response_time_ms,
                            "keywords_found": r.keywords_found,
                            "keywords_missing": r.keywords_missing,
                            "output_preview": r.output_preview,
                            "error": r.error,
                        }
                        for r in results
                    ],
                },
                indent=2,
            )
        )
        print(f"\n📄 Results saved to: {output_path}")

    # Print summary
    success = print_summary(results)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
