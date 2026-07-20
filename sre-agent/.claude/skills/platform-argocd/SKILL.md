---
name: platform-argocd
description: Argo CD application inspection, sync, rollback, restart, and diff via CLI. Prod/stg apps have app-name echo gates for state changes; destructive verbs blocked. Use when investigating GitOps deploy failures, out-of-sync apps, or rollout issues.
allowed-tools: Bash(argocd *)
---

# Skill: Argo CD (Portable)

Use this skill for Argo CD CLI work. Single-instance generic — the target instance is controlled by `ARGOCD_SERVER` (required in direct/local mode; no baked-in default hostname). Guardrails are **app-name-based**, not instance-based: a prod app regex-matched as such gets restricted treatment regardless of which server it lives on.

## Authentication

**IMPORTANT**: In proxy/production mode, credentials may be injected automatically.
Do not assume `ARGOCD_PASSWORD` is visible — run `argocd account get-user-info` first.

In **direct/local mode**, set in repo root `.env` (passed to the sre-agent container via docker-compose `env_file`). The `argocd` CLI reads `ARGOCD_*` from the environment — no secondary env files.

- `ARGOCD_SERVER` (required — e.g. `argocd.example.com`)
- `ARGOCD_USERNAME` (default: `admin`)
- `ARGOCD_PASSWORD` (required for login)
- `ARGOCD_GRPC_WEB` (default: `true`)
- `ARGOCD_HTTP_TIMEOUT` (default: `30`)

See `sre-agent/.claude/skills/platform-argocd/.env.example` for a template.

Session persistence: after `argocd login`, token is stored in `~/.config/argocd/config`. Mount host config into the container for in-container runs (see docker-compose.yml).

## Use When

- Argo CD application list / get / history / logs / diff
- App sync (with interactive prune approval flow)
- Rollback to a specific revision
- Workload restart via `argocd app actions run <Kind> <Name> restart`
- `app wait` for sync/health after a change
- Inventory inspection: `cluster list`, `proj list`, `repo list`

## Do Not Use For

