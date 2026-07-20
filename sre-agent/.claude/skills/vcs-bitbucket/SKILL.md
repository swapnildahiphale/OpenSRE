---
name: vcs-bitbucket
description: Bitbucket Data Center and Cloud repos, pull requests, branches, issues, webhooks, and pipelines via bkt CLI. Safe read-before-write workflow. Use when investigating PR failures, repo state, or Bitbucket pipeline issues.
allowed-tools: Bash(bkt *)
---

## Authentication

**IMPORTANT**: In proxy/production mode, credentials may be injected automatically.
Do not assume `BKT_TOKEN` is visible in the shell — run the smoke test below before mutating commands.

In **direct/local mode**, OpenSRE uses **environment-variable auth** (no `bkt auth login` required). Set in repo root `.env` (passed to the sre-agent container via docker-compose):

| Variable | Required | Description |
|---|---|---|
| `BKT_TOKEN` | Yes | Atlassian API token (Cloud) or PAT (Data Center). Bypasses OS keychain. |
| `BKT_HOST` | Yes | `https://bitbucket.org` (Cloud) or `https://bitbucket.example.com` (DC) |
| `BKT_USERNAME` | Cloud: yes | Atlassian account **email** (Cloud API tokens). DC: PAT owner username. |
| `BKT_WORKSPACE` | Cloud: recommended | Default workspace slug (e.g. `your-workspace`) |
| `BKT_PROJECT` | DC: recommended | Default project key |
| `BKT_REPO` | No | Default repo slug when commands omit `--repo` |

The default workspace comes from `BKT_WORKSPACE` in the repo root `.env`, which is passed into the sre-agent container via docker-compose `env_file`. Omit `--workspace` on commands unless you need to override that default. Do not hardcode workspace names in command examples.

See `.claude/skills/vcs-bitbucket/.env.example` for templates.

Verify before running commands (read-only smoke test — works in Docker and on host):

```bash
bkt repo list --limit 1
```

Expected: at least one repository line for your workspace (e.g. `your-workspace/<repo-slug>`).

On **macOS host only**, `bkt auth status` may also show `token source: BKT_TOKEN` when env vars are set. In the **sre-agent container** (Linux), `bkt auth status` / `bkt auth doctor` only inspect libsecret/keychain and will say "No hosts configured" even when `BKT_*` env auth works — do not treat that as a failure if `bkt repo list` succeeds.

**Host-only fallback:** `bkt auth login ... --web` stores credentials in macOS Keychain — that does **not** propagate into Docker. Prefer `BKT_*` in `.env` for container runs.

**Dependency check:** `bkt --version` must succeed. The binary is pre-installed in the sre-agent Docker image; on the host install via `brew install avivsinai/tap/bitbucket-cli`.

# Skill: Bitbucket CLI (Portable)

Use this skill for Bitbucket operations from terminal-based agents.

## Cross-Compatibility

This skill is repository-local and tool-agnostic.
It works in Codex, Claude Code, Cursor, and other IDE agents via the `bkt` CLI.

## Token Scopes

You can name the Bitbucket token whatever you want. As an example, `opensre-bitbucket` is a reasonable token name for this skill.

If you are using a Bitbucket token for app/API access, the configured scopes should include:

Read:

- `read:user:bitbucket`
- `read:issue:bitbucket`
- `read:pullrequest:bitbucket`
- `read:repository:bitbucket`

Write:

- `write:issue:bitbucket`
- `write:pullrequest:bitbucket`
- `write:repository:bitbucket`

These scopes match the read/write workflows documented in this skill for repositories, pull requests, and Bitbucket issues.

## Safe Workflow

**OpenSRE / Docker:** Credentials are injected via `BKT_*` environment variables. **Do not** run `bkt auth status` or `bkt auth login` as a prerequisite — on Linux those commands report "No hosts configured" even when env auth works. **Start with** `bkt repo list --limit 1`; if it returns repos, proceed.

1. Confirm exact target host/project/workspace/repo/PR before execution.
2. Start with read-only commands (`bkt repo list`, `view`, `pr list`) before any mutation.
3. For mutating commands (`create`, `edit`, `merge`, `delete`, `grant`, `run`), confirm the exact command and target in the response before running.
4. Do not ask the user for credentials when `bkt repo list` succeeds — env auth is already configured.
5. Do not use `--allow-insecure-store` unless the user explicitly requests it and accepts the risk.
6. After each write, immediately verify with a read command and report resulting IDs/state.

## Read/Search Commands

```bash
bkt repo list --limit 20
bkt repo view <slug>
bkt pr list --state OPEN --limit 20
bkt pr view <id>
bkt branch list
bkt webhook list
bkt pipeline list
```

Cloud issue tracking:

```bash
bkt issue list --state open
bkt issue view <id> --comments
```

## Write Commands

Pull request actions:

```bash
bkt pr create --title "feat: ..." --source feature/x --target main
bkt pr comment <id> --text "..."
bkt pr merge <id>
```

Repository and branch actions:

```bash
bkt repo create <name> --description "..."
bkt branch create <name> --from main
bkt branch delete <name>
```

Webhooks/pipelines:

```bash
bkt webhook create --name "CI" --url https://ci.example.com/hook --event repo:refs_changed
bkt pipeline run --ref main
```

Permissions (DC):

```bash
bkt perms project grant --project <KEY> --user <user> --perm PROJECT_WRITE
bkt perms repo grant --project <KEY> --repo <slug> --user <user> --perm REPO_WRITE
```

## Output and API Escape Hatch

```bash
bkt pr list --json
bkt pr list --yaml
bkt api /rest/api/1.0/projects --param limit=100 --json
```

## References

- Full command appendix: `.claude/skills/vcs-bitbucket/references/commands.md`

## Troubleshooting

| Symptom | Meaning | Do this |
|---------|---------|---------|
| `newosproc`, `failed to create new OS thread`, `fork: Resource temporarily unavailable` | Process/thread budget exhausted (container PID cap or fork storm) | Stop spawning new tools; use **one** Bitbucket REST call via `curl -u "$BKT_USERNAME:$BKT_TOKEN"` or a single `python3` script |
| `bkt repo list` fails with above | Environment constraint, not auth | Do **not** install `gh`, do **not** dump `env`/`printenv`, do **not** retry `bkt` in a tight loop |
| Auth works via curl Basic but Bearer 401 | Wrong auth mode | Prefer Basic auth with `BKT_USERNAME` + `BKT_TOKEN` (already documented for Cloud) |

**REST fallback** (when `bkt` cannot fork):

```bash
curl -s -u "${BKT_USERNAME}:${BKT_TOKEN}" \
  "https://api.bitbucket.org/2.0/workspaces/${BKT_WORKSPACE}/search/code?search_query=dynamic-config.json"
```

Adjust host/path for Data Center (`${BKT_HOST}/rest/api/1.0/...`). One curl or one short script — no parallel tool storms.

## Best Practices

- Keep host/context explicit on every command in multi-tenant environments.
- Prefer scoped contexts over repeatedly passing project/workspace flags.
- Report command output facts only; do not infer missing server state.
- For write failures, re-read current state before retrying.
