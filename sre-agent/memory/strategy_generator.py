# memory/strategy_generator.py
"""LLM-based investigation strategy generation from past episodes."""

import logging
import os
from typing import Dict, List

logger = logging.getLogger(__name__)


def generate_strategy(episodes: List[Dict], alert_type: str, service_name: str) -> str:
    """
    Generate an investigation strategy from past episodes using LLM.
    """
    if not episodes:
        return ""

    # Build episode summaries for the prompt
    episode_summaries = []
    for i, ep in enumerate(episodes, 1):
        resolved = "RESOLVED" if ep.get("resolved") else "UNRESOLVED"
        root_cause = ep.get("root_cause", "Not identified")
        skills = ", ".join(ep.get("skills_used", [])[:5]) or "none recorded"
        summary = ep.get("summary", "No summary")
        services = ", ".join(ep.get("services", [])) or ep.get(
            "service_name", "unknown"
        )

        episode_summaries.append(
            f"Episode {i} [{resolved}]:\n"
            f"  Services: {services}\n"
            f"  Skills used: {skills}\n"
            f"  Root cause: {root_cause}\n"
            f"  Summary: {summary}"
        )

    episodes_text = "\n\n".join(episode_summaries)

    prompt = (
        f'Analyze these {len(episodes)} past investigation episodes for "{alert_type}" '
        f'alerts affecting "{service_name}" and generate a concise investigation strategy.\n\n'
        f"{episodes_text}\n\n"
        "Generate a markdown strategy with these sections:\n"
        "1. **Common Root Causes** - patterns seen across episodes\n"
        "2. **Recommended Investigation Steps** - ordered by effectiveness\n"
        "3. **Key Skills/Commands** - tools that worked well\n"
        "4. **Anti-patterns** - approaches that didn't help\n\n"
        "Be specific and actionable. Keep it under 300 words.\n\nStrategy:"
    )

    try:
        from config import AgentConfig, ModelConfig, build_llm
        from langchain_core.messages import HumanMessage

        model_name = os.getenv("MEMORY_LLM_MODEL", "claude-haiku-4-5-20251001")
        agent_config = AgentConfig(
            name="memory-strategy",
            model=ModelConfig(name=model_name, max_tokens=500),
        )
        llm = build_llm(agent_config)
        response = llm.invoke([HumanMessage(content=prompt)])
        result = (response.content or "").strip()
        logger.info(
            f"[STRATEGY] Generated strategy for {alert_type}/{service_name}: "
            f"{len(result)} chars"
        )
        return result
    except Exception as e:
        logger.error(f"[STRATEGY] LLM call failed: {e}")
        return ""
