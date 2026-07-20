---
name: platform-jenkins
description: Jenkins job discovery, build triggers, console reads, and chained workflows across named Jenkins controllers. Built-in controllers are legacy and aws. Use when investigating CI/CD failures, triggering deploys, or orchestrating build-then-deploy chains.
allowed-tools: Bash(python *)
---

# Jenkins Integration

Interact with existing Jenkins jobs across multiple named Jenkins instances using
portable REST API scripts. This skill does **not** create or reconfigure Jenkins jobs.

Built-in controller examples (set real URLs in `.env` — no org defaults in code):

- `legacy`: `https://jenkins.example.com` (override with `JENKINS_LEGACY_BASE_URL`)
- `aws`: `https://jenkins-aws.example.com` (override with `JENKINS_AWS_BASE_URL`)

## Authentication

**Credentials are read from the environment automatically — do not check, echo, or
verify them before running a script.** Every script calls `os.environ` directly for
its Jenkins base URL, username, and API token; there is no secondary env file, no
Keychain, and nothing you need to inspect first. Just run the script for the
controller you need (`--env legacy` or `--env aws`).

If a variable is missing, the script itself raises a clear error naming the exact
variable (e.g. `Missing JENKINS_LEGACY_API_TOKEN. Set it in repo root .env (or export
JENKINS_API_TOKEN).`) — that error *is* your signal to check `.env`, not something to
pre-empt by checking env vars or hunting for a `.env` file before running the script.

Credentials live in repo root `.env` (passed to sre-agent via docker-compose
`env_file`). See `.env.example` and `sre-agent/.claude/skills/platform-jenkins/.env.example`.

**Legacy controller (`--env legacy`):**

- `JENKINS_LEGACY_BASE_URL` (required)
- `JENKINS_LEGACY_USERNAME`
- `JENKINS_LEGACY_API_TOKEN`

**AWS controller (`--env aws`):**

- `JENKINS_AWS_BASE_URL` (required)
- `JENKINS_AWS_USERNAME`
- `JENKINS_AWS_API_TOKEN`

**Optional:**

- `JENKINS_USERNAME`, `JENKINS_API_TOKEN` — shared fallback when both controllers use the same account
- `JENKINS_HTTP_TIMEOUT` (seconds; default `20`)

## Setup

```bash
# Add JENKINS_* vars to repo root .env, then:
docker compose up -d --force-recreate sre-agent

python .claude/skills/platform-jenkins/scripts/get_whoami.py --env legacy
python .claude/skills/platform-jenkins/scripts/get_whoami.py --env aws
```

## Safe workflow

1. Confirm the target Jenkins instance first: `legacy` or `aws`.
2. Read/list before write actions.
3. Use exact slash-delimited job paths (e.g. `folder-a/subfolder-b/job-name`).
4. For writes, confirm job path, parameters, and whether the action is trigger or stop.
5. After triggering, capture the queue item URL/id and follow until a build number appears.
6. On `401`, `403`, or `404`, report the concrete error and stop — do not guess paths.

## Available scripts

All scripts are in `.claude/skills/platform-jenkins/scripts/`. The exact flags below
match each script's `argparse` definition — do not read script source to learn the
CLI, and do not re-derive flags by trial and error.

Every script below except `run_workflow.py` requires `--env legacy|aws`.

### Read commands

**get_whoami.py** — verify identity
```bash
python .claude/skills/platform-jenkins/scripts/get_whoami.py --env legacy
```
Flags: `--env` (required).

**list_jobs.py** — list jobs, optionally recursive into folders
```bash
python .claude/skills/platform-jenkins/scripts/list_jobs.py --env legacy [--parent-path PATH] [--recursive] [--max-depth N] [--name-contains TEXT]
```
Flags: `--env` (required). `--parent-path` (optional, defaults to Jenkins root). `--recursive` (optional flag, walks into folders/multibranch containers). `--max-depth` (optional, default `5`, only applies with `--recursive`). `--name-contains` (optional, case-insensitive substring filter on job path).

**get_job.py** — job details
```bash
python .claude/skills/platform-jenkins/scripts/get_job.py --env aws --job-path folder-a/my-job [--tree JENKINS_TREE]
```
Flags: `--env`, `--job-path` (both required). `--tree` (optional, overrides the default Jenkins tree selector).

**get_job_parameters.py** — parameter definitions for a job
```bash
python .claude/skills/platform-jenkins/scripts/get_job_parameters.py --env aws --job-path folder-a/deploy-job
```
Flags: `--env`, `--job-path` (both required). No `--tree` option on this script.

