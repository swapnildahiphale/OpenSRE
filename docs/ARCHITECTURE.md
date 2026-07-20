# OpenSRE Architecture

OpenSRE is an AI SRE platform that investigates production incidents. A root investigator agent plans work, dispatches specialist subagents, loads integration skills on demand, and streams progress back to clients over SSE. Episodic memory and a service topology knowledge graph live in Neo4j; configuration and agent-run traces live in PostgreSQL.

## System Overview

```
     Web UI              Slack Bot              Teams Bot
     (Next.js)         (Socket Mode)         (Microsoft Teams)
       :3002                                    :3978
         \                  |                    /
          \                 |                   /
           v                v                  v
         ┌─────────────────────────────────────────┐
         │               sre-agent                 │
         │                 :8001                   │
         └──────────────────┬──────────────────────┘
                            │
         ┌──────────────────┼──────────────┬─────────────────┐
         v                  v              v                 v
    ┌──────────┐      ┌──────────┐  ┌──────────┐   ┌─────────────┐
    │ config-  │      │ Postgres │  │  Neo4j   │   │ LiteLLM     │
    │ service  │      │ agent    │  │ memory + │   │ (optional,  │
    │ :8081    │      │ runs +   │  │ knowledge│   │  :4001)     │
    │          │      │ config   │  │ graph    │   │             │
    └──────────┘      └──────────┘  └──────────┘   └─────────────┘
```

**Entry points**

- **Web UI** — admin console and investigation UI; streams SSE from sre-agent.
- **Slack bot** — Socket Mode; @mentions and threads; streams the same SSE protocol.
- **Teams bot** — Microsoft Teams channels or DMs; streams the same SSE protocol.
- **REST API** — `POST /investigate` and related thread endpoints on sre-agent (used by the clients above).

## Investigation Flow

1. A user starts an investigation from the web console, Slack, Teams, or the REST API.
2. sre-agent creates or resumes a thread and opens an `InteractiveAgentSession` (Claude Agent SDK).
3. The root agent (typically `investigator`) plans the work, loads skills on demand, and dispatches specialists via the SDK `Task` tool.
4. After concrete symptoms are known (error text, failing service, stack trace), the agent may invoke `memory-search` and `infrastructure-neo4j` — there is no automatic pre-injection of past episodes or topology.
5. Tool calls, thoughts, subagent progress, and the final answer stream to the client as SSE events.
6. On turn completion, the lifecycle hook upserts a Neo4j `:Episode` (one per `correlation_id` / thread) and persists the full tool trace to PostgreSQL for replay in the web UI.

There is no LangGraph orchestration layer. The SDK session is the runtime.

## Agent SDK Runtime

The investigation engine is `InteractiveAgentSession` in `sre-agent/agent.py`. It wraps `ClaudeSDKClient` and maps SDK messages to the SSE event protocol in `events.py`.

### Root agent and subagents

- The **root agent** is resolved from team config (`investigator` preferred, then `planner`). Its system prompt comes from `agents.{id}.prompt.system` in config-service.
- **Specialist subagents** are registered as SDK `AgentDefinition` objects, built from the team's agent topology (`sub_agents` edges). The root delegates via the SDK `Task` tool (also exposed as `Agent` in newer SDK builds).
- **Skills** live under `sre-agent/.claude/skills/*/SKILL.md`. The SDK `Skill` tool loads metadata first (~100 tokens per skill) and full content on demand. Skill scripts run via `Bash` under the loaded skill.

### Message stream drain

`execute()` follows the SDK-recommended pattern:

1. Start `client.query()` with a streaming user-message generator (concurrent task).
2. Drain the response with `receive_messages()` — **not** `receive_response()` alone.

`receive_messages()` does not stop on `ResultMessage`. The session tracks outstanding background tasks and only emits a terminal `result` event when no background work remains.

### Background subagents

Subagents started with `run_in_background` emit `TaskStartedMessage` / `TaskNotificationMessage` on the SDK stream. While tasks are outstanding:

- Interim root text is emitted as `thought` events.
- Clients receive `background_waiting` with pending task IDs.
- The parent auto-continues when all tasks complete — no manual follow-up prompt required.

### Mid-run message queue

Users can add context while an investigation is running:

- API: `POST /threads/{thread_id}/queue-message`
- SSE: `message_queued` when queued text is merged into the SDK turn

Queued messages are debounced and merged at turn boundaries into a single numbered guidance block (`message_queue.py`). The streaming input generator stays open until the turn ends, then force-flushes any remaining queue.

### SSE event types (high level)

| Type | Purpose |
|------|---------|
| `thought` | Agent reasoning / interim narration |
| `tool_start` / `tool_end` | Skill, Bash, Task, and other tool lifecycle |
| `task_started` / `task_notification` | Background subagent lifecycle |
| `background_waiting` | Parent waiting on outstanding background tasks |
| `message_queued` | Mid-run user message accepted or consumed |
| `question` | `AskUserQuestion` clarifying prompt |
| `result` | Terminal answer for the turn |
| `error` | Failure or timeout |

Wall-clock cap: `AGENT_TIMEOUT_SECONDS` (default 600s), independent of SDK `max_turns` from config-service.

## Deployment Modes

| | Default (`make dev` / self-host) | Sandbox mode |
|---|----------------------------------|--------------|
| **Server** | `server_simple.py` | `server.py` |
| **Agent process** | Same process as the API | Per-thread K8s sandbox pods |
| **Isolation** | Trusted local / single-tenant use | Filesystem and network isolation |
| **Skills** | Copied to per-thread workspace under `/tmp/sessions/{thread_id}` | Baked into sandbox image at `/app/.claude` |

