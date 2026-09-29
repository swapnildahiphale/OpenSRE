# Jira Ticket Follow-up Implementation Plan

> **For agentic workers:** Implement task-by-task. Steps use checkbox syntax.

**Goal:** Route investigation follow-ups to a linked Jira ticket (agent decides + memory; scheduler clocks + records).

**Architecture:** Extend `investigation_followups` with `ticket_key`. Scheduler, when due and ticket set, calls sre-agent ticket-followup; agent reads Jira, may resolve memory and/or post comment; scheduler records nudge-sent or abandon. No ticket → existing Teams/Web path.

**Tech Stack:** Postgres/Alembic, FastAPI (config-service + sre-agent), opensre-scheduler, existing `project-jira` client patterns.

## Global Constraints

- Scheduler never writes Episode memory.
- Ticket attach = explicit paste only (`/browse/KEY` or `ticket: KEY`).
- Jira only; TEMP nudge windows unchanged for now.

---

## Task 1: Schema + config-service API

**Files:**
- `config_service/alembic/versions/20260918_followup_ticket.py` (new)
- `config_service/src/db/investigation_followups.py`
- `config_service/src/api/routes/investigation_followups.py`
- `config_service/tests/test_investigation_followups_*.py`

- [ ] Add `ticket_key`, `ticket_provider` columns
- [ ] Include in `_to_dict` / upsert optional fields
- [ ] `POST /{correlation_id}/attach-ticket` `{ticket_key, ticket_provider=jira}`
- [ ] Tests

## Task 2: Agent ticket follow-up brain

**Files:**
- `sre-agent/ticket_followup.py` (new)
- `sre-agent/tests/test_ticket_followup.py` (new)
- `sre-agent/server_simple.py` (endpoint + attach on investigate)
- `sre-agent/Dockerfile` (COPY new module)

- [ ] `extract_explicit_ticket_key(text)`
- [ ] `evaluate_ticket_followup(correlation_id, ticket_key)` → action enum
- [ ] Resolved+fix → `apply_resolution`
- [ ] ask/nudge → post Jira comment via skill client
- [ ] `POST /internal/episodes/{id}/ticket-followup`
- [ ] On investigate: attach ticket if explicit key in prompt

## Task 3: Scheduler Jira branch

**Files:**
- `opensre-scheduler/scheduler.py`
- `opensre-scheduler/tests/test_scheduler.py`

- [ ] If `ticket_key`: call agent ticket-followup; on resolved→abandon; on ask/nudge→nudge-sent; on skip/defer→return
- [ ] Else existing Teams/Web path
- [ ] Tests

## Task 4: Rebuild + smoke

- [ ] Rebuild config-service, sre-agent, scheduler
- [ ] Migrate; health OK
