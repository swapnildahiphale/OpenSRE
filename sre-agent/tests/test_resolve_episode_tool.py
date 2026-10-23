"""Unit tests for resolve_episode (in-process resolution tool)."""

import asyncio
from unittest.mock import MagicMock

import pytest
from memory.models import Episode


@pytest.fixture
def fake_store(monkeypatch):
    store = MagicMock()
    store.get_by_correlation.return_value = None
    upserts = []

    def upsert(ep):
        upserts.append(ep)
        store._last = ep

    store.upsert_episode.side_effect = upsert
    monkeypatch.setattr("resolution_tool._store", store)
    monkeypatch.setattr(
        "resolution_tool._embed_episode", lambda ep: [0.01] * 8
    )
    monkeypatch.setattr("resolution_tool._cancel_followup_nudges", lambda tid: None)
    return store, upserts


def test_empty_text_rejected(fake_store):
    import resolution_tool as rt

    out = asyncio.run(rt.apply_resolution("thread-1", "  "))
    assert out.get("is_error") is True
    assert fake_store[0].upsert_episode.call_count == 0


def test_stub_create_when_no_episode(fake_store):
    import resolution_tool as rt

    out = asyncio.run(
        rt.apply_resolution(
            "thread-new",
            "restarted the checkout pod",
            resolved_by="Jane",
            matched_suggestion="yes",
        )
    )
    assert out.get("status") == "confirmed"
    assert fake_store[0].upsert_episode.call_count == 1
    ep = fake_store[1][0]
    assert ep.correlation_id == "thread-new"
    assert ep.resolution_status == "confirmed"
    assert ep.fix_summary == "restarted the checkout pod"
    assert ep.matched_suggestion == "yes"
    assert len(ep.resolution_history) == 1
    assert ep.resolution_history[0]["resolved_by"] == "Jane"


def test_append_not_overwrite_on_second_confirm(fake_store):
    import resolution_tool as rt

    existing = Episode(
        episode_id="e1",
        correlation_id="thread-1",
        resolution_status="confirmed",
        fix_summary="first fix",
        resolution_note_raw="first fix",
        matched_suggestion="yes",
        resolution_history=[
            {
                "ts": "t0",
                "resolved_by": "Alice",
                "text": "first fix",
                "fix_summary": "first fix",
                "matched_suggestion": "yes",
            }
        ],
        created_at="t0",
        updated_at="t0",
    )
    fake_store[0].get_by_correlation.return_value = existing

    asyncio.run(
        rt.apply_resolution(
            "thread-1",
            "also onboarded the secret",
            resolved_by="Bob",
            matched_suggestion="no",
            fix_summary="onboarded secret",
        )
    )
    ep = fake_store[1][0]
    assert len(ep.resolution_history) == 2
    assert ep.resolution_history[0]["text"] == "first fix"
    assert ep.resolution_history[0]["resolved_by"] == "Alice"
    assert ep.resolution_history[1]["resolved_by"] == "Bob"
    assert ep.fix_summary == "onboarded secret"
    assert ep.matched_suggestion == "no"
    assert ep.resolution_status == "confirmed"


def test_tool_handler_delegates(fake_store):
    import resolution_tool as rt

    out = asyncio.run(
        rt.resolve_episode.handler(
            {
                "thread_id": "t1",
                "text": "rolled back deploy",
                "resolved_by": "Ops",
                "matched_suggestion": "unsure",
            }
        )
    )
    assert out.get("status") == "confirmed"
    assert fake_store[1][0].resolution_note_raw == "rolled back deploy"


def test_guidance_mentions_resolve_episode():
    from investigation_lifecycle import investigation_guidance_append

    text = investigation_guidance_append()
    assert "resolve_episode" in text
