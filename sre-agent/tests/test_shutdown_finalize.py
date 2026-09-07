import asyncio
from unittest.mock import MagicMock, patch

import pytest
import server_simple


@pytest.fixture(autouse=True)
def clear_shutdown_state():
    server_simple._background_tasks.clear()
    server_simple._active_sessions.clear()
    server_simple._run_id_by_thread.clear()
    yield
    server_simple._background_tasks.clear()
    server_simple._active_sessions.clear()
    server_simple._run_id_by_thread.clear()


def test_shutdown_completes_in_flight_run_as_interrupted():
    server_simple._run_id_by_thread["thread-sd"] = "run-sd"
    server_simple._background_tasks["thread-sd"] = MagicMock()
    server_simple._active_sessions.clear()

    with patch("server_simple.httpx.patch") as mock_patch:
        mock_patch.return_value = MagicMock(raise_for_status=lambda: None)
        asyncio.run(server_simple._finalize_on_shutdown())

    body = mock_patch.call_args.kwargs["json"]
    assert body["status"] == "interrupted"
    assert "shutting down" in (body["error_message"] or "").lower()


def test_shutdown_interrupts_active_session_with_timeout():
    drained = []

    async def fake_interrupt():
        drained.append(True)
        if False:
            yield None

    session = MagicMock()
    session.interrupt = fake_interrupt
    server_simple._active_sessions["thread-sd"] = session
    server_simple._background_tasks["thread-sd"] = MagicMock()
    server_simple._run_id_by_thread.clear()

    asyncio.run(server_simple._finalize_on_shutdown())
    assert drained == [True]
