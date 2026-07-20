"""LLM + heuristic extraction of episode fields. Generic (not alert-only), conversation-aware."""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional

from .models import Component, Episode, KeyFinding

logger = logging.getLogger(__name__)

_MODEL = os.getenv("MEMORY_LLM_MODEL", "claude-haiku-4-5-20251001")


def llm_text_completion(prompt: str, max_tokens: int = 300) -> str:
    try:
        from anthropic import Anthropic

        client = Anthropic()
        msg = client.messages.create(
            model=_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            b.text for b in msg.content if getattr(b, "type", "") == "text"
        ).strip()
    except Exception as e:
        logger.error("[MEMORY] LLM completion failed: %s", e)
        return ""


def compute_effectiveness(resolved: bool, root_cause: Optional[str]) -> float:
    if resolved and root_cause and root_cause.strip():
        return 0.8
    if resolved:
        return 0.4
    return 0.1


def extract_skills_used(tool_calls: List[dict]) -> List[str]:
    seen: List[str] = []
    for tc in tool_calls or []:
        if tc.get("tool_name") == "Skill":
            skill = (tc.get("tool_input") or {}).get("skill")
            if skill and skill not in seen:
                seen.append(skill)
    return seen


def extract_key_findings(tool_calls: List[dict], limit: int = 8) -> List[KeyFinding]:
    finds: List[KeyFinding] = []
    for tc in tool_calls or []:
        out = tc.get("tool_output")
        if not out:
            continue
        ti = tc.get("tool_input") or {}
        finds.append(
            KeyFinding(
                skill=ti.get("skill") or tc.get("tool_name", ""),
                query=str(ti.get("query") or ti.get("command") or ""),
                finding=str(out)[:500],
            )
        )
        if len(finds) >= limit:
            break
    return finds


@dataclass
class Extraction:
    issue_type: str = "unknown"
    issue_description: str = ""
    severity: Optional[str] = None
    components: List[Component] = field(default_factory=list)
    root_cause: Optional[str] = None
    resolved: bool = False
    summary: str = ""


_EXTRACT_PROMPT = """You are summarizing an SRE investigation into a compact JSON record.
The investigation may be an alert, a Slack question, a pipeline/deploy failure, or any infra issue.

{prior_block}Investigation request:
{prompt}

Investigation result (latest turn):
{result}

Return ONLY minified JSON with these keys:
- issue_type: short kebab-case classification of the PROBLEM SHAPE (e.g. "connection-pool-exhaustion",
  "deploy-pipeline-failure", "crashloop-backoff", "latency-spike"). Not alert-specific.
- issue_description: one sentence describing what was reported/asked.
- severity: one of "critical","warning","info", or null if not applicable.
- components: array of {{"type","name"}} affected subjects. type is free-form:
  "service","jenkins_job","deployment","k8s_namespace","database","host","kafka_topic",...
- root_cause: the CURRENT best root cause (string), or null if not identified.
- resolved: boolean — true when a root cause has been identified with enough supporting evidence in the latest turn; false otherwise. This reflects diagnostic completeness, not whether the production issue was fixed or remediated.
- summary: 1-2 sentence summary of the whole investigation so far.

If a prior record is shown, CONSOLIDATE: the latest result supersedes earlier conclusions
(e.g. a corrected root cause replaces the previous one). Do not blend contradictory root causes.
JSON:"""


def extract_investigation(
    prompt: str,
    result_text: str,
    tool_calls: List[dict],
    prior: Optional[Episode] = None,
) -> Extraction:
    prior_block = ""
    if prior is not None:
        prior_block = (
            "Prior record for THIS conversation (may be corrected by the latest turn):\n"
            f'{{"issue_type": "{prior.issue_type}", "root_cause": {json.dumps(prior.root_cause)}, '
            f'"resolved": {str(prior.resolved).lower()}, "summary": {json.dumps(prior.summary)}}}\n\n'
        )
    raw = llm_text_completion(
        _EXTRACT_PROMPT.format(
            prior_block=prior_block, prompt=prompt[:2000], result=result_text[:4000]
        ),
        max_tokens=500,
    )
    data = _safe_json(raw)
    comps = [
        Component(type=c.get("type", "unknown"), name=c.get("name", ""))
        for c in data.get("components", [])
        if isinstance(c, dict) and c.get("name")
    ]
    return Extraction(
        issue_type=data.get("issue_type") or "unknown",
        issue_description=data.get("issue_description") or prompt[:200],
        severity=data.get("severity"),
        components=comps,
        root_cause=data.get("root_cause"),
        resolved=bool(data.get("resolved", False)),
        summary=data.get("summary") or (result_text[:200] if result_text else ""),
    )


def _safe_json(raw: str) -> dict:
    if not raw:
        return {}
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```")[1] if "```" in s[3:] else s.strip("`")
        s = s[4:] if s.startswith("json") else s
    start, end = s.find("{"), s.rfind("}")
    if start >= 0 and end > start:
        s = s[start : end + 1]
    try:
        return json.loads(s)
    except Exception as e:
        logger.warning("[MEMORY] could not parse extraction JSON: %s", e)
        return {}
