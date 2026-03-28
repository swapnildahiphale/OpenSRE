"""Writeup node -- generates structured investigation report."""

import json
import logging
import re

from config import AgentConfig, ModelConfig, build_llm
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

WRITEUP_SYSTEM_PROMPT = """You are the Writeup agent for an AI SRE system.
Generate a structured incident investigation report from the investigation findings.

Respond with BOTH:
1. A markdown narrative (conclusion)
2. A JSON structured report

## JSON Report Schema
```json
{{
    "title": "Brief incident title",
    "severity": "critical|high|medium|low|info",
    "status": "resolved|mitigated|ongoing|inconclusive",
    "affected_services": ["service-name"],
    "executive_summary": "2-3 sentence summary of what happened, the root cause, and current status.",
    "impact": {{
        "user_facing": "Description of user-visible impact",
        "service_impact": "Description of service-level impact",
        "blast_radius": "Scope of affected systems"
    }},
    "timeline": [
        {{"time": "HH:MM", "event": "Description"}}
    ],
    "root_cause": {{
        "summary": "Concise root cause statement",
        "confidence": "confirmed|probable|hypothesis",
        "details": "Detailed explanation with evidence"
    }},
    "action_items": [
        {{"priority": "immediate|short_term|long_term", "action": "Specific recommended action"}}
    ],
    "lessons_learned": ["Key takeaway or improvement suggestion"]
}}
```

Write the markdown narrative first, then a JSON code block with the structured report.
IMPORTANT: Follow the schema exactly. Use the exact field names and enum values shown above.
"""


def writeup(state: dict) -> dict:
    """Generate structured investigation report.

    Produces both a markdown narrative (conclusion) and structured JSON report.
    """
    alert = state.get("alert", {})
    agent_states = state.get("agent_states", {})
    hypotheses = state.get("hypotheses", [])
    messages = state.get("messages", [])
    team_config_raw = state.get("team_config", {})

    # Build LLM
    agents_config = team_config_raw.get("agents", {})
    writeup_raw = agents_config.get("writeup", {})

    agent_config = AgentConfig(
        name="writeup",
        model=_build_model_config(writeup_raw),
    )

    # Build findings input
    content = f"## Alert\n```json\n{json.dumps(alert, indent=2)}\n```\n\n"

    content += "## Investigation Findings\n\n"
    for agent_id, agent_state in agent_states.items():
        content += f"### {agent_id}\n"
        if isinstance(agent_state, dict):
            content += f"{agent_state.get('findings', 'No findings')}\n\n"
        else:
            # agent_state may be a raw string if reducer or Send() flattened it
            logger.warning(
                f"[WRITEUP] agent_states[{agent_id}] is {type(agent_state).__name__}, expected dict"
            )
            content += f"{agent_state}\n\n"

    if hypotheses:
        content += "## Hypotheses Tested\n"
        for h in hypotheses:
            content += f"- {h.get('hypothesis', str(h))}\n"
        content += "\n"

    if messages:
        content += "## Investigation Notes\n"
        for msg in messages[-5:]:
            if isinstance(msg, dict):
                content += (
                    f"- [{msg.get('role', '?')}] {msg.get('content', '')[:200]}\n"
                )
        content += "\n"

    content += "Generate the incident report with markdown narrative and JSON structured report."

    try:
        llm = build_llm(agent_config)

        response = llm.invoke(
            [
                SystemMessage(
                    content=writeup_raw.get("prompt", {}).get("system", "")
                    or WRITEUP_SYSTEM_PROMPT
                ),
                HumanMessage(content=content),
            ],
            config={"run_name": "writeup", "metadata": {"agent_id": "writeup"}},
        )

        response_text = response.content
        logger.info(f"[WRITEUP] LLM response length: {len(response_text)} chars")

        # Strip <think>...</think> reasoning tags (some models include these)
        clean_text = re.sub(r"<think>[\s\S]*?</think>", "", response_text).strip()
        if len(clean_text) < len(response_text):
            logger.info(
                f"[WRITEUP] Stripped reasoning tags, {len(response_text)} -> {len(clean_text)} chars"
            )

        # Extract JSON report from response
        structured_report = {}
        try:
            if "```json" in clean_text:
                json_block = clean_text.split("```json")[1].split("```")[0]
                structured_report = json.loads(json_block.strip())
            elif "```" in clean_text:
                # Try generic code block
                json_block = clean_text.split("```")[1].split("```")[0]
                structured_report = json.loads(json_block.strip())
            else:
                # Try to find raw JSON object in the response
                json_match = re.search(
                    r'\{[^{}]*"title"[^{}]*\}', clean_text, re.DOTALL
                )
                if not json_match:
                    json_match = re.search(
                        r'\{[\s\S]*"executive_summary"[\s\S]*\}', clean_text
                    )
                if json_match:
                    try:
                        structured_report = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        pass
        except (json.JSONDecodeError, IndexError) as parse_err:
            logger.warning(f"[WRITEUP] JSON extraction failed: {parse_err}")

        # Extract markdown narrative (everything before the JSON block)
        conclusion = clean_text
        if "```json" in conclusion:
            conclusion = conclusion.split("```json")[0].strip()
        elif "```" in conclusion:
            conclusion = conclusion.split("```")[0].strip()

        if not structured_report:
            logger.warning(
                "[WRITEUP] No structured JSON found in LLM response, extracting from narrative"
            )
            # Use empty strings so _enrich_from_narrative will fill from narrative
            structured_report = {
                "title": alert.get("name") or "Investigation Report",
                "severity": alert.get("severity", "info"),
                "status": "inconclusive",
                "affected_services": [s for s in [alert.get("service")] if s],
                "executive_summary": "",
                "root_cause": {
                    "summary": "",
                    "confidence": "hypothesis",
                },
                "action_items": [],
            }

        # Normalize to match UI schema
        structured_report = _normalize_report(structured_report, alert)

        # If structured_report is too thin, enrich from the narrative
        structured_report = _enrich_from_narrative(structured_report, conclusion, alert)

        logger.info(
            f"[WRITEUP] Report generated: title={structured_report.get('title', 'untitled')}, "
            f"keys={list(structured_report.keys())}, "
            f"has_timeline={bool(structured_report.get('timeline'))}, "
            f"has_actions={bool(structured_report.get('action_items'))}"
        )

        return {
            "conclusion": conclusion,
            "structured_report": structured_report,
        }

    except Exception as e:
        logger.error(f"[WRITEUP] Failed: {e}")
        return {
            "conclusion": f"Investigation report generation failed: {e}\n\nRaw findings available in agent states.",
            "structured_report": {
                "title": alert.get("name", "Investigation Report"),
                "severity": alert.get("severity", "info"),
                "error": str(e),
                "resolution_status": "investigating",
            },
        }


