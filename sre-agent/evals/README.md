# OpenSRE eval harness

Runs the investigation agent against a dataset of incident scenarios and scores
the results in [Langfuse](https://langfuse.com).

For *which* evaluation method to use and why, read
[`docs/EVALUATION_LANGFUSE.md`](../../docs/EVALUATION_LANGFUSE.md) first. This
file is just the mechanics.

## Setup

Add Langfuse credentials to the repo-root `.env` (see `.env.example`):

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://us.cloud.langfuse.com   # or EU / your self-hosted URL
```

Keys come from your Langfuse project under **Settings > API Keys**. Setting them
also switches the agent's tracing on, because `OBSERVABILITY_BACKEND`
auto-detects from whichever credentials are present.

Then bring up the stack and push the scenarios into Langfuse:

```bash
make dev
cd sre-agent
uv run python -m evals.sync_dataset
```

`sync_dataset` is idempotent — each scenario's `name` is its dataset item id, so
re-running it after editing `scenarios.yaml` updates items instead of duplicating
them.

## Running

**This runner does not inject faults.** Each fault scenario assumes its own
fault — and only its own — is active in the environment, so scenarios are run
one at a time with the fault set up beforehand. `scripts/eval_agent_performance.py`
has the otel-demo fault-injection helpers. Asking for several fault scenarios in
one pass exits with an error rather than producing scores graded against an
environment that still contains the previous scenario's fault.

```bash
cd sre-agent

# one scenario, with its fault already injected
uv run python -m evals.run_experiment --scenario cart-crashloop

# deterministic evaluators only — free, no judge model calls
uv run python -m evals.run_experiment --scenario cart-crashloop --no-judge

# the healthy-system control needs no fault setup
uv run python -m evals.run_experiment --scenario healthy-control

# gate: exit non-zero if the headline score regresses
uv run python -m evals.run_experiment --scenario cart-crashloop --fail-under 0.8

# only if something outside this runner injects and clears each fault per item
uv run python -m evals.run_experiment --allow-multi-fault
```

Each run creates a dataset run in Langfuse and prints its URL. Compare runs
side by side in **Datasets > opensre-investigations > Runs**.

## What gets scored

Per item, deterministic (`evaluators/code.py`):

| Score | Meaning |
|---|---|
| `report_completeness` | Fraction of required sections present (root cause, evidence, impact, recommendation) |
| `expected_tools_used` | Whether the scenario's expected diagnostic steps appear in the trajectory |
| `required_evidence` | Fraction of decisive tokens (for example `CrashLoopBackOff`) cited in the report |
| `red_herring_avoided` | 1.0 unless the report blames a listed decoy or omits `ruling_out` tokens |
| `no_unsafe_mutations` | 1.0 unless a state-changing command ran without a dry-run |
| `within_latency_budget` | Whether the run finished inside the scenario's budget |
| `investigation_latency_seconds` | Raw duration, for trending |

Per item, judged (`evaluators/judge.py`):

| Score | Meaning |
|---|---|
| `root_cause_correctness` | 1.0 / 0.5 / 0.0 for CORRECT / PARTIAL / INCORRECT against the reference root cause |
| `evidence_grounded` | 0.0-1.0 for whether claims are backed by observations the agent actually made |

Across the run (`evaluators/run_level.py`): `avg_root_cause_correctness` (the
CI gate reads this), `avg_evidence_grounded`, `avg_report_completeness`,
`avg_required_evidence`, `red_herring_pass_rate`, `safety_pass_rate`,
`p95_latency_seconds`.

Items an evaluator declines to score return `None` and are excluded from
averages rather than counted as failures — a judge malfunction should lower
confidence, not look like an agent regression.

## Adding a scenario

Add an entry to `scenarios.yaml` and re-run `sync_dataset`. The important fields are `expected_output.root_cause` (prose, not keywords —
the judge compares meaning) and, when the scenario has a decoy, `forbidden_claims`
plus `ruling_out`. `required_evidence` is the deterministic check that the
report named the decisive observation.

Scenarios assume a fixture environment with the corresponding fault injected —
`metadata.fault` records which one. Variants that share the same fault identity
(kind + target, or kind + flag) can run together. Distinct faults still cannot,
unless you pass `--allow-multi-fault`. `scripts/eval_agent_performance.py` has
the otel-demo fault injection helpers if you need to set that up.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `EVAL_DATASET_NAME` | `opensre-investigations` | Langfuse dataset to run against |
| `EVAL_AGENT_URL` | `http://localhost:8001` | Agent under test |
| `EVAL_CONFIG_SERVICE_URL` | `http://localhost:8081` | Used to mint a team token |
| `EVAL_TEAM_TOKEN` | _(minted)_ | Skip minting and use this token |
| `EVAL_ADMIN_TOKEN` | `local-admin-token` | Admin token used for minting |
| `EVAL_JUDGE_MODEL` | `claude-haiku-4-5-20251001` | Judge model |
| `EVAL_SCENARIO_TIMEOUT` | `900` | Hard per-scenario ceiling, seconds |

## Tests

```bash
cd sre-agent && uv run python -m pytest tests/test_evals.py -v
```

These cover the scenario file's shape and the evaluators' scoring logic with the
judge mocked, so they need neither Langfuse nor a running agent.
