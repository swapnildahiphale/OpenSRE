# Proposal: Investigation Outcome Follow-up (Teams + Web)

**Status:** Draft for review  
**Author:** Amol Kekan  
**Audience:** OpenSRE maintainers (Swapnil Dahiphale and contributors)  
**Related:** Episodic memory, Teams bot, web console investigation runs, investigation lifecycle  
**Date:** 2026-09-05  

---

## 1. Summary

OpenSRE today is strong at **investigation memory** (symptoms, evidence, suspected root cause, suggested remediations) but weak at **resolution memory** (what actually fixed the issue, if anything).

This proposal adds a **lightweight follow-up loop** so OpenSRE can learn confirmed resolutions when users share them, and honestly mark investigations as **abandoned** when nobody follows up.

**Channel model:**
- **Same outcome logic** for all entry points (Teams, Web, future Slack)
- **Different delivery surface** per channel (Teams Adaptive Card vs Web UI panel)

**Core principle:** OpenSRE never invents the fix. It only stores a resolution when a human shares it. Silence → `abandoned`.

---

## 2. Problem statement

### Current behavior

After an investigation, OpenSRE typically:

1. Diagnoses the issue  
2. Shares findings / root cause hypotheses  
3. Suggests possible remediations  
4. Persists an episodic memory episode for future recall  

### Gap

The platform does **not** reliably know:

- Whether the incident was actually resolved  
- Which fix was applied (if any)  
- Whether the successful fix matched OpenSRE’s suggestion  
- How to recommend that fix for similar future incidents  

Existing `Episode.resolved` is closer to “diagnosis complete” than “production issue fixed.”

### Why this matters

Without resolution feedback, memory recall can say:

> “Last time we saw X, we suspected Y and suggested Z.”

With resolution feedback, memory can say:

> “Last time we saw X, the team resolved it by doing Z (confirmed).”

That is the difference between helpful diagnosis memory and compounding operational learning.

---

## 3. Target use case (internal / multi-channel)

This design is optimized for how many teams actually use OpenSRE:

| Reality | Implication |
|--------|-------------|
| Chat often starts from **Microsoft Teams** | Follow-up should prefer the original thread when possible |
| Chat also starts from **OpenSRE Web console** | Follow-up must work on the same investigation/run page |
| Users are often **Dev / QA**, not always Ops | They ask “X is down,” then ask Ops or try a fix |
| Ops often continues in a **new** Teams/Web thread | Outcome must be linkable across threads/actors, not only same-thread |
| Users rarely open a ticket first | Ticket is optional, but when present it is the best join key |
| Users rarely fill long web forms after the fact | One-tap actions beat process-heavy forms |
| Continuous metric watchers burn tokens | No always-on background analysis |

Ticket systems (Jira, etc.) remain useful when present, but **must not be the only path**. When a ticket *is* created for Ops, it becomes the primary way to reconnect a later Ops thread to the original investigation.

---

## 4. Goals and non-goals

### Goals

1. Capture **human-confirmed** resolution text when available  
2. Deliver follow-up **in the same channel** where the investigation started (Teams thread or Web run page)  
3. Make human effort **optional and minimal** (buttons + short text)  
4. Update episodic memory only with trusted resolution data  
5. Mark unresolved / unanswered follow-ups as **`abandoned`** (honest state)  
6. Keep v1 small enough to ship and validate  
7. Keep outcome storage **channel-agnostic** (one model, multiple UIs)  
8. Support **handoff across threads/actors** (QA investigates → Ops resolves in a new thread) when a join key exists  

### Non-goals (v1)

1. Continuous background metric/alert watching  
2. Automatic “infer what changed” analysis when service recovers  
3. Requiring Jira/ticket creation for every investigation  
4. Requiring a separate heavyweight form outside chat / the Web run page  
5. Fully autonomous remediations without human confirmation of outcome  
6. Silent auto-merge of unrelated threads based only on fuzzy symptom similarity (always confirm with human)  

---

## 5. Proposed user flow

Same logic for **Teams** and **Web**. Only the UI delivery differs.