def _enrich_from_narrative(report: dict, narrative: str, alert: dict) -> dict:
    """If the structured report is too thin, extract key info from the markdown narrative."""
    # Check if report is missing critical fields
    has_summary = bool(report.get("executive_summary"))
    has_root_cause = bool(
        report.get("root_cause", {}).get("summary")
        if isinstance(report.get("root_cause"), dict)
        else report.get("root_cause")
    )
    has_actions = bool(report.get("action_items"))

    if has_summary and has_root_cause and has_actions:
        return report  # Report is rich enough

    if not narrative or len(narrative) < 50:
        return report  # No useful narrative to extract from

    # Extract executive summary from narrative
    if not has_summary:
        # Try section-based extraction first
        summary_text = _extract_section(
            narrative,
            [
                "executive summary",
                "summary",
                "overview",
                "incident summary",
            ],
        )
        if summary_text:
            report["executive_summary"] = summary_text[:500]
        else:
            # Fall back to first substantial paragraph
            paragraphs = [
                p.strip()
                for p in narrative.split("\n\n")
                if p.strip() and not p.strip().startswith("#")
            ]
            for p in paragraphs:
                clean = p.lstrip("*_- ")
                if len(clean) > 40 and not clean.startswith("```"):
                    report["executive_summary"] = clean[:500]
                    break

    # Extract root cause from narrative
    if not has_root_cause:
        rc_text = _extract_section(
            narrative,
            [
                "primary root cause",
                "root cause analysis",
                "root cause",
                "cause",
            ],
        )
        if rc_text:
            report["root_cause"] = {
                "summary": rc_text[:300],
                "confidence": "probable",
            }

    # Extract title from narrative heading if report title is generic
    if report.get("title") in ("Investigation Report", "Investigation"):
        heading_match = re.search(r"^#\s+(.+?)$", narrative, re.MULTILINE)
        if heading_match:
            title = heading_match.group(1).strip().rstrip("#").strip()
            if len(title) > 5:
                report["title"] = title[:100]

    # Extract status from narrative
    if report.get("status") == "inconclusive":
        lower = narrative.lower()
        if any(w in lower for w in ["resolved", "remediated", "fix applied"]):
            report["status"] = "resolved"
        elif any(w in lower for w in ["mitigated", "partially"]):
            report["status"] = "mitigated"
        elif any(w in lower for w in ["ongoing", "still occurring", "persists"]):
            report["status"] = "ongoing"

    # Ensure affected_services from alert if still missing
    if not report.get("affected_services"):
        svc = alert.get("service")
        if svc:
            report["affected_services"] = [svc]

    # Final safety net: if still no summary, use the narrative itself
    if not report.get("executive_summary") and len(narrative) > 50:
        report["executive_summary"] = narrative[:500]
    rc = report.get("root_cause")
    if isinstance(rc, dict) and not rc.get("summary") and len(narrative) > 50:
        rc["summary"] = "See full narrative report"

    return report