**list_builds.py** — recent builds for a job
```bash
python .claude/skills/platform-jenkins/scripts/list_builds.py --env aws --job-path folder-a/my-job [--limit N] [--tree JENKINS_TREE]
```
Flags: `--env`, `--job-path` (both required). `--limit` (optional, default `20`). `--tree` (optional).

**get_build.py** — single build details
```bash
python .claude/skills/platform-jenkins/scripts/get_build.py --env legacy --job-path folder-a/my-job --build-number 123 [--tree JENKINS_TREE]
```
Flags: `--env`, `--job-path`, `--build-number` (all required, `--build-number` is an int). `--tree` (optional).

**get_console.py** — console log text for a build
```bash
python .claude/skills/platform-jenkins/scripts/get_console.py --env aws --job-path folder-a/my-job --build-number 123 [--tail-lines N]
```
Flags: `--env`, `--job-path`, `--build-number` (all required). `--tail-lines` (optional int — if set, prints only the last N lines instead of the full console text). This is the only console-log script; there is no separate "get logs" script.

**get_queue_item.py** — queue item status
```bash
python .claude/skills/platform-jenkins/scripts/get_queue_item.py --env legacy --queue-id 4567
```
Flags: `--env`, `--queue-id` (both required, `--queue-id` is an int). No `--job-path` on this script.

**wait_for_build.py** — block until a queued/running build finishes
```bash
python .claude/skills/platform-jenkins/scripts/wait_for_build.py --env legacy --job-path folder-a/my-job (--queue-id 4567 | --build-number 123) [--poll-interval-seconds N] [--queue-timeout-seconds N] [--build-timeout-seconds N]
```
Flags: `--env`, `--job-path` (required). Exactly one of `--queue-id` or `--build-number` must be given (enforced at runtime, not by argparse — passing neither raises an error). `--poll-interval-seconds`, `--queue-timeout-seconds`, `--build-timeout-seconds` (all optional floats with built-in defaults).

### Write commands

**trigger_build.py** — trigger a build, with or without parameters
```bash
# Non-parameterized
python .claude/skills/platform-jenkins/scripts/trigger_build.py --env legacy --job-path folder-a/my-job

# Parameterized (repeat --param per KEY=VALUE)
python .claude/skills/platform-jenkins/scripts/trigger_build.py \
  --env aws --job-path folder-a/my-job \
  --param BRANCH=main --param DEPLOY_ENV=stage
```
Flags: `--env`, `--job-path` (required). `--param KEY=VALUE` (optional, repeatable).

**stop_build.py** — stop a running build
```bash
python .claude/skills/platform-jenkins/scripts/stop_build.py --env legacy --job-path folder-a/my-job --build-number 123
```
Flags: `--env`, `--job-path`, `--build-number` (all required).

**run_workflow.py** — chained build-then-deploy workflow from a JSON file
```bash
python .claude/skills/platform-jenkins/scripts/run_workflow.py --workflow-file ./jenkins-workflow.json [--default-env legacy|aws]
```
Flags: `--workflow-file` (required, path to the JSON workflow definition). `--default-env` (optional, `legacy` or `aws` — fallback env for steps that omit their own `env`). **This script does not take `--env`** — env is per-step inside the JSON file (or via `--default-env`), not a top-level CLI flag.

Example workflow file:

```json
{
  "name": "build-and-deploy",
  "defaultEnv": "aws",
  "stopOnFailure": true,
  "pollIntervalSeconds": 10,
  "steps": [
    {
      "id": "build_app",
      "name": "Build app",
      "jobPath": "folder-a/build-job",
      "parameters": { "BRANCH": "main" },
      "waitForBuild": true,
      "requireResult": "SUCCESS"
    },
    {
      "id": "deploy_app",
      "name": "Deploy app",
      "jobPath": "folder-a/deploy-job",
      "parameters": { "UPSTREAM_BUILD": "${steps.build_app.buildNumber}" },
      "waitForBuild": true,
      "requireResult": "SUCCESS"
    }
  ]
}
```

## Best practices

- Prefer `list_jobs.py` before assuming a folder path.
- Prefer `get_job_parameters.py` before triggering parameterized builds.
- Use `get_queue_item.py` after `trigger_build.py` until Jenkins assigns a build number.
- Use `wait_for_build.py` when a later step depends on an earlier job's result.
- Use `run_workflow.py` for reproducible build-to-deploy chains.
- Use `--tail-lines` on console reads to avoid dumping huge logs.
- Treat trigger and stop as write actions even though they don't mutate job config.
