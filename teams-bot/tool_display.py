"""Display-layer helpers for Teams progress text.

Port of web_ui/src/lib/toolDisplay.ts (humanize + nest Bash under Skill).
Teams has no expand UI — nested Bash is counted, not listed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from state import ToolCall

SKILL_SCRIPT_RE = re.compile(r"\.claude/skills/[^/\s]+(?:/[^/\s]+)*/scripts/([^\s]+)")

PLAN_TOOLS = frozenset({"TodoWrite", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet"})


def is_plan_tool(name: str) -> bool:
    return name in PLAN_TOOLS


@dataclass
class DisplayTool:
    """Top-level tool row after nesting. nested_bash held for count only."""

    tool: ToolCall
    nested_bash: list[ToolCall] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.tool.name


def humanize_tool_summary(tool: ToolCall) -> Optional[str]:
    """Short label from SDK input fields (non-technical / humanized mode)."""
    inp = tool.input if isinstance(tool.input, dict) else {}
    name = tool.name

    if name == "Bash":
        cmd = str(inp.get("command") or "")
        if not cmd:
            return None
        m = SKILL_SCRIPT_RE.search(cmd)
        if m:
            script = m.group(1)
            after = cmd[cmd.index(script) + len(script) :].strip()
            label = f"{script} {after}".strip() if after else script
            return label[:120]
        return cmd[:100]

    if name == "Skill":
        skill = inp.get("skill")
        if not skill:
            return None
        args = str(inp.get("args") or "")[:80]
        return f"{skill} — {args}" if args else str(skill)

    if name in {"Read", "Write", "Edit"}:
        path = inp.get("file_path")
        if not path:
            return None
        p = str(path)
        return p.rsplit("/", 1)[-1] or p

    if name == "Grep":
        pat = inp.get("pattern")
        return f'pattern: "{pat}"' if pat else None

    if name == "Glob":
        pat = inp.get("pattern")
        return f'glob: "{pat}"' if pat else None

    if name in {"Task", "Agent"}:
        desc = inp.get("description")
        if not desc:
            return None
        sub = inp.get("subagent_type") or "subagent"
        return f"{sub}: {str(desc)[:100]}"

    if name == "TodoWrite":
        todos = inp.get("todos") if isinstance(inp.get("todos"), list) else []
        done = sum(
            1 for t in todos if isinstance(t, dict) and t.get("status") == "completed"
        )
        return f"rewrite plan — {done}/{len(todos)} done"

    if name == "TaskCreate":
        subj = inp.get("subject")
        return f"+ {str(subj)[:100]}" if subj else "new task"

    if name == "TaskUpdate":
        st = f" → {inp['status']}" if inp.get("status") else ""
        subj = inp.get("subject")
        tid = inp.get("taskId") or inp.get("id") or inp.get("task_id")
        if subj:
            return f"update {str(subj)[:80]}{st}"
        if tid:
            return f"update {str(tid)[:8]}{st}"
        return f"update{st}" if st else "update"

    if name == "TaskList":
        return "snapshot"

    if name == "TaskGet":
        tid = inp.get("taskId") or inp.get("id")
        return f"read {tid}"[:100] if tid else "read task"

    # Fallback: first string value in input
    for v in inp.values():
        if isinstance(v, str) and v:
            return v[:100]
    return None


def nest_bash_under_skills(tools: list[ToolCall]) -> list[DisplayTool]:
    """Nest Bash under the latest Skill in this thought.

    Do not close the skill on Agent/Read. Channel k8s runs often do
    Skill then kubectl Bash; listing every command filled the updating bubble.
    """
    out: list[DisplayTool] = []
    open_skill: Optional[DisplayTool] = None

    for tool in tools:
        if tool.name == "Skill":
            open_skill = DisplayTool(tool=tool, nested_bash=[])
            out.append(open_skill)
            continue
        if tool.name == "Bash" and open_skill is not None:
            open_skill.nested_bash.append(tool)
            continue
        out.append(DisplayTool(tool=tool, nested_bash=[]))

    return out
