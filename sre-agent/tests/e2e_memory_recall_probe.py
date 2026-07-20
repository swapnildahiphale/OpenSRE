#!/usr/bin/env python3
"""E2E probe: stream /investigate SSE and report memory-related signals."""

import json
import sys
import time
import uuid
from urllib import request

API = "http://localhost:8001/investigate"
TIMEOUT_S = 600


def run_investigation(prompt: str, thread_id: str | None = None) -> dict:
    thread_id = thread_id or f"mem-e2e-{uuid.uuid4().hex[:8]}"
    body = json.dumps({"prompt": prompt, "thread_id": thread_id}).encode()
    req = request.Request(
        API,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    tool_starts: list[dict] = []
    tool_ends: list[dict] = []
    thoughts: list[str] = []
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
            elif etype == "tool_end":
                tool_ends.append(data)
            elif etype == "thought":
                t = data.get("text") or data.get("content") or ""
                if t:
                    thoughts.append(t[:200])
            elif etype == "error":
                errors.append(str(data))

    memory_hits = []
    for ts in tool_starts:
        name = (ts.get("name") or "").lower()
        inp = json.dumps(ts.get("input") or {})
        if "memory" in name or "memory-search" in inp or "memory_search" in inp:
            memory_hits.append(ts)
        if name == "skill" and "memory-search" in inp:
            memory_hits.append(ts)
        if name == "bash" and "memory-search" in inp:
            memory_hits.append(ts)

    return {
        "thread_id": thread_id,
        "elapsed_s": round(time.time() - start, 1),
        "tool_start_count": len(tool_starts),
        "memory_tool_hits": len(memory_hits),
        "memory_tools": memory_hits,
        "tool_names": list({t.get("name") for t in tool_starts}),
        "errors": errors,
        "thought_snippets": thoughts[:5],
    }


if __name__ == "__main__":
    prompt = (
        sys.argv[1]
        if len(sys.argv) > 1
        else (
            "Checkout service in otel-demo returns HTTP 500 with HikariPool connection timeout. "
            "Logs indicate slow queries on the orders table, likely a missing index. "
            "Search memory for similar past investigations and summarize root causes that worked."
        )
    )
    print("Prompt:", prompt[:120], "...", flush=True)
    result = run_investigation(prompt)
    print(json.dumps(result, indent=2))
