from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import TeamConfig

logger = logging.getLogger(__name__)

HARD_CAP = 6000


@dataclass
class TeamContextSection:
    id: str
    title: str
    content: str


def _legacy_sections(raw: dict) -> list[TeamContextSection]:
    """Synthesize sections from LangGraph-era top-level keys (read-only)."""
    out: list[TeamContextSection] = []
    if raw.get("service_info"):
        out.append(
            TeamContextSection(
                "service_info", "Infrastructure", str(raw["service_info"])
            )
        )
    if raw.get("known_instability"):
        ki = raw["known_instability"]
        body = "\n".join(ki) if isinstance(ki, list) else str(ki)
        out.append(TeamContextSection("known_instability", "Known issues", body))
    if raw.get("approval_gates"):
        gates = raw["approval_gates"]
        body = "\n".join(gates) if isinstance(gates, list) else str(gates)
        out.append(TeamContextSection("approval_gates", "Incident workflow", body))
    notes: list[str] = []
    if raw.get("business_context"):
        notes.append(str(raw["business_context"]))
    if raw.get("common_resources"):
        cr = raw["common_resources"]
        notes.append("\n".join(cr) if isinstance(cr, list) else str(cr))
    if raw.get("additional_instructions"):
        ai = raw["additional_instructions"]
        notes.append("\n".join(ai) if isinstance(ai, list) else str(ai))
    if notes:
        out.append(
            TeamContextSection("legacy_notes", "Additional context", "\n\n".join(notes))
        )
    return out


def _sections_with_content(sections: list[TeamContextSection]) -> list[str]:
    lines: list[str] = []
    for sec in sections:
        body = (sec.content or "").strip()
        if not body:
            continue
        title = (sec.title or sec.id or "Section").strip()
        lines.append(f"### {title}\n\n{body}\n")
    return lines


def _resolve_sections(team_config: TeamConfig) -> list[TeamContextSection]:
    raw = team_config.raw_config or {}
    sections = list(team_config.team_context or [])
    if any((s.content or "").strip() for s in sections):
        return sections
    # Legacy fallback only when team_context was never configured (key absent).
    # An explicit empty sections array means the operator cleared team context.
    if "team_context" not in raw:
        return _legacy_sections(raw)
    return sections


def render_team_context_block(team_config: TeamConfig) -> str:
    lines = _sections_with_content(_resolve_sections(team_config))
    if not lines:
        return ""

    block = "## Team Context\n\n" + "\n".join(lines)
    result = "\n\n" + block
    if len(result) > HARD_CAP:
        logger.warning(
            "[TEAM_CONTEXT] truncating %d chars to %d", len(result), HARD_CAP
        )
        result = result[:HARD_CAP] + "...[truncated]"
    return result
