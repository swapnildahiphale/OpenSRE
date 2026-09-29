"""Pure SSE-event → state mutation (no I/O)."""

import json
from dataclasses import dataclass
from typing import Any, Optional

from state import InvestigationState, ThoughtSection, ToolCall


def parse_sse_event(line: str) -> Optional[dict]:
    if not line.startswith("data: "):
        return None
    try:
        return json.loads(line[6:])
    except json.JSONDecodeError:
        return None


@dataclass
class StreamStepResult:
    update_progress: bool = False
    post_question: Optional[list] = None
    question_timed_out: bool = False
    finished: bool = False  # result or error received


def _find_tool(
    state: InvestigationState, tool_use_id: Optional[str], name: str
) -> Optional[ToolCall]:
    for thought in state.thoughts:
        for tool in thought.tools:
            if tool_use_id and tool.tool_use_id == tool_use_id:
                return tool
            if not tool_use_id and tool.running and tool.name == name:
                return tool
    return None


def _clear_background_wait(state: InvestigationState) -> None:
    state.background_waiting_label = None
    state.pending_background_count = 0
    state.background_notification = None


def handle_stream_event(state: InvestigationState, event: dict) -> StreamStepResult:
    event_type = event.get("type")
    data: dict[str, Any] = event.get("data") or {}

    if event_type == "run_started":
        run_id = data.get("run_id")
        if run_id:
            state.run_id = str(run_id)
        return StreamStepResult()

    if event_type == "thought":
        text = data.get("text", "")
        if not text:
            return StreamStepResult()
        if state.thoughts:
            state.thoughts[-1].completed = True
        state.thoughts.append(ThoughtSection(text=text))
        return StreamStepResult(update_progress=True)

    if event_type == "tool_start":
        if not state.thoughts:
            state.thoughts.append(ThoughtSection(text="Investigating..."))
        tool = ToolCall(
            name=data.get("name", "Unknown"),
            tool_use_id=data.get("tool_use_id"),
            input=data.get("input") or {},
        )
        state.thoughts[-1].tools.append(tool)
        state.current_tool = tool
        return StreamStepResult(update_progress=True)

    if event_type == "tool_end":
        tool = _find_tool(state, data.get("tool_use_id"), data.get("name", "Unknown"))
        if tool:
            tool.running = False
            tool.success = data.get("success", True)
            tool.summary = data.get("summary")
        state.current_tool = None
        return StreamStepResult(update_progress=True)

    if event_type == "result":
        if state.thoughts:
            state.thoughts[-1].completed = True
        state.final_result = data.get("text", "")
        state.current_tool = None
        _clear_background_wait(state)
        return StreamStepResult(finished=True)

    if event_type == "error":
        state.error = data.get("message", "Unknown error")
        state.current_tool = None
        _clear_background_wait(state)
        return StreamStepResult(finished=True)

    if event_type == "question":
        return StreamStepResult(post_question=data.get("questions") or [])

    if event_type == "question_timeout":
        return StreamStepResult(question_timed_out=True)

    if event_type == "task_started":
        return StreamStepResult(update_progress=True)

    if event_type == "background_waiting":
        pending_count = int(data.get("pending_count") or 0)
        label = data.get("label") or f"Waiting on {pending_count} background agent(s)…"
        state.background_waiting_label = label
        state.pending_background_count = pending_count
        state.background_notification = None
        return StreamStepResult(update_progress=True)

    if event_type == "task_notification":
        summary = str(data.get("summary") or "")[:80]
        if summary:
            state.background_notification = f"Background agent finished: {summary}"
        else:
            state.background_notification = "Background agent finished"
        if state.pending_background_count > 0:
            state.pending_background_count -= 1
        if state.pending_background_count <= 0:
            state.background_waiting_label = None
        else:
            state.background_waiting_label = (
                f"Waiting on {state.pending_background_count} background agent(s)…"
            )
        return StreamStepResult(update_progress=True)

    return StreamStepResult()
