"""Activity routing helpers and handler registration."""

import logging
import re
from typing import Any

import aiohttp
from card_builder import build_welcome_card
from investigation_runner import (
    queue_message,
    run_investigation,
    sanitize_thread_id,
    shape_answers_from_card_data,
    submit_answers,
)
from state import active_investigations, pending_questions

logger = logging.getLogger(__name__)

SUBMIT_VERB = "opensre.submit_answers"


def is_personal_chat(conversation_type: str | None) -> bool:
    return (conversation_type or "").lower() in {"personal", "1:1"}


def is_azure_webchat(channel_id: str | None) -> bool:
    # Azure Bot "Test in Web Chat" uses channelId=webchat (not Teams personal scope).
    return (channel_id or "").lower() == "webchat"


def is_direct_bot_chat(
    conversation_type: str | None, channel_id: str | None = None
) -> bool:
    return is_personal_chat(conversation_type) or is_azure_webchat(channel_id)


def should_handle_message(
    *,
    text: str,
    mentioned: bool,
    conversation_type: str | None,
    channel_id: str | None = None,
) -> bool:
    if is_direct_bot_chat(conversation_type, channel_id):
        return bool((text or "").strip())
    return mentioned and bool((text or "").strip())


def strip_bot_mention(text: str, bot_name: str = "OpenSRE") -> str:
    cleaned = re.sub(r"<at>[^<]*</at>", "", text or "", flags=re.IGNORECASE)
    cleaned = re.sub(re.escape(bot_name), "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _dict_to_adaptive_card(card: dict):
    # SDK MessageActivityInput.add_card() requires typed AdaptiveCard, not raw dict.
    from microsoft_teams.cards.core import AdaptiveCard

    return AdaptiveCard.model_validate(card)


def register_handlers(app) -> None:
    from microsoft_teams.api import MessageActivity, MessageActivityInput
    from microsoft_teams.apps import ActivityContext

    @app.on_message
    async def on_message(ctx: ActivityContext[MessageActivity]):
        activity = ctx.activity
        conversation = activity.conversation
        conv_type = getattr(conversation, "conversation_type", None) or getattr(
            conversation, "conversationType", None
        )
        text = activity.text or ""
        mentioned = _has_mention(activity)
        channel_id = getattr(activity, "channel_id", None) or getattr(
            activity, "channelId", None
        )
        if not should_handle_message(
            text=text,
            mentioned=mentioned,
            conversation_type=conv_type,
            channel_id=channel_id,
        ):
            return

        cleaned = strip_bot_mention(text)
        if not cleaned:
            return

        if cleaned.lower() in {"help", "status"}:
            await ctx.send(
                MessageActivityInput().add_card(
                    _dict_to_adaptive_card(build_welcome_card())
                )
            )
            return

        thread_id = sanitize_thread_id(conversation.id)

        if thread_id in active_investigations:
            try:
                await queue_message(thread_id=thread_id, text=cleaned)
            except aiohttp.ClientResponseError as exc:
                if exc.status == 409:
                    # Race: investigation finished in the window between our check and
                    # the queue call. Fall through so the message starts a follow-up run
                    # with the same thread_id (agent retains conversation context).
                    pass
                else:
                    logger.exception("queue_message failed for thread %s", thread_id)
                    await ctx.send(
                        MessageActivityInput().add_text(
                            "Couldn't queue your message — please try again."
                        )
                    )
                    return
            else:
                await ctx.send(
                    MessageActivityInput().add_text(
                        "Message queued — I'll use it after the current step."
                    )
                )
                return

        # Channel/group threads reject Bot Framework streaming (HTTP 405).
        # 1:1 and Azure Web Chat still use ctx.stream for live progress.
        # Channels edit one text bubble via PUT (MessageActivityInput.with_id).
        use_stream = is_direct_bot_chat(conv_type, channel_id)
        progress_activity_id: str | None = None

        async def stream_update(content: str) -> None:
            nonlocal progress_activity_id
            if use_stream:
                ctx.stream.update(content)
                return
            if not progress_activity_id:
                return
            try:
                # ActivitySender.send() PUTs when activity.id is set — no new toast.
                await ctx.send(
                    MessageActivityInput(text=content).with_id(progress_activity_id)
                )
            except Exception:
                logger.exception(
                    "failed to update channel progress %s", progress_activity_id
                )

        async def stream_close() -> None:
            # HttpStream.close() is synchronous; must run before sending cards.
            if use_stream:
                ctx.stream.close()

        async def send_card(card: dict):
            sent = await ctx.send(
                MessageActivityInput().add_card(_dict_to_adaptive_card(card))
            )
            return getattr(sent, "id", None)

        async def update_card(activity_id: str, card: dict) -> None:
            # PUT the existing activity so question-timeout does not spawn a new card.
            try:
                await ctx.send(
                    MessageActivityInput()
                    .with_id(activity_id)
                    .add_card(_dict_to_adaptive_card(card))
                )
            except Exception:
                logger.exception("failed to update/replace card %s", activity_id)

        if not use_stream:
            sent = await ctx.send(
                MessageActivityInput().add_text(
                    "Working on it — I'll reply in this thread."
                )
            )
            progress_activity_id = getattr(sent, "id", None)

        # Await runner in-handler so ctx.stream stays valid for 1:1 / Web Chat.
        await run_investigation(
            thread_id=thread_id,
            prompt=cleaned,
            stream_update=stream_update,
            stream_close=stream_close,
            send_card=send_card,
            update_card=update_card,
        )

    @app.on_card_action_execute(SUBMIT_VERB)
    async def on_submit(ctx):
        flat = _flatten_card_action_data(ctx.activity)
        thread_id = flat.get("answer_thread_id")
        questions = pending_questions.get(thread_id or "", [])
        thread_id, answers = shape_answers_from_card_data(flat, questions)
        if not thread_id:
            return _ok_response("Missing thread id")
        await submit_answers(thread_id=thread_id, answers=answers)
        pending_questions.pop(thread_id, None)
        return _ok_response("Answer submitted")


def _has_mention(activity: Any) -> bool:
    entities = getattr(activity, "entities", None) or []
    for ent in entities:
        ent_type = getattr(ent, "type", None)
        if ent_type == "mention":
            return True
    return False


def _flatten_card_action_data(activity: Any) -> dict:
    value = getattr(activity, "value", None)
    action = getattr(value, "action", None) if value else None
    data = getattr(action, "data", None) if action else None
    if not isinstance(data, dict):
        return {}
    # Action.Execute merges Input.* field values into action.data alongside verb data.
    return dict(data)


def _ok_response(message: str):
    from microsoft_teams.api import AdaptiveCardActionMessageResponse

    return AdaptiveCardActionMessageResponse(
        status_code=200,
        type="application/vnd.microsoft.activity.message",
        value=message,
    )
