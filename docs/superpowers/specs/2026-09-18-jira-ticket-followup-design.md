# Jira ticket follow-up — design

**Date:** 2026-09-18  
**Status:** Approved (Swapnil + Amol)  
**Extends:** Investigation resolution follow-up (Teams + Web)

## Goal

When an investigation has an **explicitly linked Jira ticket**, all timed follow-ups go to that ticket. When no ticket is linked, keep existing Teams / Web behavior.

## Rules (locked)

1. Ticket present → follow-ups **only on Jira** (never Teams push / Web banner for that clock).
2. Ticket absent → original channel (Teams or Web).
3. Ticket is attached only when a human **explicitly pastes** a ticket ID/link in chat (browse URL or `ticket: KEY`). No silent auto-detect from long investigation text.
4. Jira only for v1.
5. Before each due fire: **scheduler wakes agent**; agent reads Jira and decides.
6. Scheduler **never** updates Episode memory. Agent does all memory writes.
7. Pickup is **on the existing nudge cadence only** (no webhooks / mid-window poll).

## Decision matrix (agent)

At due time, agent fetches the issue + comments:

| Jira state | Agent action | Scheduler delivery |
|------------|--------------|--------------------|
| Resolved/Done **and** fix text found | `apply_resolution` → memory | Stop followup (`stopped_at`); no comment |
| Resolved/Done **and** no fix text | Return `ask_assignee` + comment body | Post Jira comment; `nudge-sent` |
| Still open **and** explicit fix confirm in comments | `apply_resolution` → memory | Stop followup; no comment |
| Still open **and** recent human comment (WIP) | Return `defer` (`recent_activity`) | `reschedule` due only — **do not** bump `nudge_count` |
| Still open, quiet / stale comments | Return `nudge` + comment body | Post Jira comment; `nudge-sent` |
| Active agent run on thread | Return `skip` | Leave due; retry next poll |
| Jira error / missing key | Return `defer` | Leave due; log; retry |

Ordinary ticket progress comments do **not** reset the 1/2/3 counter. Soft-defer only delays the next fire while the ticket is “hot.”

## Service boundary

```
opensre-scheduler          sre-agent                    config-service
     |                         |                              |
     |-- claim due ----------->|                              |
     |-- if ticket_key:        |                              |
     |   POST ticket-followup->|-- read Jira                  |
     |                         |-- maybe apply_resolution     |
     |                         |-- maybe POST Jira comment    |
     |<-- {action, text} ------|                              |
     |-- abandon / nudge-sent -------------------------------->|
     |-- if no ticket_key: existing Teams/Web path            |
```

Pragmatic delivery: **agent posts the Jira comment** when action is `ask_assignee` or `nudge` (it already holds Jira creds / client). Scheduler only advances the clock (`nudge-sent` / `abandon`). Scheduler still owns Teams push + Web `last_nudge_text`.

## Data

`investigation_followups`:

- `ticket_key` nullable string (e.g. `PROJ-123`)
- `ticket_provider` nullable string (`jira` when set)

When `ticket_key` is set, dispatch uses the Jira path.

## Attach

On `/investigate` (and follow-up turns): if prompt explicitly contains a ticket link (`…/browse/KEY` or `ticket: KEY`), upsert/attach `ticket_key` on the followup row.

When a ticket is attached (paste **or** successful agent `create_issue`):
- delivery switches to **Jira-only**
- cadence **restarts at Follow-up 1 of 3** (`nudge_count=0`, fresh `nudge_due_at`)

Human chat activity (`upsert` with `still_open=true`) also restarts the series at 1 of 3 (and reopens abandoned rows).

## Non-goals (this slice)

- ServiceNow / other trackers
- Jira webhooks
- Auto-detect bare keys inside long RCA text
- Stage A Adaptive Card UI (separate)
- Reverting TEMP 5m/10m/15m windows (still local test cadence)
