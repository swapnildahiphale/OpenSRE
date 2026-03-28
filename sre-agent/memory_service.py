# memory_service.py
"""
Memory service — thin wrapper exposing memory system to server.py and agent.py.

Provides integration functions:
1. get_memory_context_for_prompt() — pre-investigation lookup
2. store_investigation() — post-investigation storage
3. format_memory_hints() — hint injection for system prompt
4. get_memory_stats() / get_all_episodes() / search_similar() / get_strategies()
"""

import logging
from typing import List, Optional

from memory.hints import format_memory_hints_for_prompt
from memory.integration import (
    enhance_investigation_with_memory,
)
from memory.integration import (
    get_all_episodes as _get_all_episodes,
)
from memory.integration import (
    get_memory_stats as _get_memory_stats,
)
from memory.integration import (
    get_strategies as _get_strategies,
)
from memory.integration import (
    search_similar as _search_similar,
)
from memory.integration import (
    store_investigation_result as _store_result,
)

logger = logging.getLogger(__name__)


def get_memory_context_for_prompt(
    prompt: str,
    thread_id: str,
    service_name: str = "",
    alert_type: str = "",
    org_id: str = "",
) -> str:
    """
    Pre-investigation memory lookup. Enhances the prompt with context
    from similar past investigations.

    Called in server.py before sending prompt to agent session.
    """
    try:
        enhanced = enhance_investigation_with_memory(
            prompt=prompt,
            service_name=service_name,
            alert_type=alert_type,
            error_message=prompt,
            org_id=org_id,
        )
        if enhanced != prompt:
            logger.info(
                f"[MEMORY] Enhanced prompt for thread {thread_id} with memory context"
            )
        return enhanced
    except Exception as e:
        logger.error(f"[MEMORY] Failed to get memory context: {e}")
        return prompt


def store_investigation(
    thread_id: str,
    prompt: str,
    result_text: str,
    success: bool = True,
    agent_run_id: Optional[str] = None,
    tool_calls_data: Optional[List[dict]] = None,
    duration_seconds: Optional[float] = None,
    org_id: str = "",
    team_node_id: Optional[str] = None,
    service_name: str = "",
    alert_type: str = "",
) -> None:
    """
    Post-investigation storage. Stores investigation as episode in config-service.

    Called in server.py after stream completion. Stores ALL investigations.
    """
    try:
        _store_result(
            thread_id=thread_id,
            prompt=prompt,
            result_text=result_text,
            success=success,
            agent_run_id=agent_run_id,
            tool_calls_data=tool_calls_data,
            duration_seconds=duration_seconds,
            org_id=org_id,
            team_node_id=team_node_id,
            service_name=service_name,
            alert_type=alert_type,
        )
    except Exception as e:
        logger.error(f"[MEMORY] Failed to store investigation: {e}")


def format_memory_hints(
    service_name: str = "",
    alert_type: str = "",
) -> Optional[str]:
    """
    Format memory hints for injection into agent system prompt.

    Called in agent.py when building the system prompt.
    """
    if not service_name and not alert_type:
        return None

    try:
        return format_memory_hints_for_prompt(
            service_name=service_name,
            alert_type=alert_type,
        )
    except Exception as e:
        logger.error(f"[MEMORY] Failed to format hints: {e}")
        return None


def get_memory_stats(org_id: str = "") -> dict:
    """Get memory system statistics from config-service."""
    return _get_memory_stats(org_id=org_id)


def get_all_episodes(org_id: str = "") -> list:
    """Get all stored episodes from config-service."""
    return _get_all_episodes(org_id=org_id)


def search_similar(
    prompt: str, service_name: str = "", alert_type: str = "", org_id: str = ""
) -> list:
    """Search for similar past investigations via config-service."""
    return _search_similar(
        prompt=prompt,
        service_name=service_name,
        alert_type=alert_type,
        org_id=org_id,
    )


def get_strategies(
    org_id: str = "", alert_type: str = "", service_name: str = ""
) -> list:
    """Get investigation strategies from config-service."""
    return _get_strategies(
        org_id=org_id,
        alert_type=alert_type,
        service_name=service_name,
    )
