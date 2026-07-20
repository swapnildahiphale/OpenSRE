---
name: memory-search
description: Search OpenSRE memory for past investigations similar to what you are seeing now. Use after you have concrete evidence (error message, failing component, stack trace)—not on vague initial alerts alone.
allowed-tools: Bash(python *)
---

# memory-search

Search OpenSRE memory for past investigations similar to what you are seeing now.

## When to use

Use memory search **after** you have concrete evidence—not on vague initial alerts alone:

- You have an error message, stack trace, or failing job output
- You identified a failing component or service
- A symptom may have been investigated before and you want prior root causes or skills that worked

**Do not** search on ticket titles alone (e.g. "build pipeline failing"). Gather facts first (read Jenkins console, check logs), then search with an enriched query.

## Query guide

Build queries from **symptom + component + system**:

- **Symptom** — what went wrong (OOM, connection pool exhausted, 503, test failure)
- **Component** — where it failed (surveys-module, checkout, payment-db)
- **System** — context (Jenkins, Kubernetes, PostgreSQL)

## Usage

```bash
python .claude/skills/memory-search/scripts/search.py \
  --query "Maven OOM surveys-module test failure Jenkins" --limit 5
```

## JSON output

Returns JSON to stdout:

```json
{
  "success": true,
  "result": {
    "episodes": [...],
    "strategy": "..."
  }
}
```

### `episodes`

Each match includes:

| Field | Description |
|-------|-------------|
| `issue_type` | Classified issue category |
| `root_cause` | Root cause from the past investigation |
| `resolved` | Whether the prior incident was resolved |
| `summary` | Brief investigation summary |
| `skills_used` | Skills that helped resolve it |
| `services` | Affected services |
| `score` | Similarity score (higher = closer match) |

Prioritize resolved episodes with matching root cause and `skills_used`.

### `strategy` (when available)

When two or more strong matches exist, the result may include a `strategy` field with a playbook synthesized from similar past investigations. Use it alongside the individual episodes.

On failure, `success` is `false` and `error` describes the problem. Failures are non-blocking—investigation continues.
