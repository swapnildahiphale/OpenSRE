#!/usr/bin/env python3
"""
Stream Event Protocol

Defines structured events for communication between sre-agent and slack-bot.
Events are streamed as SSE (Server-Sent Events) with JSON payloads.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class StreamEvent:
    """
    Structured event for agent-to-client communication.

    Event Types:
    - thought: Agent's reasoning/thinking text
    - tool_start: Tool execution starting
    - tool_end: Tool execution completed
    - result: Final response from agent
    - error: Error occurred
    - approval: Permission needed (future)
    - question: Clarifying question (future)
    """

    type: str
    data: dict
    thread_id: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def to_sse(self) -> str:
        """Format as SSE data line."""
        return f"data: {json.dumps(self.to_dict())}\n\n"


# Factory functions for creating specific event types


def thought_event(
    thread_id: str,
    text: str,
    parent_tool_use_id: Optional[str] = None,
) -> StreamEvent:
    """Create a thought/reasoning event."""
    data = {"text": text}
    if parent_tool_use_id:
        data["parent_tool_use_id"] = parent_tool_use_id
    return StreamEvent(
        type="thought",
        data=data,
        thread_id=thread_id,
    )


def tool_start_event(
    thread_id: str,
    name: str,
    tool_input: Optional[dict] = None,
    tool_use_id: Optional[str] = None,
    parent_tool_use_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    agent_type: Optional[str] = None,
    parent_agent_id: Optional[str] = None,
    parent_agent_type: Optional[str] = None,
    depth: int = 0,
) -> StreamEvent:
    """Create a tool start event.

    Attribution fields (agent_id/agent_type/parent_agent_id/parent_agent_type/
    depth) come from the SDK PreToolUse hook's agent_id resolution in
    InteractiveAgentSession (agent.py). They are emitted unconditionally so the
    web UI / persistence layer can rely on them always being present, even for
    root-level calls (None / 0).
    """
    data = {"name": name}
    if tool_use_id:
        data["tool_use_id"] = tool_use_id
    if parent_tool_use_id:
        data["parent_tool_use_id"] = parent_tool_use_id
    # Nested-agent attribution (always present; root calls carry None/0).
    data["agent_id"] = agent_id
    data["agent_type"] = agent_type
    data["parent_agent_id"] = parent_agent_id
    data["parent_agent_type"] = parent_agent_type
    data["depth"] = depth
    if tool_input:
        # Extract relevant info based on tool type
        if name == "Bash" and "command" in tool_input:
            data["command"] = tool_input["command"]
        elif name in ("Read", "Write", "Edit") and "file_path" in tool_input:
            data["file_path"] = tool_input["file_path"]
        elif name == "Glob" and "pattern" in tool_input:
            data["pattern"] = tool_input["pattern"]
        elif name == "Grep" and "pattern" in tool_input:
            data["pattern"] = tool_input["pattern"]
        elif name in ("Task", "Agent"):
            # "Agent" is the tool name used by newer Claude Agent SDK builds for
            # subagent dispatch; "Task" is kept for older builds / historical data.
            if "description" in tool_input:
                data["description"] = tool_input["description"]
            if "subagent_type" in tool_input:
                data["subagent_type"] = tool_input["subagent_type"]
        elif name == "Skill":
            if "skill" in tool_input:
                data["skill"] = tool_input["skill"]
            if "args" in tool_input:
                data["args"] = tool_input["args"]
        # Store full input for debugging (truncated)
        data["input"] = _truncate_dict(tool_input, max_str_len=200)
    return StreamEvent(
        type="tool_start",
        data=data,
        thread_id=thread_id,
    )


def tool_end_event(
    thread_id: str,
    name: str,
    success: bool = True,
    summary: Optional[str] = None,
    error: Optional[str] = None,
    output: Optional[str] = None,
    tool_use_id: Optional[str] = None,
    parent_tool_use_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    agent_type: Optional[str] = None,
    parent_agent_id: Optional[str] = None,
    parent_agent_type: Optional[str] = None,
    depth: int = 0,
) -> StreamEvent:
    """Create a tool completion event.

    Attribution fields mirror tool_start_event so tool_end carries the same
    agent context (sourced from the PostToolUse hook). Always present, even for
    root-level calls (None / 0), so the SSE consumer can attribute the end
    event without cross-referencing the matching start.
    """
    data = {
        "name": name,
        "success": success,
        # Nested-agent attribution (always present; root calls carry None/0).
        "agent_id": agent_id,
        "agent_type": agent_type,
        "parent_agent_id": parent_agent_id,
        "parent_agent_type": parent_agent_type,
        "depth": depth,
    }
    if tool_use_id:
        data["tool_use_id"] = tool_use_id
    if parent_tool_use_id:
        data["parent_tool_use_id"] = parent_tool_use_id
    if summary:
        data["summary"] = summary
    if error:
        data["error"] = error
    if output:
        data["output"] = output
    return StreamEvent(
        type="tool_end",
        data=data,
        thread_id=thread_id,
    )


def result_event(
    thread_id: str,
    text: str,
    success: bool = True,
    subtype: Optional[str] = None,
    images: Optional[list] = None,
    files: Optional[list] = None,
) -> StreamEvent:
    """
    Create a final result event.

    Args:
        thread_id: Thread identifier
        text: Result text (may contain markdown image/file refs that were extracted)
        success: Whether the operation succeeded
        subtype: Optional subtype (e.g., "interrupted")
        images: Optional list of extracted images:
                [{path: str, data: str (base64), media_type: str, alt: str}, ...]
        files: Optional list of extracted files:
               [{path: str, data: str (base64), media_type: str, filename: str, description: str, size: int}, ...]
    """
    data = {
        "text": text,
        "success": success,
        "subtype": subtype,
    }
    if images:
        data["images"] = images
    if files:
        data["files"] = files
    return StreamEvent(
        type="result",
        data=data,
        thread_id=thread_id,
    )


def error_event(
    thread_id: str,
    message: str,
    recoverable: bool = False,
) -> StreamEvent:
    """Create an error event."""
    return StreamEvent(
        type="error",
        data={
            "message": message,
            "recoverable": recoverable,
        },
        thread_id=thread_id,
    )


# Future: approval and question events (Phase 3+)


def approval_event(
    thread_id: str,
    tool_name: str,
    tool_input: dict,
    request_id: str,
) -> StreamEvent:
    """Create an approval request event."""
    return StreamEvent(
        type="approval",
        data={
            "tool": tool_name,
            "input": _truncate_dict(tool_input, max_str_len=500),
            "request_id": request_id,
        },
        thread_id=thread_id,
    )


def question_event(
    thread_id: str,
    questions: list,
) -> StreamEvent:
    """Create a clarifying question event for AskUserQuestion tool."""
    return StreamEvent(
        type="question",
        data={"questions": questions},
        thread_id=thread_id,
    )


def question_timeout_event(
    thread_id: str,
) -> StreamEvent:
    """Create a timeout event when user doesn't respond to AskUserQuestion in time."""
    return StreamEvent(
        type="question_timeout",
        data={
            "message": "Agent waited 60 seconds and decided to continue without your response."
        },
        thread_id=thread_id,
    )


