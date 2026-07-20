"""Sanitize env/printenv Bash tool output before SSE stream and DB persistence.

Keeps variable names visible for debugging; strips all values so secrets never
land in traces or the web UI.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Env-dump commands: match as shell words, not filename suffixes like ".env".
_ENV_CMD = re.compile(r"(?:^|[|;&]\s*)(?:/usr/bin/)?env(?:\s|$|[|;&])")
_PRINTENV_CMD = re.compile(r"(?:^|[|;&]\s*)printenv\b")
_EXPORT_P_CMD = re.compile(r"(?:^|[|;&]\s*)export\s+-p\b")
# Bare `set` with no args (shell builtin lists all vars); not `kubectl set …`.
_BARE_SET_CMD = re.compile(r"^\s*set\s*(?:$|[;&|])")

# KEY=value, export KEY=value, declare -x KEY="value" (export -p / set output).
_ENV_LINE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
_DECLARE_X_LINE = re.compile(r"^declare\s+-x\s+([A-Za-z_][A-Za-z0-9_]*)(?:=(.*))?$")

# Above this many env lines, emit a compact names-only summary instead.
_SUMMARY_THRESHOLD = 15

_REDACTED = "<redacted>"


def is_env_dump_command(command: str) -> bool:
    """Return True when a Bash command dumps environment variables."""
    if not command or not command.strip():
        return False
    cmd = command.strip()
    if _BARE_SET_CMD.match(cmd):
        return True
    if _EXPORT_P_CMD.search(cmd):
        return True
    if _PRINTENV_CMD.search(cmd):
        return True
    if _ENV_CMD.search(cmd):
        return True
    return False


def _parse_env_key(line: str) -> str | None:
    """Extract an environment variable name from one output line, if present."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    m = _ENV_LINE.match(stripped)
    if m:
        return m.group(1)
    m = _DECLARE_X_LINE.match(stripped)
    if m:
        return m.group(1)
    return None


def _redact_env_text(text: str) -> str:
    """Replace env var values with <redacted>; preserve non-env lines."""
    lines = text.splitlines()
    keys: list[str] = []
    redacted_lines: list[str] = []
    any_env = False

    for line in lines:
        key = _parse_env_key(line)
        if key:
            any_env = True
            keys.append(key)
            redacted_lines.append(f"{key}={_REDACTED}")
        else:
            redacted_lines.append(line)

    if not any_env:
        return text

    if len(keys) > _SUMMARY_THRESHOLD:
        names = ", ".join(keys)
        return f"{names} ({len(keys)} vars, values redacted)"

    return "\n".join(redacted_lines)


def sanitize_bash_output(command: str, output: str | None) -> str | None:
    """Redact values from env/printenv/set output; pass everything else through."""
    if output is None or not is_env_dump_command(command):
        return output

    # SDK Bash responses are sometimes JSON-wrapped with stdout/stderr fields.
    wrapper = _try_parse_json_output(output)
    if wrapper is not None:
        changed = False
        for field in ("stdout", "stderr"):
            if field in wrapper and wrapper[field] is not None:
                inner = wrapper[field]
                if isinstance(inner, str):
                    sanitized = _redact_env_text(inner)
                    if sanitized != inner:
                        wrapper[field] = sanitized
                        changed = True
        if changed:
            return json.dumps(wrapper)
        return output

    return _redact_env_text(output)


def _try_parse_json_output(output: str) -> dict | None:
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(data, dict) and ("stdout" in data or "stderr" in data):
        return data
    return None


def _extract_command(tool_input: Any) -> str | None:
    if isinstance(tool_input, dict):
        cmd = tool_input.get("command")
        if isinstance(cmd, str):
            return cmd
    return None


def sanitize_tool_end_payload(
    tool_name: str,
    tool_input: Any,
    output: str | None,
    error: str | None,
) -> tuple[str | None, str | None]:
    """Entry point for hooks and persistence. Returns (output, error)."""
    if tool_name != "Bash":
        return output, error

    command = _extract_command(tool_input)
    if not command or not is_env_dump_command(command):
        return output, error

    return (
        sanitize_bash_output(command, output),
        sanitize_bash_output(command, error) if error else error,
    )
