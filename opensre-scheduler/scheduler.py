"""Nudge/abandon poll loop for investigation follow-ups.

Owns timing only. Never classifies fixes. Resolution confirm stays on the
agent's resolve_episode path; this service only asks on a timer and gives
up on a timer.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import timedelta
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

CONFIG_SERVICE_URL = os.environ.get("CONFIG_SERVICE_URL", "http://config-service:8080")
SRE_AGENT_URL = os.environ.get("SRE_AGENT_URL", "http://sre-agent:8000")
TEAMS_BOT_URL = os.environ.get("TEAMS_BOT_URL", "").rstrip("/")
INTERNAL_SERVICE_SECRET = os.environ.get("INTERNAL_SERVICE_SECRET", "")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "30"))

# TEMP for manual test — revert to 30m / 3h / 24h before merge
# Cadence must match config-service investigation_followups.window().
WINDOW = {
    0: timedelta(minutes=1),
    1: timedelta(minutes=2),
    2: timedelta(minutes=3),
}


def window(nudge_count: int) -> timedelta:
    """Silence window before the next nudge/abandon check."""
    return WINDOW.get(nudge_count, WINDOW[2])


def _internal_headers() -> dict[str, str]:
    # When secret is set, header value must equal it (config-service auth).
    token = INTERNAL_SERVICE_SECRET or "opensre-scheduler"
    return {"X-Internal-Service": token}


MAX_NUDGES = 3


def build_nudge_text(ctx: dict[str, Any], nudge_count: int = 0) -> str:
    """Plain-text nudge body (Teams / Web chat bubble / last_nudge_text).

    nudge_count is the count *before* this delivery (0 → "1 of 3").
    """
    n = int(nudge_count or 0) + 1
    if n < 1:
        n = 1
    if n > MAX_NUDGES:
        n = MAX_NUDGES
    return (
        f"Has this been fixed yet? Reply here to let me know. "
        f"(Follow-up {n} of {MAX_NUDGES})"
    )


async def scheduler_loop(stop_event: Optional[asyncio.Event] = None) -> None:
    """Poll due followups forever (or until stop_event is set)."""
    while True:
        if stop_event is not None and stop_event.is_set():
            return
        try:
            due = await fetch_due_rows()
            for row in due:
                asyncio.create_task(dispatch(row))
        except Exception:
            logger.exception("scheduler poll failed")
        if stop_event is not None:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=POLL_INTERVAL)
                return
            except asyncio.TimeoutError:
                continue
        else:
            await asyncio.sleep(POLL_INTERVAL)


async def fetch_due_rows(limit: int = 10) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{CONFIG_SERVICE_URL}/api/v1/internal/investigation-followups/due",
            params={"limit": limit},
            headers=_internal_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
    return list(data.get("followups") or [])


async def fetch_nudge_context(correlation_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{SRE_AGENT_URL}/internal/episodes/{correlation_id}/nudge-context",
            headers=_internal_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
    return data if isinstance(data, dict) else {}


async def abandon(row: dict[str, Any]) -> None:
    """Flip Episode to abandoned and stop the Postgres delivery clock."""
    cid = row["correlation_id"]
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Order doesn't matter — both writes are idempotent.
        await client.post(
            f"{SRE_AGENT_URL}/internal/episodes/{cid}/abandon",
            headers=_internal_headers(),
        )
        await client.post(
            f"{CONFIG_SERVICE_URL}/api/v1/internal/investigation-followups/"
            f"{cid}/abandon",
            headers=_internal_headers(),
        )


async def record_nudge_sent(correlation_id: str, last_nudge_text: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{CONFIG_SERVICE_URL}/api/v1/internal/investigation-followups/"
            f"{correlation_id}/nudge-sent",
            headers=_internal_headers(),
            json={"last_nudge_text": last_nudge_text},
        )
        resp.raise_for_status()


async def reschedule(correlation_id: str) -> None:
    """Push due without bumping nudge_count (ticket soft-defer)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{CONFIG_SERVICE_URL}/api/v1/internal/investigation-followups/"
            f"{correlation_id}/reschedule",
            headers=_internal_headers(),
        )
        resp.raise_for_status()


