# OpenSRE - AI SRE Agent

AI-powered SRE agent for automated incident investigation using LangGraph-based orchestration.

## Quick Start

```bash
cd sre-agent

# Setup
uv venv && source .venv/bin/activate
uv pip install langgraph langchain langchain-core langchain-openai python-dotenv fastapi uvicorn

# Configure
cp env.example .env
# Add your OPENROUTER_API_KEY (or ANTHROPIC_API_KEY) to .env

# Run server
python server.py
```

## Agent Configuration

The agent supports rich configuration via config_service for team-specific behavior:

### Agent Config Fields

Each agent in your team config supports:

- **`enabled`** (bool): Whether this agent is active
- **`prompt.system`** (str): Agent's system prompt defining its role and behavior
- **`prompt.prefix`** (str): Description shown when used as subagent
- **`tools.enabled`** (list): Allowed tools (`["*"]` for all)
- **`tools.disabled`** (list): Tools to exclude from enabled set
- **`model`** (object): Model settings for LLM calls
  - **`temperature`** (float, 0.0-1.0): Sampling temperature (None = provider default)
  - **`max_tokens`** (int): Maximum response tokens
  - **`top_p`** (float, 0.0-1.0): Nucleus sampling parameter
- **`max_turns`** (int): Maximum conversation turns (prevents infinite loops)
- **`skills`** (object): Per-agent skill enable/disable overrides

### Example Configuration

```json
{
  "agents": {
    "investigator": {
      "enabled": true,
      "model": {
        "temperature": 0.3,
        "max_tokens": 4000,
        "top_p": 0.9
      },
      "max_turns": 50,
      "prompt": {
        "system": "You are an SRE investigator specialized in incident analysis...",
        "prefix": "Use for incident investigation and root cause analysis"
      },
      "tools": {
        "enabled": ["*"],
        "disabled": ["Write", "Edit"]
      }
    },
    "k8s-specialist": {
      "enabled": true,
      "max_turns": 30,
      "prompt": {
        "system": "You are a Kubernetes specialist...",
        "prefix": "Use for pod crashes, deployments, resource issues"
      }
    },
    "log-analyst": {
      "enabled": true,
      "max_turns": 20,
      "prompt": {
        "system": "You are a log analysis specialist...",
        "prefix": "Use for analyzing application logs and error patterns"
      }
    }
  }
}
```

### Model Settings

Model settings are applied **globally** to the graph execution:

- Settings from the **planner config** apply to all subagents unless overridden
- LiteLLM proxy forwards these to the configured LLM provider
- Supported by most models (temperature, max_tokens, top_p)

### Execution Limits

- **`max_turns`**: Prevents infinite loops by limiting ReAct iterations
- Applied per-subagent (each subagent has its own ReAct loop cap)
- When exceeded, investigation returns partial results with status="incomplete"
- `AGENT_MAX_TURNS` env var overrides config-service value (default: 25)

### Subagent Delegation

The planner node selects which subagents to dispatch based on the alert context and hypotheses. Selected subagents execute in parallel via LangGraph's `Send()` fan-out. Each subagent has its own ReAct loop with scoped tools and system prompt from team config.

Subagents are configurable from team config — not hardcoded.

## API

### Simple Investigation

```bash
curl -X POST http://localhost:8001/investigate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What files are in this directory?"}' \
  --no-buffer
```

Returns SSE stream of agent output.

## Architecture

### Local Development
```
Request → server.py:8001 → graph.py (LangGraph) → Stream Results
                ↓                    ↓
          LiteLLM:4001    planner → subagents → synthesizer → writeup
```

The agent runs in-process using LangGraph graph orchestration. All LLM calls go through the LiteLLM proxy.

## Integrations

Integrations are implemented via **skills with Python scripts**, not MCP tools. This keeps the agent's context clean and enables progressive disclosure of knowledge.

### Available Integrations

