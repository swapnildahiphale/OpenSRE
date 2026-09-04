"""Shared post-investigation memory hooks and investigation guidance.

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
    "\n\n## OpenSRE episodic memory (`memory-search` skill)\n\n"
    "OpenSRE keeps its own episodic memory of past investigations in Neo4j — separate from any\n"
    "Claude Code MEMORY.md or built-in memory feature, and not pre-loaded. Once YOU have concrete\n"
    "evidence in your own findings (error text, failing job/service, stack trace):\n\n"
    '1. Add a todo: "Search OpenSRE episodic memory for similar past investigations"\n'
    "2. Invoke the `memory-search` skill (not Claude's own memory) with a specific query\n"
    "   (symptom + component + system)\n\n"
    "Do not search on vague initial alerts alone — gather facts first (e.g. read build logs).\n"
    "But once you have evidence in hand, you have either invoked `memory-search` or stated why\n"
    "you did not — whether you are the root planner presenting a root cause, or a dispatched\n"
    "specialist reporting findings back. New evidence later in the same investigation may call\n"
    "for searching again — this is not a one-shot check.\n"
    "Gathering evidence and concluding without ever checking OpenSRE's episodic memory for a\n"
    "prior occurrence is not an acceptable investigation.\n"
)

_KG_GUIDANCE = (
    "\n\n## Knowledge graph (agent-driven topology)\n\n"
    "Service topology and blast radius are NOT pre-loaded. After you identify an affected\n"
    "service or deployment (from the alert, logs, or metrics):\n\n"
    '1. Add a todo: "Query knowledge graph for service topology"\n'
    "2. Invoke the `infrastructure-neo4j` skill with the service name\n\n"
    "Skip if no service/component is known yet. If Neo4j is unavailable, continue without it.\n"
)

_LESSON_STORE_GUIDANCE = (
    "\n\n## Where lessons go\n\n"
    "OpenSRE's own memory is the lesson store. Every conversation is written to it\n"
    "automatically as an episode when the turn ends — you do not need to persist anything\n"
    "yourself, and a correction from a human becomes part of that episode.\n\n"
    "Do NOT write CLAUDE.md or MEMORY.md files to record findings, feedback or lessons.\n"
    "Those are Claude Code session files: they are scoped to this workspace, they are\n"
    "discarded with it, and no future investigation will ever read them. Put the correction\n"
    "in your response instead, so it lands in the episode.\n"
)


def investigation_guidance_append() -> str:
    """Permanent guidance for agent-driven memory and KG recall.

    Appended to the root system prompt and to every registered sub-agent's
    prompt — sub-agents get no preset and no append, so guidance omitted from
    their prompt text does not reach them at all.
    """
    return _MEMORY_GUIDANCE + _KG_GUIDANCE + _LESSON_STORE_GUIDANCE


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