def message_queued_event(thread_id: str, *, pending_count: int) -> StreamEvent:
    """Notify clients that a user message was queued mid-investigation."""
    return StreamEvent(
        type="message_queued",
        data={"pending_count": pending_count},
        thread_id=thread_id,
    )


def task_started_event(
    thread_id: str,
    *,
    task_id: str,
    description: str,
    tool_use_id: Optional[str] = None,
    task_type: Optional[str] = None,
) -> StreamEvent:
    """Notify clients that a background SDK task has started."""
    data = {
        "task_id": task_id,
        "description": description,
    }
    if tool_use_id is not None:
        data["tool_use_id"] = tool_use_id
    if task_type is not None:
        data["task_type"] = task_type
    return StreamEvent(
        type="task_started",
        data=data,
        thread_id=thread_id,
    )


def background_waiting_event(
    thread_id: str,
    *,
    pending_count: int,
    pending_task_ids: list[str],
    label: Optional[str] = None,
) -> StreamEvent:
    """Notify clients that the agent is waiting on background tasks."""
    if label is None:
        label = f"Waiting on {pending_count} background agent(s)…"
    return StreamEvent(
        type="background_waiting",
        data={
            "pending_count": pending_count,
            "pending_task_ids": pending_task_ids,
            "label": label,
        },
        thread_id=thread_id,
    )


def task_notification_event(
    thread_id: str,
    *,
    task_id: str,
    status: str,
    summary: str,
) -> StreamEvent:
    """Notify clients that a background SDK task has completed or failed."""
    return StreamEvent(
        type="task_notification",
        data={
            "task_id": task_id,
            "status": status,
            "summary": summary,
        },
        thread_id=thread_id,
    )


def _truncate_dict(d: dict, max_str_len: int = 200) -> dict:
    """Truncate string values in a dict to avoid huge payloads."""
    result = {}
    for k, v in d.items():
        if isinstance(v, str) and len(v) > max_str_len:
            result[k] = v[:max_str_len] + "..."
        elif isinstance(v, dict):
            result[k] = _truncate_dict(v, max_str_len)
        else:
            result[k] = v
    return result
