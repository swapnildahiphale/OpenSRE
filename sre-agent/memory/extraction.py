"""LLM + heuristic extraction of episode fields. Generic (not alert-only), conversation-aware."""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

from .models import Component, Episode, KeyFinding

logger = logging.getLogger(__name__)

_MODEL = os.getenv("MEMORY_LLM_MODEL", "claude-haiku-4-5-20251001")

EXTRACTION_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "issue_type",
        "issue_description",
        "severity",
        "components",
        "root_cause",
        "resolved",
        "summary",
    ],
    "properties": {
        "issue_type": {"type": "string"},
        "issue_description": {"type": "string"},
        "severity": {"type": ["string", "null"]},
        "components": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["type", "name"],
                "properties": {
                    "type": {"type": "string"},
                    "name": {"type": "string"},
                },
            },
        },
        "root_cause": {"type": ["string", "null"]},
        "resolved": {"type": "boolean"},
        "summary": {"type": "string"},
    },
}


def _initial_structured_cap() -> str:
    provider = os.getenv("MEMORY_LLM_PROVIDER", "anthropic")
    if provider == "openai_compat":
        return "json_object"
    return "json_schema"


_structured_cap = _initial_structured_cap()


def _anthropic_client():
    from anthropic import Anthropic

    return Anthropic()


def _format_unsupported(exc: Exception) -> bool:
    if isinstance(exc, TypeError):
        return True
    status = getattr(exc, "status_code", None)
    if status == 400:
        return True
    msg = str(exc).lower()
    return "output_config" in msg or "response_format" in msg


def _extract_message_text(msg) -> str:
    return "".join(
        b.text for b in msg.content if getattr(b, "type", "") == "text"
    ).strip()


def _anthropic_messages_create(client, prompt: str, max_tokens: int, json_schema: dict | None):
    """Create an Anthropic message, optionally with structured output config."""
    global _structured_cap
    kwargs = {
        "model": _MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if json_schema is not None and _structured_cap == "json_schema":
        output_config = {"format": {"type": "json_schema", "schema": json_schema}}
        try:
            return client.messages.create(**kwargs, output_config=output_config)
        except TypeError as e:
            if "output_config" not in str(e):
                raise
            try:
                return client.messages.create(
                    **kwargs, extra_body={"output_config": output_config}
                )
            except Exception as e:
                if not _format_unsupported(e):
                    raise
                _structured_cap = "prompt"
                return client.messages.create(**kwargs)
        except Exception as e:
            if not _format_unsupported(e):
                raise
            _structured_cap = "prompt"
            return client.messages.create(**kwargs)
    return client.messages.create(**kwargs)


def _openai_compat_completion(prompt: str, max_tokens: int, json_schema: dict | None) -> str:
    """OpenAI-compatible chat completions via httpx (no OpenAI SDK)."""
    global _structured_cap
    import httpx

    base = (os.getenv("OPENAI_BASE_URL") or os.getenv("ANTHROPIC_BASE_URL") or "").rstrip(
        "/"
    )
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or ""
    payload: dict = {
        "model": _MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if json_schema is not None and _structured_cap == "json_object":
        payload["response_format"] = {"type": "json_object"}
    try:
        resp = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=60.0,
        )
        if resp.status_code == 400 and json_schema is not None:
            body = resp.text.lower()
            if "response_format" in body or "json_schema" in body:
                _structured_cap = "prompt"
                payload.pop("response_format", None)
                resp = httpx.post(
                    f"{base}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=payload,
                    timeout=60.0,
                )
        resp.raise_for_status()
        data = resp.json()
        return (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.error("[MEMORY] openai_compat completion failed: %s", e)
        return ""


def llm_text_completion(
    prompt: str, max_tokens: int = 300, json_schema: dict | None = None
) -> str:
    provider = os.getenv("MEMORY_LLM_PROVIDER", "anthropic")
    try:
        if provider == "openai_compat":
            return _openai_compat_completion(prompt, max_tokens, json_schema)
        client = _anthropic_client()
        msg = _anthropic_messages_create(client, prompt, max_tokens, json_schema)
        return _extract_message_text(msg)
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
    status: str = "ok"


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
    prompt_text = _EXTRACT_PROMPT.format(
        prior_block=prior_block, prompt=prompt[:2000], result=result_text[:4000]
    )
    try:
        raw = llm_text_completion(
            prompt_text, max_tokens=500, json_schema=EXTRACTION_JSON_SCHEMA
        )
    except Exception:
        raw = ""
    if not raw:
        try:
            raw = llm_text_completion(
                prompt_text, max_tokens=500, json_schema=EXTRACTION_JSON_SCHEMA
            )
        except Exception:
            raw = ""
    data = _safe_json(raw)
    if not data and (not raw.strip() or not _raw_looks_like_json_object(raw)):
        return Extraction(
            issue_type="unknown",
            issue_description=prompt[:200],
            severity=None,
            components=[],
            root_cause=None,
            resolved=False,
            summary=result_text[:200] if result_text else "",
            status="failed",
        )
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
        status="ok",
    )


def _raw_looks_like_json_object(raw: str) -> bool:
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```")[1] if "```" in s[3:] else s.strip("`")
        s = s[4:] if s.startswith("json") else s
    start, end = s.find("{"), s.rfind("}")
    return start >= 0 and end > start


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
    s = re.sub(r",\s*([}\]])", r"\1", s)
    try:
        return json.loads(s)
    except Exception as e:
        logger.warning("[MEMORY] could not parse extraction JSON: %s", e)
        return {}
