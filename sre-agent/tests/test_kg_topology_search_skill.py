import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("neo4j")
pytestmark = pytest.mark.skipif(not os.getenv("NEO4J_URI"), reason="needs Neo4j")

SRE_AGENT_ROOT = Path(__file__).resolve().parent.parent


def test_topology_search_script_returns_json():
    script = ".claude/skills/infrastructure-neo4j/scripts/topology_search.py"
    out = subprocess.run(
        [sys.executable, script, "--service", "checkout"],
        capture_output=True,
        text=True,
        cwd=SRE_AGENT_ROOT,
        env={**os.environ, "PYTHONPATH": str(SRE_AGENT_ROOT)},
    )
    assert out.returncode == 0, out.stderr
    body = json.loads(out.stdout)
    assert body["success"] is True
    assert "service" in body["result"]
    assert "blast_radius" in body["result"]


def test_topology_search_missing_service():
    script = ".claude/skills/infrastructure-neo4j/scripts/topology_search.py"
    out = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True,
        cwd=SRE_AGENT_ROOT,
        env={**os.environ, "PYTHONPATH": str(SRE_AGENT_ROOT)},
    )
    assert out.returncode != 0
