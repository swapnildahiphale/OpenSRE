# GitHub CLI Command Reference

Complete command reference for `gh`. Run `gh <command> --help` for details.

Safety note:
- Prefer `GITHUB_TOKEN` in repo `.env` for Docker/headless runs.
- Never paste real tokens into shared chat/log output.
- Confirm targets before merge/create/delete operations.

## Authentication

### Environment (OpenSRE default)

```bash
# In repo root .env (passed to sre-agent via docker-compose env_file)
GITHUB_TOKEN=ghp_...
# GITHUB_REPOSITORY=owner/repo   # optional default
# GH_HOST=github.example.com       # GitHub Enterprise only
```

`gh` also accepts `GH_TOKEN` (same precedence as `GITHUB_TOKEN`).

### Interactive (host only — not for Docker)

```bash
gh auth login --web
gh auth status
gh auth logout
```

## Repository

```bash
gh repo list [--limit 20] [--source owner]
gh repo view [owner/repo]
gh repo clone owner/repo
gh repo fork owner/repo
```

## Pull Requests

```bash
gh pr list [--repo owner/repo] [--state open|closed|merged|all] [--limit 20]
gh pr view [<number>] [--repo owner/repo]
gh pr diff [<number>] [--repo owner/repo]
gh pr checks [<number>] [--repo owner/repo]
gh pr status

# Write
gh pr create --title "..." --body "..." [--base main] [--head branch]
gh pr comment <number> --body "..."
gh pr review <number> --approve|--request-changes|--comment --body "..."
gh pr merge <number> [--squash|--merge|--rebase]
gh pr close <number>
```

## GitHub Actions

```bash
gh run list [--repo owner/repo] [--branch BRANCH] [--limit 10]
gh run view <run-id> [--repo owner/repo]
gh run view <run-id> --log-failed
gh run watch <run-id>
gh run rerun <run-id> [--failed]

gh workflow list [--repo owner/repo]
gh workflow view <name|.yml> [--repo owner/repo]
gh workflow run <workflow> [--ref BRANCH]
```

## Issues

```bash
gh issue list [--repo owner/repo] [--state open|closed|all] [--label bug]
gh issue view <number> [--repo owner/repo]
gh issue create --title "..." --body "..."
gh issue comment <number> --body "..."
gh issue close <number>
```

## API Escape Hatch

```bash
gh api repos/owner/repo/pulls/123
gh api search/code -f q='repo:owner/repo error handler'
gh api repos/owner/repo/commits/SHA
gh api repos/owner/repo/actions/runs?per_page=5
```

## JSON Output

```bash
gh pr list --repo owner/repo --json number,title,state,headRefName,url
gh run list --repo owner/repo --json databaseId,status,conclusion,headBranch,url
gh issue list --repo owner/repo --json number,title,state,labels
```

Pipe through `jq` for filtering:

```bash
gh run list --repo owner/repo --json name,status,conclusion --jq '.[] | select(.conclusion=="failure")'
```

## Common Flags

| Flag | Meaning |
|------|---------|
| `-R`, `--repo` | `owner/repo` target |
| `--json` | Machine-readable fields |
| `-q`, `--jq` | Filter JSON output |
| `-t`, `--template` | Go template on JSON output |

When `GITHUB_REPOSITORY` or `GH_REPO` is set in the environment, many commands default to that repository.
