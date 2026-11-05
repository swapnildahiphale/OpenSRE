# Handoff for Swapnil — Investigation resolution + Jira follow-up

**From:** Amol Kekan  
**Date:** 2026-09-29  
**Branch:** `feature/investigation-resolution-follow-up` (pushed to this repo)  
**Status:** Implemented and manually tested locally (TEMP short cadence). Not merge-ready until TEMP windows are reverted and a full review passes.

---

## 1. Goal (one sentence)

After an investigation, ask on a timer whether the issue was fixed; store **human-confirmed** `fix_summary` on the Episode (or mark **abandoned**). If a Jira ticket is linked, all timed follow-ups go **only to that ticket**.

**Core rule:** OpenSRE never invents the fix. Silence / no confirm after 3 nudges → abandoned.

---

## 2. Docs to read (in order)

| Doc | What it is |
|-----|------------|
| This file | Current implementation status + known gaps + how to run |
| [`docs/superpowers/specs/2026-09-18-jira-ticket-followup-design.md`](../superpowers/specs/2026-09-18-jira-ticket-followup-design.md) | **Locked** Jira ticket follow-up rules (read this) |
| [`docs/superpowers/plans/2026-09-18-jira-ticket-followup.md`](../superpowers/plans/2026-09-18-jira-ticket-followup.md) | Jira slice implementation plan |
| [`docs/proposals/investigation-outcome-followup.md`](./investigation-outcome-followup.md) | Original product proposal (Teams Stage A cards, etc.) |
| [`docs/proposals/investigation-outcome-followup-handoff.md`](./investigation-outcome-followup-handoff.md) | Early chat handoff (pre-implementation) |
| Confluence (if still current) | Investigation Outcome Follow-up design (link in older handoff docs) |

**Note:** Early docs still mention Adaptive Cards / Stage A as product vision. **v1 that shipped in this branch** is: same-thread chat confirm + scheduler nudges (Web/Teams) + Jira ticket path. Stage A Adaptive Cards are **not** in this branch.

---

## 3. Architecture (what landed)

```text
Human turn (/investigate)
  → Episode (Neo4j): diagnosis + resolution_status
  → investigation_followups (Postgres): nudge clock, channel, ticket_key

Silence → opensre-scheduler claims due rows
  → if ticket_key: POST sre-agent ticket-followup (read Jira, maybe resolve / comment)
  → else Teams nudge OR Web chat-bubble nudge
  → nudge-sent | reschedule | abandon

Human says fix in chat → agent resolve_episode → Episode confirmed + stop clock
```

| Piece | Location |
|-------|----------|
| Followup table + APIs | `config_service/src/db/investigation_followups.py`, `.../routes/investigation_followups.py` |
| Migrations | `20260916_investigation_followups`, `20260918_followup_ticket` |
| Scheduler | `opensre-scheduler/` (+ compose + Helm template) |
| Confirm tool | `sre-agent/resolution_tool.py` (`resolve_episode`) |
| Ticket brain | `sre-agent/ticket_followup.py` |
| Investigate upsert / priming / web-nudge | `sre-agent/server_simple.py` |
| Auto-attach on Jira create | `sre-agent/agent.py` PostToolUse hook |
| Teams nudge | `teams-bot/nudge_handler.py` |
| Web UI badge / transcript / drawer | `web_ui/...` |

---

## 4. Behavior locked in code (product)

### Cadence

- Intended production: **30m → 3h → 24h**, max **3** nudges, then abandon.
- **Currently TEMP in code:** **1m / 2m / 3m** in:
  - `config_service/.../investigation_followups.py` (`_WINDOW`)
  - `opensre-scheduler/scheduler.py` (`WINDOW`)
  - `sre-agent/ticket_followup.py` (`_ACTIVITY_WINDOW`)
- **Must revert before merge.**

### Reset rules

- Human continues chat (`upsert` `still_open=true`) → restart at **1 of 3** (clears count + last nudge; can reopen abandoned).
- Ticket attach (paste or successful create) → Jira-only + restart at **1 of 3**.
- Ordinary Jira WIP comments → **do not** reset the counter; may **soft-defer** (push `nudge_due_at` only via `/reschedule`).

### Jira path

- Ticket linked → no Web/Teams timed nudges for that clock.
- Done **without** explicit fix-in-comments → **ask assignee** comment (do **not** treat Jira resolution boilerplate “Work has been completed…” or ticket description as the fix).
- Done **with** clear fix language in comments → `apply_resolution` + stop.
- Still open + recent human comment → soft-defer; quiet → nudge N of 3.

### Attach

- Explicit paste: `/browse/KEY`, `ticket: KEY`, sole-key message.
- Auto-attach: `create_issue.py` **or** inline REST create that prints `Created: KEY` (+ Jira signals / browse URL).

---

## 5. What was tested locally (Amol)

- Web investigation → followup row → TEMP nudges as chat bubbles (“N of 3”).
- Continue chat → counter reset to 1 of 3 (after fix for “stuck at 3 of 3”).
- Create Jira ticket mid-chat (inline `requests` create) → needed broader auto-attach (fixed).
- Ticket path: comment on Jira; Done with no fix details → ask-assignee (after fixing false resolve on resolution.description).
- A disposable test Jira ticket was used for wrap-up; not a production incident.

Credentials for local Jira were only in **gitignored** `.env` (from Cursor `mcp.json`). **Do not commit `.env`.**

---

## 6. Known gaps / follow-ups for you

1. **Revert TEMP windows** to 30m / 3h / 24h (three files above) + update tests that assert minute windows.
2. Stage A Adaptive Cards (Teams) — deferred; original proposal still describes them.
3. Optional: recognize “test only / close thread / no prod impact” comments as stop without fix-confirm regex.
4. Soft-defer “once” vs “while hot”: current rule is time-based recent human comment within activity window.
5. Full CI / review pass before merge to `main`.
6. Helm/chart + compose for `opensre-scheduler` — verify in a clean env.

---

## 7. How to run locally (no Amol secrets)

```bash
cp .env.example .env
# Set ANTHROPIC_API_KEY (and optional JIRA_* for ticket path — Cloud or DC; see .env.example)
docker compose up --build
# or: make dev
```

Useful checks:

```bash
# Followup rows
docker exec -it opensre-postgres psql -U opensre -d opensre -c \
  "SELECT correlation_id, ticket_key, nudge_count, nudge_due_at, stopped_at FROM investigation_followups ORDER BY updated_at DESC LIMIT 5;"

docker logs -f opensre-scheduler
```

---

## 8. Secrets checklist for this branch

- `.env` is gitignored — must never be committed.
- No Jenkins / Jira / Anthropic tokens belong in this PR.
- Test fixtures may use example hostnames; they are not live credentials.

---

## 9. Suggested next steps for Swapnil

1. Pull this branch; skim this handoff + Jira design spec.
2. Revert TEMP cadence; run unit tests (`config_service`, `sre-agent`, `opensre-scheduler`).
3. Smoke-test Web path, then Jira path with **your** Jira creds in local `.env`.
4. Open PR to `main` when ready; call out TEMP revert + any product questions in the PR body.
