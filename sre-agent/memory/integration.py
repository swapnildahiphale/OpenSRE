# memory/integration.py
"""
Integration layer for episodic memory with the OpenSRE agent system.

Stores episodes in PostgreSQL via config-service HTTP API.
Provides memory-enhanced investigation planning and strategy generation.
"""

import logging
import os
import uuid
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)

CONFIG_SERVICE_URL = os.getenv("CONFIG_SERVICE_URL", "")
_INTERNAL_HEADERS = {"X-Internal-Service": "sre-agent"}
_DEFAULT_ORG_ID = os.getenv("OPENSRE_TENANT_ID", "default")


# ---------------------------------------------------------------------------
# LLM helper
# ---------------------------------------------------------------------------


def llm_text_completion(prompt: str, max_tokens: int = 200) -> str:
    """Call LLM for text completion using the same LiteLLM path as the main agent."""
    try:
        from config import AgentConfig, ModelConfig, build_llm
        from langchain_core.messages import HumanMessage

        model_name = os.getenv("MEMORY_LLM_MODEL", "claude-haiku-4-5-20251001")
        agent_config = AgentConfig(
            name="memory",
            model=ModelConfig(name=model_name, max_tokens=max_tokens),
        )
        llm = build_llm(agent_config)
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content or ""
    except Exception as e:
        logger.error(f"[MEMORY] LLM call failed: {e}")
        return ""


# ---------------------------------------------------------------------------
# Config-service HTTP helpers
# ---------------------------------------------------------------------------


def _config_url(path: str) -> str:
    """Build config-service URL."""
    return f"{CONFIG_SERVICE_URL}/api/v1/internal{path}"


def _post(path: str, json: dict) -> Optional[dict]:
    """POST to config-service."""
    if not CONFIG_SERVICE_URL:
        return None
    try:
        resp = httpx.post(
            _config_url(path), json=json, headers=_INTERNAL_HEADERS, timeout=10.0
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"[MEMORY] POST {path} failed: {e}")
        return None


def _get(path: str, params: Optional[dict] = None) -> Optional[dict]:
    """GET from config-service."""
    if not CONFIG_SERVICE_URL:
        return None
    try:
        resp = httpx.get(
            _config_url(path), params=params, headers=_INTERNAL_HEADERS, timeout=10.0
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"[MEMORY] GET {path} failed: {e}")
        return None


