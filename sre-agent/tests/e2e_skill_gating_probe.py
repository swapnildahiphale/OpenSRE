#!/usr/bin/env python3
"""E2E probe: stream /investigate SSE and report memory + KG skill signals."""

import json
import sys
import time
import uuid
from pathlib import Path
from urllib import error, request

# Allow running as script from sre-agent/
sys.path.insert(0, str(Path(__file__).resolve().parent))
from skill_trace import count_skill_invocations, early_skill_invocations  # noqa: E402

API = "http://localhost:8001/investigate"
TIMEOUT_S = 600
EARLY_TOOL_LIMIT = 5


def run_investigation(prompt: str, thread_id: str | None = None) -> dict:
    thread_id = thread_id or f"skill-e2e-{uuid.uuid4().hex[:8]}"
    body = json.dumps({"prompt": prompt, "thread_id": thread_id}).encode()
    req = request.Request(
        API,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    tool_starts: list[dict] = []
    errors: list[str] = []
    start = time.time()

    with request.urlopen(req, timeout=TIMEOUT_S) as resp:
        for raw in resp:
            if time.time() - start > TIMEOUT_S:
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data: "):
                continue
            try:
                evt = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            etype = evt.get("type")
            data = evt.get("data") or {}
            if etype == "tool_start":
                tool_starts.append(data)
            elif etype == "error":
                errors.append(str(data))

    totals = count_skill_invocations(tool_starts)
    early = early_skill_invocations(tool_starts, limit=EARLY_TOOL_LIMIT)

    return {
        "thread_id": thread_id,
        "elapsed_s": round(time.time() - start, 1),
        "tool_start_count": len(tool_starts),
        "memory_tool_hits": totals["memory"],
        "kg_tool_hits": totals["kg"],
        "early_memory_hits": early["memory"],
        "early_kg_hits": early["kg"],
        "tool_names": list({t.get("name") for t in tool_starts}),
        "errors": errors,
    }


def server_available() -> bool:
    try:
        request.urlopen("http://localhost:8001/health", timeout=2)
        return True
    except (error.URLError, TimeoutError, OSError):
        return False


# Scenario prompts for gating verification
VAGUE_JENKINS_PROMPT = (
    "surveys build pipeline is failing — here is the Jenkins job link only: "
    "https://jenkins.example.com/job/surveys/442 . No service name in the alert."
)

SERVICE_RICH_PROMPT = (
    "Checkout service in otel-demo returns HTTP 500 with HikariPool connection timeout. "
    "Logs show slow queries on orders table. Query knowledge graph for checkout topology "
    "and search memory for similar connection pool investigations."
)


if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else SERVICE_RICH_PROMPT
    print("Prompt:", prompt[:120], "...", flush=True)
    if not server_available():
        print(json.dumps({"error": "sre-agent not reachable at localhost:8001"}))
        sys.exit(1)
    print(json.dumps(run_investigation(prompt)))
