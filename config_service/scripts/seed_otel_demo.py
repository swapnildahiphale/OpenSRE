#!/usr/bin/env python3
"""
Seed the OTel Demo configuration for AI SRE incident triage.

This updates:
1. 'default' team config under 'local' org
2. Team configuration with:
   - OTel Demo service catalog (25 microservices)
   - Service dependency map
   - Detection PromQL queries
   - Custom planner prompt for SRE incident triage
3. Output configuration pointing to the Slack channel

Usage:
    cd config_service
    poetry run python scripts/seed_otel_demo.py

Environment variables:
    OTEL_DEMO_SLACK_CHANNEL_ID: Slack channel ID (default from env)
    OTEL_DEMO_SLACK_CHANNEL_NAME: Slack channel name
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import os
import uuid

from sqlalchemy import select
from src.core.dotenv import load_dotenv
from src.db.config_models import NodeConfiguration
from src.db.models import (
    NodeType,
    OrgNode,
    TeamOutputConfig,
)
from src.db.session import db_session

# Configuration
ORG_ID = "local"
TEAM_NODE_ID = "default"
TEAM_NAME = "Default"

# ---------------------------------------------------------------------------
# Service catalog
# ---------------------------------------------------------------------------
SERVICES = {
    "frontend": {
        "language": "TypeScript/Next.js",
        "type": "web-ui",
        "port": 8080,
        "dependencies": [
            "product-catalog",
            "cart",
            "checkout",
            "recommendation",
            "ad",
            "currency",
            "image-provider",
            "product-reviews",
        ],
        "description": "Main web storefront. Renders product pages, cart, and checkout.",
    },
    "frontend-proxy": {
        "language": "Envoy",
        "type": "proxy",
        "port": 8080,
        "dependencies": ["frontend", "grafana", "jaeger"],
        "description": "Envoy reverse proxy for all inbound traffic.",
    },
    "checkout": {
        "language": "Go",
        "type": "backend",
        "port": 8080,
        "dependencies": [
            "cart",
            "payment",
            "shipping",
            "currency",
            "email",
            "product-catalog",
            "kafka",
        ],
        "description": "Orchestrates the checkout flow: validates cart, charges payment, ships order, sends confirmation email, publishes to Kafka.",
    },
    "payment": {
        "language": "Node.js",
        "type": "backend",
        "port": 8080,
        "dependencies": [],
        "description": "Processes credit card charges.",
    },
    "cart": {
        "language": "C# (.NET)",
        "type": "backend",
        "port": 8080,
        "dependencies": ["valkey"],
        "description": "Shopping cart backed by Valkey (Redis). Stores cart items per user.",
    },
    "product-catalog": {
        "language": "Go",
        "type": "backend",
        "port": 8080,
        "dependencies": [],
        "description": "Lists and searches 12 products. Used by frontend, checkout, recommendation.",
    },
    "recommendation": {
        "language": "Python",
        "type": "backend",
        "port": 8080,
        "dependencies": ["product-catalog"],
        "description": "Suggests related products. Has an in-memory cache layer.",
    },
    "shipping": {
        "language": "Rust",
        "type": "backend",
        "port": 8080,
        "dependencies": ["quote"],
        "description": "Calculates shipping quotes and creates shipments.",
    },
    "quote": {
        "language": "PHP",
        "type": "backend",
        "port": 8080,
        "dependencies": [],
        "description": "Calculates shipping cost based on item count.",
    },
    "email": {
        "language": "Ruby",
        "type": "backend",
        "port": 8080,
        "dependencies": [],
        "description": "Sends order confirmation emails.",
    },
    "currency": {
        "language": "C++",
        "type": "backend",
        "port": 8080,
        "dependencies": [],
        "description": "Converts prices between currencies.",
    },
    "ad": {
        "language": "Java",
        "type": "backend",
        "port": 8080,
        "dependencies": [],
        "description": "Returns contextual ads.",
    },
    "image-provider": {
        "language": "Nginx",
        "type": "static",
        "port": 8080,
        "dependencies": [],
        "description": "Serves product images.",
    },
    "product-reviews": {
        "language": "Go",
        "type": "backend",
        "port": 8080,
        "dependencies": [],
        "description": "Customer reviews with AI summarization.",
    },
    "accounting": {
        "language": "C# (.NET)",
        "type": "async-processor",
        "port": 8080,
        "dependencies": ["kafka", "postgres"],
        "description": "Consumes order events from Kafka, records transactions in PostgreSQL.",
    },
    "fraud-detection": {
        "language": "Kotlin",
        "type": "async-processor",
        "port": 8080,
        "dependencies": ["kafka"],
        "description": "Consumes order events from Kafka, checks for fraudulent transactions.",
    },
    "load-generator": {
        "language": "Python/Playwright",
        "type": "synthetic",
        "port": None,
        "dependencies": ["frontend"],
        "description": "Generates synthetic user traffic.",
    },
    "kafka": {
        "language": "Apache Kafka",
        "type": "infrastructure",
        "port": 9092,
        "dependencies": [],
        "description": "Message broker for async order processing. Checkout publishes, accounting and fraud-detection consume.",
    },
    "valkey": {
        "language": "Valkey (Redis fork)",
        "type": "infrastructure",
        "port": 6379,
        "dependencies": [],
        "description": "In-memory cache for shopping cart data.",
    },
    "postgres": {
        "language": "PostgreSQL",
        "type": "infrastructure",
        "port": 5432,
        "dependencies": [],
        "description": "Relational database for accounting records.",
    },
    "otel-collector": {
        "language": "OpenTelemetry Collector",
        "type": "observability",
        "port": 4317,
        "dependencies": [],
        "description": "Collects traces, metrics, and logs from all services via OTLP. Exports to Jaeger, Prometheus, and OpenSearch.",
    },
    "prometheus": {
        "language": "Prometheus",
        "type": "observability",
        "port": 9090,
        "dependencies": ["otel-collector"],
        "description": "Time-series metrics storage. Query via PromQL.",
    },
    "jaeger": {
        "language": "Jaeger",
        "type": "observability",
        "port": 16686,
        "dependencies": ["otel-collector"],
        "description": "Distributed tracing backend and UI.",
    },
    "grafana": {
        "language": "Grafana",
        "type": "observability",
        "port": 3000,
        "dependencies": ["prometheus", "jaeger"],
        "description": "Dashboards and visualization for metrics and traces.",
    },
}

# ---------------------------------------------------------------------------
# Service dependency chains (business flows)
# ---------------------------------------------------------------------------
DEPENDENCY_CHAINS = {
    "checkout_flow": {
        "description": "Main business-critical path: user places an order",
        "chain": [
            "Frontend → Checkout Service orchestrates:",
            "  1. GetCart() → Cart → Valkey",
            "  2. GetProducts() → Product Catalog",
            "  3. ConvertCurrency() → Currency Service",
            "  4. GetShippingQuote() → Shipping → Quote Service",
            "  5. ChargeCard() → Payment",
            "  6. ShipOrder() → Shipping",
            "  7. SendConfirmation() → Email",
            "  8. EmptyCart() → Cart",
            "  9. PublishOrder() → Kafka → Accounting + Fraud Detection",
        ],
    },
    "product_browse_flow": {
        "description": "User browses products and sees recommendations",
        "chain": [
            "Frontend → Product Catalog (list/search products)",
            "Frontend → Recommendation (suggested products) → Product Catalog",
            "Frontend → Ad Service (contextual ads)",
            "Frontend → Image Provider (product images)",
            "Frontend → Product Reviews (customer reviews + AI summaries)",
        ],
    },
    "async_processing_flow": {
        "description": "Asynchronous order processing after checkout",
        "chain": [
            "Checkout → Kafka (publish order event)",
            "Kafka → Accounting (record transaction → PostgreSQL)",
            "Kafka → Fraud Detection (analyze for fraud)",
        ],
    },
}

# ---------------------------------------------------------------------------
# Failure impact map
# ---------------------------------------------------------------------------
FAILURE_IMPACT = {
    "payment": "Checkout fails entirely — no orders created, no emails, no accounting records.",
    "product-catalog": "Complete site outage — affects frontend, recommendations, checkout.",
    "cart": "Cannot add items or view cart. Checkout blocked.",
    "kafka": "Orders process but accounting and fraud detection stop (async, checkout still works).",
    "recommendation": "Product pages load slower, no suggestions shown.",
    "email": "Orders succeed but no confirmation emails sent. Memory leak causes eventual OOM.",
    "ad": "No ads displayed. High CPU may cause cascading latency.",
    "image-provider": "Product images load very slowly (5-10s) or timeout.",
}

# ---------------------------------------------------------------------------
# Observability endpoints
# ---------------------------------------------------------------------------
ENVIRONMENT_MANIFEST = {
    "metrics": {
        "backend": "prometheus",
        "naming_convention": "opentelemetry",
        "key_metrics": {
            "request_rate": "calls_total",
            "error_rate": 'calls_total{status_code="STATUS_CODE_ERROR"}',
            "latency_histogram": "duration_milliseconds_bucket",
            "latency_p99": 'histogram_quantile(0.99, rate(duration_milliseconds_bucket{service_name="SERVICE"}[5m]))',
        },
        "label_conventions": {
            "service": "service_name",
            "operation": "span_name",
            "status": "status_code",
            "error_value": "STATUS_CODE_ERROR",
            "ok_value": "STATUS_CODE_OK",
        },
        "service_name_format": "{service}service",
        "notes": "OTel Demo uses 'calls_total' not 'http_requests_total'. Labels use service_name not service. Status codes are STATUS_CODE_OK/STATUS_CODE_ERROR not HTTP codes.",
    },
    "logs": {
        "backend": "opensearch",
        "index_pattern": "otel",
        "field_mapping": {
            "timestamp": "@timestamp",
            "level": "SeverityText",
            "message": "Body",
            "service": "ServiceName",
            "trace_id": "TraceId",
            "span_id": "SpanId",
        },
        "notes": "Single 'otel' index, NOT logs-*. Use SeverityText (not 'level'). Use Body (not 'message'). Do NOT use Loki — this environment uses OpenSearch.",
    },
    "traces": {
        "backend": "jaeger",
        "service_name_format": "{service}service",
        "notes": "Jaeger service names match the OTel service.name attribute (e.g., 'cartservice', 'paymentservice'). These do NOT have 'otel-demo-' prefix.",
    },
    "kubernetes": {
        "namespace": "otel-demo",
        "notes": "All pods in otel-demo namespace. Deployments prefixed with 'otel-demo-'.",
    },
}

# ---------------------------------------------------------------------------
# Observability endpoints
# ---------------------------------------------------------------------------
OBSERVABILITY = {
    "prometheus": {
        "url": "http://otel-demo-prometheus-server:9090",
        "usage": "Time-series metrics. PromQL queries for error rates, latency, resource usage. Primary detection backend.",
    },
    "opensearch": {
        "url": "http://otel-demo-opensearch:9200",
        "index": "otel",
        "usage": "Log analysis. Search service logs for errors, exceptions, and patterns. Use Lucene query syntax.",
    },
    "jaeger": {
        "url": "http://otel-demo-jaeger-query:16686",
        "usage": "Distributed tracing. Trace request flows across services, find slow spans, correlate errors.",
    },
    "grafana": {
        "url": "http://otel-demo-grafana:80",
        "usage": "Dashboards for metrics visualization. Access via Grafana API.",
    },
    "kubernetes": {
        "cluster": "opensre-demo",
        "namespace": "otel-demo",
        "usage": "Pod status, events, logs, deployments. Use K8s skills for debugging.",
    },
}


# ---------------------------------------------------------------------------
# Build business context for system prompt
# ---------------------------------------------------------------------------
def _build_business_context() -> str:
    lines = []

    # Service catalog
    lines.append("## Service Catalog\n")
    lines.append("| Service | Language | Type | Dependencies |")
    lines.append("|---------|----------|------|--------------|")
    for name, info in SERVICES.items():
        if info["type"] in ("observability", "infrastructure"):
            continue
        deps = ", ".join(info["dependencies"]) if info["dependencies"] else "none"
        lines.append(f"| {name} | {info['language']} | {info['type']} | {deps} |")

    # Dependency chains
    lines.append("\n## Critical Business Flows\n")
    for flow_id, flow in DEPENDENCY_CHAINS.items():
        lines.append(f"### {flow['description']}")
        lines.append("```")
        for step in flow["chain"]:
            lines.append(step)
        lines.append("```\n")

    # Failure impact
    lines.append("## Failure Impact Map\n")
    lines.append("| Service Down | Business Impact |")
    lines.append("|-------------|----------------|")
    for svc, impact in FAILURE_IMPACT.items():
        lines.append(f"| {svc} | {impact} |")

    # Observability endpoints
    lines.append("\n## Observability Endpoints\n")
    for name, info in OBSERVABILITY.items():
        url = info.get("url", info.get("repo", ""))
        lines.append(f"- **{name}**: {url}")
        lines.append(f"  {info['usage']}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# System prompt for OTel Demo SRE planner
# ---------------------------------------------------------------------------
PLANNER_PROMPT = """You are an expert SRE investigator for the OpenTelemetry Demo — a microservices e-commerce application running on Kubernetes.

