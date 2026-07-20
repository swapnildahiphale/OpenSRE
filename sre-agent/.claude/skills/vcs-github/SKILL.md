---
name: vcs-github
description: GitHub repos, pull requests, Actions workflows, commits, and issues via gh CLI. Safe read-before-write workflow. Use when investigating PR/CI failures, deployment regressions, or repository state on GitHub.
allowed-tools: Bash(gh *)
---

## Authentication

**IMPORTANT**: In proxy/production mode, credentials may be injected automatically.
Do not assume `GITHUB_TOKEN` is visible in the shell — run the smoke test below before mutating commands.

In **direct/local mode**, OpenSRE uses **environment-variable auth** (no `gh auth login` required). Set in repo root `.env` (passed to the sre-agent container via docker-compose):

| Variable | Required | Description |
|---|---|---|
| `GITHUB_TOKEN` | Yes (or `GH_TOKEN`) | GitHub personal access token (classic or fine-grained). `gh` accepts either name; `GITHUB_TOKEN` is the OpenSRE convention. |
| `GITHUB_REPOSITORY` | No | Default `owner/repo` when commands omit `-R` / `--repo` (alias: `GH_REPO`) |
| `GH_HOST` | Enterprise only | GitHub Enterprise hostname (e.g. `github.example.com`). Use with `GITHUB_ENTERPRISE_TOKEN` or `GH_ENTERPRISE_TOKEN`. |

The default repository comes from `GITHUB_REPOSITORY` in the repo root `.env`, which is passed into the sre-agent container via docker-compose `env_file`. Omit `-R owner/repo` on commands when that default is set. Do not hardcode org or repo names in command examples.

See `.claude/skills/vcs-github/.env.example` for templates.

Verify before running commands (read-only smoke test — works in Docker and on host):

```bash
gh auth status
gh repo list --limit 1
```

Expected: `gh auth status` reports logged in to `github.com` (or your `GH_HOST`) via token from environment; `gh repo list` returns at least one repository line.

On **macOS host only**, `gh auth login` stores credentials in the system keychain — that does **not** propagate into Docker. Prefer `GITHUB_TOKEN` in `.env` for container runs.

**Dependency check:** `gh --version` must succeed. The binary is pre-installed in the sre-agent Docker image; on the host install via `brew install gh`.

# Skill: GitHub CLI (Portable)

Use this skill for GitHub operations from terminal-based agents.

## Cross-Compatibility

This skill is repository-local and tool-agnostic.
It works in Codex, Claude Code, Cursor, and other IDE agents via the `gh` CLI.

## Token Scopes

Fine-grained PAT (recommended) or classic PAT scopes for the workflows below:

Read:

- Repository: Contents, Metadata, Pull requests, Actions (read)
- Optional: Issues (read)

Write (only when mutating):

- Pull requests (write)
- Issues (write)
- Contents (write) — if creating branches/commits via API

Name the token neutrally (e.g. `opensre-github`); do not commit real tokens.

## Safe Workflow

**OpenSRE / Docker:** Credentials are injected via `GITHUB_TOKEN` / `GH_TOKEN`. **Do not** run `gh auth login` as a prerequisite in the container. **Start with** `gh repo list --limit 1`; if it returns repos, proceed.

1. Confirm exact target host/owner/repo/PR/run before execution.
2. Start with read-only commands (`gh repo view`, `gh pr list`, `gh run list`) before any mutation.
3. For mutating commands (`gh pr create`, `gh pr merge`, `gh issue create`), confirm the exact command and target in the response before running.
4. Do not ask the user for credentials when `gh repo list` succeeds — env auth is already configured.
5. After each write, immediately verify with a read command and report resulting IDs/state.

## Read/Search Commands

Repository and branches:

```bash
gh repo list --limit 20
gh repo view owner/repo
gh api repos/owner/repo/branches --jq '.[].name'
```

Pull requests:

```bash
gh pr list --repo owner/repo --state open --limit 20
gh pr view 123 --repo owner/repo
gh pr diff 123 --repo owner/repo
gh pr checks 123 --repo owner/repo
```

GitHub Actions (CI):

```bash
gh run list --repo owner/repo --limit 10
gh run view <run-id> --repo owner/repo
gh run view <run-id> --repo owner/repo --log-failed
```

Commits and issues:

```bash
gh api repos/owner/repo/commits --jq '.[0:5] | .[] | {sha: .sha[0:7], message: .commit.message}'
gh api repos/owner/repo/commits/<sha>
gh issue list --repo owner/repo --state open --limit 20
gh issue view 42 --repo owner/repo
```

Code search (REST):

```bash
gh api search/code -f q='filename:docker-compose.yml repo:owner/repo'
```

When `GITHUB_REPOSITORY` is set, omit `--repo owner/repo` / `-R owner/repo` on subcommands that accept it.

## Write Commands

Pull request actions:

```bash
gh pr create --repo owner/repo --title "feat: ..." --body "..." --base main
gh pr comment 123 --repo owner/repo --body "..."
gh pr merge 123 --repo owner/repo --squash
```

Issues:

```bash
gh issue create --repo owner/repo --title "..." --body "..."
gh issue comment 42 --repo owner/repo --body "..."
```

Workflow dispatch:

```bash
gh workflow run ci.yml --repo owner/repo --ref main
```

## Output and API Escape Hatch

```bash
gh pr list --repo owner/repo --json number,title,state,url
gh run list --repo owner/repo --json databaseId,status,conclusion,headBranch
gh api repos/owner/repo/pulls/123 --jq '.title, .mergeable_state'
```

## Investigation Workflows

### PR / CI failure

```
1. gh pr view <n> --repo owner/repo
2. gh pr checks <n> --repo owner/repo
3. gh run list --repo owner/repo --branch <head-branch> --limit 5
4. gh run view <run-id> --repo owner/repo --log-failed
5. gh api repos/owner/repo/commits/<sha>  (deployed commit)
```

### Recent regressions on main

```
1. gh api repos/owner/repo/commits?sha=main --jq '.[0:10]'
2. gh run list --repo owner/repo --branch main --limit 10
3. gh pr list --repo owner/repo --state merged --limit 10
```

## References

- Full command appendix: `.claude/skills/vcs-github/references/commands.md`

## Troubleshooting

| Symptom | Meaning | Do this |
|---------|---------|---------|
| `HTTP 401: Bad credentials` | Missing/invalid token | Confirm `GITHUB_TOKEN` in repo `.env` and sre-agent container env; token not expired |
| `newosproc`, `fork: Resource temporarily unavailable` | Process/thread budget exhausted | Stop parallel tool storms; use **one** `gh api ...` or **one** `curl -H "Authorization: Bearer $GITHUB_TOKEN"` call |
| `gh auth status` says not logged in but token is set | Token env not visible to subprocess | Export is automatic via docker-compose `env_file`; retry `gh repo list --limit 1` |
| Enterprise 404 on github.com | Wrong host | Set `GH_HOST` and enterprise token vars |

**REST fallback** (when `gh` cannot fork):

```bash
curl -s -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/${GITHUB_REPOSITORY}/pulls?state=open&per_page=5"
```

For GitHub Enterprise, replace `api.github.com` with `https://${GH_HOST}/api/v3`. One curl or one short script — no parallel tool storms.

## Best Practices

- Keep `-R owner/repo` explicit in multi-tenant environments unless `GITHUB_REPOSITORY` is confirmed.
- Prefer `--json` + `--jq` for structured facts over parsing tables.
- Report command output facts only; do not infer missing server state.
- For write failures, re-read current state before retrying.
