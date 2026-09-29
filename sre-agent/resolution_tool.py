"""In-process resolve_episode tool — record a human-confirmed production fix.

Triggered from inside a resumed investigation turn when the agent recognizes
a fix report. Resolution state lives on the Neo4j Episode; this module also
stops pending nudges via config-service (sets investigation_followups.stopped_at).
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from claude_agent_sdk import create_sdk_mcp_server, tool

from memory.embeddings import get_default_embedder
from memory.models import Episode
from memory.store import EpisodeStore

logger = logging.getLogger(__name__)

_store = EpisodeStore()
_CONFIG_SERVICE_URL = os.getenv("CONFIG_SERVICE_URL", "http://config-service:8080")
_INTERNAL_HEADERS = {"X-Internal-Service": "sre-agent"}


def _embed_episode(ep: Episode) -> list[float]:
    text = " ".join(
        filter(
            None,
            [
                ep.issue_type,
                ep.issue_description,
                ep.summary,
                ep.root_cause or "",
                ep.fix_summary or "",
            ],
        )
    )
    return get_default_embedder().embed(text)


def _stub_episode(thread_id: str) -> Episode:
    now = datetime.now(timezone.utc).isoformat()
    return Episode(
        episode_id=str(uuid.uuid4()),
        correlation_id=thread_id,
        issue_type="unknown",
        issue_description="",
        summary="",
        resolution_status="open",
        created_at=now,
        updated_at=now,
    )


def _cancel_followup_nudges(thread_id: str) -> None:
    """Reuse abandon endpoint — sets stopped_at; idempotent."""
    try:
        resp = httpx.post(
            f"{_CONFIG_SERVICE_URL}/api/v1/internal/investigation-followups/"
            f"{thread_id}/abandon",
            headers=_INTERNAL_HEADERS,
            timeout=5.0,
        )
        if resp.status_code == 404:
            logger.info(
                "[RESOLVE] no followup row to stop for corr=%s", thread_id
            )
            return
        resp.raise_for_status()
    except Exception as e:
        logger.warning(
            "[RESOLVE] failed to stop followup nudges for corr=%s: %s",
            thread_id,
            e,
        )


async def apply_resolution(
    thread_id: str,
    text: str,
    resolved_by: Optional[str] = None,
    matched_suggestion: Optional[str] = None,
    fix_summary: Optional[str] = None,
) -> dict[str, Any]:
    """Core write path — callable from tests without going through the SDK tool."""
    text = (text or "").strip()
    if not text:
        return {
            "content": [{"type": "text", "text": "error: empty confirm text"}],
            "is_error": True,
        }

    suggestion = matched_suggestion or "unsure"
    if suggestion not in ("yes", "no", "unsure"):
        suggestion = "unsure"

    summary = (fix_summary or text).strip() or text
    episode = _store.get_by_correlation(thread_id)
    if episode is None:
        episode = _stub_episode(thread_id)

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "resolved_by": resolved_by,
        "text": text,
        "fix_summary": summary,
        "matched_suggestion": suggestion,
    }
    history = list(episode.resolution_history or [])
    history.append(entry)
    episode.resolution_history = history
    episode.resolution_note_raw = text
    episode.fix_summary = summary
    episode.matched_suggestion = suggestion  # type: ignore[assignment]
    episode.resolution_status = "confirmed"
    episode.updated_at = entry["ts"]
    episode.embedding = _embed_episode(episode)
    _store.upsert_episode(episode)
    _cancel_followup_nudges(thread_id)

    logger.info(
        "[RESOLVE] confirmed corr=%s by=%s matched=%s",
        thread_id,
        resolved_by,
        suggestion,
    )
    return {
        "content": [
            {
                "type": "text",
                "text": f"Recorded confirmed fix for {thread_id}: {summary}",
            }
        ],
        "status": "confirmed",
    }


@tool(
    "resolve_episode",
    (
        "Record a human-confirmed production fix onto this investigation's "
        "episodic memory. Call when the user's message describes what fixed "
        "the issue (not a request for more investigation). If unsure whether "
        "the message is a fix report, ask a clarifying question instead of "
        "calling this tool."
    ),
    {
        "thread_id": str,
        "text": str,
        "resolved_by": str,
        "matched_suggestion": str,
        "fix_summary": str,
    },
)
async def resolve_episode(args: dict) -> dict:
    return await apply_resolution(
        thread_id=args.get("thread_id") or "",
        text=args.get("text") or "",
        resolved_by=args.get("resolved_by") or None,
        matched_suggestion=args.get("matched_suggestion") or None,
        fix_summary=args.get("fix_summary") or None,
    )


def build_resolution_mcp_server():
    """SDK MCP server config for ClaudeAgentOptions.mcp_servers."""
    return create_sdk_mcp_server(
        name="resolution",
        version="1.0.0",
        tools=[resolve_episode],
    )


RESOLVE_EPISODE_TOOL_NAME = "resolve_episode"
