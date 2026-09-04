# sre-agent/report.py
"""
Structured report extraction from agent result text.

The investigator agent may embed a fenced JSON block in its final answer:

    ```json
    {"root_cause": "...", "confidence": 0.9, "services": [...]}
    ```

extract_structured_report() parses this block and returns the dict,
or None if absent or malformed.
"""

import json
import re
from typing import Optional

_FENCE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def extract_structured_report(result_text: str) -> Optional[dict]:
    """Pull the agent's structured_report JSON from its final markdown, if present and valid."""
    if not result_text:
        return None
    m = _FENCE.search(result_text)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


def strip_structured_report_block(text: str) -> str:
    """Remove the structured_report JSON fence _FENCE matched, collapsing
    the blank line(s) left behind. Only meaningful to call after
    extract_structured_report() has confirmed the fence actually parsed -
    see clean_and_extract(), which keeps the two in lockstep."""
    m = _FENCE.search(text)
    if not m:
        return text
    stripped = text[: m.start()] + text[m.end():]
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)
    return stripped.rstrip()


def clean_and_extract(text: str) -> tuple[str, Optional[dict]]:
    """Extract the structured_report block from agent result text and
    return (display_text, structured_report).

    display_text has the fence removed only when extraction actually
    succeeded - a fence that fails to parse stays visible in display_text
    rather than silently vanishing, since it might not have been the
    metadata block at all.
    """
    if not text:
        return text, None
    structured = extract_structured_report(text)
    if structured is None:
        return text, None
    return strip_structured_report_block(text), structured