- Creating applications (GitOps — belongs in the manifest repo PR)
- Modifying application specs (use GitOps commits)
- Repo / cluster / project management on prod Argo CD (blocked)
- Per-engineer identity in audit logs (no SSO today; see [Known Limitations](#known-limitations))

## Safety Contract

### Tier A — allowed, no confirmation (all apps)

- **Read**: `app list`, `app get`, `app get --refresh`, `app history`, `app logs`, `app diff`, `app wait`, `app resources`, `app manifests`
- **Inventory**: `cluster list`, `cluster get`, `proj list`, `proj get`, `repo list`, `repo get`
- **Session**: `account get-user-info`, `account can-i`, `context`, `version`

### Tier B-light — allowed, no confirmation (non-prod apps)

- `app sync` (no prune)
- `app rollback <rev>`
- `app terminate-op`
- `app actions run <Kind> <Name> restart --namespace <ns>`
- `app set`, `app patch`, `app create`
- `cluster add`, `proj create`, `repo add`

### Tier B-gated — confirmation required (non-prod apps, delete-family)

- `app sync --prune` — triggers the two-step interactive approval flow (see [Prune approval flow](#prune-approval-flow) below)
- `app delete`
- `cluster rm`, `proj delete`, `repo rm`

### Prod / stg mode (app name matches the classification regex below)

**Allowed with no confirmation:** everything in Tier A.

**Gated with app-name echo** (user types the app name back before execution):

- `app sync` (no prune)
- `app terminate-op`
- `app actions run <Kind> <Name> restart`

**Blocked outright:**

- `app sync --prune` (deletion via GitOps commits + change-management only)
- `app rollback` (rollbacks via GitOps revert PR)
- `app delete`, `app create`, `app set`, `app patch`
- `cluster add`, `cluster rm`, `proj create`, `proj delete`, `repo add`, `repo rm`

Refusal message:

> "This op on a prod/stg app should go through GitOps PR + change-management approval — not via this skill."

### Unknown apps

If an app name doesn't match any classification rule, skill refuses Tier B verbs and prompts: `"App '<name>' isn't matched by the prod/stg/non-prod patterns. Classify for this session: [prod / stg / non-prod]."` Classification persists for the chat session only.

### Prune approval flow

`sync --prune` deletes resources in the cluster that are no longer defined in the app's desired state. Never run with `--prune` in the same turn as the initial request. Workflow:

1. User asks for `sync-prune` on a non-prod app.
2. Agent replies with a risk summary and the exact command:

   ```bash
   argocd app sync <App> --prune
   ```

3. Agent waits for explicit confirmation in a follow-up message ("yes", "I approve", "confirm prune").
4. Only after explicit confirmation does the agent run the command.

On prod/stg apps, `sync --prune` is blocked entirely — not even the approval flow is offered.

### Never

- Never print credentials, tokens, or env-var values.
- Never echo the content of `ARGOCD_PASSWORD` in assistant output.
- Never modify auth state (`argocd logout`) without explicit user request.
- Never wrap destructive operations in shell aliases to bypass gates.

## Environment Classification

Signal: Argo CD application name, passed as the first token in the `<App> [Resource] <Action>` shorthand.

Apply the **5-step regex** in order (case-insensitive, first match wins):

| Step | Pattern | Classification |
|---|---|---|
| 1 | `non-?prod` \| `nprd` \| `npd` | **non-prod** (permissive) |
| 2 | `prod` \| `prd` \| `production` | **prod** (restricted) |
| 3 | `stg` \| `staging` \| `stage` | **stg** (restricted) |
| 4 | `dev` \| `qa` \| `uat` \| `sandbox` \| `test` \| `ephemeral` | **non-prod** (permissive) |
| 5 | (no match) | **unknown** → prompt user |

## Shorthand

Agent parses user messages of the form:

```text
<ArgoApplicationName> [ <Resource> ] <Action>
```

- `<ArgoApplicationName>` — required; the Argo CD `Application` metadata name.
- `<Resource>` — optional; omit for whole-app operations. See [Resource formats](#resource-formats) below.
- `<Action>` — required; one of: `sync`, `sync-prune`, `refresh`, `restart`, `resources`, `diff`, `wait`, `rollback`, `terminate-op`.

**Parsing rules:** treat the first token as the application name and the last token as the action. If there are more than two tokens, join all middle tokens (reinsert spaces) to form the `Resource` string. Action is case-insensitive; application and resource strings preserve the user's casing.

### Action → command map

| Action | Command |
|---|---|
| `sync` | `argocd app sync <App>` |
| `sync` (with `<Resource>` = `group:kind:namespace/name`) | `argocd app sync <App> --resource <Resource>` |
| `sync-prune` | Prune approval flow → `argocd app sync <App> --prune` |
| `refresh` | `argocd app get <App> --refresh` |
| `resources` | `argocd app resources <App>` |
| `diff` | `argocd app diff <App>` |
| `wait` | `argocd app wait <App> --health --sync` |
| `rollback <revision>` | `argocd app rollback <App> <revision>` |
| `restart` (with `<Resource>` = `<namespace> <kind> <name>`) | `argocd app actions run <App> <Kind> <Name> restart --namespace <ns>` |
| `terminate-op` | `argocd app terminate-op <App>` |

### Resource formats

- **Selective sync** (`sync` + resource): Argo CD CLI form `group:kind:namespace/name` (e.g. `apps:Deployment:qa-ns/api-gateway`). Cluster-scoped kinds omit the namespace.
- **Restart** (`restart` + resource): space-separated three tokens `<namespace> <kind> <name>` (e.g. `qa-ns deployment api-gateway`). Agent maps `kind` to `Deployment` / `StatefulSet` / `DaemonSet` for the `argocd app actions run` call.

## Required Environment

```bash
ARGOCD_SERVER            # required in direct/local mode (e.g. argocd.example.com)
ARGOCD_USERNAME          # default: admin
ARGOCD_PASSWORD          # required for login
ARGOCD_GRPC_WEB          # default: true
ARGOCD_HTTP_TIMEOUT      # default: 30 (seconds)
```

## Setup

1. Add `ARGOCD_*` variables to repo root `.env` (see `.env.example`).
2. Recreate `sre-agent` if the container was already running: `docker compose up -d --force-recreate sre-agent`.
3. Verify: `argocd account get-user-info` (or `argocd login` on first use if no session token yet).

## Workflow

1. Agent verifies the session is active: `argocd account get-user-info`. On failure, print the login one-liner from [Setup](#setup) and refuse further action.
2. Agent parses the shorthand: first token = app, last = action, middle = optional resource.
3. Agent classifies the app using the 5-step regex in [Environment Classification](#environment-classification).
4. Agent looks up the action's tier and applies the gate:
   - Tier A → run directly
   - Tier B-light on non-prod → run directly
   - Tier B-gated on non-prod → show command, wait for "yes"
   - Tier B-light on prod/stg allowed subset → require app-name echo
   - Blocked verbs on prod/stg → refuse with redirect
   - `sync-prune` → trigger the two-step approval flow
   - Unknown app + Tier B → prompt user to classify
5. Agent executes the command and emits the Output Contract.

## Output Contract

- **App**: name, classification (prod/stg/non-prod/unknown), target cluster + namespace (from `app get`)
- **State**: sync status, health status, last-sync revision + timestamp
- **Command run**: exact `argocd` invocation
- **Evidence**: `argocd app history <app>` reference; related resources from `argocd app resources <app>`
- **KB Context Stamp**: commit SHA, branch, last commit date, loaded KB files with their `Last Reviewed`, product-line mode
- **Errors**: surface `argocd account can-i <action> applications/<app>` as the next-step diagnostic

## Known Limitations

- **No SSO**: audit logs record `admin` for every action. Per-engineer identity is a future enhancement.
- **Single-instance** model: target prod Argo CD by overriding `ARGOCD_SERVER`, not via a `--env` flag. Prod guardrails are app-name driven.
- **Prune approval** relies on conversation memory — chat reset mid-flow requires restart.
- **Sync windows**: skill surfaces when a sync is blocked by an Argo CD sync window but never attempts to override.
- **`app wait`** returns on timeout; skill reports elapsed time so user can decide whether to re-run.

## Troubleshooting

- `rpc error: code = Unauthenticated` — token expired; re-run the login step from Setup.
- `context deadline exceeded` — toggle `ARGOCD_GRPC_WEB` (some ingress configurations require it, others forbid it).
- `permission denied` on an action — run `argocd account can-i <action> applications/<app>` for RBAC diagnosis.
- `sync window is active` — print the window info and refuse to override. User must wait or go through Argo CD UI with elevated privileges.
- `connection refused` / TLS errors — check `ARGOCD_SERVER` is correct and reachable from your network.
