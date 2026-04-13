# OpenSRE Architecture

## System Overview

```
                    Slack / Web UI / API
                           |
              ┌────────────┼────────────┐
              ↓            ↓            ↓
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Slack Bot│ │ Web UI   │ │ REST API │
        │ (Socket  │ │ (Next.js)│ │          │
        │  Mode)   │ │ :3002    │ │          │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             └─────────────┼────────────┘
                           ↓
                    ┌──────────────┐
                    │  SRE Agent   │
                    │  - LangGraph │
                    │  - 46 Skills │
                    │  - Memory    │
                    │  :8001       │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ↓            ↓            ↓
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Config   │ │ LiteLLM  │ │ Neo4j    │
        │ Service  │ │ Proxy    │ │ Knowledge│
        │ (Postgres│ │ :4001    │ │ Graph    │
        │  :8081)  │ │          │ │ :7475    │
        └──────────┘ └──────────┘ └──────────┘
```

## Investigation Flow

1. Alert arrives via Slack @mention, web console, or REST API
2. SRE Agent enhances the prompt with episodic memory (similar past incidents)
3. LangGraph runs: `init_context` → `memory_lookup` / `kg_context` → `planner` → parallel subagents → `synthesizer` → `writeup` → `memory_store`
4. Subagents execute in parallel via LangGraph `Send()` fan-out
5. Results stream back via SSE to Slack thread or web UI
6. Investigation stored as an episodic memory episode for future reference

## Agent System

The SRE agent uses LangGraph for graph-based orchestration with 46 production skills.

- **Progressive skill loading** — ~100 tokens of metadata loaded initially, full content on demand
- **Multi-provider LLM** — routes through LiteLLM proxy (OpenRouter, Anthropic, OpenAI, and 14+ others)
- **Configurable subagents** — routed based on problem type from team config
- **Full trace recording** — tool call inputs/outputs stored for replay in web UI

## Episodic Memory

Stores past investigation episodes in PostgreSQL for memory-guided investigations.

- **Multi-factor similarity** — matches on alert type (0.5), service (0.3), resolved status (0.2)
- **Memory-enhanced prompts** — similar past episodes and strategies injected before investigation
- **Strategy generation** — LLM analyzes patterns from 2+ similar episodes to generate reusable strategies

## Knowledge Graph

Neo4j stores service topology for infrastructure-aware investigations.

- Service dependency mapping and traversal
- Blast radius analysis before investigation begins
- Topology-aware alert correlation

## Skills (46)

| Category | Skills |
|----------|--------|
| **Observability** | Coralogix, Grafana, Elasticsearch, Datadog, Splunk, New Relic, Honeycomb, Jaeger, Sentry, Loki, VictoriaLogs, VictoriaMetrics, Amplitude |
| **Incidents** | PagerDuty, Incident.io, Opsgenie, Blameless, FireHydrant |
| **Infrastructure** | Kubernetes, AWS, Docker, GCP, Azure, Neo4j |
| **Databases** | PostgreSQL, MySQL, Snowflake, BigQuery |
| **Streaming** | Kafka |
| **Platform** | Vercel, flagd (OpenFeature) |
| **Project & Docs** | GitLab, Jira, Linear, Notion, ClickUp, Sourcegraph, Google Docs |
| **Investigation** | Root cause analysis, observability methodology, metrics analysis, remediation, knowledge base (RAPTOR), incident comms |

## Local Development Stack

All services run via `docker-compose`:

| Service | Role |
|---------|------|
| **PostgreSQL** | Config, episode, and agent run storage |
| **LiteLLM** | LLM proxy — routes to OpenRouter/Anthropic/others |
| **Neo4j** | Knowledge graph for service topology |
| **Config Service** | Hierarchical org/team config with token auth |
| **SRE Agent** | LangGraph investigation engine |
| **Web UI** | Next.js dashboard, agent runs, memory browser |

```bash
make dev        # Start all services
make dev-slack  # Start all + Slack bot
```