Default mode is the supported path for local development and typical self-hosting. Sandbox mode is a separate production-oriented stack and is not required to run OpenSRE.

## Episodic Memory

Implementation: `sre-agent/memory/` + hooks in `investigation_lifecycle.py`.

- **Storage** — `:Episode` nodes in Neo4j, keyed by `correlation_id` (one episode per conversation/thread).
- **Retrieval** — vector similarity via `neo4j-graphrag` (`EpisodeRetriever`); embeddings computed on issue text, summary, and root cause.
- **Recall** — agent-driven only through the `memory-search` skill after concrete evidence exists. Root-agent guidance is appended in `investigation_guidance_append()`; nothing is pre-injected at request time.
- **Traces** — full tool-call inputs/outputs and run metadata persist in PostgreSQL (config-service agent-runs API) for the Investigations UI.
- **`resolved` flag** — means a root cause was identified with supporting evidence in the investigation output. It does **not** mean production was fixed or remediated.

Post-turn extraction (`memory/extraction.py`) populates issue type, components, skills used, key findings, and effectiveness score.

## Knowledge Graph

Neo4j holds service topology (dependencies, blast radius) alongside episodic memory in the same database.

- Queried agent-driven via the `infrastructure-neo4j` skill after an affected service or deployment is known.
- Not loaded automatically on vague initial alerts.
- If Neo4j is unavailable, investigations continue without topology context.

## Skills (51)

Skills are the primary integration surface: methodology docs plus optional Python scripts under each skill directory. Teams can disable skills per config; credentials are supplied via environment variables at runtime.

| Category | Examples |
|----------|----------|
| **Core Methodology** | Investigation framework, observability methodology, infrastructure debugging, remediation |
| **Observability** | Coralogix, Grafana, Elasticsearch, Datadog, Splunk, New Relic, Honeycomb, Jaeger, Sentry, Loki, VictoriaLogs, VictoriaMetrics, metrics analysis |
| **Infrastructure & Cloud** | Kubernetes, AWS, Docker, GCP, Azure, Neo4j (topology) |
| **Alerting & On-call** | PagerDuty, Opsgenie |
| **Incident Management** | Incident.io, Blameless, FireHydrant, incident comms |
| **Databases** | PostgreSQL, MySQL, Snowflake, BigQuery |
| **Docs & Knowledge** | Confluence knowledge base, RAPTOR, Notion, Google Docs |
| **Memory** | memory-search |
| **Code & Version Control** | GitHub, Bitbucket, GitLab, Sourcegraph |
| **Ticketing & Project** | Jira, Linear, ClickUp |
| **Other Integrations** | Jenkins, Argo CD, Vercel, Kafka, Amplitude, flagd (OpenFeature) |

Add a skill by creating `sre-agent/.claude/skills/<id>/SKILL.md` and regenerating the config-service catalog (`config_service/scripts/gen_skills_catalog.py`).

## Configuration

**config-service** is the control plane:

- Hierarchical org → team tree with deep merge (dicts merge, lists replace).
- Team tokens for runtime auth; admin tokens for the configuration UI.
- Agent prompts and topology at nested paths: `agents.{agent_id}.prompt.system`, plus `sub_agents`, model, and tool settings per agent.
- Skills enablement and integration credentials are team-scoped; sre-agent resolves org/team from the bearer token on each investigation.

Web UI and sre-agent read merged config at investigation start. Audit logging records config changes.

## Local Development Stack

```bash
cp .env.example .env   # set ANTHROPIC_API_KEY
make dev               # core stack
make dev-slack         # core + Slack bot
make dev-teams         # core + Teams bot
```

| Service | Port | Role |
|---------|------|------|
| Web UI | 3002 | Next.js console |
| sre-agent | 8001 | Investigation API + SSE |
| config-service | 8081 | Config, tokens, agent-run storage |
| PostgreSQL | 5433 | Config DB + agent runs |
| Neo4j Browser / Bolt | 7475 / 7688 | Memory + topology graph |
| Slack bot | — | Optional (`--profile slack` / `make dev-slack`) |
| Teams bot | 3978 | Optional (`--profile teams` / `make dev-teams`) |
| LiteLLM | 4001 | Optional (`--profile litellm`) |

By default the agent calls Anthropic directly (`ANTHROPIC_API_KEY`). To use OpenRouter or other providers, start the LiteLLM profile and set `ANTHROPIC_BASE_URL` to the proxy.

## Key Files

| File | Role |
|------|------|
| `sre-agent/agent.py` | Agent session, subagent registry, SDK hooks, stream drain |
| `sre-agent/server_simple.py` | Default FastAPI server for `make dev` / self-hosting |
| `sre-agent/server.py` | Sandbox-mode FastAPI server (K8s-isolated agents) |
| `sre-agent/investigation_lifecycle.py` | Memory/KG root guidance, episode finalize hook |
| `sre-agent/message_queue.py` | Mid-run message merge formatting |
| `sre-agent/events.py` | SSE event types and serializers |
| `sre-agent/memory/` | Neo4j episode store, retrieval, extraction |
| `sre-agent/config.py` | Team config loading, root/subagent resolution |
| `web_ui/` | Next.js admin console and investigation UI |
| `slack-bot/` | Slack bot (Socket Mode → sre-agent SSE) |
| `teams-bot/` | Microsoft Teams bot (SSE client to sre-agent) |
| `config_service/` | Hierarchical config API, skills catalog, Postgres persistence |

## Related Docs

- `docs/MEMORY_SYSTEM.md` — episodic memory design (when present in your checkout)
- `teams-bot/README.md` — Teams bot setup and Azure messaging endpoint
- Slack: set `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN`, then `make dev-slack`
- `.env.example` — required environment variables for self-hosting
