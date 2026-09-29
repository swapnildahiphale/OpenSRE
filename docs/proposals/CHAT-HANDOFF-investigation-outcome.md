# Chat handoff — Investigation Outcome Follow-up

**Purpose:** Full context from prior Cursor chat so a **new Superpowers session** can continue without re-deriving decisions.  
**Author:** Amol Kekan  
**Last updated:** 2026-09-16  
**Prior chat transcript:** `~/.cursor/projects/Users-Amol-Kekan-amol-OpenSRE/agent-transcripts/23491500-9e93-4cb7-b5ad-a9bf8dc47a29/`

---

## How to start the new chat (Superpowers)

Paste something like:

```text
Use Superpowers. Start with brainstorming (or writing-plans if scope is already agreed).

Read and treat as source of truth:
1. docs/proposals/CHAT-HANDOFF-investigation-outcome.md
2. docs/proposals/investigation-outcome-followup.md

Goal: turn the Investigation Outcome Follow-up proposal into an implementation plan (then code), after confirming remaining open decisions.

Do NOT invent auto "what changed" analysis or continuous metric watchers.
Do NOT assume channel Teams finals are Adaptive Cards — they are plain text today.
```

---

## Who / repo

| Item | Value |
|------|--------|
| User | Amol Kekan |
| Local repo | OpenSRE checkout (local) |
| Fork remote `origin` | `amolkekan/OpenSRE` |
| Upstream | `swapnildahiphale/OpenSRE` |
| Branch for first PR | `feature/amol_kekan` (setup fixes) |
| Current branch (as of handoff) | `main` tracking `upstream/main` |
| Uncommitted local work | `docs/proposals/` (proposal + this handoff) — **not committed** |

### User preferences (keep)

- No `Co-authored-by: Cursor` on commits unless asked
- No “Made with Cursor” / security-note / `Fixes #N` in PR bodies unless asked
- Commit only when explicitly asked
- Sync from **upstream** before new feature work

---

## Phase 1 — Done: local setup + first contribution

### Problems found on fresh `make dev`

1. External Docker volumes missing → `external volume "opensre-neo4j-data" not found`
2. SSO schema drift → `sso_configs.provider_type does not exist` (later fixed upstream)
3. Org ID mismatch → admin token / UI used null/`undefined`/`org1` vs seeded `local`
4. Token Management 404 → org-wide token list required `node_id == org_id`; seed uses `node_id=root`

### Shipped

