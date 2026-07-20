# OpenSRE — AI SRE Platform

## What this is

OpenSRE is an open-source AI SRE platform that investigates production incidents. It uses LLM-powered agents with episodic memory and a Neo4j knowledge graph to diagnose issues, identify root causes, and produce structured investigation reports.

## Architecture

```
Web UI -> sre-agent (Claude Agent SDK)
                |
          +-----+-----+
          |     |     |
       Memory Skills  KG
config-service <- used by web_ui, sre-agent
```

**sre-agent** is the core investigation agent. Uses the Claude Agent SDK: a root `investigator` agent dispatches specialist subagents via the SDK `Task` tool. 51 skills (progressive knowledge loading) via the SDK Skill tool.

**web_ui** is the admin console and agent entry point (Next.js, pnpm). Agent runs, config editor, knowledge base explorer, memory pages.

**config-service** is the control plane. Hierarchical org->team config with deep merge. Manages tokens and audit logging.

**memory system** -- Neo4j-backed episodic memory in `sre-agent/memory/`. One episode per conversation; semantic retrieval via neo4j-graphrag. Agent-driven recall through the `memory-search` skill (not pre-injected).

**knowledge graph** -- Neo4j integration for service topology, dependency traversal, blast radius analysis (agent-driven via `infrastructure-neo4j`).

**LiteLLM proxy** -- OPTIONAL multi-provider proxy (OpenRouter/others), off by default. Start with `docker compose --profile litellm up` and point `ANTHROPIC_BASE_URL` at it. See `litellm_config.example.yaml`.

## Local development

```bash
# Copy the example env and add your API key
cp .env.example .env
# Set ANTHROPIC_API_KEY in .env (OpenRouter via the optional LiteLLM proxy)

# Start all services (postgres, config-service, neo4j, sre-agent, web console)
make dev
```

Or use Docker Compose directly:

```bash
docker compose up
```

The web console will be available at `http://localhost:3002`.

Optional chat bots:
- `make dev-teams` — Microsoft Teams bot (`teams-bot/`, port 3978)
- `make dev-slack` — Slack bot (requires `slack-bot/` + Slack tokens)

## Key files

| File | What it does |
|------|-------------|
| sre-agent/agent.py | Claude Agent SDK engine -- InteractiveAgentSession, AgentDefinition registry, hooks |
| sre-agent/server_simple.py | Simple-mode FastAPI server (in-process, direct Anthropic) |
| sre-agent/config.py | TeamConfig/AgentConfig loading from config-service |
| sre-agent/server.py | FastAPI server, SSE streaming over the SDK message stream (events.py) |
| sre-agent/tools/ | Neo4j semantic layer (KG queries) |
| sre-agent/memory/ | Episodic memory system (Neo4j) |
| config_service/src/api/main.py | Config API with hierarchical merge |
| web_ui/src/app/ | Next.js app router pages |
| teams-bot/ | Microsoft Teams bot (SSE to sre-agent) |
| litellm_config.example.yaml | Example LiteLLM proxy config (optional) |

## Conventions

- Python services use `uv` (sre-agent, config-service)
- web_ui is Next.js with pnpm
- Linting: ruff (config in ruff.toml)
- Skills over tools: add integrations as `.claude/skills/*/SKILL.md` with scripts
- Config hierarchy: org base, team overrides. Dicts merge, lists replace.
- Error format: `{"success": bool, "result": ..., "error": "..."}`
- SSE streaming: events defined in events.py

## Contributing

See `CONTRIBUTING.md` for guidelines. Please open an issue before starting major work.
