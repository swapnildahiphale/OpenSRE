# teams-bot/progress_text.py
"""Flat progress text for Teams SDK ctx.stream (v1: no subagent nesting).

Thoughts stay chronological with the current (incomplete) thought last.
Tools are humanized and Bash is nested under Skill — see tool_display.py.
"""

from __future__ import annotations

from state import InvestigationState, ThoughtSection, ToolCall
from tool_display import (
    DisplayTool,
    humanize_tool_summary,
    is_plan_tool,
    nest_bash_under_skills,
)


def _status_mark(tool: ToolCall) -> str:
    if tool.running:
        return "…"
    if tool.success:
        return "✓"
    return "✗"


def _plan_line(tools: list[ToolCall]) -> str | None:
    """One-line plan summary from Task*/TodoWrite inputs; None if none."""
    plan_tools = [t for t in tools if is_plan_tool(t.name)]
    if not plan_tools:
        return None

    # TodoWrite: prefer full rewrite counts
    for t in reversed(plan_tools):
        if t.name == "TodoWrite" and isinstance(t.input, dict):
            todos = (
                t.input.get("todos") if isinstance(t.input.get("todos"), list) else []
            )
            done = sum(
                1
                for x in todos
                if isinstance(x, dict) and x.get("status") == "completed"
            )
            return f"  Plan: {done}/{len(todos)} done"

    creates = [t for t in plan_tools if t.name == "TaskCreate"]
    updates = [t for t in plan_tools if t.name == "TaskUpdate"]
    completed = sum(
        1
        for t in updates
        if isinstance(t.input, dict) and t.input.get("status") == "completed"
    )
    total = max(len(creates), completed) if creates or updates else len(plan_tools)
    if creates and not updates:
        return f"  Plan: {len(creates)} tasks"
    if total:
        return f"  Plan: {completed}/{total} done"
    return f"  Plan: {len(plan_tools)} updates"


def _tool_row(dt: DisplayTool) -> list[str]:
    """Humanized top-level row; optional nested Bash count under Skill."""
    mark = _status_mark(dt.tool)
    label = humanize_tool_summary(dt.tool) or dt.tool.name
    lines = [f"  - {mark} {label}"]
    if dt.nested_bash:
        lines.append(f"    ↳ {len(dt.nested_bash)} commands")
    return lines


def _render_thought_tools(thought: ThoughtSection, *, is_current: bool) -> list[str]:
    # Nest Bash under Skill; drop plan tools (covered by the plan line).
    nested = nest_bash_under_skills(thought.tools)
    display = [dt for dt in nested if not is_plan_tool(dt.tool.name)]
    lines: list[str] = []

    # Live thought: last 3 top-level rows (1:1 stream tail).
    if is_current and not thought.completed:
        plan = _plan_line(thought.tools)
        if plan:
            lines.append(plan)
        visible = display[-3:]
        hidden = len(display) - len(visible)
        if hidden > 0:
            lines.append(f"  +{hidden} more")
        for dt in visible:
            lines.extend(_tool_row(dt))
        return lines

    # Older / completed thoughts: collapse so the channel edit is not a diary.
    if display:
        n = len(display)
        lines.append(f"  ↳ Used {n} tool{'s' if n != 1 else ''}")
    else:
        plan = _plan_line(thought.tools)
        if plan:
            lines.append(plan)
    return lines


def build_progress_text(state: InvestigationState) -> str:
    lines = ["**OpenSRE — Investigating…**", ""]
    # Last 3 thoughts; chronological → current thought ends the stream body
    thoughts = state.thoughts[-3:]
    if not thoughts:
        lines.append("_Starting investigation…_")
        return "\n".join(lines)
    for index, thought in enumerate(thoughts):
        mark = "✓" if thought.completed else "…"
        lines.append(f"{mark} {thought.text}")
        lines.extend(
            _render_thought_tools(thought, is_current=index == len(thoughts) - 1)
        )
    if state.background_notification:
        lines.append("")
        lines.append(f"_{state.background_notification}_")
    if state.background_waiting_label:
        lines.append("")
        lines.append(f"_{state.background_waiting_label}_")
    return "\n".join(lines)
