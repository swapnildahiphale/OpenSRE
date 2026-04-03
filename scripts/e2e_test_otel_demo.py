#!/usr/bin/env python3
"""
OpenSRE E2E Fault Injection Test

Tests the OpenSRE agent's ability to investigate real faults in a Kubernetes
cluster running OpenTelemetry Demo.

Prerequisites:
- kind cluster "opensre-test" with otel-demo deployed
- OpenSRE stack running (docker compose up -d)
- NodePort access: Prometheus (9090), Grafana (3001), frontend (8090)

Usage:
    python scripts/e2e_test_otel_demo.py                    # cart fault (default)
    python scripts/e2e_test_otel_demo.py --fault product    # product catalog fault
    python scripts/e2e_test_otel_demo.py --fault all        # all 4 faults
"""

import json
import os
import subprocess
import sys
import time

import requests

# Configuration
OTEL_NAMESPACE = os.getenv("OTEL_NAMESPACE", "otel-demo")
KUBE_CONTEXT = os.getenv("KUBE_CONTEXT", "")
AGENT_URL = os.getenv("AGENT_URL", "http://localhost:8001")
CONFIG_URL = os.getenv("CONFIG_URL", "http://localhost:8081")
AUTH_TOKEN = None  # Populated at startup

# Fault definitions
AVAILABLE_FAULTS = {
    "cart": {
        "flag": "cartServiceFailure",
        "service": "cartservice",
        "description": "Cart EmptyCart operation fails intermittently (~10% rate via cartServiceFailure flag)",
        "expected_keywords": [
            "cart",
            "error",
            "fail",
            "service",
            "otel-demo",
            "pod",
            "status",
        ],
        "investigation_prompt": (
            "Users are reporting intermittent errors during checkout in the otel-demo namespace. "
            "The cart service EmptyCart operation appears to fail at a low rate. "
            "Investigate — check infrastructure health, application metrics, error rates, and traces."
        ),
    },
    "product": {
        "flag": "productCatalogFailure",
        "service": "productcatalogservice",
        "description": "Product catalog GetProduct fails (~5% rate via productCatalogFailure flag)",
        "expected_keywords": [
            "product",
            "catalog",
            "error",
            "fail",
            "service",
            "otel-demo",
        ],
        "investigation_prompt": (
            "Users are seeing errors when browsing product pages in the otel-demo namespace. "
            "The product catalog service appears to be returning errors on some requests. "
            "Investigate — check infrastructure health, application metrics, error rates, "
            "and logs to find the root cause."
        ),
    },
    "recommendation": {
        "flag": "recommendationServiceCacheFailure",
        "service": "recommendationservice",
        "description": "Recommendation service cache fails, causing high latency",
        "expected_keywords": [
            "recommendation",
            "cache",
            "latency",
            "slow",
            "service",
            "otel-demo",
        ],
        "investigation_prompt": (
            "Users are experiencing slow page loads in the otel-demo namespace. "
            "Investigate the recommendation service — check infrastructure, latency metrics, "
            "and traces. Look for cache-related issues causing high latency."
        ),
    },
    "ad": {
        "flag": "adServiceHighCpu",
        "service": "adservice",
        "description": "Ad service experiences high CPU load (via adServiceHighCpu flag)",
        "expected_keywords": [
            "ad",
            "cpu",
            "service",
            "otel-demo",
            "resource",
        ],
        "investigation_prompt": (
            "The ad service in the otel-demo namespace is experiencing performance degradation. "
            "Users report slow ad loading. "
            "Investigate — check infrastructure health, CPU/resource usage, metrics, "
            "and traces to identify what is causing the slowdown."
        ),
    },
}


