"""Unit tests for opensre-scheduler dispatch / window."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

import scheduler


def test_window_boundaries():
    assert scheduler.window(0) == timedelta(minutes=1)
    assert scheduler.window(1) == timedelta(minutes=2)
    assert scheduler.window(2) == timedelta(minutes=3)
    assert scheduler.window(3) == timedelta(minutes=3)
    assert scheduler.window(99) == timedelta(minutes=3)


def test_build_nudge_text_includes_n_of_max():
    assert "1 of 3" in scheduler.build_nudge_text({}, 0)
    assert "2 of 3" in scheduler.build_nudge_text({}, 1)
    assert "3 of 3" in scheduler.build_nudge_text({}, 2)


@pytest.mark.asyncio
async def test_dispatch_abandons_when_nudge_count_ge_3():
    row = {"correlation_id": "t1", "nudge_count": 3, "entry_channel": "web"}
    with patch.object(scheduler, "abandon", new_callable=AsyncMock) as abandon:
        with patch.object(
            scheduler, "fetch_nudge_context", new_callable=AsyncMock
        ) as ctx:
            with patch.object(
                scheduler, "send_nudge", new_callable=AsyncMock
            ) as send:
                await scheduler.dispatch(row)
    abandon.assert_awaited_once_with(row)
    ctx.assert_not_awaited()
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_skips_when_active_run():
    row = {"correlation_id": "t2", "nudge_count": 0, "entry_channel": "web"}
    with patch.object(
        scheduler,
        "fetch_nudge_context",
        new_callable=AsyncMock,
        return_value={"has_active_run": True},
    ):
        with patch.object(
            scheduler, "send_nudge", new_callable=AsyncMock
        ) as send:
            with patch.object(
                scheduler, "abandon", new_callable=AsyncMock
            ) as abandon:
                await scheduler.dispatch(row)
    send.assert_not_awaited()
    abandon.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_sends_nudge_when_idle():
    row = {"correlation_id": "t3", "nudge_count": 1, "entry_channel": "web"}
    ctx = {"has_active_run": False, "summary": "slow", "recommended_actions": []}
    with patch.object(
        scheduler,
        "fetch_nudge_context",
        new_callable=AsyncMock,
        return_value=ctx,
    ):
        with patch.object(
            scheduler, "send_nudge", new_callable=AsyncMock
        ) as send:
            await scheduler.dispatch(row)
    send.assert_awaited_once_with(row, ctx)


@pytest.mark.asyncio
async def test_send_nudge_web_posts_chat_then_records():
    row = {
        "correlation_id": "t-web",
        "nudge_count": 0,
        "entry_channel": "web",
    }
    with patch.object(
        scheduler,
        "post_web_nudge",
        new_callable=AsyncMock,
        return_value={"ok": True, "run_id": "abc"},
    ) as web:
        with patch.object(
            scheduler, "record_nudge_sent", new_callable=AsyncMock
        ) as recorded:
            with patch.object(
                scheduler, "send_teams_nudge", new_callable=AsyncMock
            ) as teams:
                await scheduler.send_nudge(row, {})
    web.assert_awaited_once()
    recorded.assert_awaited_once()
    assert "Has this been fixed yet?" in recorded.await_args.args[1]
    assert "1 of 3" in recorded.await_args.args[1]
    teams.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_nudge_web_skips_record_when_active():
    row = {
        "correlation_id": "t-web-busy",
        "nudge_count": 0,
        "entry_channel": "web",
    }
    with patch.object(
        scheduler,
        "post_web_nudge",
        new_callable=AsyncMock,
        return_value={"ok": False, "skipped": True, "reason": "active_run"},
    ):
        with patch.object(
            scheduler, "record_nudge_sent", new_callable=AsyncMock
        ) as recorded:
            await scheduler.send_nudge(row, {})
    recorded.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_nudge_teams_posts_then_records(monkeypatch):
    monkeypatch.setattr(scheduler, "TEAMS_BOT_URL", "http://teams-bot:3978")
    row = {
        "correlation_id": "t-teams",
        "nudge_count": 0,
        "entry_channel": "teams",
        "trigger_actor_teams_id": "29:jane",
        "conversation_ref": {
            "conversation_id": "19:abc",
            "service_url": "https://smba.example/",
            "channel_id": "msteams",
        },
    }
    with patch.object(
        scheduler, "send_teams_nudge", new_callable=AsyncMock
    ) as teams:
        with patch.object(
            scheduler, "record_nudge_sent", new_callable=AsyncMock
        ) as recorded:
            await scheduler.send_nudge(row, {})
    teams.assert_awaited_once()
    assert teams.await_args.args[2] == "29:jane"
    recorded.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_ticket_resolved_abandons():
    row = {
        "correlation_id": "t-jira",
        "nudge_count": 0,
        "entry_channel": "web",
        "ticket_key": "OPS-1",
    }
    with patch.object(
        scheduler,
        "call_ticket_followup",
        new_callable=AsyncMock,
        return_value={"action": "resolved", "fix_summary": "fixed"},
    ):
        with patch.object(scheduler, "abandon", new_callable=AsyncMock) as abandon:
            with patch.object(
                scheduler, "send_nudge", new_callable=AsyncMock
            ) as send:
                await scheduler.dispatch(row)
    abandon.assert_awaited_once_with(row)
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_ticket_nudge_records_sent():
    row = {
        "correlation_id": "t-jira2",
        "nudge_count": 0,
        "entry_channel": "web",
        "ticket_key": "OPS-2",
    }
    with patch.object(
        scheduler,
        "call_ticket_followup",
        new_callable=AsyncMock,
        return_value={"action": "nudge", "comment_text": "please update"},
    ):
        with patch.object(
            scheduler, "record_nudge_sent", new_callable=AsyncMock
        ) as recorded:
            with patch.object(
                scheduler, "send_nudge", new_callable=AsyncMock
            ) as send:
                await scheduler.dispatch(row)
    recorded.assert_awaited_once_with("t-jira2", "please update")
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_ticket_skip_does_nothing():
    row = {
        "correlation_id": "t-jira3",
        "nudge_count": 0,
        "ticket_key": "OPS-3",
        "entry_channel": "web",
    }
    with patch.object(
        scheduler,
        "call_ticket_followup",
        new_callable=AsyncMock,
        return_value={"action": "skip", "reason": "active_run"},
    ):
        with patch.object(scheduler, "abandon", new_callable=AsyncMock) as abandon:
            with patch.object(
                scheduler, "record_nudge_sent", new_callable=AsyncMock
            ) as recorded:
                with patch.object(
                    scheduler, "reschedule", new_callable=AsyncMock
                ) as resched:
                    await scheduler.dispatch(row)
    abandon.assert_not_awaited()
    recorded.assert_not_awaited()
    resched.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_ticket_recent_activity_reschedules():
    row = {
        "correlation_id": "t-jira-soft",
        "nudge_count": 1,
        "ticket_key": "OPS-9",
        "entry_channel": "web",
    }
    with patch.object(
        scheduler,
        "call_ticket_followup",
        new_callable=AsyncMock,
        return_value={"action": "defer", "reason": "recent_activity"},
    ):
        with patch.object(
            scheduler, "reschedule", new_callable=AsyncMock
        ) as resched:
            with patch.object(
                scheduler, "record_nudge_sent", new_callable=AsyncMock
            ) as recorded:
                await scheduler.dispatch(row)
    resched.assert_awaited_once_with("t-jira-soft")
    recorded.assert_not_awaited()
