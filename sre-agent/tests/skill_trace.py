"""Detect memory-search and KG skill invocations from SSE tool_start events."""

from __future__ import annotations

import json
from typing import Any


def _tool_text(tool_start: dict[str, Any]) -> str:
    name = (tool_start.get("name") or "").lower()
    inp = tool_start.get("input") or {}
    serialized = json.dumps(inp).lower()
    return f"{name} {serialized}"


def is_memory_skill_invocation(tool_start: dict[str, Any]) -> bool:
    """True when a tool_start event reflects a memory-search skill run."""
    text = _tool_text(tool_start)
    if "memory-search" in text or "skills/memory-search" in text:
        return True
    name = (tool_start.get("name") or "").lower()
    if name == "skill":
        skill = str((tool_start.get("input") or {}).get("skill", "")).lower()
        return "memory-search" in skill
    return False


def is_kg_skill_invocation(tool_start: dict[str, Any]) -> bool:
    """True when a tool_start event reflects infrastructure-neo4j / topology search."""
    text = _tool_text(tool_start)
    markers = (
        "infrastructure-neo4j",
        "topology_search",
        "skills/infrastructure-neo4j",
    )
    if any(m in text for m in markers):
        return True
    name = (tool_start.get("name") or "").lower()
    if name == "skill":
        skill = str((tool_start.get("input") or {}).get("skill", "")).lower()
        return "infrastructure-neo4j" in skill
    return False


def count_skill_invocations(tool_starts: list[dict[str, Any]]) -> dict[str, int]:
    memory = sum(1 for t in tool_starts if is_memory_skill_invocation(t))
    kg = sum(1 for t in tool_starts if is_kg_skill_invocation(t))
    return {"memory": memory, "kg": kg}


def early_skill_invocations(
    tool_starts: list[dict[str, Any]], limit: int = 5
) -> dict[str, int]:
    """Count skill hits in the first N tool starts (before evidence gathering)."""
    return count_skill_invocations(tool_starts[:limit])
