"""Shared configuration for the OpenSRE Langfuse eval harness.

Everything the harness needs to reach Langfuse and the agent lives here so the
runner, the dataset sync and the evaluators all agree on names and endpoints.
"""

import os
from pathlib import Path

# Name of the Langfuse dataset holding the investigation scenarios. Experiment
# runs attach to this name, so changing it starts a fresh comparison history.
DATASET_NAME = os.getenv("EVAL_DATASET_NAME", "opensre-investigations")

# Scenario definitions that sync_dataset.py pushes into the dataset above.
SCENARIOS_PATH = Path(__file__).parent / "scenarios.yaml"

# The agent under test. Defaults to the local Docker Compose sre-agent.
AGENT_URL = os.getenv("EVAL_AGENT_URL", "http://localhost:8001")

# Config service, used to mint a team token when EVAL_TEAM_TOKEN is not set.
CONFIG_SERVICE_URL = os.getenv("EVAL_CONFIG_SERVICE_URL", "http://localhost:8081")
ADMIN_TOKEN = os.getenv("EVAL_ADMIN_TOKEN", "local-admin-token")

# Model used by the LLM-as-a-judge evaluators. Deliberately a different (and
# cheaper) model than the investigator so the judge is not grading its own work
# with the same weights.
JUDGE_MODEL = os.getenv("EVAL_JUDGE_MODEL", "claude-haiku-4-5-20251001")

# Hard ceiling on a single scenario, independent of the per-scenario latency
# budget that the latency evaluator scores against.
SCENARIO_TIMEOUT_SECONDS = int(os.getenv("EVAL_SCENARIO_TIMEOUT", "900"))


def require_langfuse_credentials() -> str:
    """Fail fast with an actionable message if Langfuse is not configured.

    Returns the resolved host. The Langfuse v4 SDK reads LANGFUSE_BASE_URL, but
    OpenSRE's .env and Helm chart use LANGFUSE_HOST, so accept either and mirror
    it across for the SDK.
    """
    missing = [
        name
        for name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
        if not os.getenv(name)
    ]
    if missing:
        raise SystemExit(
            f"Missing {' and '.join(missing)}.\n"
            "Create a project API key pair under Settings > API Keys in Langfuse "
            "and add the keys to your .env (see .env.example)."
        )

    host = (
        os.getenv("LANGFUSE_BASE_URL")
        or os.getenv("LANGFUSE_HOST")
        or "https://us.cloud.langfuse.com"
    )
    os.environ["LANGFUSE_BASE_URL"] = host
    os.environ["LANGFUSE_HOST"] = host
    return host