def get_auth_token() -> str:
    """Get a team token from config-service for agent API auth."""
    try:
        resp = requests.post(
            f"{CONFIG_URL}/api/v1/admin/orgs/local/teams/default/tokens",
            headers={
                "Authorization": "Bearer local-admin-token",
                "Content-Type": "application/json",
            },
            json={
                "description": "e2e-test",
                "permissions": ["team:read", "team:write"],
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("token", "")
    except Exception as e:
        print(f"   WARN: Could not get auth token: {e}")
    return ""


def run_kubectl(args: list) -> subprocess.CompletedProcess:
    """Run kubectl command against the test cluster."""
    cmd = ["kubectl"]
    if KUBE_CONTEXT:
        cmd += ["--context", KUBE_CONTEXT]
    cmd += args
    return subprocess.run(cmd, capture_output=True, text=True)


def get_flagd_config() -> dict:
    """Get current flagd configuration."""
    result = run_kubectl(
        [
            "get",
            "configmap",
            "otel-demo-flagd-config",
            "-n",
            OTEL_NAMESPACE,
            "-o",
            "jsonpath={.data.demo\\.flagd\\.json}",
        ]
    )
    if result.returncode != 0:
        raise Exception(f"Failed to get flagd config: {result.stderr}")
    return json.loads(result.stdout) if result.stdout else {}


def set_fault_flag(flag_name: str, enabled: bool) -> bool:
    """Enable or disable a fault flag in flagd."""
    action = "Enabling" if enabled else "Disabling"
    print(f"   {action} fault flag: {flag_name}")

    config = get_flagd_config()
    if flag_name not in config.get("flags", {}):
        print(f"   FAIL: Flag '{flag_name}' not found in flagd ConfigMap!")
        print(
            f"   Available flags: {', '.join(sorted(config.get('flags', {}).keys()))}"
        )
        return False

    config["flags"][flag_name]["defaultVariant"] = "on" if enabled else "off"
    patch = {"data": {"demo.flagd.json": json.dumps(config, indent=2)}}

    result = run_kubectl(
        [
            "patch",
            "configmap",
            "otel-demo-flagd-config",
            "-n",
            OTEL_NAMESPACE,
            "--type=merge",
            "-p",
            json.dumps(patch),
        ]
    )
    if result.returncode != 0:
        print(f"   FAIL: {result.stderr}")
        return False

    # Restart flagd to pick up changes
    run_kubectl(
        ["rollout", "restart", "deployment/otel-demo-flagd", "-n", OTEL_NAMESPACE]
    )
    print("   Waiting for flagd restart...")
    time.sleep(20)

    # Verify flagd is running (it can OOM with low memory limits)
    result = run_kubectl(
        [
            "get",
            "pods",
            "-n",
            OTEL_NAMESPACE,
            "-l",
            "app.kubernetes.io/component=flagd",
            "--no-headers",
        ]
    )
    if "Running" not in result.stdout:
        print("   WARN: flagd not Running after restart, waiting longer...")
        time.sleep(15)

    # Restart the affected service to ensure fresh gRPC connection to flagd.
    # After flagd restarts, services using OpenFeature SDK may have stale
    # connections that show PROVIDER_NOT_READY errors.
    fault_service_deployments = _get_affected_deployments(flag_name)
    for deploy in fault_service_deployments:
        print(f"   Restarting {deploy} for fresh flagd connection...")
        run_kubectl(
            ["rollout", "restart", f"deployment/{deploy}", "-n", OTEL_NAMESPACE]
        )
    if fault_service_deployments:
        time.sleep(20)

    return True


# Map flags to the deployment(s) that evaluate them
FLAG_SERVICE_DEPLOYMENTS = {
    "productCatalogFailure": ["otel-demo-productcatalogservice"],
    "cartServiceFailure": ["otel-demo-cartservice"],
    "adServiceHighCpu": ["otel-demo-adservice"],
    "recommendationServiceCacheFailure": ["otel-demo-recommendationservice"],
    "paymentServiceFailure": ["otel-demo-paymentservice"],
    "paymentServiceUnreachable": ["otel-demo-paymentservice"],
}


def _get_affected_deployments(flag_name: str) -> list:
    """Return deployment names that evaluate the given flag."""
    return FLAG_SERVICE_DEPLOYMENTS.get(flag_name, [])


def wait_for_symptoms(service_name: str, timeout: int = 30) -> bool:
    """Wait for failure symptoms to appear."""
    print(f"   Watching for {service_name} symptoms ({timeout}s)...")
    start = time.time()

    while time.time() - start < timeout:
        result = run_kubectl(
            [
                "get",
                "events",
                "-n",
                OTEL_NAMESPACE,
                "--field-selector",
                "type=Warning",
            ]
        )
        if service_name.lower() in result.stdout.lower():
            print("   OK: Warning events detected")
            return True
        time.sleep(5)

    print("   INFO: No K8s-level symptoms (application-level fault, expected)")
    return True


def verify_fault_active(fault_info: dict, timeout: int = 120) -> bool:
    """Query Prometheus to verify fault is producing errors/symptoms."""
    service = fault_info["service"]
    prom_url = "http://localhost:9090"

    # Use span-based metrics (available in otel-demo)
    # Note: [5m] window needed — scrape intervals can be 30s+, so [1m] often
    # has too few samples for rate() to produce a result
    query = f'sum(rate(calls_total{{service_name="{service}",status_code="STATUS_CODE_ERROR"}}[5m]))'

    print(f"   Verifying fault via Prometheus ({timeout}s timeout)...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(
                f"{prom_url}/api/v1/query", params={"query": query}, timeout=5
            )
            result = resp.json()
            data = result.get("data", {}).get("result", [])
            if data and float(data[0]["value"][1]) > 0:
                print(f"   OK: Fault verified — errors detected for {service}")
                return True
        except Exception:
            pass
        time.sleep(10)

    print(f"   WARN: No errors detected for {service} after {timeout}s")
    print(f"   Fault injection may not be working for flag '{fault_info['flag']}'")
    return False


def check_prometheus(service_name: str) -> dict:
    """Query Prometheus for service metrics with retry."""
    prom_url = "http://localhost:9090"
    query = f'sum(rate(http_server_duration_milliseconds_count{{service_name=~".*{service_name}.*"}}[2m]))'
    for attempt in range(3):
        try:
            resp = requests.get(
                f"{prom_url}/api/v1/query",
                params={"query": query},
                timeout=15,
            )
            return resp.json()
        except Exception as e:
            if attempt < 2:
                time.sleep(5)
            else:
                return {"error": str(e)}


def call_agent(prompt: str, timeout: int = 900) -> dict:
    """Call the OpenSRE agent via SSE streaming /investigate endpoint."""
    print(f"   Sending to {AGENT_URL}/investigate ...")
    print(f"   Prompt: {prompt[:80]}...")

    try:
        headers = {"Content-Type": "application/json"}
        if AUTH_TOKEN:
            headers["Authorization"] = f"Bearer {AUTH_TOKEN}"

        resp = requests.post(
            f"{AGENT_URL}/investigate",
            json={"prompt": prompt},
            headers=headers,
            stream=True,
            timeout=timeout,
        )

        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:300]}"}

        events = []
        accumulated_text = ""
        tool_calls = []
        thoughts = []

        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue

            data_str = line[6:]
            if data_str == "[DONE]":
                break

            try:
                event = json.loads(data_str)
                events.append(event)
                etype = event.get("event", event.get("type", ""))

                if etype in ("result", "text"):
                    text = (
                        event.get("data", {}).get("text", "")
                        if isinstance(event.get("data"), dict)
                        else str(event.get("data", ""))
                    )
                    accumulated_text += text

                elif etype == "tool_start":
                    name = event.get("data", {}).get("name", "unknown")
                    tool_calls.append(name)
                    print(f"      Tool: {name}")

                elif etype == "thought":
                    text = (
                        event.get("data", {}).get("text", "")
                        if isinstance(event.get("data"), dict)
                        else str(event.get("data", ""))
                    )
                    if text:
                        thoughts.append(text)
                        if len(text) > 100:
                            print(f"      Think: {text[:100]}...")
            except json.JSONDecodeError:
                pass

        return {
            "success": True,
            "output": accumulated_text,
            "event_count": len(events),
            "tool_calls": tool_calls,
            "thoughts": thoughts,
        }

    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except Exception as e:
        return {"error": str(e)}


