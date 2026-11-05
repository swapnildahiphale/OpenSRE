# Handoff: Investigation Outcome Follow-up (chat → next session)

**Purpose:** Carry context into a new chat (e.g. with Superpowers plugin).  
**Date of discussion:** 2026-09-05 → 2026-09-16  
**Author of proposal:** Amol Kekan  
**Reviewer / collaborator:** Swapnil Dahiphale  

**Primary proposal:** [`investigation-outcome-followup.md`](./investigation-outcome-followup.md)  
**Especially:** §6 (Teams vs Web), §7 (Stage A/B), **§9.1 Codebase grounding**

---

## 1. One-sentence goal

After an investigation, capture **human-confirmed** resolution (or honestly mark **abandoned**) so episodic memory learns what actually fixed the issue — not only what was diagnosed.

**Core rule:** OpenSRE never invents the fix. Silence → `abandoned`.

---

## 2. Problem vs today

| Today | Gap |
|-------|-----|
| Strong diagnosis memory (symptoms, evidence, suspected RCA, suggestions) | Weak **resolution** memory |
| `Episode.resolved` ≈ diagnostic completeness | Not “production issue fixed” |
| Teams channel: plain-text final report in thread | No structured “what next / what fixed it” |
| Users often reply with fix intent in chat | That text is not stored as confirmed outcome |

---

## 3. Proposed UX (channel-aware, same outcome model)

| Channel | Stage A (right after investigation) | Later nudges |
|---------|--------------------------------------|--------------|
| **Teams** | After existing final reply (plain text in channel, card in 1:1), post a **separate** Adaptive Card in the **same thread** — do **not** rewrite the report into a card | Same thread (T+30m / T+3h) — may defer in v1 |
| **Web** | Inline panel on run / conversation page | Pull-on-return badge on Agent Runs (v1) |

**Stage A choices:** I'll fix it | Need Ops help | Ignore  

**Stage B (if shipped):** Resolved (+ fix note) | Still open | Stop asking  

---

## 4. Clarifications from discussion

### Why Adaptive Card?

- One-tap buttons (low friction vs reply keywords)
- Same pattern as clarifying-question cards (`Action.Execute`)
- Keeps channel **report as plain text**; card is only for actions
- Cleaner optional ticket / investigation ID fields

### Why “separate” card — and is it a new thread?

- **Same thread.** “Separate” = a **new message** after the final report, not a new conversation.
- Do **not** fold Stage A into the final report message (would force rewriting channel finals into cards).

### How Teams chat works today vs proposal

```text
TODAY:
  @OpenSRE → Investigating… → plain-text report → optional chat replies → stop
  Memory: diagnosis episode only

PROPOSAL:
  same as today through the report
  → NEW Stage A card (same thread)
  → wait for human fix note (or nudge / abandon)
  → Memory: diagnosis + confirmed fix_summary (or abandoned)
```

---

## 5. Real Teams example (used in discussion)

Thread: Jenkins deploy succeeded but Argo sync incomplete (`or1uat-cai` / `agent-assist`).

Flow observed:

1. OpenSRE diagnoses partial Argo sync  
2. Recommends `argocd app sync …`  
3. Swapnil syncs manually, asks OpenSRE to validate  
4. OpenSRE finds deeper issue: Synced but Degraded — missing Secret / onboarding gap  
5. Swapnil: “We'll onboard this service in or1uat-cai”  
6. OpenSRE: “Ping me when onboarding is done”

**Why it matters:** Humans already almost complete the loop in chat; OpenSRE does not store a structured `fix_summary`. Multi-turn (diagnose → validate → deeper RCA) means Stage A must not block further investigation turns.

---

## 6. Swapnil feedback so far

> Yes but did not get a chance to work fully on it. basically need to ground it to the codebase and see how we can implement it

**Response direction:** Grounded proposal in code (§9.1); discuss in chat first; update Confluence once finalized.

Meeting prep (Amol ↔ Swapnil) happened around 2026-09-16; decisions from that meeting may still need to be recorded here after the fact.

---

## 7. Codebase grounding (summary of §9.1)

### Teams