def _extract_section(text: str, heading_keywords: list[str]) -> str:
    """Extract content from a markdown section matching any of the heading keywords.

    Handles patterns like:
        ## Executive Summary
        ## 2. Executive Summary
        ### Primary Root Cause
        **Root Cause:**
    """
    lower = text.lower()

    for keyword in heading_keywords:
        # Pattern 1: markdown heading (## keyword, ### keyword, with optional numbering)
        pattern = rf"^#{1,4}\s+(?:\d+\.\s+)?{re.escape(keyword)}\b.*$"
        match = re.search(pattern, lower, re.MULTILINE | re.IGNORECASE)
        if match:
            after = text[match.end() :].lstrip("\n")
            return _extract_until_next_heading(after)

        # Pattern 2: bold marker (**keyword** or **keyword:**)
        pattern = rf"\*\*{re.escape(keyword)}\b[^*]*\*\*:?"
        match = re.search(pattern, lower, re.IGNORECASE)
        if match:
            after = text[match.end() :].lstrip("\n :").lstrip()
            return _extract_until_next_heading(after)

        # Pattern 3: plain text marker (keyword:)
        idx = lower.find(f"{keyword}:")
        if idx >= 0:
            after = text[idx + len(keyword) + 1 :].lstrip()
            return _extract_until_next_heading(after)

    return ""


def _extract_until_next_heading(text: str) -> str:
    """Extract text content until the next markdown heading or end of text."""
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        # Stop at next heading or horizontal rule
        if stripped.startswith("#") or stripped.startswith("---"):
            break
        # Skip empty lines at the start
        if not lines and not stripped:
            continue
        lines.append(stripped)
    # Join and clean up
    result = " ".join(
        line.lstrip("*_- ") for line in lines if line and not line.startswith("```")
    )
    return result.strip()


