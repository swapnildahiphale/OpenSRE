from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from investigation_runner import (
    queue_message,
    run_investigation,
    sanitize_thread_id,
    shape_answers_from_card_data,
)


def test_sanitize_thread_id():
    tid = sanitize_thread_id("19:abc@thread.tacv2")
    assert tid.startswith("teams-")
    assert "@" not in tid
    assert " " not in tid


def test_shape_answers_from_card_data():
    questions = [{"question": "Which env?", "options": [{"label": "prod"}]}]
    data = {
        "answer_thread_id": "teams-abc",
        "answer_0": "prod",
        "comment_0": "prod west",
    }
    thread_id, answers = shape_answers_from_card_data(data, questions)
    assert thread_id == "teams-abc"
    assert answers["question_0"] == "prod // prod west"


@pytest.mark.asyncio
async def test_queue_message_posts_url_and_payload():
    mock_resp = AsyncMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = AsyncMock(return_value={"queued": True, "pending_count": 1})

    mock_post_ctx = AsyncMock()
    mock_post_ctx.__aenter__.return_value = mock_resp
    mock_post_ctx.__aexit__.return_value = None

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_post_ctx)

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = None

    with patch(
        "investigation_runner.aiohttp.ClientSession", return_value=mock_session_ctx
    ):
        with patch("investigation_runner.Config") as mock_cfg_cls:
            mock_cfg_cls.return_value.SRE_AGENT_URL = "http://agent:8001/"
            mock_cfg_cls.return_value.INVESTIGATE_AUTH_TOKEN = "tok"

            result = await queue_message(thread_id="teams-abc", text="also check redis")

    mock_session.post.assert_called_once_with(
        "http://agent:8001/threads/teams-abc/queue-message",
        json={"text": "also check redis"},
        headers={"Accept": "text/event-stream", "Authorization": "Bearer tok"},
    )
    assert result == {"queued": True, "pending_count": 1}


async def _make_sse_runner(sse_lines: list[str], send_card, stream_close=None):
    """Helper: mock aiohttp to stream sse_lines then close, run investigation."""
    sse_bytes = ("\n".join(sse_lines) + "\n").encode()

    async def _iter_any():
        yield sse_bytes

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.content.iter_any = _iter_any

    mock_post_ctx = AsyncMock()
    mock_post_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_post_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_post_ctx)

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "investigation_runner.aiohttp.ClientSession", return_value=mock_session_ctx
    ):
        with patch("investigation_runner.Config") as mock_cfg:
            mock_cfg.return_value.SRE_AGENT_URL = "http://agent:8001"
            mock_cfg.return_value.INVESTIGATE_AUTH_TOKEN = ""
            await run_investigation(
                thread_id="teams-test",
                prompt="investigate latency",
                stream_update=AsyncMock(),
                stream_close=stream_close or AsyncMock(),
                send_card=send_card,
                update_card=AsyncMock(),
            )


@pytest.mark.asyncio
async def test_queued_message_continuation_delivers_final_answer():
    """Backend emits result then continues for a queued message.
    Only one final card is sent (at stream close), with the LAST result text."""
    sse_lines = [
        'data: {"type": "thought", "data": {"text": "Checking..."}}',
        'data: {"type": "result", "data": {"text": "First finding"}}',
        'data: {"type": "thought", "data": {"text": "Checking redis too..."}}',
        'data: {"type": "result", "data": {"text": "Final answer after queued message"}}',
    ]
    cards_sent: list[dict] = []

    async def fake_send_card(card: dict):
        cards_sent.append(card)
        return None

    await _make_sse_runner(sse_lines, send_card=fake_send_card)

    # Exactly one card sent (at stream close, not on first result)
    assert len(cards_sent) == 1
    # Card contains the last result, not the first
    card_str = str(cards_sent[0])
    assert "Final answer after queued message" in card_str
    assert "First finding" not in card_str


@pytest.mark.asyncio
async def test_error_event_sends_card_immediately():
    """error event is terminal — card is sent before HTTP stream closes,
    not waiting for the bottom handler."""
    sse_lines = [
        'data: {"type": "error", "data": {"message": "agent timed out"}}',
        # More events after the error — these must NOT be processed
        'data: {"type": "thought", "data": {"text": "ghost thought"}}',
    ]
    cards_sent: list[dict] = []
    stream_close_calls = []

    async def fake_send_card(card: dict):
        cards_sent.append(card)
        return None

    async def fake_stream_close():
        stream_close_calls.append(True)

    await _make_sse_runner(
        sse_lines, send_card=fake_send_card, stream_close=fake_stream_close
    )

    # stream_close called (could be from the error path or bottom handler)
    assert len(stream_close_calls) >= 1
    # Exactly one error card
    assert len(cards_sent) == 1
    card_str = str(cards_sent[0])
    assert "agent timed out" in card_str
