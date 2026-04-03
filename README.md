<h1 align="center">OpenSRE</h1>

<p align="center">
  <b>Your AI SRE that investigates production incidents</b><br>
  <sub>Long-term memory · Knowledge graph · 46 production skills</sub>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="Apache 2.0 License" /></a>
  <a href="https://github.com/swapnildahiphale/OpenSRE/stargazers"><img src="https://img.shields.io/github/stars/swapnildahiphale/OpenSRE?style=social" alt="GitHub Stars" /></a>
  <a href="https://github.com/swapnildahiphale/OpenSRE/network/members"><img src="https://img.shields.io/github/forks/swapnildahiphale/OpenSRE?style=social" alt="GitHub Forks" /></a>
  <a href="https://github.com/swapnildahiphale/OpenSRE/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome" /></a>
  <a href="https://www.opensre.in/docs"><img src="https://img.shields.io/badge/docs-opensre.in-green.svg" alt="Documentation" /></a>
  <a href="https://www.opensre.in"><img src="https://img.shields.io/badge/website-opensre.in-green.svg" alt="Website" /></a>
</p>

<p align="center">
  <a href="https://g1ctb3hnwvhw6s5v.public.blob.vercel-storage.com/how-it-works.mp4">
    <img src=".github/assets/hero-thumbnail.webp" alt="OpenSRE — How it works" width="720" />
  </a>
  <br>
  <sub>Click to watch OpenSRE investigate an incident in 60 seconds</sub>
</p>

<h4 align="center">
  <a href="https://www.opensre.in">Website</a> ·
  <a href="https://www.opensre.in/docs">Docs</a> ·
  <a href="https://demo.opensre.in">Live Demo</a> ·
  <a href="CONTRIBUTING.md">Contributing</a>
</h4>

## Why OpenSRE?

| | |
|:--|:--|
| **Learns from every incident** | OpenSRE remembers past investigations — what worked, what didn't. Similar incident at 3am? It already knows the playbook. |
| **Understands your infrastructure** | Neo4j knowledge graph maps service dependencies, so the agent knows blast radius before it starts investigating. |
| **Plugs into what you already use** | 46 production skills for Datadog, Grafana, PagerDuty, Elasticsearch, Kubernetes, AWS, and more. No rip-and-replace. |

## Quick Start

```bash
git clone https://github.com/swapnildahiphale/OpenSRE.git
cd OpenSRE
cp .env.example .env
# Add your OPENROUTER_API_KEY (or ANTHROPIC_API_KEY) to .env
make dev
```

This starts Postgres, config-service, LiteLLM proxy, Neo4j, sre-agent, and the web console. Migrations run automatically. Open **http://localhost:3002** and paste the admin token shown in the terminal to sign in.

> **[Full setup guide](https://www.opensre.in/docs)** · **[Slack integration](docs/SLACK_SETUP.md)**

## Architecture

<p align="center">
  <img src=".github/assets/architecture.png" alt="OpenSRE Architecture" width="900" />
</p>

## Features

| Feature | Description |
|:--------|:------------|
| **46 Production Skills** | Elasticsearch, Datadog, Grafana, PagerDuty, K8s, AWS, and more |
| **Long-term Memory** | Stores investigations, surfaces past solutions for similar incidents |
| **Knowledge Graph** | Neo4j service topology, dependency traversal, blast radius |
| **Multi-provider LLM** | Claude, OpenAI, Gemini, DeepSeek, Mistral, Ollama, and more |
| **Web Console** | Dashboard, agent runs, memory browser |
| **Slack Integration** | Investigate incidents directly from Slack |

**[→ See all features](https://www.opensre.in)**

## Useful Commands

| Command | What it does |
|---------|-------------|
| `make dev` | Start all services (Postgres, config, LiteLLM, agent, web UI) |
| `make dev-slack` | Start all services + Slack bot |
| `make stop` | Stop all services |
| `make status` | Show service health status |
| `make logs` | Follow all service logs |
| `make logs-agent` | Follow sre-agent logs only |
| `make clean` | Remove containers, volumes, and images |

### Slack integration

[Create a Slack app](https://api.slack.com/apps?new_app=1) using the [manifest](slack-bot/slack-manifest.json), add `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` to `.env`, and run `make dev-slack`. [Full guide](docs/SLACK_SETUP.md).

## E2E Testing with EKS

Run OpenSRE against a real Kubernetes cluster with the [OpenTelemetry Demo](https://opentelemetry.io/docs/demo/) app to test end-to-end investigations.

### Prerequisites

- An existing EKS cluster with `kubectl` and `helm` installed
- AWS CLI configured with access to the cluster

### Setup

```bash
export EKS_CLUSTER=my-cluster
export EKS_REGION=us-west-2
make e2e-setup-eks
```

This installs the otel-demo app on your EKS cluster, sets up port-forward tunnels to Prometheus/Grafana/Jaeger, starts sre-agent and the web UI, and generates a team token you can use to sign in.

### Run fault injection tests

```bash
make e2e-test                    # Quick cart failure investigation (raw curl)
make e2e-test-cart               # Cart service fault — ~10% EmptyCart failures
make e2e-test-product            # Product catalog fault — ~5% GetProduct failures
make e2e-test-recommendation     # Recommendation service cache failure
make e2e-test-ad                 # Ad service failure — all requests fail
make e2e-test-all                # Run all 4 fault injection tests sequentially
```

Each test injects a fault into the otel-demo app via feature flags, then triggers an OpenSRE investigation to diagnose it.

### EKS commands

| Command | What it does |
|---------|-------------|
| `make e2e-setup-eks` | Full setup: otel-demo on EKS + tunnels + agent + token |
| `make e2e-teardown-eks` | Uninstall otel-demo from EKS and stop tunnels |
| `make e2e-status` | Show cluster, pods, and observability status |
| `make e2e-token` | Generate a team token for web UI access |
| `make eks-port-forward` | Start port-forward tunnels to EKS |
| `make eks-port-forward-stop` | Stop port-forward tunnels |

### Local cluster (Kind)

For testing without a cloud cluster, you can use Kind instead:

```bash
make e2e-setup       # Create Kind cluster + install otel-demo + start agent
make e2e-teardown    # Delete Kind cluster and clean up
```

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. Please open an issue before starting major work.

## License

OpenSRE is licensed under the [Apache License 2.0](LICENSE).