| Step | Hook |
|------|------|
| Final report (unchanged) | `teams-bot/investigation_runner.py` → `send_final_reply()` — channel: `build_final_text`; 1:1: `build_final_card` |
| Stage A | **After** `send_final_reply()` in `_run_investigation_body` → `send_card(build_outcome_followup_card(...))` |
| Pattern to reuse | `card_builder.build_question_card` + `bot_handlers` `@app.on_card_action_execute` (`opensre.submit_answers`) |
| New verb (suggested) | e.g. `opensre.outcome_followup` → POST config-service outcomes API (not `/answer`) |
| Join keys today | `sanitize_thread_id` → agent `thread_id` / `correlation_id`; `run_id` from SSE |
| Stage B gap | No teams-bot scheduler; must persist conversation ref in `followup_refs` |

### Web

| Step | Hook |
|------|------|
| Stage A panel | `web_ui/.../agent-runs/[runId]/page.tsx` when run completed |
| Follow-up due badge | `agent-runs/page.tsx` — **next to** `EpisodeResolutionBadge`, do not overload it |
| Naming collision | Composer “Ask a follow-up…” = more investigation turns ≠ outcome Stage A |

### config-service

- New Postgres **`InvestigationOutcome`** (pattern like `AgentFeedback` / `PendingRemediation`)
- Join: `run_id`, `correlation_id`, optional `ticket_id`
- Episodes are Neo4j-only; outcomes stay Postgres beside `agent_runs`

### Memory

- `Episode.resolved` today = diagnostic completeness (LLM extract)
- New: `EpisodeStore.apply_resolution(...)` — **not** via `extract_investigation`
- `resolved` + `fix_summary` → update + re-embed; `abandoned` → status only, no invented fix

### Suggested v1 slice (smallest shippable)

1. Outcome model + API (config-service)  
2. Teams Stage A card + handler  
3. Web Stage A panel  
4. Memory `apply_resolution` on resolve/abandon  
5. **Defer:** timed Teams nudges, Ops cross-thread soft-match, “matched suggestion?”

---

## 8. Open decisions (ask Swapnil / decide before Confluence)

1. Stage A–only v1 vs Stage A + nudge skeleton?  
2. Adaptive Card after plain-text final vs text keywords only?  
3. When Stage A fires on multi-turn threads (first report vs “user taking over”)?  
4. Web pull-on-return OK for v1?  
5. New outcome table vs fields on `agent_runs` / episode?  
6. Ops handoff (ticket/investigation id) in v1 or later?  
7. On Ops link: nudges move to Ops thread or both?  
8. “Matched OpenSRE suggestion?” in v1 or later?  
9. Success metric that matters most (memory hit rate, less repeat incidents, etc.)?

---

## 9. Files / artifacts

| Path | Role |
|------|------|
| `docs/proposals/investigation-outcome-followup.md` | Full proposal (+ §9.1 grounding) |
| `docs/proposals/investigation-outcome-followup-handoff.md` | This handoff |
| `teams-bot/investigation_runner.py`, `card_builder.py`, `bot_handlers.py` | Teams hooks |
| `web_ui/src/app/team/agent-runs/...` | Web hooks |
| `config_service` `AgentRun` / `PendingRemediation` / `AgentFeedback` | Patterns for outcome store |
| `sre-agent/memory/` | Episode model + upsert; needs `apply_resolution` |

**Note:** Proposal/handoff may be local-only until committed/pushed. Confluence update deferred until finalized in discussion.

---

## 10. Suggested prompt for a new Superpowers chat

Copy-paste starter:

```text
Read docs/proposals/investigation-outcome-followup.md (especially §9.1)
and docs/proposals/investigation-outcome-followup-handoff.md.

We are implementing investigation outcome follow-up (Stage A after Teams/Web
investigations → store human-confirmed fix or abandoned → update episodic memory).

Constraints:
- Channel final reports stay plain text; Stage A is a separate Adaptive Card in the same thread
- Do not overload Episode.resolved (diagnostic) with production-fix outcome
- Prefer smallest v1: outcome API + Teams Stage A + Web Stage A + apply_resolution
- Defer timed nudges / Ops soft-match unless we decide otherwise

Next: use Superpowers workflow to plan/implement v1 (or update Confluence once decisions below are locked).
Open decisions are listed in the handoff §8.
```

---

## 11. Status

| Item | Status |
|------|--------|
| Product proposal drafted | Done |
| Adaptive Card / same-thread clarified | Done |
| Codebase grounding §9.1 | Done (local doc) |
| Discuss with Swapnil | In progress / meeting held — **capture outcomes here** |
| Confluence doc update | **Waiting** until finalized |
| Implementation | Not started |
