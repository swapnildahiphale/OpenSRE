"""Init context node -- validates alert and loads team config."""

import logging
import os
import uuid

from config import load_team_config

logger = logging.getLogger(__name__)


def init_context(state: dict) -> dict:
    """Validate alert payload, generate investigation_id, load team config.

    This is the entry node of the graph.
    """
    alert = state.get("alert", {})
    thread_id = state.get("thread_id", str(uuid.uuid4()))

    # Validate alert
    if not alert:
        return {
            "status": "error",
            "conclusion": "No alert data provided.",
            "investigation_id": str(uuid.uuid4()),
        }

    # Load team config
    try:
        team_config = load_team_config()
        raw_config = team_config.raw_config
    except Exception as e:
        logger.warning(f"Failed to load team config, using defaults: {e}")
        raw_config = {}

    # Get planner config for max_iterations
    planner_config = raw_config.get("agents", {}).get("planner", {})
    max_iterations = int(
        os.getenv("MAX_ITERATIONS", planner_config.get("max_iterations", 3))
    )
    max_react_loops = int(os.getenv("SUBAGENT_MAX_REACT_LOOPS", "25"))

    investigation_id = str(uuid.uuid4())

    logger.info(
        f"[INIT] Investigation {investigation_id} for alert: "
        f"{alert.get('name', 'unknown')} on {alert.get('service', 'unknown')}"
    )

    return {
        "investigation_id": investigation_id,
        "thread_id": thread_id,
        "team_config": raw_config,
        "max_iterations": max_iterations,
        "max_react_loops": max_react_loops,
        "iteration": 0,
        "status": "running",
        "agent_states": {},
        "messages": [],
        "hypotheses": [],
        "selected_agents": [],
        "images": state.get("images", []),
    }