```text
                    Investigation completes
                              │
                              ▼
                 ┌────────────────────────────┐
                 │   Stage A — follow-up UI   │
                 │  (Teams card OR Web panel) │
                 │  What do you want to do?   │
                 └────────────┬───────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   [I'll fix it]        [Need Ops help]        [Ignore]
          │                   │                   │
          │                   │ ask optional      │
          │                   │ ticket ID         │
          │                   │                   │
          └─────────┬─────────┘                   │
                    │                             │
                    ▼                             ▼
         Wait for resolution note      outcome = ignored
         (or timed nudges)             stop follow-ups
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
 User shares fix         No update yet
        │                       │
        ▼                       ▼
 outcome=resolved         T+30m nudge (same channel)
 + fix_summary                  │
 update memory                  │
                          still no update?
                                │
                                ▼
                          T+3h nudge (same channel)
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
            User replies              No reply / still open
                    │                       │
                    ▼                       ▼
         resolved + fix text        outcome = abandoned
         update memory              update memory
                                    stop follow-ups
```

---

## 6. Channel delivery: Teams vs Web

Follow-up is **channel-aware delivery** over a **shared outcome model**.

### 6.0 How Teams works today (important correction)

OpenSRE’s Teams bot is **not Adaptive-Card-first** for normal channel investigations. What users see today (channel / group chat):

| Moment | What Teams shows today |
|--------|-------------------------|
| Progress (“Investigating…”, plan checks) | **Plain text** in the thread (stream/update) |
| Final report (summary / scope / timeline) | **Plain text / markdown** in the same thread — **not** an Adaptive Card |
| Clarifying questions (when agent asks) | **Adaptive Card** with Submit (`opensre.submit_answers`) |
| Final report in **1:1 / personal / Web Chat** | Adaptive Card (`build_final_card`) |
| Welcome / help in personal chat | Adaptive Card |

This matches channel usage: `@OpenSRE investigate <ticket/url>` → threaded text progress → threaded text final report.

So the earlier “Stage A = Adaptive Card in the same thread” line is a **proposed addition**, not a description of current final-report UX. Channel finals already deliberately use `plain_text_final` / `build_final_text` (see `teams-bot` README + `investigation_runner`).

**Implication for follow-up design:** Stage A/B for channel must either:

1. **Post a new Adaptive Card after the plain-text final** (recommended for buttons), or  
2. Fall back to **reply-keyword / short text** (“reply `resolved: …`”) if cards are undesirable in channel  

v1 recommendation: keep the investigation report as plain text (unchanged), then send a **small follow-up Adaptive Card** in the same thread (same pattern already used for clarifying questions).

| | **Started from Teams** | **Started from OpenSRE Web** |
|--|------------------------|------------------------------|
| Investigation report today | Channel: plain text · 1:1: Adaptive Card | Run transcript in Web UI |
| Stage A surface (**proposed**) | **New** follow-up Adaptive Card in the **same thread** (after plain-text final in channel); same idea in 1:1 | Panel / banner on the investigation run page (and/or end of transcript) |
| Nudge surface (**proposed**) | Follow-up Adaptive Card reply in the **same Teams thread** | In-app follow-up on that **same run** when user returns; optional bell/badge on Agent Runs list |
| How user is reached at 30m / 3h | Bot posts into the existing thread (push) | User may be offline → show **pending follow-up** state on the run; when they open Web UI / that run, show Stage B card. Optional later: email / Teams DM if identity exists (not required for v1) |
| Primary action style | Adaptive Card buttons (reuse question-card Action.Execute pattern) | Same buttons in Web UI component |
| Outcome API | Same backend (`investigation_outcomes`) | Same backend |

### 6.1 Why Web nudges cannot be identical to Teams push

Teams can **push** into an active thread.  
Web users often leave the browser after the investigation.

So for Web v1:

1. **Immediate Stage A** on the run page when the investigation finishes (while they are still looking).  
2. Persist `pending_followup` on the run.  
3. At T+30m / T+3h: mark nudge due (server-side schedule).  
4. When the user next opens OpenSRE (home / Agent Runs / that run): show a clear **“Follow-up needed”** banner/card.  
5. If still unanswered after final nudge window → mark **`abandoned`**.

This avoids depending on email and avoids inventing push infrastructure in v1.

### 6.2 Web UX sketch

**On run detail page after investigation completes:**

> What next?  
> [I’ll fix it] [Need Ops help] [Ignore]

**Pending follow-up badge** on Agent Runs list:

> Follow-up due · Investigation: “X is down”

**When opening a run with due nudge:**

> Still open or resolved?  
> [Resolved — share what fixed it] [Still open] [Stop asking]

