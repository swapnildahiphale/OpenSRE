# sre-agent/tests/test_async_agent_continuation.py
import asyncio
from unittest.mock import AsyncMock, MagicMock

from agent import InteractiveAgentSession
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    TaskNotificationMessage,
    TaskStartedMessage,
)


def _result(**kwargs):
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


def _assistant(text: str):
    return AssistantMessage(content=[TextBlock(text=text)], model="test")


def test_sync_turn_still_emits_single_terminal_result():
    async def _run():
        session = InteractiveAgentSession("t-sync")
        session.client = MagicMock()

        async def fake_query(prompt):
            async for _ in prompt:
                pass

        async def fake_receive_messages():
            yield _assistant("All good")
            yield _result(result="All good")

        session.client.query = AsyncMock(side_effect=fake_query)
        session.client.receive_messages = MagicMock(side_effect=fake_receive_messages)

        events = [e async for e in session.execute("hi")]
        types = [e.type for e in events]
        assert types.count("result") == 1
        assert "background_waiting" not in types
        assert session.is_running is False

    asyncio.run(_run())


def test_background_task_interim_then_notification_then_final():
    async def _run():
        session = InteractiveAgentSession("t-bg")
        session.client = MagicMock()

        async def fake_query(prompt):
            async for _ in prompt:
                pass

        async def fake_receive_messages():
            yield TaskStartedMessage(
                subtype="task_started",
                data={},
                task_id="bg-1",
                description="Deep check",
                uuid="u1",
                session_id="sess-1",
                tool_use_id="toolu_1",
                task_type="agent",
            )
            yield _assistant("I'll notify you when done")
            yield _result(result="I'll notify you when done")
            yield TaskNotificationMessage(
                subtype="task_notification",
                data={},
                task_id="bg-1",
                status="completed",
                output_file="",
                summary="Found Redis latency",
                uuid="u2",
                session_id="sess-1",
                tool_use_id="toolu_1",
                usage=None,
            )
            yield _assistant("Root cause: Redis latency")
            yield _result(result="Root cause: Redis latency")

        session.client.query = AsyncMock(side_effect=fake_query)
        session.client.receive_messages = MagicMock(side_effect=fake_receive_messages)

        events = [e async for e in session.execute("investigate")]
        types = [e.type for e in events]
        assert "task_started" in types
        assert "background_waiting" in types
        assert "task_notification" in types
        assert types.count("result") == 1
        # Interim text must appear as thought, not as the only result
        thoughts = [e.data.get("text", "") for e in events if e.type == "thought"]
        assert any("notify" in t.lower() for t in thoughts)
        results = [e for e in events if e.type == "result"]
        assert "Redis" in results[0].data["text"]

    asyncio.run(_run())


def test_multiple_outstanding_requires_all_notifications():
    async def _run():
        session = InteractiveAgentSession("t-multi")
        session.client = MagicMock()

        async def fake_query(prompt):
            async for _ in prompt:
                pass

        async def fake_receive_messages():
            for tid in ("bg-1", "bg-2"):
                yield TaskStartedMessage(
                    subtype="task_started",
                    data={},
                    task_id=tid,
                    description=tid,
                    uuid=tid,
                    session_id="sess-1",
                    tool_use_id=None,
                    task_type="agent",
                )
            yield _result(result="waiting")
            yield TaskNotificationMessage(
                subtype="task_notification",
                data={},
                task_id="bg-1",
                status="completed",
                output_file="",
                summary="one",
                uuid="n1",
                session_id="sess-1",
                tool_use_id=None,
                usage=None,
            )
            # Still outstanding bg-2 — must not emit terminal result yet
            yield TaskNotificationMessage(
                subtype="task_notification",
                data={},
                task_id="bg-2",
                status="failed",
                output_file="",
                summary="two failed",
                uuid="n2",
                session_id="sess-1",
                tool_use_id=None,
                usage=None,
            )
            yield _result(result="done after both")

        session.client.query = AsyncMock(side_effect=fake_query)
        session.client.receive_messages = MagicMock(side_effect=fake_receive_messages)

        events = [e async for e in session.execute("multi")]
        assert [e.type for e in events].count("result") == 1
        assert events[-1].type == "result"
        assert "done after both" in events[-1].data["text"]

    asyncio.run(_run())


def test_terminal_result_breaks_when_receive_messages_hangs():
    """execute() must break after terminal ResultMessage even if the stream continues.

    receive_messages() does not end on ResultMessage (unlike receive_response()).
    Finite test mocks hid this: they stopped yielding after the terminal result.
    """

    async def _run():
        session = InteractiveAgentSession("t-hang")
        session.client = MagicMock()

        async def fake_query(prompt):
            async for _ in prompt:
                pass

        hang_forever = asyncio.Event()

        async def fake_receive_messages():
            yield _assistant("Done")
            yield _result(result="Done")
            # Real SDK keeps the stream open; consumer must break after terminal result.
            await hang_forever.wait()
            yield _assistant("should never be seen")

        session.client.query = AsyncMock(side_effect=fake_query)
        session.client.receive_messages = MagicMock(side_effect=fake_receive_messages)

        async def collect_events():
            return [e async for e in session.execute("hi")]

        events = await asyncio.wait_for(collect_events(), timeout=2.0)
        types = [e.type for e in events]
        assert types.count("result") == 1
        assert session.is_running is False

    asyncio.run(_run())