def _normalize_report(report: dict, alert: dict) -> dict:
    """Normalize LLM-generated report to match the UI's InvestigationReportData schema."""

    # Step 0: camelCase -> snake_case for common LLM output variations
    camel_map = {
        "rootCause": "root_cause",
        "rootCauseAnalysis": "root_cause_analysis",
        "actionItems": "action_items",
        "lessonsLearned": "lessons_learned",
        "affectedServices": "affected_services",
        "servicesAffected": "services_affected",
        "executiveSummary": "executive_summary",
        "resolutionStatus": "resolution_status",
        "hypothesesTested": "hypotheses_tested",
        "blastRadius": "blast_radius",
        "serviceImpact": "service_impact",
        "userFacing": "user_facing",
    }
    for camel, snake in camel_map.items():
        if camel in report and snake not in report:
            report[snake] = report.pop(camel)

    # Normalize nested impact object camelCase keys
    impact = report.get("impact")
    if isinstance(impact, dict):
        for camel, snake in camel_map.items():
            if camel in impact and snake not in impact:
                impact[snake] = impact.pop(camel)

    # Field name aliases: services/services_affected -> affected_services
    for alias in ("services", "services_affected"):
        if alias in report and "affected_services" not in report:
            report["affected_services"] = report.pop(alias)

    # Field name aliases: resolution_status -> status
    if "resolution_status" in report and "status" not in report:
        report["status"] = report.pop("resolution_status")

    # root_cause / root_cause_analysis: string or dict -> {summary, confidence}
    for rc_key in ("root_cause", "root_cause_analysis"):
        if rc_key in report and "root_cause" not in report and rc_key != "root_cause":
            report["root_cause"] = report.pop(rc_key)
    rc = report.get("root_cause")
    if isinstance(rc, str):
        report["root_cause"] = {"summary": rc, "confidence": "probable"}
    elif isinstance(rc, dict) and "summary" not in rc:
        # Handle various LLM output schemas:
        # {analysis: "..."}, {description: "..."}, {primary: "...", contributing: [...]}
        summary = (
            rc.get("analysis")
            or rc.get("description")
            or rc.get("detail")
            or rc.get("primary")
            or rc.get("primary_root_cause")
            or ""
        )
        # Build details from contributing factors if present
        details = (
            rc.get("details")
            or rc.get("contributing_factors")
            or rc.get("contributing")
        )
        if isinstance(details, list):
            details = "; ".join(str(d) for d in details)
        # If still no summary, serialize as readable text (not raw dict)
        if not summary:
            summary = json.dumps(rc, indent=2) if rc else "See narrative report"
        report["root_cause"] = {
            "summary": summary,
            "confidence": rc.get("confidence", "probable"),
            "details": details,
        }

    # Normalize executive_summary: dict -> string
    es = report.get("executive_summary")
    if isinstance(es, dict):
        # Flatten dict like {incident: "...", impact: "...", resolution: "..."} to string
        parts = [str(v) for v in es.values() if v]
        report["executive_summary"] = " ".join(parts)

    # Ensure title exists
    if not report.get("title"):
        report["title"] = alert.get("name") or "Investigation Report"

    # Ensure severity exists (fall back to alert severity)
    if not report.get("severity"):
        report["severity"] = alert.get("severity", "info")

    # Normalize timeline: dict -> list of {time, event}
    tl = report.get("timeline")
    if isinstance(tl, dict):
        # Convert dict like {detection_time: "...", resolution_time: "..."} to array
        report["timeline"] = [
            {"time": k.replace("_", " ").title(), "event": str(v)}
            for k, v in tl.items()
            if v
        ]
    elif isinstance(tl, list):
        # Ensure each entry has the expected shape
        report["timeline"] = [
            e if isinstance(e, dict) and "event" in e else {"time": "", "event": str(e)}
            for e in tl
        ]

    # Normalize lessons_learned: dict -> list of strings
    ll = report.get("lessons_learned")
    if isinstance(ll, dict):
        # Flatten dict like {went_well: [...], improvements: [...]} to flat list
        flat = []
        for category, items in ll.items():
            if isinstance(items, list):
                flat.extend(str(i) for i in items)
            elif isinstance(items, str):
                flat.append(items)
        report["lessons_learned"] = flat
    elif isinstance(ll, list):
        report["lessons_learned"] = [str(i) for i in ll]

    # Normalize impact: ensure expected sub-keys
    impact = report.get("impact")
    if isinstance(impact, dict):
        # Map common LLM variations to expected keys
        for src, dst in [
            ("user_impact", "user_facing"),
            ("user", "user_facing"),
            ("business_impact", "blast_radius"),
            ("business", "blast_radius"),
            ("technical_impact", "service_impact"),
            ("technical", "service_impact"),
        ]:
            if src in impact and dst not in impact:
                impact[dst] = impact.pop(src)

    # Normalize action_items: description -> action, priority aliases
    priority_map = {
        "critical": "immediate",
        "high": "immediate",
        "medium": "short_term",
        "low": "long_term",
        "info": "long_term",
    }
    for item in report.get("action_items", []):
        # Normalize action text field: description/recommendation -> action
        if "action" not in item or not item["action"]:
            item["action"] = (
                item.get("description")
                or item.get("detail")
                or item.get("recommendation")
                or item.get("title")
                or ""
            )
        # Normalize priority values
        p = item.get("priority", "").lower()
        if p in priority_map:
            item["priority"] = priority_map[p]

    return report


def _build_model_config(raw: dict) -> ModelConfig:
    model_data = raw.get("model", {})
    return ModelConfig(
        name=model_data.get("name", "claude-sonnet-4-20250514"),
        temperature=model_data.get("temperature"),
        max_tokens=model_data.get("max_tokens"),
        top_p=model_data.get("top_p"),
    )
