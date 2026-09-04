"""Investigation state for the Teams bot (Slack MessageState trimmed)."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolCall:
    name: str
    tool_use_id: Optional[str] = None
    input: dict = field(default_factory=dict)
    running: bool = True
    success: Optional[bool] = None
    summary: Optional[str] = None


@dataclass
class ThoughtSection:
    text: str
    completed: bool = False
    tools: list = field(default_factory=list)  # list[ToolCall]


@dataclass
class InvestigationState:
    thread_id: str
    run_id: Optional[str] = None
    thoughts: list = field(default_factory=list)
    current_tool: Optional[ToolCall] = None
    final_result: Optional[str] = None
    error: Optional[str] = None
    background_waiting_label: Optional[str] = None
    pending_background_count: int = 0
    background_notification: Optional[str] = None

    def current_thought_text(self) -> str:
        return self.thoughts[-1].text if self.thoughts else ""


# thread_id -> question list from SSE "question" event
pending_questions: dict[str, list[dict[str, Any]]] = {}

# thread_id -> Teams activity id of the question card (for timeout updates)
question_activity_ids: dict[str, str] = {}

# thread_ids with an in-flight run_investigation (SSE still open)
active_investigations: set[str] = set()