### 6.3 Entry-channel field

Store on the outcome / run:

| Field | Example |
|-------|---------|
| `entry_channel` | `teams` \| `web` \| `slack` (future) |
| `followup_ref` | Teams `conversation_id` / thread id, or web `run_id` |

Nudges prefer the **current primary follow-up surface**. After an Ops handoff link, that may move from the QA thread to the Ops thread (see §6.4).

### 6.4 Cross-thread / Ops handoff (QA → ticket → Ops new thread)

This is a common real flow:

```text
QA thread (Teams or Web)
   → OpenSRE investigates + suggests fix
   → QA: "Need Ops help" (+ optional ticket)
   → QA creates / shares Jira ticket for Ops
Ops opens a NEW Teams/Web thread with OpenSRE
   → Mentions ticket (or investigation ID)
   → OpenSRE links to original outcome
   → Ops shares what fixed it → same outcome = resolved + memory update
```

**Problem:** Same-thread-only follow-up fails here — Ops never returns to QA’s thread.

**Solution:** Treat the outcome as **actor- and thread-agnostic**, with explicit **join keys**.

#### Join keys (priority order)

| Priority | Join key | How it gets set | How Ops reconnects |
|----------|----------|-----------------|--------------------|
| 1 | `ticket_id` (Jira/etc.) | QA pastes on Stage A “Need Ops help”, or OpenSRE extracts from chat | Ops pastes / mentions same ticket in the new thread |
| 2 | `investigation_id` / `run_id` | Shown on Stage A card + suggested for ticket description | Ops pastes `INV-…` / run id, or “continue investigation …” |
| 3 | Soft match (same org/team + service + open `pending_followup`) | Server-side candidates only | OpenSRE **asks Ops to confirm** link; never silent merge |

Ticket is still optional globally. For this handoff pattern, **encouraging a ticket ID (or investigation ID in the ticket)** is the reliable path.

#### Behavior when Ops starts a new thread

1. Detect join key in Ops message (ticket key regex, explicit investigation id, or “related to …” phrasing).  
2. Lookup open outcomes (`pending_followup`) for that org/team.  
3. If exact match on ticket / investigation id → **auto-link** and acknowledge:  
   > Linked to QA’s investigation of *X* (`TICKET-123`). Prior diagnosis: …  
4. If only soft candidates → Adaptive Card / Web prompt:  
   > Is this the same as [QA investigation summary] / [ticket]?  
   > [Yes, link] [No, new investigation]  
5. On link:  
   - Add Ops thread to `followup_refs[]`  
   - Set `primary_followup_ref` to Ops thread (nudges go here)  
   - Optionally stop or soften nudges on the original QA thread  
   - Keep one outcome record; do not fork memory  
6. Ops can then complete Stage B (`Resolved` + `fix_summary`) from **their** thread. Same memory rules apply.

#### What QA’s Stage A should capture for handoff

On **Need Ops help**:

- Optional **ticket ID** field (primary join key)  
- Always show a short **Investigation ID** QA can paste into the Jira description  
- Copy hint: “Paste this ID (and ticket) when Ops chats with OpenSRE”

#### Without any join key

If Ops starts a fresh thread with no ticket / investigation id and soft match is weak or declined:

- Treat as a **new** investigation (current behavior)  
- Original QA outcome still follows its own nudge → `abandoned` window  
- No invented cross-link  

#### Memory implication

Resolution from Ops updates the **same** outcome / episode as QA’s diagnosis. Future recall becomes:

> “QA investigated X; Ops confirmed fix Z via ticket ABC.”

Not two disconnected memories.

---

## 7. Stage details

### Stage A — right after investigation

**Teams:** After the existing final reply (plain text in channel, card in 1:1), post a **separate follow-up Adaptive Card** in the same thread — do not rewrite the report into a card  
**Web:** Inline panel on run / conversation page  

Prompt (example):

> Investigation complete. What next?
>
> - **I’ll fix it** — when done, share what fixed it so OpenSRE can remember for next time  
> - **Need Ops help** — optionally paste a ticket ID so we can attach it later  
> - **Ignore** — no more follow-ups  

| Choice | Behavior |
|--------|----------|
| I’ll fix it | Expect a later resolution note; schedule nudges if none arrives |
| Need Ops help | Optional ticket ID + always show investigation ID for handoff; schedule nudges; enable cross-thread link when Ops returns with that key |
| Ignore | Stop follow-ups; store `ignored` / treat like abandoned for memory purposes |

