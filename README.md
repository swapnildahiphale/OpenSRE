<h1 align="center">OpenSRE</h1>
<p align="center">
  <b>AI SRE platform with episodic memory and knowledge graph</b><br>
  Investigate production incidents, find root causes, and learn from every investigation.
</p>

<h4 align="center">
  <a href="https://opensre.in">Website</a> |
  <a href="https://demo.opensre.in">Live Demo</a> |
  <a href="docs/FORK_ROADMAP.md">Roadmap</a> |
  <a href="docs/FEATURES.md">Features</a> |
  <a href="ATTRIBUTION.md">Attribution</a>
</h4>

<h4 align="center">
  <a href="https://opensre.in">
    <img src="https://img.shields.io/badge/website-opensre.in-green.svg" alt="OpenSRE Website" />
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="Apache 2.0 License" />
  </a>
</h4>

## What is OpenSRE?

OpenSRE is an AI SRE platform that automatically investigates production incidents, correlates alerts, analyzes logs, and finds root causes.

- **Episodic Memory** — learns from every investigation, surfaces past solutions for similar incidents
- **Neo4j Knowledge Graph** — service topology awareness, blast radius analysis, dependency traversal
- **Memory UI** — dashboard to browse past investigations, search similar incidents, view strategies

## Architecture

```
                    Slack / Web UI / API
                           |
                    +------v------+
                    |  sre-agent  |  LangGraph orchestration
                    +------+------+
                           |
              +------------+------------+
              |            |            |
        Memory System   46 Skills   Knowledge Graph
        (episodic)     (production)  (Neo4j)
              |            |            |
        Past incidents  Observability  Service topology
        Proven strategies  K8s, AWS    Dependencies
        Success patterns  Code, Logs   Blast radius
```

## Features

### Core Platform
- **46 production skills** — Elasticsearch, Datadog, Grafana, PagerDuty, K8s, AWS, and more
- **Configurable specialist subagents** — auto-routed based on problem type
- **Chat integration** — Slack, Microsoft Teams, Google Chat
- **Web console** — dashboard, agent run interface, config editor
- **Multi-provider LLM** — Claude, OpenAI, Gemini, DeepSeek, Mistral, Ollama, and 14 more
- **Config service** — hierarchical org/team configuration with audit logging
- **Alert correlation** — temporal + topology + semantic analysis
- **Knowledge base (RAPTOR)** — hierarchical retrieval over runbooks

### OpenSRE Additions
- **Episodic memory system** — stores and retrieves investigation episodes
- **Multi-factor similarity matching** — alert type, service, error message, success rate
- **Memory-guided investigation** — past strategies injected into agent prompts
- **Neo4j knowledge graph** — service topology queries before investigation
- **Memory UI pages** — episode browser, similarity search, strategy explorer
- **LiteLLM proxy** — route any model name through OpenRouter or other providers

## Quick Start

```bash
git clone https://github.com/swapnildahiphale/OpenSRE.git
cd OpenSRE
cp .env.example .env
# Edit .env to add your OPENROUTER_API_KEY (or ANTHROPIC_API_KEY)
make dev
```

This starts Postgres, config-service, LiteLLM proxy, Neo4j, sre-agent, and the web console. Migrations run automatically.

**Slack integration:** [Create a Slack app](https://api.slack.com/apps?new_app=1) using the [manifest](slack-bot/slack-manifest.json), add `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` to `.env`, and run `make dev-slack`. [Full guide](docs/SLACK_SETUP.md).

## License

OpenSRE is licensed under the [Apache License 2.0](LICENSE).
