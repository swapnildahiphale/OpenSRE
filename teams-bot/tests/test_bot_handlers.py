from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bot_handlers import (
    is_azure_webchat,
    is_direct_bot_chat,
    is_personal_chat,
    register_handlers,
    should_handle_message,
    strip_bot_mention,
)
from investigation_runner import sanitize_thread_id
from state import active_investigations


def test_strip_bot_mention():
    assert (
        strip_bot_mention("Hello <at>OpenSRE</at> check pods", "OpenSRE")
        == "Hello  check pods"
    )


def test_channel_requires_mention():
    assert (
        should_handle_message(text="hi", mentioned=False, conversation_type="channel")
        is False
    )
    assert (
        should_handle_message(text="hi", mentioned=True, conversation_type="channel")
        is True
    )


def test_personal_always_handles():
    assert (
        should_handle_message(
            text="help", mentioned=False, conversation_type="personal"
        )
        is True
    )


@pytest.mark.asyncio
async def test_channel_investigation_does_not_use_activity_stream():
    on_message_handler = None

    class FakeApp:
        def on_message(self, fn):
            nonlocal on_message_handler
            on_message_handler = fn
            return fn

        def on_card_action_execute(self, _verb):
            def decorator(fn):
                return fn

            return decorator

    register_handlers(FakeApp())
    ctx = MagicMock()
    ctx.send = AsyncMock(return_value=MagicMock(id="act-ch"))
    ctx.stream = MagicMock()
    ctx.stream.update = MagicMock()
    ctx.stream.close = MagicMock()
    mention = MagicMock(type="mention")
    ctx.activity = MagicMock(
        text="<at>OpenSRE</at> Investigate oc-1234",
        entities=[mention],
        conversation=MagicMock(
            # Synthetic conversation id — never paste a real Teams thread id.
            id="19:00000000000000000000000000000000@thread.tacv2",
            conversation_type="channel",
            conversationType=None,
        ),
        channel_id="msteams",
        channelId="msteams",
    )
    with patch("bot_handlers.run_investigation", new_callable=AsyncMock) as mock_run:
        await on_message_handler(ctx)

    mock_run.assert_awaited_once()
    kwargs = mock_run.await_args.kwargs
    assert kwargs["plain_text_final"] is True
    ctx.stream.update.assert_not_called()
    # Ack is one send; progress edits reuse that activity id (PUT, not stream).
    assert ctx.send.await_count == 1
    await kwargs["stream_update"]("Working on Jira…")
    await kwargs["stream_close"]()
    ctx.stream.update.assert_not_called()
    ctx.stream.close.assert_not_called()
    assert ctx.send.await_count == 2
    progress = ctx.send.await_args_list[-1].args[0]
    assert progress.id == "act-ch"
    assert progress.text == "Working on Jira…"
    await kwargs["update_card"](
        "act-q", {"type": "AdaptiveCard", "body": [], "actions": []}
    )
    timeout_card = ctx.send.await_args_list[-1].args[0]
    assert timeout_card.id == "act-q"


@pytest.mark.asyncio
async def test_personal_investigation_keeps_activity_stream():
    on_message_handler = None

    class FakeApp:
        def on_message(self, fn):
            nonlocal on_message_handler
            on_message_handler = fn
            return fn

        def on_card_action_execute(self, _verb):
            def decorator(fn):
                return fn

            return decorator

    register_handlers(FakeApp())
    ctx = MagicMock()
    ctx.send = AsyncMock(return_value=MagicMock(id="act-p"))
    ctx.stream = MagicMock()
    ctx.stream.update = MagicMock()
    ctx.stream.close = MagicMock()
    ctx.activity = MagicMock(
        text="oc-1234",
        entities=[],
        conversation=MagicMock(
            id="a:16i0nmlwexample",
            conversation_type="personal",
            conversationType=None,
        ),
        channel_id="msteams",
        channelId="msteams",
    )
    with patch("bot_handlers.run_investigation", new_callable=AsyncMock) as mock_run:
        await on_message_handler(ctx)

    kwargs = mock_run.await_args.kwargs
    await kwargs["stream_update"]("progress")
    await kwargs["stream_close"]()
    ctx.stream.update.assert_called_once()
    ctx.stream.close.assert_called_once()
    assert kwargs["plain_text_final"] is False


