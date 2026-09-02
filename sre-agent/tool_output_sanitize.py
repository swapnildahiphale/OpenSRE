"""Sanitize tool inputs and outputs before SSE stream and DB persistence.

Redacts environment dumps, Authorization headers, bearer tokens, common API key
patterns, AWS keys, and other credential shapes so secrets never land in traces
or the web UI.
"""

from __future__ import annotations

import copy
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

# Shared secret key names for JSON object keys and generic key=value assignments.
# Both matchers derive from this list so they cannot drift.
_SECRET_KEY_ALT = (
    r"token|api[_-]?key|apikey|access[_-]?key|access[_-]?token|"
    r"client[_-]?secret|secret|password|passwd|authorization"
)

# JSON string values may contain escaped quotes; match until an unescaped closing quote.
_JSON_STRING_VALUE = r'"(?:[^"\\]|\\.)*"'

# Secret-shaped substrings in arbitrary tool output, commands, and errors.
_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Authorization / auth headers (curl -H, HTTP responses, etc.)
    (
        re.compile(
            r"(?i)(Authorization\s*:\s*)(Bearer|Basic|Token)\s+[^\s'\"]+",
            re.MULTILINE,
        ),
        r"\1\2 " + _REDACTED,
    ),
    (
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-+/=]{8,}"),
        "Bearer " + _REDACTED,
    ),
    (
        re.compile(r"(?i)\bBasic\s+[A-Za-z0-9+/=]{8,}"),
        "Basic " + _REDACTED,
    ),
    # AWS access key IDs and common secret-key assignments.
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), _REDACTED),
    (
        re.compile(
            r"(?i)(aws[_\s-]?secret[_\s-]?access[_\s-]?key|secret_access_key)\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{40}['\"]?",
        ),
        r"\1=" + _REDACTED,
    ),
    # Well-known token prefixes.
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"), _REDACTED),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), _REDACTED),
    (re.compile(r"\bgho_[A-Za-z0-9]{20,}\b"), _REDACTED),
    (re.compile(r"\bxox[baprs]-[0-9a-zA-Z\-]{10,}\b"), _REDACTED),
    (re.compile(r"\bATATT[A-Za-z0-9_\-]{20,}\b"), _REDACTED),
    # sk-* vendor keys (Anthropic sk-ant-api03-…, OpenAI sk-proj-…, etc.).
    (re.compile(r"\bsk-[A-Za-z0-9\-]{20,}\b"), _REDACTED),
    # JSON object keys: "token": "…", "api_key" : "…" (whitespace around ':').
    (
        re.compile(
            rf'(?i)("(?:{_SECRET_KEY_ALT})")\s*:\s*{_JSON_STRING_VALUE}',
        ),
        r'\1: "' + _REDACTED + '"',
    ),
    # Prefixed JSON keys: "refresh_token": "…", "POSTGRES_PASSWORD": "…"
    (
        re.compile(
            r'(?i)("([A-Za-z0-9_]*_(?:PASSWORD|TOKEN|SECRET|API_KEY|ACCESS_KEY))")'
            rf"\s*:\s*{_JSON_STRING_VALUE}",
        ),
        r'\1: "' + _REDACTED + '"',
    ),
    # Generic key=value / key: value assignments (word-boundary keys only).
    (
        re.compile(
            rf"(?i)\b({_SECRET_KEY_ALT})\b\s*[:=]\s*['\"]?[^\s'\"]" + r"{8,}['\"]?",
        ),
        r"\1=" + _REDACTED,
    ),
    # Prefixed env / YAML keys: POSTGRES_PASSWORD=…, refresh_token: … (\b misses after '_').
    # Keep the delimiter character before the key so surrounding text is not glued.
    (
        re.compile(
            r"(?i)(^|[\s\"'\\{,])"
            r"([A-Za-z0-9_]*_(?:PASSWORD|TOKEN|SECRET|API_KEY|ACCESS_KEY))"
            r"\s*[:=]\s*\S+",
        ),
        rf"\1\2={_REDACTED}",
    ),
    # URL userinfo: scheme://user:password@host (common DB/HTTP schemes only).
    (
        re.compile(
            r"(?i)((?:https?|postgres(?:ql)?|mysql|redis|mongodb(?:\+srv)?|amqp)://)"
            r"([^:@/\s]+):([^@\s/]+)@",
        ),
        rf"\1\2:{_REDACTED}@",
    ),
    # curl -u / --user user:password (spaced, glued, or --user= / -u= forms)
    (
        re.compile(
            r"(?i)((?:^|[\s|;&])(?:--user=|-u=|--user\s+|-u\s+))"
            r"([^:\s]+):([^\s'\"]+)"
        ),
        rf"\1\2:{_REDACTED}",
    ),
    # Glued short form: curl -udeploy:pass (no space after -u)
    (
        re.compile(r"(?i)((?:^|[\s|;&])-u)([^:\s=/-][^:\s]*):([^\s'\"]+)"),
        rf"\1\2:{_REDACTED}",
    ),
    # PEM private keys.
    (
        re.compile(
            r"-----BEGIN[A-Z ]*PRIVATE KEY-----[\s\S]*?-----END[A-Z ]*PRIVATE KEY-----",
            re.MULTILINE,
        ),
        _REDACTED,
    ),
    # JWT-shaped tokens (three base64url segments).
    (
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
        ),
        _REDACTED,
    ),
]


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


