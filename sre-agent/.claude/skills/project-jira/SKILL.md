---
name: project-jira
description: Jira issue tracking and incident management. Use when creating, searching, or updating Jira issues. Supports JQL queries for incident ticket analysis and alert fatigue tracking.
allowed-tools: Bash(python *)
---

# Jira Integration

## Authentication

**IMPORTANT**: In proxy/production mode, credentials are injected automatically by a proxy layer. Do NOT check for `JIRA_API_TOKEN` or `JIRA_EMAIL` in environment variables in that mode — they won't be visible to you. Just run the scripts directly; authentication is handled transparently.

In **direct/local mode** the scripts also support self-hosted Jira Data Center via a Personal Access Token (PAT). Set the following env vars (see `.env.example` for the full block):

- Cloud (atlassian.net): `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`. Leave `JIRA_AUTH_SCHEME`/`JIRA_API_VERSION` unset → defaults to Basic auth + REST API v3 (ADF bodies).
- Data Center (self-hosted): `JIRA_URL`, `JIRA_API_TOKEN`, `JIRA_AUTH_SCHEME=bearer`, `JIRA_API_VERSION=2`. Omit `JIRA_EMAIL`. The token is sent as `Authorization: Bearer <token>` and requests go to `/rest/api/2`.

Configuration environment variables you CAN check (non-secret):
- `JIRA_URL` - Jira instance URL (e.g., `https://your-company.atlassian.net` for Cloud, `https://jira.yourcorp.com` for Data Center)
- `JIRA_API_VERSION` - `3` (Cloud, default) or `2` (Data Center)
- `JIRA_AUTH_SCHEME` - `bearer` for Data Center PAT auth; unset for Cloud Basic auth

### Body format note (v2 vs v3)
Jira Cloud (v3) uses Atlassian Document Format (ADF JSON) for `description`/`body` fields. Jira Data Center (v2) uses **Jira Wiki Markup** — a plain string that supports rich formatting: `*bold*`, `_italic_`, `||...||` tables, `{code}...{code}` blocks, headings, lists, etc. The scripts auto-pick the right format from `JIRA_API_VERSION`, so callers can pass the same `--description` / `--comment` text regardless of flavor; for v2 you may use Wiki Markup syntax to get rich rendering.

### Assignee format note (v2 vs v3)
The `--assignee` arg also adapts to the API version: Cloud (v3) expects the Atlassian **accountId**; Data Center (v2) expects the **username** (e.g. `jane.doe`). The scripts pick the right field key (`accountId` vs `name`) from `JIRA_API_VERSION`.

---

## Available Scripts

All scripts are in `.claude/skills/project-jira/scripts/`

### search_issues.py - Search with JQL
Powerful search using Jira Query Language. Best for finding incident tickets, patterns, action items.
```bash
python .claude/skills/project-jira/scripts/search_issues.py --jql "JQL_QUERY" [--max-results N]

# Examples:
python .claude/skills/project-jira/scripts/search_issues.py --jql "type = Bug AND status != Done AND created >= -7d"
python .claude/skills/project-jira/scripts/search_issues.py --jql "labels = incident AND created >= -30d" --max-results 50
```

### get_issue.py - Get Issue Details
```bash
python .claude/skills/project-jira/scripts/get_issue.py --issue-key PROJ-123
```

### create_issue.py - Create New Issue
```bash
python .claude/skills/project-jira/scripts/create_issue.py --project PROJ --summary "Title" --description "Details" [--type Bug] [--priority High] [--labels "incident,p1"]
```

### update_issue.py - Update Existing Issue
```bash
python .claude/skills/project-jira/scripts/update_issue.py --issue-key PROJ-123 [--summary "New title"] [--status "In Progress"] [--priority High]
```

### add_comment.py - Add Comment
```bash
python .claude/skills/project-jira/scripts/add_comment.py --issue-key PROJ-123 --comment "Investigation findings..."
```

### list_issues.py - List Project Issues
```bash
python .claude/skills/project-jira/scripts/list_issues.py --project PROJ [--max-results 20]
```

---

## JQL Quick Reference

### Common Patterns
```
# Recent bugs
type = Bug AND created >= -7d ORDER BY created DESC

# Open incidents
type = Incident AND status != Done

# By label
labels IN ("incident", "p1", "alert-tuning")

# Text search
summary ~ "high CPU" OR description ~ "timeout"

# Stale issues
updated <= -90d AND status != Done
```

### Operators
| Operator | Meaning | Example |
|----------|---------|---------|
| = | Equals | `status = Done` |
| != | Not equals | `status != Done` |
| ~ | Contains text | `summary ~ "error"` |
| IN | In list | `status IN ("Open", "In Progress")` |
| >= | Greater/equal | `created >= -7d` |
| ORDER BY | Sort | `ORDER BY created DESC` |

---

## Investigation Workflow

### Incident Ticket Analysis
```
1. Search for related incidents:
   search_issues.py --jql "type = Incident AND created >= -30d"

2. Get details of specific incident:
   get_issue.py --issue-key INC-456

3. Add investigation findings:
   add_comment.py --issue-key INC-456 --comment "Root cause: ..."

4. Update status:
   update_issue.py --issue-key INC-456 --status "Resolved"
```
