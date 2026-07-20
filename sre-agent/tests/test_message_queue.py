# sre-agent/tests/test_message_queue.py
import pytest
from agent import InteractiveAgentSession
from message_queue import MESSAGE_QUEUE_HEADER, format_merged_messages


def test_format_single_message():
    body = format_merged_messages(["Also check Redis"])
    assert MESSAGE_QUEUE_HEADER in body
    assert "1. Also check Redis" in body


def test_format_multiple_messages_numbered():
    body = format_merged_messages(["Check Redis", "Ignore payment"])
    assert "1. Check Redis" in body
    assert "2. Ignore payment" in body


def test_format_empty_raises():
    import pytest

    with pytest.raises(ValueError):
        format_merged_messages([])


from events import message_queued_event


def test_message_queued_event_shape():
    ev = message_queued_event("thread-1", pending_count=2)
    assert ev.type == "message_queued"
    assert ev.data["pending_count"] == 2
    assert ev.thread_id == "thread-1"


def test_enqueue_message_rejected_when_not_running():
    session = InteractiveAgentSession("t1")
    with pytest.raises(RuntimeError):
        session.enqueue_message("hello")


def test_enqueue_message_returns_pending_count():
    session = InteractiveAgentSession("t1")
    session.is_running = True
    assert session.enqueue_message("a") == 1
    assert session.enqueue_message("b") == 2


def test_execute_runs_query_concurrent_with_receive():
    """Regression: query(AsyncIterable) must run alongside receive_messages.

    ClaudeSDKClient.query() drains the iterable to completion before returning.
    Our mid-run message generator stays open until the turn ends, so awaiting
    query() first deadlocks and receive_messages() never starts.
    """
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from claude_agent_sdk import ResultMessage

    async def _run():
        session = InteractiveAgentSession("t-concurrent")
        session.client = MagicMock()

        query_started = asyncio.Event()
        concurrency_ok = asyncio.Event()
        query_done = [False]

        async def fake_query(prompt):
            query_started.set()
            # Drain like the real SDK — blocks until generator closes.
            async for _ in prompt:
                pass

        async def fake_query_tracking(prompt):
            try:
                await fake_query(prompt)
            finally:
                query_done[0] = True

        async def fake_receive_messages():
            # Let the concurrent query task start before asserting.
            await asyncio.wait_for(query_started.wait(), timeout=1.0)
            assert not query_done[0]
            concurrency_ok.set()
            yield ResultMessage(
                subtype="success",
                duration_ms=1,
                duration_api_ms=1,
                is_error=False,
                num_turns=1,
                session_id="sess-1",
                result="OK",
            )

        session.client.query = AsyncMock(side_effect=fake_query_tracking)
        session.client.receive_messages = MagicMock(side_effect=fake_receive_messages)

        events = []
        async for event in session.execute("Reply OK"):
            events.append(event)

        assert concurrency_ok.is_set()
        assert any(getattr(e, "type", None) == "result" for e in events)
        assert query_done[0] is True
        assert session.is_running is False

    asyncio.run(_run())


def _result_message(**kwargs):
    from claude_agent_sdk import ResultMessage

    defaults = dict(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=1,
        session_id="sess-1",
        result="OK",
    )
    defaults.update(kwargs)
    return ResultMessage(**defaults)


def test_debounce_merge_yields_one_merged_message():
    """Rapid enqueue_message calls merge into one SDK user yield."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from message_queue import MESSAGE_QUEUE_HEADER

    async def _run():
        session = InteractiveAgentSession("t-debounce")
        session.client = MagicMock()
        queued_yields: list[str] = []

        async def fake_query(prompt):
            async for msg in prompt:
                content = msg.get("message", {}).get("content", "")
                if isinstance(content, str) and MESSAGE_QUEUE_HEADER in content:
                    queued_yields.append(content)

        async def fake_receive_messages():
            await asyncio.sleep(0.8)
            yield _result_message()

        session.client.query = AsyncMock(side_effect=fake_query)
        session.client.receive_messages = MagicMock(side_effect=fake_receive_messages)

        exec_task = asyncio.create_task(_collect_execute(session, "Start"))
        await asyncio.sleep(0.05)
        session.enqueue_message("Check Redis")
        session.enqueue_message("Ignore payment")
        await exec_task

        assert len(queued_yields) == 1
        assert "1. Check Redis" in queued_yields[0]
        assert "2. Ignore payment" in queued_yields[0]

    asyncio.run(_run())


def test_interrupt_clears_pending_without_yield():
    """Interrupt drops pending messages — no post-interrupt generator yield."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from message_queue import MESSAGE_QUEUE_HEADER

    async def _run():
        session = InteractiveAgentSession("t-interrupt")
        session.client = MagicMock()
        queued_yields: list[str] = []

        async def fake_query(prompt):
            async for msg in prompt:
                content = msg.get("message", {}).get("content", "")
                if isinstance(content, str) and MESSAGE_QUEUE_HEADER in content:
                    queued_yields.append(content)

        async def fake_receive_messages():
            await asyncio.sleep(0.5)
            yield _result_message()

        session.client.query = AsyncMock(side_effect=fake_query)
        session.client.receive_messages = MagicMock(side_effect=fake_receive_messages)
        session.client.interrupt = AsyncMock()

        exec_task = asyncio.create_task(_collect_execute(session, "Start"))
        await asyncio.sleep(0.05)
        session.enqueue_message("should be dropped")
        assert session._pending_messages == ["should be dropped"]

        async for _ in session.interrupt():
            pass

        assert session._pending_messages == []
        exec_task.cancel()
        try:
            await exec_task
        except asyncio.CancelledError:
            pass

        assert queued_yields == []

    asyncio.run(_run())


def test_turn_end_flush_yields_pending_and_continues_receive():
    """Pending messages at turn end are force-flushed; receive_messages runs again."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from message_queue import MESSAGE_QUEUE_HEADER

    async def _run():
        session = InteractiveAgentSession("t-flush")
        session.client = MagicMock()
        queued_yields: list[str] = []
        receive_cycles = 0

        async def fake_query(prompt):
            async for msg in prompt:
                content = msg.get("message", {}).get("content", "")
                if isinstance(content, str) and MESSAGE_QUEUE_HEADER in content:
                    queued_yields.append(content)

        async def fake_receive_messages():
            nonlocal receive_cycles
            receive_cycles += 1
            if receive_cycles == 1:
                session.enqueue_message("late guidance")
                yield _result_message(result="Turn 1")
                return
            yield _result_message(result="Turn 2")

        session.client.query = AsyncMock(side_effect=fake_query)
        session.client.receive_messages = MagicMock(side_effect=fake_receive_messages)

        events = await _collect_execute(session, "Start")

        assert receive_cycles == 2
        assert len(queued_yields) == 1
        assert "1. late guidance" in queued_yields[0]
        assert any(
            getattr(e, "type", None) == "message_queued"
            and e.data.get("pending_count") == 0
            for e in events
        )

    asyncio.run(_run())


async def _collect_execute(session: InteractiveAgentSession, prompt: str):
    events = []
    async for event in session.execute(prompt):
        events.append(event)
    return events
