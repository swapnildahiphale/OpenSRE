from events import (
    background_waiting_event,
    task_notification_event,
    task_started_event,
)


def test_task_started_event_shape():
    ev = task_started_event(
        "t1",
        task_id="task-abc",
        description="Check Redis",
        tool_use_id="toolu_1",
        task_type="agent",
    )
    assert ev.type == "task_started"
    assert ev.thread_id == "t1"
    assert ev.data["task_id"] == "task-abc"
    assert ev.data["description"] == "Check Redis"
    assert ev.data["tool_use_id"] == "toolu_1"
    assert ev.data["task_type"] == "agent"


def test_background_waiting_event_shape():
    ev = background_waiting_event(
        "t1",
        pending_count=2,
        pending_task_ids=["a", "b"],
        label="Waiting on 2 background agent(s)…",
    )
    assert ev.type == "background_waiting"
    assert ev.data["pending_count"] == 2
    assert ev.data["pending_task_ids"] == ["a", "b"]
    assert "Waiting" in ev.data["label"]


def test_task_notification_event_shape():
    ev = task_notification_event(
        "t1",
        task_id="task-abc",
        status="completed",
        summary="Redis healthy",
    )
    assert ev.type == "task_notification"
    assert ev.data["status"] == "completed"
    assert ev.data["summary"] == "Redis healthy"
