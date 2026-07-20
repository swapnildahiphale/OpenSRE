"""Shared post-investigation memory hooks and root-agent investigation guidance.

investigation_guidance_append — permanent memory + KG instructions (agent.py).
memory_system_prompt_append  — alias for backward compatibility.
finalize_investigation       — per-turn upsert of ONE episode per conversation.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from memory.embeddings import get_default_embedder
from memory.extraction import (
    compute_effectiveness,
    extract_investigation,
    extract_key_findings,
    extract_skills_used,
)
from memory.models import Episode
from memory.store import EpisodeStore

logger = logging.getLogger(__name__)

_MEMORY_GUIDANCE = (
    "\n\n## Memory (agent-driven recall)\n\n"
    "Past investigation summaries are NOT pre-loaded. After you have concrete evidence\n"
    "(error text, failing job/service, stack trace):\n\n"
    '1. Add a todo: "Search memory for similar past investigations"\n'
    "2. Invoke the `memory-search` skill with a specific query (symptom + component + system)\n\n"
    "Do not search memory on vague initial alerts alone — gather facts first (e.g. read build logs).\n"
)

_KG_GUIDANCE = (
    "\n\n## Knowledge graph (agent-driven topology)\n\n"
    "Service topology and blast radius are NOT pre-loaded. After you identify an affected\n"
    "service or deployment (from the alert, logs, or metrics):\n\n"
    '1. Add a todo: "Query knowledge graph for service topology"\n'
    "2. Invoke the `infrastructure-neo4j` skill with the service name\n\n"
    "Skip if no service/component is known yet. If Neo4j is unavailable, continue without it.\n"
)


def investigation_guidance_append() -> str:
    """Permanent root-agent guidance for agent-driven memory and KG recall."""
    return _MEMORY_GUIDANCE + _KG_GUIDANCE


def memory_system_prompt_append() -> str:
    """Backward-compatible alias — use investigation_guidance_append() in new code."""
    return investigation_guidance_append()


_store = EpisodeStore()
_MIN_RESULT_LEN = 50


def ensure_memory_schema() -> None:
    try:
        _store.ensure_schema()
    except Exception as e:
        logger.error("[MEMORY] schema bootstrap failed: %s", e)


def _embed_episode_text(ep: Episode) -> List[float]:
    text = " ".join(
        filter(
            None, [ep.issue_type, ep.issue_description, ep.summary, ep.root_cause or ""]
        )
    )
    return get_default_embedder().embed(text)


def finalize_investigation(
    correlation_id: str,
    agent_run_id: Optional[str],
    prompt: str,
    result_text: str,
    tool_calls: List[dict],
    duration_seconds: Optional[float] = None,
    org_id: str = "default",
    team_node_id: Optional[str] = None,
) -> None:
    try:
        if not result_text or len(result_text.strip()) < _MIN_RESULT_LEN:
            logger.info("[MEMORY-SKIP] result too short for corr=%s", correlation_id)
            return
        prior = _store.get_by_correlation(correlation_id)
        ext = extract_investigation(prompt, result_text, tool_calls, prior=prior)
        now = datetime.now(timezone.utc).isoformat()

        skills = extract_skills_used(tool_calls)
        if prior:
            skills = list(dict.fromkeys((prior.skills_used or []) + skills))

        ep = Episode(
            episode_id=(prior.episode_id if prior else str(uuid.uuid4())),
            correlation_id=correlation_id,
            agent_run_id=agent_run_id,
            org_id=org_id,
            team_node_id=team_node_id,
            issue_type=ext.issue_type,
            issue_description=ext.issue_description,
            severity=ext.severity,
            components=ext.components,
            skills_used=skills,
            key_findings=extract_key_findings(tool_calls),
            resolved=ext.resolved,
            root_cause=ext.root_cause,
            summary=ext.summary,
            effectiveness_score=compute_effectiveness(ext.resolved, ext.root_cause),
            duration_seconds=duration_seconds,
            created_at=(prior.created_at if prior else now),
            updated_at=now,
        )
        ep.embedding = _embed_episode_text(ep)
        _store.upsert_episode(ep)
        logger.info(
            "[MEMORY-STORE] corr=%s resolved=%s type=%s",
            correlation_id,
            ep.resolved,
            ep.issue_type,
        )
    except Exception as e:
        logger.error(
            "[MEMORY-ERROR] finalize failed for corr=%s: %s", correlation_id, e
        )
