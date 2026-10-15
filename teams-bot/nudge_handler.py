"""POST /internal/nudge — outbound Teams nudge for opensre-scheduler.

Auth mirrors config-service's require_internal_service: header must be present;
when INTERNAL_SERVICE_SECRET is set, the header value must match it.
Sends via ActivitySender with the stored per-conversation service_url (not
App.send's default service_url).
"""

from __future__ import annotations

import logging
import os
import secrets
from typing import Any, Optional

logger = logging.getLogger(__name__)

_app: Any = None


def bind_app(app: Any) -> None:
    """Keep a reference so send_to_conversation_ref can use activity_sender."""
    global _app
    _app = app


def register_nudge_route(app: Any) -> None:
    """Register POST /internal/nudge on the SDK HTTP adapter."""
    bind_app(app)
    app.server.adapter.register_route("POST", "/internal/nudge", handle_nudge)


def _header(headers: dict, name: str) -> str:
    if not isinstance(headers, dict):
        return ""
    lower = name.lower()
    for key, value in headers.items():
        if str(key).lower() == lower:
            return str(value or "")
    return ""


def _authorize(headers: dict) -> bool:
    """Return True iff the request is allowed as an internal service call."""
    token = _header(headers, "x-internal-service")
    if not token:
        return False
    expected = os.environ.get("INTERNAL_SERVICE_SECRET", "")
    if expected and not secrets.compare_digest(token, expected):
        return False
    return True


def _build_message(text: str, mention_id: Optional[str]):
    from microsoft_teams.api import Account, MessageActivityInput

    message = MessageActivityInput(text=text or "")
    if mention_id:
        # add_text=False: do not append a second <at>…</at>; the scheduler
        # supplies the full nudge body. The mention entity still notifies.
        message = message.add_mention(
            account=Account(id=mention_id, name=""),
            add_text=False,
        )
    return message


async def send_to_conversation_ref(conversation_ref: dict, message) -> None:
    """Post ``message`` using the stored ConversationReference fields."""
    if _app is None:
        raise RuntimeError("nudge handler not bound to App — call register_nudge_route")
    if not getattr(_app, "id", None):
        raise RuntimeError("app credentials not configured")

    from microsoft_teams.api import Account, ConversationAccount, ConversationReference

    ref = ConversationReference(
        channel_id=conversation_ref.get("channel_id") or "msteams",
        service_url=conversation_ref["service_url"],
        bot=Account(id=_app.id),
        conversation=ConversationAccount(
            id=conversation_ref["conversation_id"],
            tenant_id=conversation_ref.get("tenant_id"),
        ),
    )
    await _app.activity_sender.send(message, ref)


async def handle_nudge(request: dict) -> dict:
    """HttpRouteHandler for POST /internal/nudge."""
    headers = request.get("headers") or {}
    if not _authorize(headers):
        return {"status": 401, "body": {"error": "unauthorized"}}

    body = request.get("body") or {}
    conversation_ref = body.get("conversation_ref")
    text = body.get("text")
    mention_id = body.get("mention_id")

    if not isinstance(conversation_ref, dict):
        return {"status": 400, "body": {"error": "conversation_ref required"}}
    if not conversation_ref.get("conversation_id") or not conversation_ref.get(
        "service_url"
    ):
        return {
            "status": 400,
            "body": {"error": "conversation_ref needs conversation_id and service_url"},
        }
    if not isinstance(text, str) or not text.strip():
        return {"status": 400, "body": {"error": "text required"}}

    mention = mention_id if isinstance(mention_id, str) and mention_id.strip() else None
    message = _build_message(text.strip(), mention)
    try:
        await send_to_conversation_ref(conversation_ref, message)
    except Exception as e:
        logger.exception("nudge send failed: %s", e)
        return {"status": 502, "body": {"error": "send failed"}}

    return {"status": 200, "body": {"ok": True}}