## YOUR ENVIRONMENT

You are investigating incidents in a distributed system with 25 microservices written in 8 languages (Go, Node.js, Python, Java, .NET, Rust, PHP, Ruby). All services emit OpenTelemetry traces, metrics, and logs to a central collector.

**Kubernetes cluster**: opensre-demo, namespace: otel-demo
**Observability**: Prometheus (metrics), OpenSearch (logs), Jaeger (traces), Grafana (dashboards)

## INCIDENT INVESTIGATION METHODOLOGY

### Phase 1: Scope the Problem
- What symptoms are reported? (errors, latency, downtime)
- What services are likely affected? (check the dependency map below)
- When did it start?

### Phase 2: Gather Evidence (Statistics First)
1. **Check metrics** — Query Prometheus for error rates (`calls_total{status_code="STATUS_CODE_ERROR"}`), latency (`duration_milliseconds`), resource usage
2. **Check logs** — Query OpenSearch (`otel` index) for service errors and exceptions
3. **Check traces** — Query Jaeger for request flows and error spans
4. **Check K8s** — Pod status, events, restarts

### Phase 3: Correlate & Diagnose
- Cross-reference metrics, logs, and traces
- Follow the dependency chain to find root cause

### Phase 4: Remediate
- If the root cause is a pod crash: use remediation scripts to restart
- If the root cause is resource exhaustion: scale the deployment
- Always verify the fix resolved the issue