| Integration | What It Provides | Environment Variables |
|-------------|------------------|----------------------|
| **Kubernetes** | Pod inspection, logs, events, resource status | `KUBECONFIG` (auto-detected) |
| **Coralogix** | Logs, metrics, traces, alerts (DataPrime queries) | `CORALOGIX_API_KEY`, `CORALOGIX_DOMAIN` |
| **AWS** | EC2, CloudWatch, ECS (planned) | `AWS_REGION`, `AWS_ACCESS_KEY_ID` |
| **Git** | Commit history, deployment correlation | Always available (uses local git) |

### How Integrations Work

Each integration is a skill containing:
- **SKILL.md** — methodology and reference documentation
- **scripts/** — Python scripts that call the actual APIs (Kubernetes, Coralogix, etc.)

When the agent needs to use an integration:
1. Reads the skill metadata (progressive disclosure)
2. Executes relevant Python scripts via Bash
3. Gets structured output without bloating context with tool descriptions

See `env.example` for all available integrations.

## Skills

**46 skills** organized by category provide on-demand methodology and best practices:

| Category | Skills |
|----------|--------|
| **Observability** | Coralogix, Grafana, Elasticsearch, Datadog, Splunk, New Relic, Honeycomb, Jaeger, Sentry, Loki, VictoriaLogs, VictoriaMetrics, Amplitude |
| **Incidents & Alerts** | PagerDuty, Incident.io, Opsgenie, Blameless, FireHydrant |
| **Infrastructure** | Kubernetes, AWS, Docker, GCP, Azure, Neo4j |
| **Databases** | PostgreSQL, MySQL, Snowflake, BigQuery |
| **Streaming** | Kafka |
| **Platform** | Vercel, flagd (OpenFeature) |
| **Project & Docs** | GitLab, Jira, Linear, Notion, ClickUp, Sourcegraph, Google Docs |
| **Investigation** | Root cause analysis, observability methodology, metrics analysis, remediation, knowledge base (RAPTOR), incident comms |

Skills are automatically invoked when relevant to the task. Located in `.claude/skills/` directory. Skills can be filtered per-agent via config-service (see `docs/SKILLS_FILTERING.md`).

## Episodic Memory

The agent has episodic memory that stores and retrieves past investigation episodes:

- **Pre-investigation**: Similar past episodes and strategies injected into agent context
- **Post-investigation**: LLM extracts structured episode metadata (summary, root cause, services, severity)
- **Strategy generation**: After 2+ similar episodes, LLM generates reusable investigation strategies

Memory is stored in PostgreSQL via config-service. See `docs/MEMORY_SYSTEM.md`.

Key files:
- `memory/integration.py` — memory enhancement and episode storage
- `memory/strategy_generator.py` — LLM-based strategy generation from episode patterns
- `memory/models.py` — episode data models
- `memory_service.py` — HTTP client for config-service memory API

## Agent Run Recording

Every investigation is recorded with full tool call traces:

- Run metadata (start time, prompt, agent config, status) stored in config-service
- Tool calls captured with input/output for each invocation
- TraceViewer in web UI shows expandable tool call timeline

## Key Files

- **graph.py** — master LangGraph graph definition with nodes, edges, and Send() fan-out
- **server.py** — FastAPI server (port 8001), SSE streaming, investigation management
- **config.py** — config-service client, skills filtering logic
- **memory/** — episodic memory system (integration, strategy generator, models)
- **memory_service.py** — HTTP client for config-service memory/episode API
- **tools/** — Neo4j semantic layer
- **pyproject.toml** — Python dependencies
- **Dockerfile** — container image
- **.claude/skills/** — 46 skills with methodology docs and scripts

## Features

- **LangGraph Orchestration** — graph-based agent topology with parallel subagent fan-out
- **Skills + Scripts Architecture** — context-efficient integrations via Python scripts
- **Episodic Memory** — learn from past investigations, strategy generation
- **Skills Filtering** — per-agent skill access control
- **Agent Run Recording** — full tool call traces for observability
- **Multi-provider LLM** — via LiteLLM proxy (OpenRouter, Anthropic, etc.)
- **Neo4j Knowledge Graph** — service topology and blast radius analysis
- **Configurable Subagents** — from team config, not hardcoded
- **Laminar Tracing** — full observability and debugging