def validate(result: dict, expected_keywords: list) -> tuple:
    """Validate agent output against expected keywords."""
    if not result.get("success"):
        print(f"   FAIL: {result.get('error')}")
        return False, []

    all_text = (result.get("output", "") + " ".join(result.get("thoughts", []))).lower()
    found = [kw for kw in expected_keywords if kw.lower() in all_text]

    if len(found) >= 3:
        print(
            f"   OK: Matched {len(found)}/{len(expected_keywords)}: {', '.join(found)}"
        )
        return True, found
    else:
        print(f"   WARN: Only {len(found)} matches: {found}")
        return False, found


def print_summary(result: dict, fault_info: dict, passed: bool, found: list):
    """Print detailed investigation summary."""
    print("\n" + "=" * 70)
    print("INVESTIGATION SUMMARY")
    print("=" * 70)
    print(f"  Fault: {fault_info['flag']} ({fault_info['description']})")
    print(f"  Result: {'PASSED' if passed else 'FAILED'}")
    print(f"  Keywords: {len(found)}/{len(fault_info['expected_keywords'])}")
    print(f"  SSE events: {result.get('event_count', 0)}")
    print(f"  Tool calls: {len(result.get('tool_calls', []))}")

    if result.get("tool_calls"):
        print("\n  Tools used:")
        seen = []
        for t in result["tool_calls"]:
            if t not in seen:
                seen.append(t)
                print(f"    - {t}")

    if result.get("thoughts"):
        print(f"\n  Agent reasoning ({len(result['thoughts'])} steps):")
        for i, t in enumerate(result["thoughts"][:8], 1):
            print(f"    {i}. {t[:150]}")

    if result.get("output"):
        print(f"\n  Agent conclusion ({len(result['output'])} chars):")
        output = result["output"]
        print(f"    {output[:2000]}")
        if len(output) > 2000:
            print("    ...[truncated]")

    print("=" * 70)