def test_is_personal_chat():
    assert is_personal_chat("personal") is True
    assert is_personal_chat("channel") is False


def test_azure_webchat_handles_without_mention():
    assert is_azure_webchat("webchat") is True
    assert is_direct_bot_chat(None, "webchat") is True
    assert (
        should_handle_message(
            text="help",
            mentioned=False,
            conversation_type=None,
            channel_id="webchat",
        )
        is True
    )


@pytest.mark.asyncio
async def test_on_message_active_thread_queues_instead_of_investigation():
    on_message_handler = None

    class FakeApp:
        def on_message(self, fn):
            nonlocal on_message_handler
            on_message_handler = fn
            return fn

        def on_card_action_execute(self, _verb):
            def decorator(fn):
                return fn

            return decorator

    register_handlers(FakeApp())
    assert on_message_handler is not None

    conversation_id = "19:abc@thread.tacv2"
    thread_id = sanitize_thread_id(conversation_id)
    active_investigations.add(thread_id)

    ctx = MagicMock()
    ctx.send = AsyncMock(return_value=MagicMock(id="act-1"))
    ctx.stream = MagicMock()
    ctx.stream.update = MagicMock()
    ctx.stream.close = MagicMock()

    activity = MagicMock()
    activity.text = "also check redis"
    activity.entities = []
    activity.conversation = MagicMock(
        id=conversation_id, conversation_type="personal", conversationType=None
    )
    activity.channel_id = None
    activity.channelId = None
    ctx.activity = activity

    try:
        with patch("bot_handlers.queue_message", new_callable=AsyncMock) as mock_queue:
            with patch(
                "bot_handlers.run_investigation", new_callable=AsyncMock
            ) as mock_run:
                await on_message_handler(ctx)

        mock_queue.assert_awaited_once_with(
            thread_id=thread_id, text="also check redis"
        )
        mock_run.assert_not_awaited()
        ctx.send.assert_awaited_once()
        sent_input = ctx.send.await_args.args[0]
        assert sent_input.text == "Message queued — I'll use it after the current step."
    finally:
        active_investigations.discard(thread_id)


@pytest.mark.asyncio
async def test_on_message_queue_409_starts_follow_up_investigation():
    """409 from queue-message means investigation just finished.
    The message must start a follow-up run (same thread_id keeps agent context);
    no error text should be sent to the user."""
    on_message_handler = None

    class FakeApp:
        def on_message(self, fn):
            nonlocal on_message_handler
            on_message_handler = fn
            return fn

        def on_card_action_execute(self, _verb):
            def decorator(fn):
                return fn

            return decorator

    register_handlers(FakeApp())
    assert on_message_handler is not None

    conversation_id = "19:409@thread.tacv2"
    thread_id = sanitize_thread_id(conversation_id)
    active_investigations.add(thread_id)

    ctx = MagicMock()
    ctx.send = AsyncMock(return_value=MagicMock(id="act-409"))
    ctx.stream = MagicMock()
    ctx.activity = MagicMock(
        text="follow up",
        entities=[],
        conversation=MagicMock(
            id=conversation_id, conversation_type="personal", conversationType=None
        ),
        channel_id=None,
        channelId=None,
    )

    import aiohttp

    try:
        with patch("bot_handlers.queue_message", new_callable=AsyncMock) as mock_queue:
            mock_queue.side_effect = aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=409,
                message="Conflict",
            )
            with patch(
                "bot_handlers.run_investigation", new_callable=AsyncMock
            ) as mock_run:
                await on_message_handler(ctx)

        # Must start a follow-up investigation — not drop the message.
        mock_run.assert_awaited_once()
        # No error text sent to user.
        ctx.send.assert_not_awaited()
    finally:
        active_investigations.discard(thread_id)
