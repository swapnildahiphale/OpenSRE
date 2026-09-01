# Choosing an evaluation approach for OpenSRE

This is the decision guide: which Langfuse evaluation method to reach for, and
why. For the mechanics of running what is already built, see
[`sre-agent/evals/README.md`](../sre-agent/evals/README.md).

## Why OpenSRE is harder to evaluate than a typical LLM app

Most LLM eval guidance assumes a single model call with a short answer you can
string-match. An OpenSRE investigation is none of those things:

- **It is a trajectory, not an answer.** A root agent dispatches subagents,
  loads skills progressively and runs dozens of tool calls over up to 10 minutes.
  Two runs that reach the same conclusion can take very different paths, and the
  path matters — a correct answer reached without gathering evidence is a lucky
  guess that will not generalise.
- **There is no single correct wording.** "Cart pods are in CrashLoopBackOff
  because the container command was overridden" and "the cart deployment's
  entrypoint exits 1 on startup, so pods never become ready" are the same
  finding. Keyword matching cannot tell them apart from a wrong answer that
  happens to share vocabulary.
- **It acts on infrastructure.** Correctness is not the only axis. An
  investigation that finds the root cause *and* deletes a production pod without
  a dry-run is a failure.
- **Ground truth is expensive.** For real incidents, only a human who was there
  knows the actual root cause. You cannot start with a labelled dataset; you have
  to build one.

Those four facts are what drive the choices below.

## The three questions that pick your method

**1. Does the thing you are measuring have an objectively right answer?**
Yes → code evaluator. No → LLM-as-a-judge.

**2. Are you testing a change before shipping, or watching what shipped?**
Before → offline experiment on a dataset. After → online evaluation on live
traces.

**3. Do you already have ground truth?**
No → start with annotation queues to create it. Yes → you can run experiments and
calibrate a judge against it.

Everything else is detail.

## Methods, mapped to OpenSRE

| Method | Answers | Cost per run | Use it for | Do not use it for |
|---|---|---|---|---|
| **Code evaluators** | Did the run follow the rules? | Free | Report structure, expected diagnostic steps, no-unsafe-mutation, latency budget | Whether the root cause is right |
| **LLM-as-a-judge** | Was the answer any good? | One model call | Root-cause correctness vs a reference, evidence groundedness, actionability | Anything a deterministic check can decide — you would be paying for noise |
| **Annotation queues** | What does a human think? | Human minutes | Building the first ground truth, calibrating the judge, auditing disagreements | Continuous scoring — it does not scale |
| **Experiments (offline)** | Did my change help? | A full suite run | Prompt/model/skill changes, regression gates in CI | Catching issues in traffic you never anticipated |
| **Online evaluation** | What is happening in production? | One judge call per sampled trace | Drift, unanticipated edge cases, growing the dataset | Pre-merge gating — the change is already live |

### Where each one lands in this codebase

- **Code evaluators** — [`sre-agent/evals/evaluators/code.py`](../sre-agent/evals/evaluators/code.py).
  `no_unsafe_mutations` is the one to keep no matter what else you cut: it reads
  the trajectory for state-changing commands and fails any that lack a dry-run.
- **LLM-as-a-judge** — [`sre-agent/evals/evaluators/judge.py`](../sre-agent/evals/evaluators/judge.py).
  `root_cause_correctness` compares against the reference root cause in the
  dataset. `evidence_grounded` is reference-free, so it also works on production
  traces where no reference exists.
- **Experiments** — [`sre-agent/evals/run_experiment.py`](../sre-agent/evals/run_experiment.py),
  over the dataset defined in [`scenarios.yaml`](../sre-agent/evals/scenarios.yaml).
- **Annotation queues and online evaluation** — configured in the Langfuse UI
  against the traces the agent now emits. Not code in this repo; see
  "What you still have to decide" below.

## The recommended order

Do not set all of this up at once. Each step makes the next one cheaper.

**Step 1 — Get traces flowing.** Set `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`
in `.env` and restart the agent. Each turn becomes an `investigation-turn` span
with every tool call nested under it, plus a nested `llm` generation that
carries model name, token usage, and USD cost from the Claude Agent SDK
`ResultMessage`. All turns of one investigation group into a single Langfuse
session keyed by thread id. You cannot evaluate what you cannot see, and
everything below reads these traces.

Cost in the Langfuse dashboard only appears on `generation` observations. Tool
spans and the turn span are not billed; if those are all you see, Total costs
stays at $0. After this generation is present, run a new investigation — existing
traces are not backfilled.

OpenSRE's investigation URL uses a different id than the Langfuse session.
`session_id` is the conversation `thread_id` (for example `thread-a1b2c3d4`).
The page `/team/agent-runs/{id}` uses the 32-hex `agent_runs.id` for that turn.
Each trace's Metadata panel includes `agent_run_id` so you can paste a Langfuse
cost row onto the matching OpenSRE investigation. Follow-up turns in the same
session overwrite `agent_run_id` with that turn's run id; `thread_id` stays
stable. Older traces are not backfilled.

> Tool spans are emitted from OpenSRE's own `PreToolUse`/`PostToolUse` hooks
> rather than from `openinference-instrumentation-claude-agent-sdk`. That
> instrumentor builds its spans inside a wrapper around the SDK's
> `receive_response()`, and `execute()` drains via `receive_messages()` instead,
> so it emits nothing for this agent. It also merges its own hooks into
> `client.options`, which would collide with the agent-attribution hooks.

