<p align="center">
  <img src=".github/assets/logo.png" alt="OpenSRE — Open-source AI SRE platform for automated incident investigation" width="320" />
</p>

<p align="center">
  <b>Your AI SRE that investigates production incidents</b><br>
  <sub>Long-term memory · Knowledge graph · 46 production skills</sub>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="Apache 2.0 License" /></a>
  <a href="https://github.com/swapnildahiphale/OpenSRE/stargazers"><img src="https://img.shields.io/github/stars/swapnildahiphale/OpenSRE?style=social" alt="GitHub Stars" /></a>
  <a href="https://github.com/swapnildahiphale/OpenSRE/network/members"><img src="https://img.shields.io/github/forks/swapnildahiphale/OpenSRE?style=social" alt="GitHub Forks" /></a>
  <a href="https://github.com/swapnildahiphale/OpenSRE/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome" /></a>
  <a href="https://www.opensre.in/docs"><img src="https://img.shields.io/badge/docs-opensre.in-green.svg" alt="OpenSRE Documentation" /></a>
  <a href="https://www.opensre.in"><img src="https://img.shields.io/badge/website-opensre.in-green.svg" alt="OpenSRE Website" /></a>
</p>

OpenSRE is an open-source AI SRE agent that automatically investigates production incidents, finds root causes, and learns from every investigation. It combines **episodic memory** (remembering past incidents and what fixed them) with a **Neo4j knowledge graph** (understanding service dependencies and blast radius) and **46 production-ready skills** for tools like Datadog, Grafana, PagerDuty, Elasticsearch, Kubernetes, and AWS. Self-hosted, provider-agnostic via LiteLLM, and licensed Apache 2.0.

<p align="center">
  <a href="https://g1ctb3hnwvhw6s5v.public.blob.vercel-storage.com/how-it-works.mp4">
    <img src=".github/assets/hero-thumbnail.webp" alt="OpenSRE demo — AI SRE agent investigating a production incident with episodic memory and knowledge graph" width="720" />
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

> **[Full setup guide](https://www.opensre.in/docs/quick-start)** · **[Slack integration](https://www.opensre.in/docs/integrations)** · **[Configuration](https://www.opensre.in/docs/configuration)**

## Architecture

<p align="center">
  <img src=".github/assets/architecture.png" alt="OpenSRE architecture diagram — LangGraph orchestration with episodic memory, 46 investigation skills, and Neo4j knowledge graph" width="900" />
</p>

> **[→ Detailed architecture docs](https://www.opensre.in/docs/architecture)** · **[Architecture overview](docs/ARCHITECTURE.md)**

## Features

| Feature | Description |
|:--------|:------------|
| **46 Production Skills** | Elasticsearch, Datadog, Grafana, PagerDuty, K8s, AWS, and more |
| **Long-term Memory** | Stores investigations, surfaces past solutions for similar incidents |
| **Knowledge Graph** | Neo4j service topology, dependency traversal, blast radius |
| **Multi-provider LLM** | Claude, OpenAI, Gemini, DeepSeek, Mistral, Ollama, and more |
| **Web Console** | Dashboard, agent runs, memory browser |
| **Slack Integration** | Investigate incidents directly from Slack |

**[→ See all features](https://www.opensre.in)** · **[Roadmap](https://www.opensre.in/docs)**

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

[Create a Slack app](https://api.slack.com/apps?new_app=1), add `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` to `.env`, and run `make dev-slack`. [Full guide](https://www.opensre.in/docs/integrations).

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

## Comparing OpenSRE

How does OpenSRE compare to commercial incident response tools like PagerDuty Copilot, Rootly AI, and Shoreline? See the full breakdown:

**[→ Comparison matrix](https://www.opensre.in/compare)** · **[Blog: OpenSRE vs Commercial Tools](https://www.opensre.in/blog/opensre-vs-commercial-incident-tools)**

## Built With

OpenSRE is built on top of proven open-source technologies:

- **[LangGraph](https://github.com/langchain-ai/langgraph)** — Agent orchestration (planner → subagents → synthesizer)
- **[Neo4j](https://neo4j.com/)** — Knowledge graph for service topology and dependency traversal
- **[FastAPI](https://fastapi.tiangolo.com/)** — Backend API with SSE streaming
- **[Next.js](https://nextjs.org/)** — Web console (dashboard, memory browser, config editor)
- **[LiteLLM](https://github.com/BerriAI/litellm)** — Multi-provider LLM proxy (18+ providers)
- **[PostgreSQL](https://www.postgresql.org/)** — Persistent storage for configs and agent state

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. Please open an issue before starting major work.

## Creator

<table>
  <tr>
    <td>
      <strong>Swapnil Dahiphale</strong> · SRE · Builder<br>
      <em>"Built by someone who's been paged at 3am."</em>
    </td>
    <td align="right">
      <a href="https://swapnil.one">
        <img src="https://img.shields.io/badge/Portfolio-000000?style=for-the-badge&logo=safari&logoColor=white" alt="Portfolio" />
      </a>&nbsp;
      <a href="https://www.linkedin.com/in/swapnil2233/">
        <img src="https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white" alt="LinkedIn" />
      </a>
    </td>
  </tr>
</table>

## License

OpenSRE is licensed under the [Apache License 2.0](LICENSE).