## TOOLS AT YOUR DISPOSAL

- **Prometheus**: PromQL metrics queries (error rates, latency, CPU, memory, GC)
- **OpenSearch**: Log queries via Lucene syntax (index: otel)
- **Jaeger**: Distributed trace analysis
- **Grafana**: Dashboard visualization
- **Kubernetes**: Pod listing, events, logs, deployment status, resource usage
- **Remediation**: Pod restart, deployment scaling, rollback

"""


# ---------------------------------------------------------------------------
# Per-agent investigation prompts (injected via {custom_prompt} slot)
# ---------------------------------------------------------------------------
KUBERNETES_AGENT_PROMPT = """\
You are the Kubernetes infrastructure investigator.

## Your Domain
Infrastructure health: pod state, cluster events, resource pressure,
container lifecycle.

## What to Investigate (in priority order)

1. **Pod health sweep** — check ALL pods in the namespace, not just the
   target service. Look for: not-ready, crash loops, restarts, OOMKilled,
   pending state.

2. **Recent events** — events explain 80% of K8s issues faster than logs.
   Look for: scheduling failures, image pull errors, probe failures,
   resource quota exceeded, evictions.

3. **Resource pressure** — check CPU and memory usage across pods. Compare
   current usage against limits. A pod near its memory limit is about to
   be killed even if it looks healthy now.

