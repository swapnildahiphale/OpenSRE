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
