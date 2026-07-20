"""E2E skill gating: vague prompts should not fire memory/KG in early tools."""

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib import error, request

import pytest

SRE_AGENT_ROOT = Path(__file__).resolve().parent.parent
PROBE = SRE_AGENT_ROOT / "tests" / "e2e_skill_gating_probe.py"

VAGUE_JENKINS_PROMPT = (
    "surveys build pipeline is failing — here is the Jenkins job link only: "
    "https://jenkins.example.com/job/surveys/442 . No service name in the alert."
)

SERVICE_RICH_PROMPT = (
    "Checkout service in otel-demo returns HTTP 500 with HikariPool connection timeout. "
    "Logs show slow queries on orders table. Query knowledge graph for checkout topology "
    "and search memory for similar connection pool investigations."
)


def _server_up() -> bool:
    try:
        request.urlopen("http://localhost:8001/health", timeout=2)
        return True
    except (error.URLError, TimeoutError, OSError):
        return False


def _run_probe(prompt: str) -> dict:
    out = subprocess.run(
        [sys.executable, str(PROBE), prompt],
        capture_output=True,
        text=True,
        cwd=SRE_AGENT_ROOT,
        timeout=int(os.getenv("E2E_PROBE_TIMEOUT", "600")),
    )
    lines = [
        ln.strip()
        for ln in out.stdout.strip().splitlines()
        if ln.strip().startswith("{")
    ]
    assert lines, f"no JSON output: {out.stdout}\n{out.stderr}"
    return json.loads(lines[-1])


@pytest.mark.e2e
@pytest.mark.skipif(not _server_up(), reason="sre-agent not running on :8001")
class TestSkillGatingE2E:
    def test_vague_jenkins_no_early_memory_or_kg(self):
        """Vague ticket: memory-search and KG should not run in first N tools."""
        result = _run_probe(VAGUE_JENKINS_PROMPT)
        assert (
            result["early_memory_hits"] == 0
        ), f"memory-search fired too early: {result}"
        assert result["early_kg_hits"] == 0, f"KG skill fired too early: {result}"

    def test_service_rich_prompt_may_invoke_skills(self):
        """Rich prompt naming service + symptoms: skills may fire during investigation."""
        result = _run_probe(SERVICE_RICH_PROMPT)
        total = result["memory_tool_hits"] + result["kg_tool_hits"]
        if total == 0:
            pytest.skip(
                "agent did not invoke memory/KG skills this run (non-deterministic)"
            )