### Stage B — timed nudges (same channel)

| When | Purpose |
|------|---------|
| **T+30 minutes** | Soft check: still open or resolved? |
| **T+3 hours** | Final check; then close the follow-up loop |

| Channel | How nudge is delivered |
|---------|------------------------|
| Teams | Bot message / Adaptive Card in the **same thread** |
| Web | Nudge becomes **due**; shown when user returns to the run / Agent Runs list |

Nudge content (example):

> Quick follow-up on this investigation:
>
> - **Resolved** — tell us what fixed it (short note)  
> - **Still open**  
> - **Stop asking**  

If **Resolved**:

- Require or strongly encourage a short `fix_summary`  
- Optional chips: `Restart` / `Rollback` / `Config change` / `Other`  
- Optional: “Was this one of OpenSRE’s suggestions?” → `Yes` / `No` / `Unsure`  
- Write confirmed outcome into memory  

If **Still open** after final nudge (or no reply):

- Mark outcome **`abandoned`**  
- Stop further nudges  
- Preserve investigation diagnosis in memory; do **not** invent a fix  

### Explicit non-behavior

If the issue appears resolved in the outside world but the user never replies:

- **Do not** auto-analyze deploys/logs/metrics to guess the fix (v1)  
- Mark **`abandoned`** (or `unknown`) unless a human shared the resolution  

This keeps memory trustworthy.

---

## 8. Data model (proposed)

New first-class outcome record (name TBD), linked to the investigation/run:

| Field | Description |
|-------|-------------|
| `id` | Unique ID |
| `run_id` / `correlation_id` / `investigation_id` | Stable join key shown to users for handoff |
| `org_id` / `team_node_id` | Tenant context |
| `entry_channel` | `teams` \| `web` \| `slack` (future) |
| `followup_refs` | One or more surfaces: original QA thread/run + linked Ops thread(s) |
| `primary_followup_ref` | Where nudges currently go (may move after Ops link) |
| `status` | `pending_followup` \| `resolved` \| `abandoned` \| `ignored` |
| `path` | `self_fix` \| `ops_help` \| `ignored` \| `unknown` |
| `ticket_id` | Optional (Jira/etc.) — primary cross-thread join key when set |
| `linked_actors` | Optional audit: who started vs who resolved (QA / Ops) |
| `fix_summary` | Human-provided fix text (required when `resolved`) |
| `matched_suggestion` | `yes` \| `no` \| `unsure` \| `null` |
| `source` | `teams_card` \| `teams_nudge` \| `web_panel` \| `web_nudge` \| `ops_linked_thread` |
| `nudge_due_at` | Next nudge time (server-side) |
| `created_by` / `updated_at` | Audit |

### Memory update rules

| Outcome status | Memory write |
|----------------|--------------|
| `resolved` + `fix_summary` | Update episode with confirmed resolution / fix for future recall |
| `abandoned` / `ignored` | Store status as abandoned; keep diagnosis; **no fabricated fix** |
| `pending_followup` | No final resolution memory yet |

---

## 9. Suggested implementation surfaces

| Layer | Change |
|-------|--------|
| **teams-bot** | Stage A card after final reply; schedule 30m/3h thread nudges; handle Adaptive Card actions; detect ticket/investigation id in new threads and offer/perform link |
| **web_ui** | Stage A panel on run detail; “Follow-up due” badge; Stage B when nudge due; optional “Link to investigation / ticket” when starting related work |
| **config-service** | Persist investigation outcome records + APIs (lookup by `ticket_id` / `investigation_id`; multi-`followup_refs`) |
| **sre-agent memory** | On confirmed resolve (from any linked actor/thread), update episode with resolution fields; on abandoned, mark accordingly |

Scheduling can be a simple durable job/queue or deferred tasks keyed by `correlation_id` + `entry_channel` (exact mechanism TBD in implementation design).

### 9.1 Codebase grounding (concrete hooks)

What exists today and where v1 should attach — no new invention of entry points.

#### Teams

