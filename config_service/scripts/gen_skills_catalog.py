"""
Skills catalog generator.

Reads every sre-agent/.claude/skills/*/SKILL.md, parses frontmatter, computes
category and required_integrations, then rewrites BUILT_IN_SKILLS_METADATA in
config_service/src/core/skills_catalog.py between sentinel comments.

Usage (from repo root):
    python config_service/scripts/gen_skills_catalog.py

Exposes build_catalog() for import by the drift-guard test.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (relative to repo root)
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]  # config_service/scripts/ -> repo root
SKILLS_DIR = REPO_ROOT / "sre-agent" / ".claude" / "skills"
CATALOG_FILE = REPO_ROOT / "config_service" / "src" / "core" / "skills_catalog.py"

# ---------------------------------------------------------------------------
# Category mapping
# ---------------------------------------------------------------------------

CORE = {"investigate", "observability", "infrastructure", "remediation"}

PREFIX_CATEGORY: dict[str, str] = {
    "observability": "Observability",
    "metrics": "Observability",
    "infrastructure": "Infrastructure & Cloud",
    "database": "Databases",
    "incident": "Incident Management",
    "alerting": "Alerting & On-call",
    "project": "Ticketing & Project",
    "vcs": "Code & Version Control",
    "docs": "Docs & Knowledge",
    "knowledge": "Docs & Knowledge",
    "memory": "Memory",
    "streaming": "Other Integrations",
    "analytics": "Other Integrations",
    "platform": "Other Integrations",
    "runtime": "Other Integrations",
}

# Prefixes that indicate the suffix is an integration name
INTEGRATION_PREFIXES = {
    "observability",
    "metrics",
    "infrastructure",
    "database",
    "incident",
    "alerting",
    "project",
    "vcs",
    "docs",
    "streaming",
    "analytics",
    "platform",
    "runtime",
    "knowledge",
}


def category_for(skill_id: str) -> str:
    if skill_id in CORE:
        return "Core Methodology"
    prefix = skill_id.split("-", 1)[0]
    return PREFIX_CATEGORY.get(prefix, "Other Integrations")


REQUIRED_INTEGRATIONS_OVERRIDE: dict[str, list[str]] = {
    "alerting-context": ["pagerduty"],
    "incident-comms": ["slack"],
    "knowledge-base": ["confluence"],
    "knowledge-raptor": [],
    "memory-search": [],
    "metrics-analysis": ["prometheus", "grafana"],
    "metrics-victoriametrics": ["victoriametrics"],
}


def required_integrations_for(skill_id: str) -> list[str]:
    if skill_id in REQUIRED_INTEGRATIONS_OVERRIDE:
        return REQUIRED_INTEGRATIONS_OVERRIDE[skill_id]
    if skill_id in CORE:
        return []
    parts = skill_id.split("-", 1)
    if len(parts) == 2:
        prefix, suffix = parts
        if prefix in INTEGRATION_PREFIXES:
            return [suffix]
    return []


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_FIELD_RE = re.compile(r"^([a-zA-Z_]+):\s*(.+)$", re.MULTILINE)


def parse_frontmatter(text: str) -> dict[str, str]:
    m = _FM_RE.match(text)
    if not m:
        return {}
    block = m.group(1)
    return {k: v.strip() for k, v in _FIELD_RE.findall(block)}


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------


def human_name_for(skill_id: str) -> str:
    """Convert a skill id like 'observability-grafana' to 'Grafana Observability'."""
    # Special cases for core/methodology skills
    DISPLAY_NAMES = {
        "investigate": "Investigation Methodology",
        "observability": "Observability Methodology",
        "infrastructure": "Infrastructure Debugging",
        "remediation": "Remediation Actions",
        "alerting-context": "Alerting Context",
        "alerting-opsgenie": "Opsgenie Alerting",
        "analytics-amplitude": "Amplitude Analytics",
        "database-bigquery": "BigQuery",
        "database-mysql": "MySQL",
        "database-postgresql": "PostgreSQL",
        "database-snowflake": "Snowflake",
        "docs-google": "Google Docs",
        "docs-notion": "Notion Docs",
        "incident-blameless": "Blameless Incidents",
        "incident-comms": "Incident Communications",
        "incident-firehydrant": "FireHydrant",
        "incident-incidentio": "Incident.io",
        "infrastructure-aws": "AWS",
        "infrastructure-azure": "Azure",
        "infrastructure-docker": "Docker",
        "infrastructure-gcp": "GCP",
        "infrastructure-kubernetes": "Kubernetes",
        "infrastructure-neo4j": "Neo4j",
        "knowledge-base": "Knowledge Base",
        "knowledge-raptor": "RAPTOR Knowledge",
        "memory-search": "Memory Search",
        "metrics-analysis": "Metrics Analysis",
        "metrics-victoriametrics": "VictoriaMetrics",
        "observability-coralogix": "Coralogix",
        "observability-datadog": "Datadog",
        "observability-elasticsearch": "Elasticsearch",
        "observability-grafana": "Grafana",
        "observability-honeycomb": "Honeycomb",
        "observability-jaeger": "Jaeger",
        "observability-loki": "Loki",
        "observability-newrelic": "New Relic",
        "observability-sentry": "Sentry",
        "observability-splunk": "Splunk",
        "observability-victorialogs": "VictoriaLogs",
        "platform-vercel": "Vercel",
        "project-clickup": "ClickUp",
        "project-jira": "Jira",
        "project-linear": "Linear",
        "runtime-config-flagd": "flagd Feature Flags",
        "streaming-kafka": "Kafka",
        "vcs-gitlab": "GitLab",
        "vcs-sourcegraph": "Sourcegraph",
    }
    return DISPLAY_NAMES.get(
        skill_id, " ".join(p.capitalize() for p in skill_id.split("-"))
    )


def build_catalog() -> list[dict]:
    """
    Read all SKILL.md files under SKILLS_DIR, build and return the catalog list
    sorted alphabetically by id.
    """
    entries = []
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_dir.is_dir() or not skill_md.exists():
            continue

        skill_id = skill_dir.name
        text = skill_md.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)

        description = fm.get("description", "")

        entries.append(
            {
                "id": skill_id,
                "name": human_name_for(skill_id),
                "description": description,
                "category": category_for(skill_id),
                "required_integrations": required_integrations_for(skill_id),
            }
        )

    entries.sort(key=lambda s: s["id"])
    return entries


# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------

_SENTINEL_BEGIN = "# === BEGIN GENERATED CATALOG ==="
_SENTINEL_END = "# === END GENERATED CATALOG ==="


def _py_str(value: str) -> str:
    """Emit a double-quoted Python string literal (matches committed catalog style)."""
    # json.dumps uses double quotes and escapes correctly for our skill metadata.
    return json.dumps(value, ensure_ascii=False)


def _format_entry(entry: dict, indent: str = "    ") -> str:
    # Prefer double-quoted literals so regenerating does not churn quote style
    # across every skill when only one entry changed.
    ri = "[" + ", ".join(_py_str(x) for x in entry["required_integrations"]) + "]"
    lines = [
        f"{indent}{{",
        f'{indent}    "id": {_py_str(entry["id"])},',
        f'{indent}    "name": {_py_str(entry["name"])},',
        f'{indent}    "description": {_py_str(entry["description"])},',
        f'{indent}    "category": {_py_str(entry["category"])},',
        f'{indent}    "required_integrations": {ri},',
        f"{indent}}}",
    ]
    return "\n".join(lines)


def generate_list_literal(entries: list[dict]) -> str:
    if not entries:
        return "BUILT_IN_SKILLS_METADATA = []"
    parts = [_format_entry(e) for e in entries]
    body = ",\n".join(parts)
    return f"BUILT_IN_SKILLS_METADATA = [\n{body},\n]"


def rewrite_catalog(entries: list[dict]) -> None:
    source = CATALOG_FILE.read_text(encoding="utf-8")

    begin_idx = source.find(_SENTINEL_BEGIN)
    end_idx = source.find(_SENTINEL_END)

    if begin_idx == -1 or end_idx == -1:
        raise RuntimeError(
            f"Sentinel comments not found in {CATALOG_FILE}. "
            f"Expected '{_SENTINEL_BEGIN}' and '{_SENTINEL_END}'."
        )

    list_literal = generate_list_literal(entries)

    new_source = (
        source[: begin_idx + len(_SENTINEL_BEGIN)]
        + "\n"
        + list_literal
        + "\n"
        + source[end_idx:]
    )

    CATALOG_FILE.write_text(new_source, encoding="utf-8")
    print(f"Wrote {len(entries)} skills to {CATALOG_FILE}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    catalog = build_catalog()
    print(f"Found {len(catalog)} skills in {SKILLS_DIR}")
    rewrite_catalog(catalog)