- **[PR #50](https://github.com/swapnildahiphale/OpenSRE/pull/50)** — **merged** into `main`
  - `scripts/ensure-volumes.sh` + Makefile `ensure-volumes` on `dev` / `dev-slack` / `dev-teams`
  - `DEFAULT_ORG_ID=local` + `web_ui/src/lib/defaultOrgId.ts` + admin UI fallbacks
  - `org_exists()` for token listing
  - Explicitly **excluded** `.env` and `docs/SETUP_ISSUES.md` from that PR

---

## Phase 2 — Done: sync with upstream

Local `main` kept synced with `upstream/main`. Always pull upstream before feature work.

---

## Phase 3 — Feature idea: resolution / follow-up memory

### Problem (confirmed)

OpenSRE stores **investigation/diagnosis memory**, not **confirmed resolution memory**:

- Has: root cause hypotheses, suggestions, episode memory
- Lacks: actual fix used, whether it worked, link to what Ops/human did
- `Episode.resolved` ≈ diagnostic completeness, **not** “incident fixed in prod”

### Internal usage constraints (enterprise chat + web)

- Teams chat + OpenSRE Web; users mostly **Dev/QA**
- Rarely create Jira first
- Pattern: “X is down” → OpenSRE suggests → ask Ops / rarely self-fix
- Continuous metric watchers = **token waste** → rejected
- No auto “analyse what changed” if resolved → **only human-shared fix** updates memory
- If no resolution after follow-ups → mark **`abandoned`**
- Closing browser ≠ abandoned; abandoned only after follow-up window with no shared resolution

### Agreed v1 design

**Channel-agnostic outcome model; channel-specific delivery**

**Stage A** (after investigation):

- `I'll fix it`
- `Need Ops help` (optional ticket ID + always show investigation ID)
- `Ignore`

**Stage B** nudges: **T+30m** and **T+3h**

- **Teams:** push into same thread
- **Web:** mark nudge due; show when user returns / Agent Runs badge (pull-based; no email required for v1)

**Memory rules:**

| Outcome | Memory |
|---------|--------|
| Resolved + human `fix_summary` | Update memory with confirmed fix |
| No resolution / ignore / timeout | `abandoned` — keep diagnosis; **do not invent fix** |

---

## Phase 4 — Cross-thread Ops handoff (added)

### Real flow

```text
QA thread → OpenSRE suggests fix
QA creates ticket for Ops
Ops opens a NEW Teams/Web thread with OpenSRE
→ must link back to same outcome
```

### Join keys (priority)

1. **`ticket_id`** — exact match → auto-link  
2. **`investigation_id` / `run_id`** — exact match → auto-link  
3. Soft match (same org/team + service + open `pending_followup`) → **Ops must confirm**; never silent merge  

On link: add Ops thread to `followup_refs[]`, move `primary_followup_ref` to Ops thread for nudges, one outcome / one memory write when Ops shares fix.

Without join key: Ops = new investigation; QA outcome ages to `abandoned`.

---

## Phase 5 — Teams UX correction (critical)

Screenshot of production Teams channel showed **threaded markdown text**, not Adaptive Cards for the final report.

### How Teams works **today** (`teams-bot/`)

| Moment | Channel / group | 1:1 / personal / Web Chat |
|--------|-----------------|---------------------------|
| Progress | Plain text stream/update | Stream |
| Final report | **Plain text** (`build_final_text`, `plain_text_final=True`) | Adaptive Card (`build_final_card`) |
| Clarifying questions | Adaptive Card + `opensre.submit_answers` | Same |
| Welcome/help | — | Adaptive Card |

Docs: `teams-bot/README.md`, `investigation_runner.py`, `card_builder.py`, `bot_handlers.py`.

### Implication for proposal

“Stage A = Adaptive Card in same thread” is a **proposed add-on**, not current final-report UX.

**v1 recommendation:** keep channel final report as plain text; post a **separate small follow-up Adaptive Card** after it (same pattern as question cards). Alternative: text-reply keywords only.

---

## Artifacts

| Artifact | Location |
|----------|----------|
| Formal proposal (local) | `docs/proposals/investigation-outcome-followup.md` |
| This handoff | `docs/proposals/CHAT-HANDOFF-investigation-outcome.md` |
| Confluence (optional) | Publish from local proposal if desired (no org-specific URL in-repo) |

### Confluence notes

- Prefer keeping the proposal in-repo as source of truth.
- If mirroring to Confluence, sync from `investigation-outcome-followup.md` and avoid committing tenant-specific URLs.

---

## Code surfaces to touch (when implementing)

| Layer | Role |
|-------|------|
| `teams-bot/` | Stage A/B cards after final reply; schedule nudges; card actions; ticket/INV link detection |
| `web_ui/` | Stage A panel on run; Follow-up due badge; Stage B on return |
| `config-service/` | Persist outcomes + APIs (by `ticket_id` / `investigation_id`; multi-`followup_refs`) |
| `sre-agent/memory/` | Write confirmed resolution; mark abandoned without inventing fix |
| Related existing | `sre-agent/investigation_lifecycle.py`, Agent Runs UI, remediations |

---

## Open decisions (for Swapnil / maintainers / next chat)

1. Approve v1 scope? (shared outcome + Teams follow-up card + Web panel + cross-thread link)
2. Outcome model home: new table vs extend run/episode fields?
3. Pull-based Web nudges OK for v1?
4. “Matched OpenSRE suggestion?” in v1 or defer?
5. After Ops link: nudges only on Ops thread, or both?
6. Channel Stage A: Adaptive Card after plain-text final, or text keywords only?
7. Help **create** Ops ticket with INV id pre-filled, or only accept pasted ticket in v1?
8. Soft-match window / similarity threshold?

---

## Explicit non-goals (do not implement in v1)

1. Continuous background metric/alert watching  
2. Automatic “infer what changed” when service recovers  
3. Requiring Jira for every investigation  
4. Silent fuzzy merge of unrelated threads  
5. Autonomous remediations without human-confirmed outcome  

---

## Suggested next-chat workflow (Superpowers)

1. **brainstorming** — only if any requirement above is still fuzzy; otherwise skip to plans  
2. **writing-plans** — implementation plan (schema, APIs, Teams card contract, Web UX, memory write path, tests)  
3. Sync `main` from `upstream` before coding  
4. **executing-plans** or **subagent-driven-development** / **TDD** as appropriate  
5. **verification-before-completion** before claiming done  
6. PR to upstream when Amol asks (fork `origin` → PR against `swapnildahiphale/OpenSRE`)

---

## One-line product rule

**No human-shared fix ⇒ no invented fix ⇒ mark `abandoned`.**