4. **Application logs for the target service** — search for error, exception,
   timeout, refused, OOM patterns. If the pod has restarted, always check the
   PREVIOUS container's logs — that's where the crash reason lives.

5. **Dependent service pods** — check pods for upstream AND downstream services
   from the topology, not just the target.

## Key Patterns
- Pod running + restarts > 0 → intermittent crashes, check previous container
- Pod running + 0 errors but dependents failing → network/DNS issue or
  silent error returns
- Multiple pods unhealthy → likely node-level or cluster-level problem
- Events showing probe failures → service is up but not responding correctly

## Early Exit
If all pods are healthy, no restarts, no events, and no error patterns in
logs — report "no K8s infrastructure issues found" and stop.

## Skills
Load the `infrastructure-kubernetes` skill to learn available investigation
methods."""

METRICS_AGENT_PROMPT = """\
You are the metrics investigator.

## Your Domain
Time-series metrics: error rates, latency distributions, resource
utilization, and service-specific metrics.

## What to Investigate (in priority order)

1. **Error rates on the target service** — look for error-indicating metrics.
   Check if errors are increasing, stable, or zero.

2. **Error rates on DOWNSTREAM services** — always check the target's
   callers and dependencies too. If the target shows zero errors but its
   callers show errors, the target may be unreachable or silently failing.

