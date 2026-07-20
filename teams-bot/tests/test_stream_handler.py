from state import InvestigationState
from stream_handler import handle_stream_event, parse_sse_event


def test_parse_sse_event_valid():
    assert parse_sse_event('data: {"type": "thought", "data": {"text": "hi"}}') == {
        "type": "thought",
        "data": {"text": "hi"},
    }


def test_parse_sse_event_ignores_non_data():
    assert parse_sse_event(": keepalive") is None


def test_thought_appends_section():
    state = InvestigationState(thread_id="t1")
    result = handle_stream_event(
        state, {"type": "thought", "data": {"text": "Checking pods"}}
    )
    assert result.update_progress is True
    assert state.thoughts[-1].text == "Checking pods"


def test_tool_start_and_end():
    state = InvestigationState(thread_id="t1")
    handle_stream_event(state, {"type": "thought", "data": {"text": "Go"}})
    handle_stream_event(
        state,
        {
            "type": "tool_start",
            "data": {
                "name": "Bash",
                "tool_use_id": "u1",
                "input": {"command": "kubectl get pods"},
            },
        },
    )
    assert state.current_tool is not None
    assert state.current_tool.running is True
    handle_stream_event(
        state,
        {
            "type": "tool_end",
            "data": {"name": "Bash", "tool_use_id": "u1", "success": True},
        },
    )
    assert state.current_tool is None
    assert state.thoughts[-1].tools[0].running is False


def test_question_and_result():
    state = InvestigationState(thread_id="t1")
    q = handle_stream_event(
        state,
        {"type": "question", "data": {"questions": [{"question": "Which env?"}]}},
    )
    assert q.post_question == [{"question": "Which env?"}]
    handle_stream_event(state, {"type": "result", "data": {"text": "Done"}})
    assert state.final_result == "Done"


def test_task_started_updates_progress_not_finished():
    state = InvestigationState(thread_id="t1")
    result = handle_stream_event(
        state,
        {
            "type": "task_started",
            "data": {
                "task_id": "task-1",
                "description": "Check Redis",
            },
        },
    )
    assert result.update_progress is True
    assert result.finished is False


def test_background_waiting_sets_label_and_updates_progress():
    state = InvestigationState(thread_id="t1")
    result = handle_stream_event(
        state,
        {
            "type": "background_waiting",
            "data": {
                "pending_count": 2,
                "pending_task_ids": ["a", "b"],
                "label": "Waiting on 2 background agent(s)…",
            },
        },
    )
    assert result.update_progress is True
    assert result.finished is False
    assert state.background_waiting_label == "Waiting on 2 background agent(s)…"
    assert state.pending_background_count == 2


def test_background_waiting_synthesizes_label_from_pending_count():
    state = InvestigationState(thread_id="t1")
    handle_stream_event(
        state,
        {
            "type": "background_waiting",
            "data": {
                "pending_count": 1,
                "pending_task_ids": ["a"],
            },
        },
    )
    assert state.background_waiting_label == "Waiting on 1 background agent(s)…"
    assert state.pending_background_count == 1


def test_task_notification_updates_progress_not_finished():
    state = InvestigationState(thread_id="t1")
    handle_stream_event(
        state,
        {
            "type": "background_waiting",
            "data": {
                "pending_count": 1,
                "pending_task_ids": ["task-abc"],
                "label": "Waiting on 1 background agent(s)…",
            },
        },
    )
    result = handle_stream_event(
        state,
        {
            "type": "task_notification",
            "data": {
                "task_id": "task-abc",
                "status": "completed",
                "summary": "Redis healthy",
            },
        },
    )
    assert result.update_progress is True
    assert result.finished is False
    assert "Background agent finished" in (state.background_notification or "")
    assert "Redis healthy" in (state.background_notification or "")
    assert state.background_waiting_label is None
    assert state.pending_background_count == 0


def test_result_clears_waiting_fields_but_marks_finished():
    state = InvestigationState(thread_id="t1")
    handle_stream_event(
        state,
        {
            "type": "background_waiting",
            "data": {
                "pending_count": 1,
                "pending_task_ids": ["a"],
                "label": "Waiting…",
            },
        },
    )
    result = handle_stream_event(state, {"type": "result", "data": {"text": "Done"}})
    assert result.finished is True
    assert state.background_waiting_label is None
    assert state.pending_background_count == 0
    assert state.background_notification is None


def test_error_clears_waiting_fields():
    state = InvestigationState(thread_id="t1")
    handle_stream_event(
        state,
        {
            "type": "background_waiting",
            "data": {
                "pending_count": 1,
                "pending_task_ids": ["a"],
                "label": "Waiting…",
            },
        },
    )
    result = handle_stream_event(
        state, {"type": "error", "data": {"message": "boom"}}
    )
    assert result.finished is True
    assert state.background_waiting_label is None
    assert state.pending_background_count == 0
    assert state.background_notification is None
