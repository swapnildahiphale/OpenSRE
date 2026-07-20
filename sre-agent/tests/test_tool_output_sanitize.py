"""Unit tests for env/printenv Bash output sanitization."""

import json

from tool_output_sanitize import (
    is_env_dump_command,
    sanitize_bash_output,
    sanitize_tool_end_payload,
)


def test_is_env_dump_command_matches_env_printenv_export_p_bare_set():
    assert is_env_dump_command("env")
    assert is_env_dump_command("env | grep TOKEN")
    assert is_env_dump_command("printenv BKT_HOST")
    assert is_env_dump_command("export -p")
    assert is_env_dump_command("set")
    assert is_env_dump_command("set; echo done")


def test_is_env_dump_command_rejects_normal_commands():
    assert not is_env_dump_command("kubectl get pods")
    assert not is_env_dump_command("kubectl set image deploy/foo bar=img:v1")
    assert not is_env_dump_command("cat config.env")
    assert not is_env_dump_command("ls -la")


def test_env_grep_redacts_secret_values():
    output = "BKT_TOKEN=ATATT3xFfGF0secretvalue\nOTHER=also-secret"
    sanitized = sanitize_bash_output("env | grep TOKEN", output)
    assert sanitized is not None
    assert "ATATT" not in sanitized
    assert "also-secret" not in sanitized
    assert "BKT_TOKEN=<redacted>" in sanitized
    assert "OTHER=<redacted>" in sanitized


def test_printenv_single_var_redacted():
    output = "BKT_HOST=api.bitbucket.org"
    sanitized = sanitize_bash_output("printenv BKT_HOST", output)
    assert sanitized == "BKT_HOST=<redacted>"


def test_kubectl_output_unchanged():
    output = "NAME    READY   STATUS\npod-1   1/1     Running"
    assert sanitize_bash_output("kubectl get pods", output) == output


def test_json_stdout_wrapper_sanitized():
    secret = "ATATT3xFfGF0secret"
    wrapper = {
        "stdout": f"BKT_TOKEN={secret}\n",
        "stderr": "",
        "returncode": 0,
    }
    raw = json.dumps(wrapper)
    sanitized = sanitize_bash_output("env", raw)
    parsed = json.loads(sanitized)
    assert secret not in parsed["stdout"]
    assert "BKT_TOKEN=<redacted>" in parsed["stdout"]


def test_sanitize_tool_end_payload_early_return_for_non_bash():
    output, error = sanitize_tool_end_payload(
        "Read",
        {"file_path": "/etc/passwd"},
        "root:x:0:0",
        None,
    )
    assert output == "root:x:0:0"
    assert error is None


def test_sanitize_tool_end_payload_redacts_bash_env():
    output, error = sanitize_tool_end_payload(
        "Bash",
        {"command": "printenv BKT_TOKEN"},
        "BKT_TOKEN=ATATTsecret",
        None,
    )
    assert output == "BKT_TOKEN=<redacted>"
    assert error is None