3. **Error breakdown by operation** — if errors exist, break down by
   operation/span/endpoint name to isolate WHICH operation is failing.

4. **Latency percentiles (p99, p95, p50)** — many faults (cache failures,
   slow dependencies, CPU pressure, traffic floods) produce latency changes
   with ZERO errors. If you only check error rates, you will miss these.

5. **Resource and runtime metrics** — check for CPU utilization, memory
   pressure, GC activity, thread pool saturation. Note: resource metrics
   may use different label schemas than request metrics — consult the
   knowledge base or discover labels via the skill.

6. **Service-specific metrics** — some services expose custom counters
   or gauges. These often reveal problems that generic request metrics miss.

7. **Request rate changes** — a sudden rate spike = traffic flood.
   A sudden rate drop = service unreachable or upstream stopped calling.

## Interpreting Zeros
- Zero errors + normal latency + normal traffic = genuinely healthy
- Zero errors + high latency = performance degradation
- Zero errors + zero traffic = service may be unreachable
- Zero everything = check if metrics exist for this service at all

## Early Exit
If the target service and its neighbors show no error rate changes, no
latency changes, and no resource anomalies — report "no metric anomalies
found" and stop.

## Skills
Load the `metrics-analysis` skill to learn query syntax and available
scripts. Use metric discovery queries to find what metrics exist before
assuming metric names."""

LOG_ANALYSIS_AGENT_PROMPT = """\
You are the log analysis investigator.

## Your Domain
Application logs from centralized log storage and direct container output.
You search for error messages, exception stack traces, and diagnostic patterns.

## What to Investigate (in priority order)

1. **Centralized log search for the target service** — search the log
   backend filtering by ERROR severity first. If no results, broaden to
   WARN severity — many services log actionable errors at WARN, not ERROR.

2. **Centralized log search for related services** — also search logs for
   upstream callers and downstream dependencies. Connection errors and
   timeouts often appear in the CALLER's logs, not the failing service's.

3. **Keyword-based search** — if severity-based search returns nothing,
   search log bodies for diagnostic keywords: error, exception, fail,
   timeout, refused, OOM, crash, panic, fatal.

4. **Direct container logs** — if centralized logging has gaps, fall back
   to reading container logs directly with keyword filtering.

5. **Structured log parsing** — some services use structured/JSON logging
   with numeric severity levels. Log level conventions vary by language.

6. **Previous container logs** — if a pod has restarted, the crash cause
   is in the PREVIOUS container's logs.