def run_test(fault_type: str = "cart") -> bool:
    """Run a single fault injection test."""
    fault_info = AVAILABLE_FAULTS.get(fault_type)
    if not fault_info:
        print(
            f"Unknown fault: {fault_type}. Available: {list(AVAILABLE_FAULTS.keys())}"
        )
        return False

    print("=" * 70)
    print(f"  OpenSRE E2E Test: {fault_type}")
    ctx = KUBE_CONTEXT or "(current context)"
    print(f"  Cluster: {ctx} | Agent: {AGENT_URL}")
    print("=" * 70)

    try:
        # 1. Pre-check
        print("\n[1/6] Pre-test health check")
        result = run_kubectl(["get", "pods", "-n", OTEL_NAMESPACE, "--no-headers"])
        running = sum(1 for l in result.stdout.strip().split("\n") if "Running" in l)
        total = len([l for l in result.stdout.strip().split("\n") if l.strip()])
        print(f"   Pods: {running}/{total} running")

        prom = check_prometheus(fault_info["service"])
        print(f"   Prometheus: {prom.get('status', prom.get('error', '?'))}")

        agent_health = requests.get(f"{AGENT_URL}/health", timeout=5).json()
        print(f"   Agent: {agent_health.get('status', '?')}")

        # 2. Inject fault
        print(f"\n[2/6] Injecting fault: {fault_info['flag']}")
        if not set_fault_flag(fault_info["flag"], enabled=True):
            return False

        # 3. Verify fault injection
        print("\n[3/6] Verifying fault injection")
        wait_for_symptoms(fault_info["service"])
        fault_verified = verify_fault_active(fault_info)
        if not fault_verified:
            print("   WARN: Continuing — fault may only affect specific operations")

        # 4. Investigate
        print("\n[4/6] Agent investigation")
        inv_result = call_agent(fault_info["investigation_prompt"], timeout=900)

        # 5. Validate
        print("\n[5/6] Validating diagnosis")
        passed, found = validate(inv_result, fault_info["expected_keywords"])

        # 6. Summary
        print("\n[6/6] Summary")
        print_summary(inv_result, fault_info, passed, found)

        return passed

    finally:
        print(f"\n  Clearing fault: {fault_info['flag']}")
        set_fault_flag(fault_info["flag"], enabled=False)


def run_all() -> bool:
    """Run all fault tests."""
    results = {}
    for ft in AVAILABLE_FAULTS:
        print(f"\n\n{'#' * 70}")
        print(f"# Test: {ft}")
        print(f"{'#' * 70}")
        results[ft] = run_test(ft)
        time.sleep(30)

    print(f"\n{'=' * 70}")
    print("FINAL RESULTS")
    print(f"{'=' * 70}")
    for ft, passed in results.items():
        print(f"  {ft}: {'PASSED' if passed else 'FAILED'}")
    passed_count = sum(1 for p in results.values() if p)
    print(f"\n  Total: {passed_count}/{len(results)}")
    return all(results.values())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OpenSRE E2E Fault Injection Test")
    parser.add_argument(
        "--fault",
        choices=list(AVAILABLE_FAULTS.keys()) + ["all"],
        default="cart",
        help="Fault type (default: cart)",
    )
    parser.add_argument("--agent-url", default="http://localhost:8001")
    parser.add_argument("--config-url", default="http://localhost:8081")
    parser.add_argument(
        "--kube-context", default="", help="Kube context (default: current context)"
    )
    parser.add_argument("--otel-namespace", default="otel-demo")
    args = parser.parse_args()

    AGENT_URL = args.agent_url
    CONFIG_URL = args.config_url
    KUBE_CONTEXT = args.kube_context
    OTEL_NAMESPACE = args.otel_namespace

    AUTH_TOKEN = get_auth_token()
    if AUTH_TOKEN:
        print(f"Auth token acquired from {CONFIG_URL}")
    else:
        print("WARNING: No auth token — agent may reject requests")

    success = run_all() if args.fault == "all" else run_test(args.fault)
    sys.exit(0 if success else 1)
