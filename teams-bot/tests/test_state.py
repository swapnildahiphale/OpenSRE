from state import (
    InvestigationState,
    ThoughtSection,
    ToolCall,
    pending_questions,
    question_activity_ids,
)


def test_investigation_state_starts_empty():
    state = InvestigationState(thread_id="teams-abc")
    assert state.thoughts == []
    assert state.current_tool is None
    assert state.final_result is None
    assert state.error is None
    assert state.current_thought_text() == ""


def test_current_thought_text_returns_last_thought():
    state = InvestigationState(thread_id="teams-abc")
    state.thoughts.append(ThoughtSection(text="Checking pods"))
    state.thoughts.append(ThoughtSection(text="Checking logs"))
    assert state.current_thought_text() == "Checking logs"


def test_tool_call_defaults():
    tool = ToolCall(name="Bash")
    assert tool.running is True
    assert tool.success is None
    assert tool.input == {}


def test_pending_maps_are_separate():
    pending_questions.clear()
    question_activity_ids.clear()
    pending_questions["t1"] = [{"question": "Restart?"}]
    question_activity_ids["t1"] = "act-1"
    assert pending_questions["t1"][0]["question"] == "Restart?"
    assert question_activity_ids["t1"] == "act-1"