def _put(path: str, json: dict) -> Optional[dict]:
    """PUT to config-service."""
    if not CONFIG_SERVICE_URL:
        return None
    try:
        resp = httpx.put(
            _config_url(path), json=json, headers=_INTERNAL_HEADERS, timeout=10.0
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"[MEMORY] PUT {path} failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Pre-investigation: enhance prompt with memory context
# ---------------------------------------------------------------------------


def enhance_investigation_with_memory(
    prompt: str,
    service_name: str = "",
    alert_type: str = "",
    error_message: str = "",
    org_id: str = "",
    max_episodes: int = 3,
) -> str:
    """
    Enhance investigation prompt with memory context from similar past investigations.

    Searches config-service for similar episodes and optionally fetches/generates
    a strategy, then prepends the context to the prompt.
    """
    org = org_id or _DEFAULT_ORG_ID
    try:
        # Search for similar episodes
        search_result = _post(
            "/episodes/search",
            {
                "org_id": org,
                "alert_type": alert_type or _extract_alert_type_from_prompt(prompt),
                "service_name": service_name or _extract_service_from_prompt(prompt),
                "limit": max_episodes,
            },
        )

        similar_episodes = (search_result or {}).get("episodes", [])
        if not similar_episodes:
            return prompt

        # Build memory context
        memory_lines = ["## Past Investigation Memory\n"]
        memory_lines.append(
            f"Found {len(similar_episodes)} similar past investigation(s):\n"
        )

        for i, episode in enumerate(similar_episodes, 1):
            services = ", ".join(episode.get("services", [])) or "unknown"
            memory_lines.append(f"### Similar Investigation #{i}")
            memory_lines.append(f"- **Services**: {services}")
            memory_lines.append(
                f"- **Alert type**: {episode.get('alert_type', 'unknown')}"
            )
            memory_lines.append(
                f"- **Resolved**: {'Yes' if episode.get('resolved') else 'No'}"
            )
            if episode.get("root_cause"):
                memory_lines.append(f"- **Root cause**: {episode['root_cause']}")
            if episode.get("summary"):
                memory_lines.append(f"- **Summary**: {episode['summary']}")
            skills = episode.get("skills_used", [])
            if skills:
                memory_lines.append(f"- **Skills used**: {', '.join(skills[:5])}")
            score = episode.get("effectiveness_score")
            if score is not None:
                memory_lines.append(f"- **Effectiveness**: {score:.0%}")
            memory_lines.append("")

        # Try to fetch/generate strategy
        detected_alert = alert_type or _extract_alert_type_from_prompt(prompt)
        detected_service = service_name or _extract_service_from_prompt(prompt)
        strategy = get_or_generate_strategy(
            org_id=org,
            alert_type=detected_alert,
            service_name=detected_service,
        )
        if strategy:
            memory_lines.append(
                "## Investigation Strategy (from past investigations)\n"
            )
            memory_lines.append(strategy)
            memory_lines.append("")

        memory_context = "\n".join(memory_lines)
        logger.info(
            f"[MEMORY] Found {len(similar_episodes)} similar investigations, "
            f"prepending memory context ({len(memory_context)} chars)"
        )

        return f"{memory_context}\n---\n\n{prompt}"

    except Exception as e:
        logger.error(f"[MEMORY] Failed to enhance prompt with memory: {e}")
        return prompt


# ---------------------------------------------------------------------------
# Post-investigation: store episode
# ---------------------------------------------------------------------------


def store_investigation_result(
    thread_id: str,
    prompt: str,
    result_text: str,
    success: bool,
    agent_run_id: Optional[str] = None,
    tool_calls_data: Optional[List[dict]] = None,
    duration_seconds: Optional[float] = None,
    org_id: str = "",
    team_node_id: Optional[str] = None,
    service_name: str = "",
    alert_type: str = "",
) -> None:
    """
    Store a completed investigation as an episode in config-service.

    Stores ALL investigations (resolved or not) for learning.
    Uses LLM to extract summary, root cause, alert classification, etc.
    """
    try:
        if not result_text or len(result_text.strip()) < 50:
            logger.info(
                f"[MEMORY-SKIP] Result too short: "
                f"result_len={len(result_text) if result_text else 0}"
            )
            return

        org = org_id or _DEFAULT_ORG_ID
        tool_calls = tool_calls_data or []

        # LLM extractions (parallel-safe, each independent)
        root_cause = _extract_concise_root_cause([result_text])
        resolved = _text_indicates_resolution(result_text)

        summary = _extract_summary(prompt, result_text)
        detected_alert = alert_type or _extract_alert_type_llm(prompt, result_text)
        detected_services = _extract_services(prompt, result_text, service_name)
        severity = _extract_severity(prompt, result_text)

        # Extract skills and key findings from tool calls
        skills_used = _extract_skills_used(tool_calls)
        key_findings = _extract_key_findings(tool_calls)

        episode_data = {
            "id": str(uuid.uuid4()),
            "agent_run_id": agent_run_id,
            "org_id": org,
            "team_node_id": team_node_id,
            "alert_type": detected_alert,
            "alert_description": prompt[:500],
            "severity": severity,
            "services": detected_services,
            "agents_used": ["sre-agent"],
            "skills_used": skills_used,
            "key_findings": key_findings,
            "resolved": resolved,
            "root_cause": root_cause,
            "summary": summary,
            "effectiveness_score": 0.8 if root_cause and resolved else 0.4,
            "confidence": 0.8 if resolved else 0.3,
            "duration_seconds": duration_seconds,
        }

        result = _post("/episodes", episode_data)
        if result:
            logger.info(
                f"[MEMORY-CREATE] Stored episode {episode_data['id']}: "
                f"{detected_alert}/{','.join(detected_services)}"
            )
        else:
            logger.warning("[MEMORY-CREATE] Failed to store episode to config-service")

    except Exception as e:
        logger.error(f"[MEMORY-ERROR] Failed to store investigation: {e}")


# ---------------------------------------------------------------------------
# Strategy generation
# ---------------------------------------------------------------------------


def get_or_generate_strategy(
    org_id: str,
    alert_type: str = "",
    service_name: str = "",
    team_node_id: Optional[str] = None,
    window: int = 5,
) -> Optional[str]:
    """
    Get cached strategy or generate a new one.

    1. GET strategy from config-service
    2. If missing, fetch last N episodes and generate via LLM
    3. PUT result to config-service for caching
    """
    if not alert_type or not CONFIG_SERVICE_URL:
        return None

    try:
        # Check for cached strategy
        params = {
            "org_id": org_id,
            "alert_type": alert_type,
            "service_name": service_name or "*",
        }
        if team_node_id:
            params["team_node_id"] = team_node_id

        existing = _get("/strategies", params)
        if existing and existing.get("strategy_text"):
            return existing["strategy_text"]

        # Fetch recent episodes for this alert type
        ep_result = _get(
            "/episodes",
            {"org_id": org_id, "alert_type": alert_type, "limit": window},
        )
        episodes = (ep_result or {}).get("episodes", [])
        if len(episodes) < 2:
            return None  # Need at least 2 episodes to generate strategy

        # Generate strategy using LLM
        from .strategy_generator import generate_strategy

        strategy_text = generate_strategy(episodes, alert_type, service_name or "*")
        if not strategy_text:
            return None

        # Cache the strategy
        _put(
            "/strategies",
            {
                "org_id": org_id,
                "team_node_id": team_node_id,
                "alert_type": alert_type,
                "service_name": service_name or "*",
                "strategy_text": strategy_text,
                "source_episode_ids": [ep["id"] for ep in episodes],
                "episode_count": len(episodes),
            },
        )

        return strategy_text

    except Exception as e:
        logger.error(f"[MEMORY] Strategy generation failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Public API functions (used by memory_service.py)
# ---------------------------------------------------------------------------


def get_memory_stats(org_id: str = "") -> dict:
    """Get memory system statistics from config-service."""
    org = org_id or _DEFAULT_ORG_ID
    result = _get("/episodes/stats", {"org_id": org})
    return result or {
        "total_episodes": 0,
        "resolved_episodes": 0,
        "unresolved_episodes": 0,
        "strategies_count": 0,
    }


def get_all_episodes(org_id: str = "", limit: int = 50) -> list:
    """Get all stored episodes from config-service."""
    org = org_id or _DEFAULT_ORG_ID
    result = _get("/episodes", {"org_id": org, "limit": limit})
    return (result or {}).get("episodes", [])


def search_similar(
    prompt: str,
    org_id: str = "",
    service_name: str = "",
    alert_type: str = "",
    limit: int = 5,
) -> list:
    """Search for similar past investigations via config-service."""
    org = org_id or _DEFAULT_ORG_ID
    result = _post(
        "/episodes/search",
        {
            "org_id": org,
            "alert_type": alert_type or _extract_alert_type_from_prompt(prompt),
            "service_name": service_name or _extract_service_from_prompt(prompt),
            "limit": limit,
        },
    )
    return (result or {}).get("episodes", [])


def get_strategies(
    org_id: str = "", alert_type: str = "", service_name: str = ""
) -> list:
    """Get strategies from config-service."""
    org = org_id or _DEFAULT_ORG_ID
    if alert_type:
        result = _get(
            "/strategies",
            {
                "org_id": org,
                "alert_type": alert_type,
                "service_name": service_name or "*",
            },
        )
        return [result] if result else []
    else:
        result = _get("/strategies/list", {"org_id": org})
        return (result or {}).get("strategies", [])


# ---------------------------------------------------------------------------
# LLM extraction helpers
# ---------------------------------------------------------------------------


def _extract_summary(prompt: str, result_text: str) -> Optional[str]:
    """Extract a 2-3 sentence investigation summary using LLM."""
    llm_prompt = (
        "Summarize this investigation in 2-3 concise sentences.\n\n"
        f"Investigation request: {prompt[:500]}\n\n"
        f"Investigation findings:\n{result_text[:2000]}\n\n"
        "Summary:"
    )
    result = llm_text_completion(llm_prompt).strip()
    return result if result else None


def _extract_alert_type_llm(prompt: str, result_text: str) -> str:
    """Classify alert type using LLM, falling back to keyword matching."""
    llm_prompt = (
        "Classify this investigation into ONE alert type category. "
        "Respond with ONLY the category name (e.g., high_latency, http_500, "
        "out_of_memory, cpu_issue, service_down, crash, timeout, error, "
        "connection_failure, disk_pressure).\n\n"
        f"Investigation: {prompt[:500]}\n\n"
        "Alert type:"
    )
    result = llm_text_completion(llm_prompt, max_tokens=20).strip().lower()
    if result and len(result) < 50:
        # Clean up: remove quotes, periods, etc.
        result = result.strip(".\"'").replace(" ", "_")
        return result
    return _extract_alert_type_from_prompt(prompt)


def _extract_services(prompt: str, result_text: str, hint: str = "") -> List[str]:
    """Extract service names from investigation text."""
    if hint:
        return [hint]
    llm_prompt = (
        "List the service names mentioned in this investigation, "
        "comma-separated. Only list actual service/microservice names, "
        "not tools or technologies.\n\n"
        f"Investigation: {prompt[:500]}\n\n"
        f"Findings: {result_text[:500]}\n\n"
        "Services:"
    )
    result = llm_text_completion(llm_prompt, max_tokens=50).strip()
    if result:
        services = [s.strip().strip(".\"'") for s in result.split(",")]
        return [s for s in services if s and len(s) < 64]
    # Fallback
    service = _extract_service_from_prompt(prompt)
    return [service] if service != "unknown" else []


def _extract_severity(prompt: str, result_text: str) -> str:
    """Assess severity from investigation context."""
    prompt_lower = prompt.lower()
    if any(w in prompt_lower for w in ["critical", "down", "outage", "p1", "sev1"]):
        return "critical"
    if any(w in prompt_lower for w in ["warning", "degraded", "slow", "p2", "sev2"]):
        return "warning"
    return "info"


def _extract_skills_used(tool_calls: List[dict]) -> List[str]:
    """Extract skill names from tool call data."""
    skills = set()
    for tc in tool_calls:
        tool_name = tc.get("tool_name", "")
        if tool_name == "Skill":
            # Extract skill name from input
            tool_input = tc.get("tool_input", {})
            if isinstance(tool_input, dict):
                skill_name = tool_input.get("skill", "")
                if skill_name:
                    skills.add(skill_name)
            elif isinstance(tool_input, str):
                skills.add(tool_input[:64])
    return sorted(skills)


def _extract_key_findings(tool_calls: List[dict]) -> List[dict]:
    """Extract key findings from tool calls with significant output."""
    findings = []
    for tc in tool_calls:
        output = tc.get("tool_output", "")
        if not output or len(str(output)) < 50:
            continue
        tool_name = tc.get("tool_name", "unknown")
        # Only capture Skill and Bash outputs as findings
        if tool_name not in ("Skill", "Bash"):
            continue
        skill_name = ""
        if tool_name == "Skill" and isinstance(tc.get("tool_input"), dict):
            skill_name = tc["tool_input"].get("skill", "")
        findings.append(
            {
                "skill": skill_name or tool_name,
                "query": str(tc.get("tool_input", ""))[:200],
                "finding": str(output)[:500],
            }
        )
    return findings[:10]  # Limit to 10 most relevant


# ---------------------------------------------------------------------------
# Private helpers (keyword-based fallbacks)
# ---------------------------------------------------------------------------


def _extract_service_from_prompt(prompt: str) -> str:
    """Best-effort extraction of service name from prompt text."""
    prompt_lower = prompt.lower()
    for keyword in ["service", "app", "application", "microservice"]:
        idx = prompt_lower.find(keyword)
        if idx > 0:
            words = prompt[:idx].strip().split()
            if words:
                return words[-1].strip(".,;:'\"")
    return "unknown"


def _extract_alert_type_from_prompt(prompt: str) -> str:
    """Best-effort extraction of alert type from prompt text."""
    prompt_lower = prompt.lower()
    alert_keywords = {
        "503": "http_503",
        "500": "http_500",
        "timeout": "timeout",
        "oom": "out_of_memory",
        "memory": "memory_issue",
        "cpu": "cpu_issue",
        "latency": "high_latency",
        "error": "error",
        "crash": "crash",
        "down": "service_down",
    }
    for keyword, alert_type in alert_keywords.items():
        if keyword in prompt_lower:
            return alert_type
    return "unknown"


def _text_indicates_resolution(text: str) -> bool:
    """Check if investigation text indicates resolution."""
    text_lower = text.lower()
    return any(
        keyword in text_lower
        for keyword in [
            "root cause",
            "identified",
            "resolved",
            "found the issue",
            "solution",
        ]
    )


def _extract_concise_root_cause(sources: List[str]) -> Optional[str]:
    """Extract concise root cause using LLM, falling back to truncation."""
    if not sources:
        return None

    combined = "\n\n".join(sources)

    prompt = f"""Extract the core root cause in 1-2 concise sentences from these investigation findings:

{combined[:2000]}

Be specific and technical. If no clear root cause, respond with "Root cause not clearly identified."

Root cause:"""

    result = llm_text_completion(prompt).strip()
    if result:
        logger.info(f"[MEMORY] Extracted root cause: {result[:100]}...")
        return result

    # Fallback: truncate first source
    return sources[0][:200] + "..." if sources[0] else None
