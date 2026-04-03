#!/usr/bin/env python3
"""
Comprehensive Fault Analysis for OTel Demo on EKS.

For each flagd fault:
1. Capture baseline metrics/logs
2. Inject the fault
3. Wait for symptoms to appear
4. Probe Prometheus, OpenSearch, Jaeger, kubectl
5. Record all observable signals
6. Disable fault and move on

Usage: python3 scripts/fault_analysis.py [--fault <name>] [--all]
"""

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request

NAMESPACE = "otel-demo"
CONFIGMAP = "otel-demo-flagd-config"
PROM_URL = "http://localhost:9090"
OPENSEARCH_URL = "http://localhost:9200"
JAEGER_URL = "http://localhost:16686/jaeger/ui"

# All faults with their expected behavior
FAULTS = {
    "cartServiceFailure": {
        "service": "cartservice",
        "description": "Cart EmptyCart gRPC call fails intermittently",
        "type": "boolean",
        "enable_variant": "on",
        "affected_pods": ["otel-demo-cartservice"],
        "expected_symptoms": ["gRPC errors on EmptyCart", "checkout failures"],
    },
    "paymentServiceFailure": {
        "service": "paymentservice",
        "description": "Payment charge requests fail",
        "type": "boolean",
        "enable_variant": "on",
        "affected_pods": ["otel-demo-paymentservice"],
        "expected_symptoms": ["payment charge errors", "checkout failures"],
    },
    "paymentServiceUnreachable": {
        "service": "paymentservice",
        "description": "Payment service completely unavailable",
        "type": "boolean",
        "enable_variant": "on",
        "affected_pods": ["otel-demo-paymentservice"],
        "expected_symptoms": ["connection refused", "service unavailable"],
    },
    "productCatalogFailure": {
        "service": "productcatalogservice",
        "description": "Product catalog query errors on specific product",
        "type": "boolean",
        "enable_variant": "on",
        "affected_pods": ["otel-demo-productcatalogservice"],
        "expected_symptoms": ["GetProduct errors", "product page failures"],
    },
    "adServiceFailure": {
        "service": "adservice",
        "description": "Ad service returns errors",
        "type": "boolean",
        "enable_variant": "on",
        "affected_pods": ["otel-demo-adservice"],
        "expected_symptoms": ["ad serving errors", "GetAds failures"],
    },
    "adServiceHighCpu": {
        "service": "adservice",
        "description": "Triggers high CPU load in ad service (Java)",
        "type": "boolean",
        "enable_variant": "on",
        "affected_pods": ["otel-demo-adservice"],
        "expected_symptoms": ["CPU spike 80-100%", "increased latency", "GC pressure"],
    },
    "adServiceManualGc": {
        "service": "adservice",
        "description": "Triggers frequent full GC pauses in ad service",
        "type": "boolean",
        "enable_variant": "on",
        "affected_pods": ["otel-demo-adservice"],
        "expected_symptoms": ["GC pauses", "latency spikes", "STW events"],
    },
    "recommendationServiceCacheFailure": {
        "service": "recommendationservice",
        "description": "Recommendation service cache failures",
        "type": "boolean",
        "enable_variant": "on",
        "affected_pods": ["otel-demo-recommendationservice"],
        "expected_symptoms": ["cache miss storm", "increased latency"],
    },
    "kafkaQueueProblems": {
        "service": "checkoutservice",
        "description": "Overloads Kafka queue with consumer lag",
        "type": "numeric",
        "enable_variant": "on",
        "affected_pods": ["otel-demo-checkoutservice", "otel-demo-kafka"],
        "expected_symptoms": ["Kafka consumer lag", "checkout delays"],
    },
    "imageSlowLoad": {
        "service": "imageprovider",
        "description": "Slow image loading (5-10s delay)",
        "type": "numeric",
        "enable_variant": "5sec",
        "affected_pods": ["otel-demo-imageprovider"],
        "expected_symptoms": ["5s latency on images", "frontend slowness"],
    },
    "loadgeneratorFloodHomepage": {
        "service": "frontend",
        "description": "Flood frontend with massive request volume",
        "type": "numeric",
        "enable_variant": "on",
        "affected_pods": ["otel-demo-loadgenerator", "otel-demo-frontend"],
        "expected_symptoms": [
            "request flood",
            "increased error rate",
            "resource pressure",
        ],
    },
}


