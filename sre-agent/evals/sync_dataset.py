#!/usr/bin/env python3
"""Push scenarios.yaml into a Langfuse dataset.

Idempotent: each scenario's `name` is used as the dataset item id, so re-running
this after editing a scenario updates that item rather than adding a duplicate.

    python -m evals.sync_dataset
"""

import argparse
import sys

import yaml
from langfuse import get_client

from .config import DATASET_NAME, SCENARIOS_PATH, require_langfuse_credentials


def load_scenarios() -> list[dict]:
    """Read and lightly validate scenarios.yaml."""
    scenarios = yaml.safe_load(SCENARIOS_PATH.read_text())

    seen = set()
    for scenario in scenarios:
        name = scenario.get("name")
        if not name:
            raise ValueError(f"Scenario is missing a `name`: {scenario}")
        if name in seen:
            raise ValueError(f"Duplicate scenario name: {name}")
        seen.add(name)

        # The judge needs a reference root cause; without it the item is unscorable.
        if not scenario.get("expected_output", {}).get("root_cause"):
            raise ValueError(f"Scenario {name} is missing expected_output.root_cause")

    return scenarios


def sync(dataset_name: str = DATASET_NAME) -> int:
    """Create the dataset if needed and upsert every scenario into it."""
    host = require_langfuse_credentials()
    scenarios = load_scenarios()
    langfuse = get_client()

    langfuse.create_dataset(
        name=dataset_name,
        description=(
            "OpenSRE incident investigation scenarios. Synced from "
            "sre-agent/evals/scenarios.yaml — edit there, not in the UI, so the "
            "definition of a correct investigation stays under review."
        ),
        metadata={"source": "sre-agent/evals/scenarios.yaml"},
    )

    for scenario in scenarios:
        langfuse.create_dataset_item(
            dataset_name=dataset_name,
            # Stable id makes this an upsert instead of an append.
            id=scenario["name"],
            input=scenario["input"],
            expected_output=scenario["expected_output"],
            metadata=scenario.get("metadata", {}),
        )
        print(f"  synced {scenario['name']}")

    langfuse.flush()
    print(f"\n{len(scenarios)} scenarios synced to dataset '{dataset_name}' at {host}")
    return len(scenarios)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        default=DATASET_NAME,
        help=f"Langfuse dataset name (default: {DATASET_NAME})",
    )
    args = parser.parse_args()
    sync(args.dataset)


if __name__ == "__main__":
    sys.exit(main())