def _redact_secrets_in_text(text: str) -> str:
    """Apply regex-based secret redaction to arbitrary text."""
    redacted = text
    for pattern, replacement in _SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _sanitize_plain_or_json_text(text: str) -> str:
    """Redact secrets in plain text or SDK JSON stdout/stderr wrappers."""
    wrapper = _try_parse_json_output(text)
    if wrapper is not None:
        changed = False
        for field in ("stdout", "stderr"):
            if field in wrapper and wrapper[field] is not None:
                inner = wrapper[field]
                if isinstance(inner, str):
                    sanitized = _redact_secrets_in_text(inner)
                    if sanitized != inner:
                        wrapper[field] = sanitized
                        changed = True
        if changed:
            return json.dumps(wrapper)
        return text

    return _redact_secrets_in_text(text)


def sanitize_bash_output(command: str, output: str | None) -> str | None:
    """Redact env dumps and secret-shaped values from Bash tool output."""
    if output is None:
        return None

    if is_env_dump_command(command):
        wrapper = _try_parse_json_output(output)
        if wrapper is not None:
            changed = False
            for field in ("stdout", "stderr"):
                if field in wrapper and wrapper[field] is not None:
                    inner = wrapper[field]
                    if isinstance(inner, str):
                        sanitized = _redact_env_text(inner)
                        sanitized = _redact_secrets_in_text(sanitized)
                        if sanitized != inner:
                            wrapper[field] = sanitized
                            changed = True
            if changed:
                output = json.dumps(wrapper)
        else:
            output = _redact_env_text(output)
            output = _redact_secrets_in_text(output)
    else:
        output = _sanitize_plain_or_json_text(output)

    return output


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


def sanitize_command(command: str) -> str:
    """Redact secret-shaped substrings embedded in a Bash command string."""
    return _redact_secrets_in_text(command)


def sanitize_tool_input(tool_name: str, tool_input: Any) -> Any:
    """Redact secrets in tool_start payloads (commands, args, etc.)."""
    if not isinstance(tool_input, dict):
        return tool_input

    sanitized = copy.deepcopy(tool_input)
    if tool_name == "Bash" and isinstance(sanitized.get("command"), str):
        sanitized["command"] = sanitize_command(sanitized["command"])

    for key, value in sanitized.items():
        if isinstance(value, str) and key != "command":
            sanitized[key] = _redact_secrets_in_text(value)

    return sanitized


def sanitize_tool_end_payload(
    tool_name: str,
    tool_input: Any,
    output: str | None,
    error: str | None,
) -> tuple[str | None, str | None]:
    """Entry point for hooks and persistence. Returns (output, error)."""
    if tool_name == "Bash":
        command = _extract_command(tool_input)
        if command:
            return (
                sanitize_bash_output(command, output),
                sanitize_bash_output(command, error) if error else error,
            )

    sanitized_output = _sanitize_plain_or_json_text(output) if output else output
    sanitized_error = _sanitize_plain_or_json_text(error) if error else error
    return sanitized_output, sanitized_error
