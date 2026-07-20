# OpenSRE - AI SRE Agent

AI-powered SRE agent for automated incident investigation using the Claude Agent SDK.

## Quick Start

```bash
cd sre-agent

# Setup
uv venv && source .venv/bin/activate
uv pip install -e .

# Configure
cp env.example .env
# Set ANTHROPIC_API_KEY in .env — no LiteLLM or OpenRouter required

# Run server (simple mode — Claude Agent SDK engine)
python server_simple.py
```

### Docker Compose (POC bring-up)

```bash
# From repo root
docker compose -f docker-compose.yml -f docker-compose.override.yml up sre-agent
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

Model settings control the Claude Agent SDK session:

- `temperature`, `max_tokens`, `top_p` supported
- Applied per-session from team config or defaults
- Calls go directly to Anthropic — no proxy layer

### Execution Limits

- **`max_turns`**: Prevents runaway sessions by capping tool-use turns (each thought+tool pair = 1 turn)
- When exceeded, investigation returns partial results with status="incomplete"
- Set per root agent in **Admin → Configuration → Agents** (config-service hierarchical merge; planner default is 50)
- **Not** an `.env` variable — `sre-agent` reads `max_turns` only from team config
- Wall-clock timeout: `AGENT_TIMEOUT_SECONDS` in `docker-compose.yml` (default 600)

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
Request → server_simple.py:8001 → agent.py (Claude Agent SDK) → Stream Results
                                        ↓
                               InteractiveAgentSession
                               (direct Anthropic API, ANTHROPIC_API_KEY)
```

The agent runs in-process via the Claude Agent SDK (`claude-agent-sdk`). LLM calls go directly to Anthropic — no LiteLLM proxy, no OpenRouter required.

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

- **agent.py** — `InteractiveAgentSession` — Claude Agent SDK engine
- **server_simple.py** — FastAPI server (port 8001), SSE streaming, simple mode entry point
- **server.py** — full server (multi-tenant, config-service integration)
- **config.py** — config-service client, skills filtering logic
- **memory/** — episodic memory system (integration, strategy generator, models)
- **memory_service.py** — HTTP client for config-service memory/episode API
- **tools/** — Neo4j semantic layer
- **pyproject.toml** — Python dependencies
- **Dockerfile** — container image
- **.claude/skills/** — 46 skills with methodology docs and scripts

## Features

- **Claude Agent SDK** — direct Anthropic API, no proxy layer required
- **Skills + Scripts Architecture** — context-efficient integrations via Python scripts
- **Episodic Memory** — learn from past investigations, strategy generation
- **Skills Filtering** — per-agent skill access control
- **Agent Run Recording** — full tool call traces for observability
- **Neo4j Knowledge Graph** — service topology and blast radius analysis
- **Laminar Tracing** — full observability and debugging
