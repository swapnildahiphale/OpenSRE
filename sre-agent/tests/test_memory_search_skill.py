import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("neo4j")
pytestmark = pytest.mark.skipif(not os.getenv("NEO4J_URI"), reason="needs Neo4j")

SRE_AGENT_ROOT = Path(__file__).resolve().parent.parent


def test_search_script_returns_json():
    script = ".claude/skills/memory-search/scripts/search.py"
    out = subprocess.run(
        [sys.executable, script, "--query", "database pool", "--limit", "3"],
        capture_output=True,
        text=True,
        cwd=SRE_AGENT_ROOT,
        env={**os.environ, "PYTHONPATH": str(SRE_AGENT_ROOT)},
    )
    assert out.returncode == 0, out.stderr
    body = json.loads(out.stdout)
    assert body["success"] is True
    assert "episodes" in body["result"]
    assert "strategy" in body["result"]
