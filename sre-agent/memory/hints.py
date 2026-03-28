# memory/hints.py
"""
Memory hint formatting for agent system prompts.

Fetches similar episodes and strategies from config-service
and formats them as text for injection into agent prompts.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def format_memory_hints_for_prompt(
    service_name: str, alert_type: str, skill_id: str = "sre-agent"
) -> Optional[str]:
    """
    Format memory hints as text suitable for injection into an agent's system prompt.

    Searches for similar episodes and strategies via the integration layer.

    Args:
        service_name: Name of the service being investigated
        alert_type: Type of alert
        skill_id: ID of the skill/agent requesting hints

    Returns:
        Formatted hint text, or None if no relevant hints found
    """
    if not service_name or not alert_type:
        return None

    try:
        from .integration import get_strategies, search_similar

        # Find similar past episodes
        episodes = search_similar(
            prompt="",
            service_name=service_name,
            alert_type=alert_type,
            limit=3,
        )

        # Get any cached strategies
        strategies = get_strategies(
            alert_type=alert_type,
            service_name=service_name,
        )

        if not episodes and not strategies:
            return None

        lines = ["## Memory-Based Investigation Hints\n"]
        lines.append(
            f"Based on past investigations for {service_name} ({alert_type}):\n"
        )

        if episodes:
            lines.append("### Past Similar Episodes")
            for ep in episodes:
                status = "resolved" if ep.get("resolved") else "unresolved"
                root = ep.get("root_cause", "unknown")
                lines.append(f"- [{status}] Root cause: {root}")
            lines.append("")

        if strategies:
            for s in strategies:
                text = s.get("strategy_text", "")
                if text:
                    lines.append("### Investigation Strategy")
                    lines.append(text)
                    lines.append("")

        result = "\n".join(lines)
        logger.info(
            f"[MEMORY-HINTS] Formatted hints for {skill_id}: "
            f"{len(episodes)} episodes, {len(strategies)} strategies"
        )
        return result

    except Exception as e:
        logger.error(f"[MEMORY-HINTS] Failed to format hints: {e}")
        return None
