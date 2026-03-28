"""Memory lookup node -- searches past episodes and generates strategy."""

import logging

from memory.integration import enhance_investigation_with_memory

logger = logging.getLogger(__name__)


def memory_lookup(state: dict) -> dict:
    """Search for similar past investigations and generate strategy.

    Uses the episodic memory system to find relevant past episodes.
    Results stored in state.memory_context for the planner.
    """
    alert = state.get("alert", {})

    service_name = alert.get("service", "")
    alert_type = alert.get("name", "")
    description = alert.get("description", "")

    # Build a prompt-like string for memory search
    search_text = f"{alert_type}: {description}" if description else str(alert)

    try:
        enhanced = enhance_investigation_with_memory(
            prompt=search_text,
            service_name=service_name,
            alert_type=alert_type,
        )

        # If enhancement added content, extract it
        if enhanced != search_text:
            memory_context = {
                "enhanced_prompt": enhanced,
                "has_similar_episodes": True,
            }
        else:
            memory_context = {
                "enhanced_prompt": "",
                "has_similar_episodes": False,
            }

        logger.info(
            f"[MEMORY] Lookup complete: similar_episodes={memory_context['has_similar_episodes']}"
        )

    except Exception as e:
        logger.error(f"[MEMORY] Lookup failed: {e}")
        memory_context = {
            "enhanced_prompt": "",
            "has_similar_episodes": False,
            "error": str(e),
        }

    return {"memory_context": memory_context}
