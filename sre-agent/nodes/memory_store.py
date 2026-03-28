"""Memory store node -- persists investigation episode after completion."""

import logging

from memory.integration import store_investigation_result

logger = logging.getLogger(__name__)


def memory_store(state: dict) -> dict:
    """Store the completed investigation as an episode in config-service.

    Extracts metadata using LLM and persists for future memory lookups.
    """
    alert = state.get("alert", {})
    conclusion = state.get("conclusion", "")
    thread_id = state.get("thread_id", "")
    investigation_id = state.get("investigation_id", "")
    agent_states = state.get("agent_states", {})

    if not conclusion or len(conclusion.strip()) < 50:
        logger.info("[MEMORY_STORE] Conclusion too short, skipping episode storage")
        return {}

    # Build tool calls data from agent states for skill extraction
    tool_calls_data = []
    for agent_id, agent_state in agent_states.items():
        evidence = agent_state.get("evidence", [])
        for entry in evidence:
            tool_calls_data.append(
                {
                    "tool_name": entry.get("tool", ""),
                    "tool_input": entry.get("args", {}),
                    "tool_output": "",  # Not stored in timeline
                }
            )

    # Build prompt from alert
    prompt = f"{alert.get('name', '')}: {alert.get('description', str(alert))}"

    try:
        store_investigation_result(
            thread_id=thread_id,
            prompt=prompt,
            result_text=conclusion,
            success=state.get("status") == "completed",
            agent_run_id=investigation_id,
            tool_calls_data=tool_calls_data,
            service_name=alert.get("service", ""),
            alert_type=alert.get("name", ""),
        )
        logger.info(
            f"[MEMORY_STORE] Episode stored for investigation {investigation_id}"
        )
    except Exception as e:
        logger.error(f"[MEMORY_STORE] Failed to store episode: {e}")

    return {}