**Step 2 — Run the deterministic evaluators.** They cost nothing and catch the
failures that matter most operationally:

```bash
cd sre-agent && uv run python -m evals.run_experiment --no-judge
```

If the agent is skipping `get_events`, blowing latency budgets or issuing
unguarded mutations, you want to know that before you spend anything on a judge.

**Step 3 — Add the judge, but treat its scores as provisional.** Turn on the full
suite and read the comments it writes, not just the numbers. You are checking
whether the judge is reasonable before you let it grade anything unattended.

**Step 4 — Build ground truth from real traffic.** Create score configs and an
annotation queue in Langfuse, push ~50 real investigation traces into it, and
have an SRE label each one: was the root cause right, and was the evidence real?
This is the slowest step and the one people skip. It is also the only thing that
turns your judge from a plausible-sounding oracle into a measured instrument.

**Step 5 — Calibrate the judge against those labels.** Run the judge over the
annotated items and compare its verdicts to the human ones. Simple agreement
accuracy is enough to start. The [judge-calibration reference](https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge)
in the Langfuse skill covers the advanced version (confusion matrix, held-out
split) if you get to the point of automating on the judge's output.

**Step 6 — Gate CI, once calibration justifies it.** `--fail-under` exits
non-zero when the headline score regresses, which is the hook a CI job would
call. There is deliberately no workflow file yet: a job is only worth writing
once something can stand up the environment and inject each scenario's fault,
and until then it would fail on every run. Do not wire this up before step 5
either — gating on an uncalibrated judge blocks good changes and waves through
bad ones, and teams stop trusting the gate within about two false alarms.

**Step 7 — Close the loop.** When online evaluation flags a production trace the
dataset would not have caught, add it to the dataset. Langfuse can create a
dataset item straight from a trace. This is what stops the suite going stale.

## Two decisions worth thinking about

### Live-fault scenarios vs. trace replay

The scenarios in `scenarios.yaml` assume a fixture environment where a fault has
actually been injected — the agent really does query a broken cluster. That is
maximum fidelity and it is the only way to evaluate the investigation *process*.
It is also slow, needs an otel-demo cluster, and cannot run on a pull request.

The alternative is to build dataset items from recorded production traces and
score only the final report. That runs anywhere and is cheap enough for CI, but
it cannot tell you whether the agent would still find the answer if the cluster
responded differently.

Use both, for different jobs: trace-derived items as the fast pre-merge gate,
live-fault scenarios as a slower scheduled run against a real environment.

### What "correct" means for an investigation

`root_cause_correctness` deliberately has three labels, not two. `PARTIAL`
covers "named the right service but the wrong mechanism", which is a real and
common outcome — the agent says payment is failing (true, and useful) but
attributes it to resource pressure rather than the feature flag (wrong, and
sends the responder down a dead end). Collapsing that into either PASS or FAIL
hides the regression where an agent drifts from precise diagnoses to vague ones.

## What is implemented, and what you still have to decide

Implemented and verified in this repo:

- Langfuse tracing: a span per turn, a nested span per tool call, session
  grouping by thread id, `metadata.agent_run_id` for mapping cost onto
  `/team/agent-runs/{id}`, and outcome tags
- A git-reviewed scenario dataset that syncs into Langfuse, including a
  healthy-system control and a red-herring twin (`cart-crashloop-red-herring`)
- Deterministic evaluators for report shape, expected tools, required evidence,
  red-herring avoidance, unguarded mutations, and latency
- Two judge evaluators and run-level aggregates, plus a `--fail-under` gate

Deliberately not built:

- **Fault injection.** The runner scores investigations; it does not set up the
  environment. `metadata.fault` records what each scenario assumes, and the
  runner refuses a multi-fault run rather than producing scores graded against
  a polluted environment. Wiring `set_fault_flag` from
  `scripts/eval_agent_performance.py` into the runner is the natural next step,
  and is what would make a CI job worth writing.

Decisions still open, because they depend on how you want to operate:

- **Sampling rate for online evaluation.** Judging every production investigation
  costs a model call each. Start at 10-20% and raise it if the signal is useful.
- **Your gate threshold.** `--fail-under 0.8` is a placeholder. Run the suite a
  few times to see the natural variance before you pick a number, or you will be
  gating on noise.
- **Who annotates, and how often.** The dataset decays as the infrastructure
  changes. Without a recurring owner, step 4 happens once and never again.
- **Whether to evaluate the memory pipeline separately.** Episode extraction
  (`sre-agent/memory/extraction.py`) is its own LLM call with structured output —
  a good candidate for cheap code evaluators, and currently unevaluated.

## References

Fetched from the Langfuse docs while building this; they are the current source
of truth if any of the above drifts.

- [Evaluation overview](https://langfuse.com/docs/evaluation/overview)
- [Core concepts](https://langfuse.com/docs/evaluation/core-concepts)
- [Experiments via SDK](https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk)
- [Datasets](https://langfuse.com/docs/evaluation/experiments/datasets)
- [LLM-as-a-Judge](https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge)
- [Code evaluators](https://langfuse.com/docs/evaluation/evaluation-methods/code-evaluators)
- [Annotation queues](https://langfuse.com/docs/evaluation/evaluation-methods/annotation-queues)
- [Experiments in CI/CD](https://langfuse.com/docs/evaluation/experiments/experiments-ci-cd)
- [Claude Agent SDK integration](https://langfuse.com/integrations/frameworks/claude-agent-sdk)