def http_get(url, timeout=10):
    """Simple HTTP GET returning parsed JSON or None."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def http_post_json(url, data, timeout=10):
    """HTTP POST with JSON body."""
    try:
        body = json.dumps(data).encode()
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def prom_query(query):
    """Execute a Prometheus instant query."""
    encoded = urllib.parse.quote(query)
    return http_get(f"{PROM_URL}/api/v1/query?query={encoded}")


def opensearch_query(query_body, size=20):
    """Query OpenSearch logs."""
    return http_post_json(f"{OPENSEARCH_URL}/otel/_search?size={size}", query_body)


def jaeger_traces(service, operation=None, limit=20, lookback="5m"):
    """Query Jaeger for traces."""
    url = f"{JAEGER_URL}/api/traces?service={service}&limit={limit}&lookback={lookback}"
    if operation:
        url += f"&operation={urllib.parse.quote(operation)}"
    return http_get(url)


def kubectl(cmd):
    """Run kubectl command and return stdout."""
    full_cmd = f"kubectl -n {NAMESPACE} {cmd}"
    try:
        result = subprocess.run(
            full_cmd, shell=True, capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"


def set_flag(flag_name, variant):
    """Set a flagd flag variant by patching the ConfigMap."""
    # Get current config
    raw = kubectl(
        f"get configmap {CONFIGMAP} -o jsonpath='{{.data.demo\\.flagd\\.json}}'"
    )
    try:
        config = json.loads(raw)
    except json.JSONDecodeError:
        print(f"  ERROR: Could not parse flagd config: {raw[:200]}")
        return False

    if flag_name not in config.get("flags", {}):
        print(f"  ERROR: Flag {flag_name} not found in config")
        return False

    config["flags"][flag_name]["defaultVariant"] = variant

    # Patch configmap
    patch = json.dumps({"data": {"demo.flagd.json": json.dumps(config, indent=2)}})
    result = subprocess.run(
        f"kubectl -n {NAMESPACE} patch configmap {CONFIGMAP} -p '{patch}'",
        shell=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        print(f"  ERROR: Failed to patch configmap: {result.stderr}")
        return False
    return True


def restart_pod(pod_prefix):
    """Restart pod by deleting it (deployment will recreate)."""
    pods = kubectl("get pods -o name").split("\n")
    for p in pods:
        if pod_prefix in p:
            kubectl(f"delete {p} --grace-period=5")
            return True
    return False


def get_error_rates():
    """Get current error rates per service."""
    result = prom_query(
        'sum by (service_name)(rate(calls_total{status_code="STATUS_CODE_ERROR"}[2m]))'
    )
    rates = {}
    if result and "data" in result:
        for r in result["data"].get("result", []):
            svc = r["metric"]["service_name"]
            rate = float(r["value"][1])
            if rate > 0:
                rates[svc] = rate
    return rates


def get_error_spans(service=None):
    """Get error span details per service."""
    query = (
        f'sum by (service_name,span_name)(rate(calls_total{{status_code="STATUS_CODE_ERROR",service_name="{service}"}}[2m])) > 0'
        if service
        else 'sum by (service_name,span_name)(rate(calls_total{status_code="STATUS_CODE_ERROR"}[2m])) > 0'
    )
    result = prom_query(query)
    spans = []
    if result and "data" in result:
        for r in result["data"].get("result", []):
            spans.append(
                {
                    "service": r["metric"]["service_name"],
                    "span": r["metric"]["span_name"],
                    "rate": float(r["value"][1]),
                }
            )
    return sorted(spans, key=lambda x: x["rate"], reverse=True)


def get_latency_p99(service):
    """Get p99 latency for a service."""
    result = prom_query(
        f'histogram_quantile(0.99, sum by (le)(rate(rpc_server_duration_milliseconds_bucket{{service_name="{service}"}}[2m])))'
    )
    if result and "data" in result:
        for r in result["data"].get("result", []):
            return float(r["value"][1])
    # Try HTTP metric
    result = prom_query(
        f'histogram_quantile(0.99, sum by (le)(rate(http_server_duration_milliseconds_bucket{{service_name="{service}"}}[2m])))'
    )
    if result and "data" in result:
        for r in result["data"].get("result", []):
            return float(r["value"][1])
    return None


def get_request_rate(service):
    """Get total request rate for a service."""
    result = prom_query(f'sum(rate(calls_total{{service_name="{service}"}}[2m]))')
    if result and "data" in result:
        for r in result["data"].get("result", []):
            return float(r["value"][1])
    return None


def get_cpu_usage(pod_prefix):
    """Get CPU usage via kubectl top."""
    output = kubectl("top pods --no-headers")
    for line in output.split("\n"):
        if pod_prefix in line:
            parts = line.split()
            if len(parts) >= 2:
                return parts[1]  # e.g., "250m"
    return None


def search_logs(service, severity="ERROR", minutes=3):
    """Search OpenSearch for logs from a service."""
    query = {
        "query": {
            "bool": {
                "must": [
                    {"match": {"resource.service.name": service}},
                ],
                "filter": [
                    {"range": {"observedTimestamp": {"gte": f"now-{minutes}m"}}}
                ],
            }
        },
        "sort": [{"observedTimestamp": {"order": "desc"}}],
    }
    if severity:
        query["query"]["bool"]["must"].append({"match": {"severity.text": severity}})
    result = opensearch_query(query, size=10)
    logs = []
    if result and "hits" in result:
        for hit in result["hits"].get("hits", []):
            src = hit["_source"]
            logs.append(
                {
                    "body": src.get("body", "")[:200],
                    "severity": src.get("severity", {}).get("text", "?"),
                    "timestamp": src.get("observedTimestamp", "?"),
                    "service": src.get("resource", {}).get("service.name", "?"),
                }
            )
    return logs


def search_logs_keyword(keyword, minutes=3):
    """Search OpenSearch for logs containing a keyword."""
    query = {
        "query": {
            "bool": {
                "must": [
                    {"match": {"body": keyword}},
                ],
                "filter": [
                    {"range": {"observedTimestamp": {"gte": f"now-{minutes}m"}}}
                ],
            }
        },
        "sort": [{"observedTimestamp": {"order": "desc"}}],
    }
    result = opensearch_query(query, size=10)
    logs = []
    if result and "hits" in result:
        for hit in result["hits"].get("hits", []):
            src = hit["_source"]
            logs.append(
                {
                    "body": src.get("body", "")[:200],
                    "severity": src.get("severity", {}).get("text", "?"),
                    "service": src.get("resource", {}).get("service.name", "?"),
                }
            )
    return logs


def get_pod_status(pod_prefix):
    """Get detailed pod status."""
    output = kubectl("get pods -o wide")
    for line in output.split("\n"):
        if pod_prefix in line:
            return line
    return None


def get_pod_events(pod_prefix):
    """Get recent events for a pod."""
    pods = kubectl("get pods -o name").split("\n")
    for p in pods:
        if pod_prefix in p:
            pod_name = p.replace("pod/", "")
            events = kubectl(
                f"get events --field-selector involvedObject.name={pod_name} --sort-by=.lastTimestamp"
            )
            return events
    return None


def get_container_logs(pod_prefix, tail=30):
    """Get recent container logs via kubectl."""
    pods = kubectl("get pods -o name").split("\n")
    for p in pods:
        if pod_prefix in p:
            return kubectl(f"logs {p} --tail={tail}")
    return None


def check_jaeger_errors(service, minutes=3):
    """Check Jaeger for error traces."""
    result = jaeger_traces(service, lookback=f"{minutes}m")
    if not result or "data" not in result:
        return {"available": False, "error": str(result)}

    traces = result.get("data", [])
    error_traces = []
    for trace in traces:
        for span in trace.get("spans", []):
            for tag in span.get("tags", []):
                if tag.get("key") == "otel.status_code" and tag.get("value") == "ERROR":
                    error_traces.append(
                        {
                            "operation": span.get("operationName", "?"),
                            "duration_us": span.get("duration", 0),
                            "service": (
                                span.get("process", {}).get("serviceName", "?")
                                if "process" in span
                                else "?"
                            ),
                        }
                    )
    return {
        "available": True,
        "total_traces": len(traces),
        "error_spans": error_traces[:10],
    }


def get_kafka_metrics():
    """Get Kafka-specific metrics."""
    metrics = {}
    result = prom_query("kafka_consumer_records_per_request_avg")
    if result and "data" in result:
        for r in result["data"].get("result", []):
            metrics["records_per_request_avg"] = float(r["value"][1])

    result = prom_query("kafka_consumer_fetch_latency_avg")
    if result and "data" in result:
        for r in result["data"].get("result", []):
            metrics["fetch_latency_avg"] = float(r["value"][1])

    result = prom_query("kafka_request_failed_total")
    if result and "data" in result:
        total = sum(float(r["value"][1]) for r in result["data"].get("result", []))
        metrics["failed_requests_total"] = total

    return metrics


def get_jvm_metrics(service):
    """Get JVM-specific metrics (for Java services like adservice)."""
    metrics = {}
    result = prom_query(
        f'sum(rate(jvm_gc_duration_seconds_sum{{service_name="{service}"}}[2m]))'
    )
    if result and "data" in result:
        for r in result["data"].get("result", []):
            metrics["gc_time_rate"] = float(r["value"][1])

    result = prom_query(
        f'sum(rate(jvm_gc_duration_seconds_count{{service_name="{service}"}}[2m]))'
    )
    if result and "data" in result:
        for r in result["data"].get("result", []):
            metrics["gc_count_rate"] = float(r["value"][1])
    return metrics


def analyze_fault(fault_name, fault_info, wait_seconds=90):
    """Full analysis of a single fault."""
    service = fault_info["service"]
    print(f"\n{'='*80}")
    print(f"  FAULT: {fault_name}")
    print(f"  Service: {service}")
    print(f"  Description: {fault_info['description']}")
    print(f"{'='*80}")

    # ── Phase 1: Baseline ──
    print("\n[1/5] Capturing baseline...")
    baseline_errors = get_error_rates()
    baseline_latency = get_latency_p99(service)
    baseline_request_rate = get_request_rate(service)
    baseline_pod = get_pod_status(fault_info["affected_pods"][0])
    baseline_error_spans = get_error_spans(service)
    baseline_logs = search_logs(service, severity="ERROR", minutes=2)
    baseline_kubectl_logs = get_container_logs(fault_info["affected_pods"][0], tail=5)

    # Extra baselines for specific faults
    baseline_jvm = {}
    baseline_kafka = {}
    if service == "adservice":
        baseline_jvm = get_jvm_metrics(service)
    if fault_name == "kafkaQueueProblems":
        baseline_kafka = get_kafka_metrics()

    print(f"  Error rate: {baseline_errors.get(service, 0):.4f}/s")
    print(
        f"  P99 latency: {baseline_latency}ms"
        if baseline_latency
        else "  P99 latency: N/A"
    )
    print(
        f"  Request rate: {baseline_request_rate:.2f}/s"
        if baseline_request_rate
        else "  Request rate: N/A"
    )
    print(f"  Error spans: {len(baseline_error_spans)}")
    print(f"  Error logs (OpenSearch): {len(baseline_logs)}")
    if baseline_jvm:
        print(f"  JVM GC rate: {baseline_jvm.get('gc_count_rate', 'N/A')}")
    if baseline_kafka:
        print(f"  Kafka metrics: {baseline_kafka}")

    # ── Phase 2: Inject Fault ──
    print(f"\n[2/5] Injecting fault: {fault_name} = {fault_info['enable_variant']}...")
    if not set_flag(fault_name, fault_info["enable_variant"]):
        print("  FAILED to inject fault, skipping")
        return None

    # flagd hot-reloads the ConfigMap, no restart needed
    # DO NOT restart affected pods — it resets Prometheus metric counters
    # and takes 2+ minutes for rate() to have enough data again
    time.sleep(5)  # give flagd time to detect ConfigMap change

    print(f"  Waiting {wait_seconds}s for fault to take effect...")
    # Wait in stages, checking periodically
    for i in range(0, wait_seconds, 15):
        time.sleep(15)
        current_errors = get_error_rates()
        svc_err = current_errors.get(service, 0)
        elapsed = i + 15
        print(
            f"    [{elapsed}s] {service} error rate: {svc_err:.4f}/s | total errors: {current_errors}"
        )

    # ── Phase 3: Probe All Backends ──
    print("\n[3/5] Probing observability backends...")

    # --- Prometheus ---
    print("\n  --- PROMETHEUS ---")
    fault_errors = get_error_rates()
    fault_error_spans = get_error_spans(service)
    fault_latency = get_latency_p99(service)
    fault_request_rate = get_request_rate(service)

    print(f"  Error rates (all services): {fault_errors}")
    print(
        f"  Service error rate: {fault_errors.get(service, 0):.4f}/s (baseline: {baseline_errors.get(service, 0):.4f}/s)"
    )
    print(
        f"  P99 latency: {fault_latency}ms (baseline: {baseline_latency}ms)"
        if fault_latency
        else "  P99 latency: N/A"
    )
    print(
        f"  Request rate: {fault_request_rate:.2f}/s (baseline: {baseline_request_rate:.2f}/s)"
        if fault_request_rate and baseline_request_rate
        else "  Request rate: N/A"
    )
    print("  Error spans:")
    for s in fault_error_spans[:10]:
        print(f"    {s['service']}/{s['span']}: {s['rate']:.4f}/s")

    # Extra Prometheus checks
    if service == "adservice":
        fault_jvm = get_jvm_metrics(service)
        print(
            f"  JVM GC rate: {fault_jvm.get('gc_count_rate', 'N/A')} (baseline: {baseline_jvm.get('gc_count_rate', 'N/A')})"
        )
        print(f"  JVM GC time rate: {fault_jvm.get('gc_time_rate', 'N/A')}")

    if fault_name == "kafkaQueueProblems":
        fault_kafka = get_kafka_metrics()
        print(f"  Kafka metrics: {fault_kafka} (baseline: {baseline_kafka})")

    # Check rpc_server duration for gRPC services
    rpc_result = prom_query(
        f'histogram_quantile(0.99, sum by (le, rpc_method)(rate(rpc_server_duration_milliseconds_bucket{{service_name="{service}"}}[2m])))'
    )
    if rpc_result and "data" in rpc_result:
        for r in rpc_result["data"].get("result", []):
            method = r["metric"].get("rpc_method", "?")
            val = float(r["value"][1])
            if val > 0:
                print(f"  RPC p99: {method} = {val:.1f}ms")

    # --- OpenSearch (Logs) ---
    print("\n  --- OPENSEARCH (LOGS) ---")
    fault_error_logs = search_logs(service, severity="ERROR", minutes=3)
    fault_warn_logs = search_logs(service, severity="WARN", minutes=3)
    fault_all_logs = search_logs(service, severity=None, minutes=3)

    print(f"  ERROR logs: {len(fault_error_logs)}")
    for log in fault_error_logs[:5]:
        print(f"    [{log['severity']}] {log['body'][:150]}")

    print(f"  WARN logs: {len(fault_warn_logs)}")
    for log in fault_warn_logs[:3]:
        print(f"    [{log['severity']}] {log['body'][:150]}")

    # Search for fault-specific keywords
    keywords = ["error", "fail", "exception", "timeout", "unavailable", "refused"]
    for kw in keywords:
        kw_logs = search_logs_keyword(kw, minutes=3)
        relevant = [
            l
            for l in kw_logs
            if service in l.get("service", "").lower()
            or service.replace("service", "") in l.get("body", "").lower()
        ]
        if relevant:
            print(f"  Keyword '{kw}': {len(relevant)} relevant logs")
            for log in relevant[:2]:
                print(f"    [{log['service']}] {log['body'][:150]}")

    # --- Jaeger (Traces) ---
    print("\n  --- JAEGER (TRACES) ---")
    jaeger_result = check_jaeger_errors(service, minutes=3)
    if jaeger_result.get("available"):
        print(f"  Total traces: {jaeger_result['total_traces']}")
        print(f"  Error spans: {len(jaeger_result['error_spans'])}")
        for es in jaeger_result["error_spans"][:5]:
            print(
                f"    {es['service']}/{es['operation']}: {es['duration_us']/1000:.1f}ms"
            )
    else:
        print(f"  Jaeger not available: {jaeger_result.get('error', 'unknown')}")

    # --- Kubernetes ---
    print("\n  --- KUBERNETES ---")
    for pod in fault_info["affected_pods"]:
        pod_status = get_pod_status(pod)
        print(f"  Pod status: {pod_status}")

        cpu = get_cpu_usage(pod)
        if cpu:
            print(f"  CPU usage: {cpu}")

        events = get_pod_events(pod)
        if events and events.strip():
            event_lines = [l for l in events.split("\n") if l.strip()][-5:]
            for e in event_lines:
                print(f"  Event: {e[:150]}")

    kubectl_logs = get_container_logs(fault_info["affected_pods"][0], tail=15)
    if kubectl_logs:
        print("  Recent logs (kubectl):")
        for line in kubectl_logs.split("\n")[-10:]:
            print(f"    {line[:150]}")

    # ── Phase 4: Disable Fault ──
    print(f"\n[4/5] Disabling fault: {fault_name}...")
    set_flag(fault_name, "off")
    time.sleep(5)  # flagd hot-reloads

    # ── Phase 5: Summary ──
    print(f"\n[5/5] DETECTION SUMMARY for {fault_name}")
    print(f"  {'─'*60}")

    detectable = []
    not_detectable = []

    # Check Prometheus
    svc_err_rate = fault_errors.get(service, 0)
    baseline_err = baseline_errors.get(service, 0)
    if svc_err_rate > baseline_err + 0.001:
        detectable.append(
            f"Prometheus: error rate {baseline_err:.4f} → {svc_err_rate:.4f}/s"
        )
    else:
        not_detectable.append(
            f"Prometheus: no error rate change ({svc_err_rate:.4f}/s)"
        )

    if fault_error_spans:
        detectable.append(f"Prometheus: {len(fault_error_spans)} error spans detected")

    if fault_latency and baseline_latency and fault_latency > baseline_latency * 1.5:
        detectable.append(
            f"Prometheus: latency spike {baseline_latency:.0f} → {fault_latency:.0f}ms"
        )

    # Check logs
    if len(fault_error_logs) > len(baseline_logs):
        detectable.append(
            f"OpenSearch: {len(fault_error_logs)} ERROR logs (baseline: {len(baseline_logs)})"
        )
    else:
        not_detectable.append("OpenSearch: no new ERROR logs")

    # Check Jaeger
    if jaeger_result.get("available") and jaeger_result.get("error_spans"):
        detectable.append(
            f"Jaeger: {len(jaeger_result['error_spans'])} error spans in traces"
        )
    elif not jaeger_result.get("available"):
        not_detectable.append("Jaeger: not available")
    else:
        not_detectable.append("Jaeger: no error traces found")

    # Check K8s
    for pod in fault_info["affected_pods"]:
        status = get_pod_status(pod)
        if status and (
            "CrashLoopBackOff" in status or "Error" in status or "OOMKilled" in status
        ):
            detectable.append(f"Kubernetes: pod {pod} in bad state")

    print(f"\n  ✅ DETECTABLE ({len(detectable)}):")
    for d in detectable:
        print(f"    • {d}")

    print(f"\n  ❌ NOT DETECTABLE ({len(not_detectable)}):")
    for n in not_detectable:
        print(f"    • {n}")

    return {
        "fault": fault_name,
        "service": service,
        "detectable": detectable,
        "not_detectable": not_detectable,
        "baseline_error_rate": baseline_errors.get(service, 0),
        "fault_error_rate": svc_err_rate,
        "baseline_latency": baseline_latency,
        "fault_latency": fault_latency,
        "error_spans": [s["span"] for s in fault_error_spans],
        "error_logs": len(fault_error_logs),
        "jaeger_available": jaeger_result.get("available", False),
    }


def main():

    parser = argparse.ArgumentParser(description="Fault analysis for OTel Demo")
    parser.add_argument("--fault", help="Specific fault to test")
    parser.add_argument("--all", action="store_true", help="Test all faults")
    parser.add_argument(
        "--wait",
        type=int,
        default=90,
        help="Seconds to wait after injection (default: 90)",
    )
    parser.add_argument("--list", action="store_true", help="List available faults")
    args = parser.parse_args()

    if args.list:
        print("Available faults:")
        for name, info in FAULTS.items():
            print(f"  {name}: {info['description']} ({info['service']})")
        return

    if not args.fault and not args.all:
        parser.print_help()
        return

    # Check connectivity
    print("Checking observability backends...")
    prom_ok = bool(http_get(f"{PROM_URL}/api/v1/status/config"))
    os_ok = bool(http_get(f"{OPENSEARCH_URL}/_cat/health"))
    jaeger_ok = bool(http_get(f"{JAEGER_URL}/api/services"))
    print(f"  Prometheus: {'✅' if prom_ok else '❌'}")
    print(f"  OpenSearch: {'✅' if os_ok else '❌'}")
    print(f"  Jaeger:     {'✅' if jaeger_ok else '❌'}")

    faults_to_test = list(FAULTS.keys()) if args.all else [args.fault]
    results = []

    for fault_name in faults_to_test:
        if fault_name not in FAULTS:
            print(f"Unknown fault: {fault_name}")
            continue
        result = analyze_fault(fault_name, FAULTS[fault_name], wait_seconds=args.wait)
        if result:
            results.append(result)
        # Wait between faults for metrics to settle
        if len(faults_to_test) > 1:
            print("\n⏳ Waiting 30s between faults for metrics to settle...")
            time.sleep(30)

    # ── Final Report ──
    if results:
        print(f"\n\n{'='*80}")
        print("  FINAL REPORT: Fault Detection Matrix")
        print(f"{'='*80}\n")

        for r in results:
            det = len(r["detectable"])
            tot = det + len(r["not_detectable"])
            status = "🟢" if det >= 2 else "🟡" if det >= 1 else "🔴"
            print(
                f"{status} {r['fault']} ({r['service']}): {det}/{tot} detection methods"
            )
            for d in r["detectable"]:
                print(f"   ✅ {d}")
            for n in r["not_detectable"]:
                print(f"   ❌ {n}")
            print()


if __name__ == "__main__":
    import urllib.parse

    main()