| Step | Hook in code |
|------|----------------|
| Final report (keep as-is) | `teams-bot/investigation_runner.py` → nested `send_final_reply()`: channel uses `build_final_text` + `send_text`; 1:1 uses `build_final_card` + `send_card` |
| Stage A card (new) | Immediately **after** `send_final_reply()` in `_run_investigation_body` — always `send_card(build_outcome_followup_card(...))` so channel keeps plain-text report |
| Card pattern to reuse | `teams-bot/card_builder.py` → `build_question_card` (`Action.Execute`, verb `opensre.submit_answers`) |
| Action handler | `teams-bot/bot_handlers.py` → mirror `@app.on_card_action_execute`; new verb e.g. `opensre.outcome_followup`; POST config-service outcomes API (not `/answer`) |
| Thread / join keys today | `sanitize_thread_id(conversation.id)` → agent `thread_id` / config-service `correlation_id`; `run_id` from SSE `run_started` on `InvestigationState` |
| Stage B gap | **No** teams-bot scheduler today. Must persist Teams conversation ref in `followup_refs` for proactive re-entry. Closest existing poll pattern: config-service `ScheduledJob` claim API |

#### Web

| Step | Hook in code |
|------|----------------|
| Stage A panel | `web_ui/src/app/team/agent-runs/[runId]/page.tsx` after transcript when `!isRunning && completed` (reuse `settle` / stream-complete path) |
| Optional inline placement | Below last `InvestigationReport` in `ConversationTranscript.tsx` |
| “Follow-up due” badge | `web_ui/src/app/team/agent-runs/page.tsx` row badges — **next to** `EpisodeResolutionBadge`, do not overload it |
| APIs used today | BFF → `GET /api/v1/team/agent-runs`, run detail, memory episodes; stream via sre-agent SSE |
| Naming collision | Chat “Ask a follow-up…” (`ConversationComposer`) = more investigation turns; Stage A = **outcome** follow-up — keep UI copy distinct |

#### config-service (outcome store)

| Decision | Grounding |
|----------|-----------|
| Where to put outcomes | **New Postgres table** (e.g. `InvestigationOutcome`), same pattern as `AgentFeedback` / `PendingRemediation` in `models.py` + Alembic + `team.py` / `internal.py` routes |
| Join keys | `AgentRun.id` (`run_id`), `AgentRun.correlation_id`, optional `ticket_id`; `trigger_source` already has `web_ui` / `teams` |
| Not Neo4j-primary | Episodes were dropped from Postgres (`20260704_drop_episode_tables`); episodes live in Neo4j only. Outcome record stays in Postgres beside `agent_runs` |
| Nudges | Store `nudge_due_at`; Web = pull-on-visit; Teams = bot poll/claim (reuse scheduled-jobs claim shape or small durable queue) |

#### Memory (sre-agent)

| Fact | Implication |
|------|-------------|
| `Episode.resolved` today | Diagnostic completeness from LLM extract (`memory/extraction.py`) — **not** “production fixed” |
| Write path | `finalize_investigation` → `EpisodeStore.upsert_episode` (MERGE on `correlation_id`) |
| Resolution write (new) | Separate `EpisodeStore.apply_resolution(...)` — **do not** go through `extract_investigation`, so re-extract cannot wipe human `fix_summary` |
| On `resolved` + fix text | Set `fix_summary` / resolution status; optionally bump `effectiveness_score`; re-embed |
| On `abandoned` / `ignored` | Store status; keep diagnosis; no invented fix |

#### Suggested v1 slice (smallest shippable)

1. **config-service:** `InvestigationOutcome` model + create/patch/get-by-`correlation_id` (team + internal)  
2. **Teams:** Stage A card after final + action handler → create outcome (`self_fix` / `ops_help` / `ignored`)  
3. **Web:** Stage A panel on run detail → same API  
4. **Memory:** `apply_resolution` only when outcome becomes `resolved` or `abandoned`  
5. **Defer:** T+30m/T+3h Teams push nudges, Ops cross-thread link soft-match, “matched suggestion?”  

---

## 10. Success metrics

After rollout, evaluate:

1. **Follow-up response rate** (Stage A + nudges), split by `entry_channel` (Teams vs Web)  
2. **% investigations with `resolved` + fix text**  
3. **% marked `abandoned`** (expected to be significant; not a failure)  
4. **Memory usefulness** — similar incidents surface prior confirmed fixes  
5. **User friction** — complaints about nudge spam (cap at 2 nudges)  

---

## 11. Rollout plan

### Phase 1 (this proposal / v1)