## What Absence Means
If a service produces no error-level logs during a known incident, that
IS a finding. It means the service doesn't log errors, catches exceptions
silently, or the log pipeline is broken. Report it.

## Early Exit
If no error or warning logs exist for the target service or its neighbors,
and keyword search also returns nothing — report "no relevant logs found"
and stop.

## Skills
Load the `observability-elasticsearch` skill (or appropriate log backend
skill) to learn query syntax and available scripts."""

TRACES_AGENT_PROMPT = """\
You are the distributed trace investigator.

## Your Domain
Distributed traces showing request flows across services. You follow
individual requests to find where failures and latency originate.

## What to Investigate (in priority order)

1. **Check trace availability** — verify the tracing backend has data for
   the target service. If no traces exist, that IS a finding — report it
   and stop.

2. **Error traces** — search for traces with error status on the target
   service. Identify which operation failed, the error message, and whether
   the error originated here or was propagated from a dependency.

3. **Slow traces** — search for traces sorted by duration. Latency faults
   appear as abnormally long spans.

4. **Cross-service error propagation** — when you find an error trace,
   follow it end-to-end. The span that ORIGINATES the error is the root
   cause — errors on upstream services are usually consequences.

5. **Operation-level analysis** — filter by specific operation to isolate
   which RPC method or route is affected.

6. **Healthy vs unhealthy comparison** — compare a successful trace and
   a failing trace for the same operation to localize the problem.

## Key Principle
Traces show causality that metrics cannot. Metrics say "service X has
errors." Traces say "service X has errors BECAUSE service Y returned a
timeout on the GetProduct call."

## Early Exit
If the tracing backend has no data for the target service or its neighbors,
report "no traces available" and stop.

