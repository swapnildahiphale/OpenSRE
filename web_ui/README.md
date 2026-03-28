# `web_ui/` — OpenSRE Web Console (Next.js) *(prototype; design is broader)*

This is the **governance + ops console** for OpenSRE. In the intended product design, it is the single place to view:
- **Configs** (team/org effective config, overrides, audit history)
- **AI pipeline proposals** (prompt/tool/config diffs) + **evaluation evidence**
- **Knowledge base** (what’s indexed, retrieval traces/evidence, KB diffs/updates)
- **Agent runs/traces** (incident triage sessions, tool calls, timelines, summaries)

The current codebase is an early implementation/prototype and today focuses primarily on config-service-backed flows.
- UI pages (admin org tree, token management, configuration views, learning pages, incident review mock screens)
- **Knowledge Base Tree Explorer** (RAPTOR tree visualization, semantic search, Q&A with citations)
- Next.js **API routes** that proxy to upstream services (`config_service/`, `knowledge_base/`)

## Current implementation (today)

### Upstream proxy model (why Next.js API routes exist)

The UI calls its own `/api/*` routes. Those routes proxy upstream to backend services:

**Config Service:**
- Identity: `/api/identity` → `config_service: GET /api/v1/auth/me`
- Team config: `/api/config/me/*` → `config_service: /api/v1/config/me/*`
- Admin org tree + tokens: `/api/admin/...` → `config_service: /api/v1/admin/...`

**RAPTOR Knowledge Base:**
- Tree structure: `/api/team/knowledge/tree` → `knowledge_base: GET /api/v1/tree/structure`
- Tree stats: `/api/team/knowledge/tree/stats` → `knowledge_base: GET /api/v1/tree/stats`
- Node children: `/api/team/knowledge/tree/nodes/{id}/children` → `knowledge_base: GET /api/v1/tree/nodes/{id}/children`
- Semantic search: `/api/team/knowledge/tree/search` → `knowledge_base: POST /api/v1/tree/search-nodes`
- Q&A: `/api/team/knowledge/tree/ask` → `knowledge_base: POST /api/v1/answer`

This keeps the browser from needing a direct network path to private services and enables cookie-based auth.

### Authentication model (dev/enterprise default)

Login is **token-to-cookie**:
- `POST /api/session/login` with `{ "token": "<team token, admin token, or admin OIDC JWT>" }`
- the server sets `opensre_session_token` as an **httpOnly cookie**
- API routes forward it upstream as `Authorization: Bearer <token>` if the client doesn’t provide an Authorization header

The login route now **validates** the token/JWT against `config_service: GET /api/v1/auth/me` before setting the cookie.

Note: set `WEB_UI_COOKIE_SECURE=1` for real HTTPS deployments. For HTTP localhost tunnels, keep it `0`.

### OIDC redirect login (recommended UX)

If you enable OIDC env vars, the UI supports an **Authorization Code + PKCE** flow:
- `GET /api/auth/login` → redirects to your IdP authorization endpoint
- `GET /api/auth/callback` → exchanges `code` for tokens server-side, validates the resulting JWT via `config_service /api/v1/auth/me`, then sets `opensre_session_token`

## Configuration

Required env vars:
- `CONFIG_SERVICE_URL`: base URL for upstream config service
- `RAPTOR_API_URL`: base URL for RAPTOR knowledge base API (for Tree Explorer)

Example:
- copy `env.example` → `.env.local` and edit

## Local development

Prereqs:
- Node.js (use `pnpm` recommended since `pnpm-lock.yaml` is committed)

Run:

```bash
pnpm install
pnpm dev
```

Open:
- `http://localhost:3000`

To connect to config service:
- local config service: set `CONFIG_SERVICE_URL=http://localhost:8080`
- tunneled internal ALB: set `CONFIG_SERVICE_URL=http://localhost:8081`

## Knowledge Base Tree Explorer

The Tree Explorer (`/team/knowledge`) provides:

- **Visual Graph** - Interactive visualization of the RAPTOR tree hierarchy using React Flow
- **Lazy Loading** - Loads top 3 layers initially (~500 nodes), expands on click
- **Semantic Search** - Find relevant nodes across 54K+ entries with score ranking
- **Q&A with Citations** - Ask questions and get answers with `[1]`, `[2]` source citations
- **Node Details** - Click any node to see full text content and metadata

The explorer connects to the RAPTOR API server (`knowledge_base/api_server.py`) which serves the `mega_ultra_v2.pkl` tree (54K+ nodes of infrastructure documentation).

## Future integrations (design intent)

As the rest of the system is productionized, the UI will additionally integrate with:
- `ai_pipeline/` (pipeline runs, eval results, proposals, promotion state)
- `knowledge_base/` (KB artifacts + retrieval evidence) ✅ **Implemented: Tree Explorer**
- `agent/` (agent runs, tool calls, incident timelines)
- `orchestrator/` (team onboarding status + runtime health)

## Infrastructure (AWS)

Terraform lives under `infra/terraform/` and provisions an internal-only ECS/ALB style deployment with SSM tunnel helpers.

