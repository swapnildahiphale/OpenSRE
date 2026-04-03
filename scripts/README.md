# OpenSRE E2E Test Scripts

Automated end-to-end testing for OpenSRE.

## Quick Start

```bash
# Quick health check (no secrets needed)
./health_check.sh

# Run all E2E tests
./e2e_test_all.sh

# Run specific tests
./e2e_test_all.sh slack           # Slack integration only
./e2e_test_all.sh otel cart       # Cart service fault only
./e2e_test_all.sh otel all        # All fault injection tests
```

## Scripts

### `health_check.sh`
Fast infrastructure validation without secrets.
- ✅ Kubernetes connectivity
- ✅ Pod status (agent, config-service, orchestrator, web-ui)
- ✅ Service existence
- ✅ Ingress and ALB provisioning
- ✅ External secrets sync
- ✅ HTTPS endpoints
- ✅ otel-demo availability

### `e2e_test_slack.py`
Full Slack integration test:
1. Posts a test message to Slack channel
2. Waits for agent response
3. Validates response in thread
4. Checks server-side logs

**Requirements:**
- `SLACK_BOT_TOKEN` in AWS Secrets Manager (`opensre/prod/slack_bot_token`)
- Slack channel ID configured

### `e2e_test_otel_demo.py`
Fault injection testing:
1. Injects a fault via flagd
2. Triggers agent investigation
3. Validates agent diagnosis
4. Clears the fault

**Available faults:**
- `cart` - Cart service failure
- `product` - Product catalog failure
- `recommendation` - Recommendation service failure
- `ad` - Ad service high CPU load

### `e2e_test_all.sh`
Master test runner combining all tests.

### `fault_analysis.py`
Comprehensive fault analysis for the otel-demo stack on EKS. For each flagd fault, it:
1. Checks connectivity to Prometheus, OpenSearch, and Jaeger
2. Injects the fault via kubectl ConfigMap patch
3. Waits for symptoms to appear (configurable via `--wait`, default 90s)
4. Queries all observability backends for detectable signals
5. Produces a detection matrix showing which backends caught the fault

```bash
# List available faults
python3 scripts/fault_analysis.py --list

# Analyze a single fault
python3 scripts/fault_analysis.py --fault cart

# Analyze all faults sequentially (waits 30s between each)
python3 scripts/fault_analysis.py --all

# Custom wait time (seconds after injection before probing)
python3 scripts/fault_analysis.py --fault product --wait 120
```

**Requirements:** kubectl access to otel-demo namespace, port-forwards active for Prometheus (9090), OpenSearch (9200), Jaeger (16686).

### `populate_neo4j.py`
Populates the Neo4j knowledge graph with the otel-demo Kubernetes cluster topology and service dependency graph. Reads Cypher statements from `scripts/populate_neo4j.cypher` and executes them against the configured Neo4j instance.

```bash
# Uses local Neo4j by default (bolt://localhost:7688)
python3 scripts/populate_neo4j.py

# Override connection via env vars
NEO4J_URI=bolt://localhost:7688 NEO4J_USERNAME=neo4j NEO4J_PASSWORD=localdev \
  python3 scripts/populate_neo4j.py
```

After loading, runs a quick verification query and prints a sample blast radius for `cartservice`. Used to seed the knowledge graph that OpenSRE's agents use for topology-aware investigations.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_PROFILE` | `playground` | AWS profile for secrets |
| `AWS_REGION` | `us-west-2` | AWS region |
| `SLACK_CHANNEL_ID` | `C0A43KYJE03` | Slack channel for testing |
| `AGENT_NAMESPACE` | `opensre` | K8s namespace for OpenSRE |
| `OTEL_NAMESPACE` | `otel-demo` | K8s namespace for otel-demo |
| `WEB_UI_URL` | `https://ui.opensre.ai` | Web UI base URL |

## CI/CD Integration

Add to GitHub Actions:

```yaml
- name: Run E2E Tests
  run: |
    aws eks update-kubeconfig --name opensre-demo --region us-west-2
    ./scripts/health_check.sh
    ./scripts/e2e_test_all.sh
```