## Skills
Load the `observability-jaeger` skill (or appropriate tracing backend
skill) to learn query methods and available scripts."""


def main() -> None:
    load_dotenv()

    slack_channel_id = os.getenv("OTEL_DEMO_SLACK_CHANNEL_ID", "C0A4967KRBM")
    slack_channel_name = os.getenv("OTEL_DEMO_SLACK_CHANNEL_NAME", "#otel-demo")

    print("Seeding OTel Demo config into local/default team...")
    print(f"  Organization: {ORG_ID}")
    print(f"  Team: {TEAM_NODE_ID}")
    print(f"  Slack channel: {slack_channel_id} ({slack_channel_name})")

    with db_session() as s:
        # 1. Check that local org exists (node_id is 'root' for the org node)
        org = s.execute(
            select(OrgNode).where(
                OrgNode.org_id == ORG_ID,
                OrgNode.node_type == NodeType.org,
            )
        ).scalar_one_or_none()

        if org is None:
            print(f"  ERROR: Organization '{ORG_ID}' not found!")
            print("  Please create the organization first or use a different org_id.")
            sys.exit(1)
        else:
            print(f"  Found organization: {org.name}")

        # 2. Verify default team node exists
        team = s.execute(
            select(OrgNode).where(
                OrgNode.org_id == ORG_ID,
                OrgNode.node_id == TEAM_NODE_ID,
            )
        ).scalar_one_or_none()

        if team is None:
            print(f"  ERROR: Team '{TEAM_NODE_ID}' not found under org '{ORG_ID}'!")
            print("  Please create the team first.")
            sys.exit(1)
        else:
            print(f"  Found team: {team.name}")

        s.flush()

        # 3. Build business context
        business_context = _build_business_context()
        full_prompt = PLANNER_PROMPT + "\n" + business_context

        config_json = {
            "team_name": TEAM_NAME,
            "description": "AI SRE for OpenTelemetry Demo — incident triage, diagnosis, and remediation",
            "routing": {
                "slack_channel_ids": [slack_channel_id],
                "github_repos": [],
                "pagerduty_service_ids": [],
                "services": list(SERVICES.keys()),
            },
            "business_context": business_context,
            "service_catalog": SERVICES,
            "dependency_chains": DEPENDENCY_CHAINS,
            "failure_impact": FAILURE_IMPACT,
            "observability": OBSERVABILITY,
            "environment_manifest": ENVIRONMENT_MANIFEST,
            "agents": {
                "planner": {
                    "enabled": True,
                    "model": {"name": "gpt-5.2", "temperature": 0.3},
                    "prompt": {
                        "system": full_prompt,
                        "prefix": "",
                        "suffix": "",
                    },
                },
                "investigation": {
                    "sub_agents": {
                        "kubernetes": True,
                        "metrics": True,
                        "log_analysis": True,
                        "traces": True,
                    },
                    "sub_agents_config": {
                        "kubernetes": {
                            "prompt": {"system": KUBERNETES_AGENT_PROMPT},
                        },
                        "metrics": {
                            "prompt": {"system": METRICS_AGENT_PROMPT},
                        },
                        "log_analysis": {
                            "prompt": {"system": LOG_ANALYSIS_AGENT_PROMPT},
                        },
                        "traces": {
                            "prompt": {"system": TRACES_AGENT_PROMPT},
                        },
                    },
                },
            },
        }

        # 4. Create/update team configuration
        team_cfg = s.execute(
            select(NodeConfiguration).where(
                NodeConfiguration.org_id == ORG_ID,
                NodeConfiguration.node_id == TEAM_NODE_ID,
            )
        ).scalar_one_or_none()

        if team_cfg is None:
            print("  Creating team configuration...")
            s.add(
                NodeConfiguration(
                    id=f"cfg-{uuid.uuid4().hex[:12]}",
                    org_id=ORG_ID,
                    node_id=TEAM_NODE_ID,
                    node_type="team",
                    config_json=config_json,
                    updated_by="seed_otel_demo",
                )
            )
        else:
            print("  Updating existing team configuration...")
            team_cfg.config_json = config_json
            team_cfg.updated_by = "seed_otel_demo"

        # 5. Create/update output configuration
        output_cfg = s.execute(
            select(TeamOutputConfig).where(
                TeamOutputConfig.org_id == ORG_ID,
                TeamOutputConfig.team_node_id == TEAM_NODE_ID,
            )
        ).scalar_one_or_none()

        if output_cfg is None:
            print("  Creating output configuration...")
            s.add(
                TeamOutputConfig(
                    org_id=ORG_ID,
                    team_node_id=TEAM_NODE_ID,
                    default_destinations=[
                        {
                            "type": "slack",
                            "channel_id": slack_channel_id,
                            "channel_name": slack_channel_name,
                        }
                    ],
                    trigger_overrides={
                        "slack": "reply_in_thread",
                        "api": "use_default",
                    },
                )
            )
        else:
            print("  Updating existing output configuration...")
            output_cfg.default_destinations = [
                {
                    "type": "slack",
                    "channel_id": slack_channel_id,
                    "channel_name": slack_channel_name,
                }
            ]

        s.commit()

    print("\nOTel Demo SRE seeding complete!")
    print("\n" + "=" * 70)
    print("DEMO SETUP SUMMARY")
    print("=" * 70)
    print(f"\nSlack Channel: {slack_channel_id} ({slack_channel_name})")
    print(f"\nServices: {len(SERVICES)} total")
    app_services = [
        k
        for k, v in SERVICES.items()
        if v["type"] not in ("observability", "infrastructure")
    ]
    print(f"  Application services: {len(app_services)}")
    print(f"  Infrastructure: {len(SERVICES) - len(app_services)}")
    print("\nObservability:")
    for name, info in OBSERVABILITY.items():
        print(f"  - {name}: {info.get('url', info.get('repo', ''))}")
    print("\n" + "=" * 70)
    print("\nNext steps:")
    print("  1. Route the #otel-demo Slack channel to this team")
    print(
        "  3. Configure integrations (Prometheus, OpenSearch, Jaeger, Grafana, K8s) in the admin UI"
    )
    print("  4. Test with: '@bot investigate payment service errors'")
    print("  5. Trigger an incident: trigger-incident.sh service-failure")


if __name__ == "__main__":
    main()