async def send_teams_nudge(
    conversation_ref: dict[str, Any],
    text: str,
    mention_id: Optional[str],
) -> None:
    if not TEAMS_BOT_URL:
        raise RuntimeError("TEAMS_BOT_URL not configured")
    body: dict[str, Any] = {"conversation_ref": conversation_ref, "text": text}
    if mention_id:
        body["mention_id"] = mention_id
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{TEAMS_BOT_URL}/internal/nudge",
            headers=_internal_headers(),
            json=body,
        )
        resp.raise_for_status()


async def call_ticket_followup(
    correlation_id: str, ticket_key: str, nudge_count: int = 0
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{SRE_AGENT_URL}/internal/episodes/{correlation_id}/ticket-followup",
            headers=_internal_headers(),
            json={"ticket_key": ticket_key, "nudge_count": nudge_count},
        )
        resp.raise_for_status()
        data = resp.json()
    return data if isinstance(data, dict) else {}


async def post_web_nudge(correlation_id: str, text: str) -> dict[str, Any]:
    """Ask sre-agent to persist a Web chat-bubble nudge (agent_run)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{SRE_AGENT_URL}/internal/episodes/{correlation_id}/web-nudge",
            headers=_internal_headers(),
            json={"text": text},
        )
        resp.raise_for_status()
        data = resp.json()
    return data if isinstance(data, dict) else {}


async def send_nudge(row: dict[str, Any], ctx: dict[str, Any]) -> None:
    text = build_nudge_text(ctx, int(row.get("nudge_count") or 0))
    channel = (row.get("entry_channel") or "web").lower()
    if channel == "teams":
        if not TEAMS_BOT_URL:
            logger.warning(
                "TEAMS_BOT_URL unset; deferring teams nudge for %s",
                row.get("correlation_id"),
            )
            return
        ref = row.get("conversation_ref")
        if not isinstance(ref, dict) or not ref.get("conversation_id"):
            logger.warning(
                "teams followup %s missing conversation_ref; skipping send",
                row.get("correlation_id"),
            )
            return
        await send_teams_nudge(
            ref,
            text,
            row.get("trigger_actor_teams_id"),
        )
    else:
        # Web: persist an agent chat bubble, then record delivery.
        result = await post_web_nudge(row["correlation_id"], text)
        if result.get("skipped"):
            logger.info(
                "skip web nudge for %s — %s",
                row.get("correlation_id"),
                result.get("reason"),
            )
            return
        if not result.get("ok"):
            logger.warning(
                "web nudge failed for %s: %s",
                row.get("correlation_id"),
                result.get("error"),
            )
            return
    await record_nudge_sent(row["correlation_id"], text)


async def dispatch(row: dict[str, Any]) -> None:
    """Handle one claimed due row: abandon, skip-if-busy, ticket, or channel nudge."""
    try:
        if int(row.get("nudge_count") or 0) >= 3:
            await abandon(row)
            return

        ticket_key = (row.get("ticket_key") or "").strip()
        if ticket_key:
            result = await call_ticket_followup(
                row["correlation_id"],
                ticket_key,
                int(row.get("nudge_count") or 0),
            )
            action = (result.get("action") or "").lower()
            if action == "skip":
                logger.info(
                    "ticket followup skip for %s — %s",
                    row.get("correlation_id"),
                    result.get("reason"),
                )
                return
            if action == "defer":
                reason = str(result.get("reason") or "")
                logger.info(
                    "ticket followup defer for %s — %s",
                    row.get("correlation_id"),
                    reason,
                )
                if reason == "recent_activity":
                    await reschedule(row["correlation_id"])
                return
            if action == "resolved":
                await abandon(row)
                return
            if action in {"ask_assignee", "nudge"}:
                text = result.get("comment_text") or build_nudge_text(
                    {}, int(row.get("nudge_count") or 0)
                )
                await record_nudge_sent(row["correlation_id"], text)
                return
            logger.warning(
                "unknown ticket followup action %s for %s",
                action,
                row.get("correlation_id"),
            )
            return

        ctx = await fetch_nudge_context(row["correlation_id"])
        if ctx.get("has_active_run"):
            logger.info(
                "skip nudge for %s — active run", row.get("correlation_id")
            )
            return
        await send_nudge(row, ctx)
    except Exception:
        logger.exception(
            "dispatch failed for %s", row.get("correlation_id")
        )