- Shared outcome model + APIs  
- **Teams:** Stage A card + 30m/3h thread nudges  
- **Web:** Stage A panel on run page + pending follow-up badge + Stage B when user returns  
- Outcome persistence (`resolved` / `abandoned`)  
- Memory update only on human-shared resolution  
- **Handoff v1:** store optional `ticket_id` + visible `investigation_id`; link new Ops thread on exact ticket/id match; confirm UI for soft candidates  

### Phase 2 (later, optional)

- Optional ticket status enrichment / Jira comment sync when ticket ID present  
- Pre-fill ticket description with investigation id + summary when OpenSRE helps create tickets  
- Stronger Web notifications (email / optional Teams DM if identity linked)  
- Better recall ranking using confirmed fixes  

### Phase 3 (later, optional)

- Sparse recovery hints (not continuous watchers)  
- Bounded auto-correlation with deploys **only as suggestions**, never silent memory writes  

---

## 12. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Users ignore nudges | Accept high `abandoned` rate; diagnosis memory still useful |
| Nudge fatigue | Max 2 nudges; “Stop asking”; same channel only |
| Web users never return | Pending badge on Agent Runs; after window → `abandoned` |
| Bad/wrong fix text | Store attribution (`created_by`); allow edit later |
| Polluting memory with guesses | No auto “what changed” analysis in v1 |
| Ticket dependency | Ticket optional; never block same-thread follow-up |
| Ops new thread never links | Show investigation id on Stage A; encourage ticket paste; soft-match confirm card |
| Wrong thread auto-linked | Exact ticket/id auto-link only; soft match always requires Ops confirm |
| Confusing Stage A with today’s Teams UX | Keep channel final report as plain text; Stage A is an **extra** card after it |
| Channel Adaptive Card friction | Reuse proven question-card Action.Execute path; optional text-reply fallback |

---

## 13. Decision asked from maintainers

Please review and advise:

1. **Approve v1 scope?** Shared outcome model + Teams cards + Web run-page follow-up + cross-thread link via ticket/investigation id  
2. **Naming / home for outcome model?** New table vs extend existing run/episode fields  
3. **Is pull-based Web nudge (show when user returns) acceptable for v1**, vs requiring email push?  
4. **Should “matched OpenSRE suggestion?” be in v1 or deferred?**  
5. **On Ops link, should nudges move fully to the Ops thread**, or continue on both QA + Ops surfaces?  
6. **Channel Stage A:** OK to add a small Adaptive Card after the plain-text final (like question cards), or prefer text-reply keywords only?  

---

## 14. Open questions

1. Exact Adaptive Card / Web panel copy and button labels (Teams Stage A is new; channel finals stay plain text)  
2. Whether `still_open` after final nudge should be a distinct status or fold into `abandoned`  
3. Retention / privacy of fix notes in multi-tenant setups  
4. How aggressively memory-search should prefer confirmed resolutions over diagnosis-only episodes  
5. For Web: should Stage A also appear as a toast/modal immediately when streaming ends, in addition to the run page panel?  
6. Should OpenSRE help **create** the Ops ticket (with investigation id pre-filled), or only accept a pasted ticket id in v1?  
7. Soft-match window: how long / how similar must an open investigation be before we offer “link?”  

---

## 15. Appendix — one-page flow (shareable)

```text
Investigate (Teams OR Web)
        → Stage A (I'll fix / Need Ops / Ignore)
                │
                ├─ Ignore → abandoned, stop
                │
                ├─ I'll fix → wait / nudges → share fix → resolved
                │
                └─ Need Ops (+ ticket / investigation id)
                        │
          ┌─────────────┴──────────────┐
          ▼                            ▼
 Same thread shares fix      Ops opens NEW thread
          │                  with ticket / INV id
          ▼                            ▼
     resolved + memory         Link to same outcome
                               Ops shares fix → resolved
                               (+ memory; one episode)

 If nobody shares fix → nudge → abandoned
```

**Rules:**
- No human-shared fix ⇒ no invented fix ⇒ mark `abandoned`.
- QA thread and Ops thread can share one outcome when joined by ticket / investigation id (or confirmed soft match).

---

## 16. Ask

Requesting feedback/approval to proceed with a detailed implementation design (schema + Teams card contracts + Web run-page UX + memory write path) and a follow-up PR once scope is agreed.
