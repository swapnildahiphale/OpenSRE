#!/usr/bin/env python3
"""Parse SSE events from an SRE-agent investigation stream.

Modes:
  --verbose   Full debug trace: every tool call with input/output (default)
  --summary   Summary only: tool counts and final result
"""

import json
import sys
import time

verbose = "--summary" not in sys.argv

tools = {}
skills = {}
tool_starts = {}  # tool_use_id -> start data
result_text = ""
result_subtype = ""
thought_count = 0
error_count = 0
tool_seq = 0
start_time = time.time()


def elapsed():
    t = time.time() - start_time
    return f"{int(t//60):02d}:{int(t%60):02d}"


def trunc(s, n=300):
    if not s:
        return ""
    s = str(s)
    return s[:n] + "..." if len(s) > n else s


for line in sys.stdin:
    line = line.strip()
    if not line.startswith("data: "):
        continue
    try:
        d = json.loads(line[6:])
    except Exception:
        continue

    evt = d.get("type", "")
    data = d.get("data", {})

    if evt == "thought":
        thought_count += 1
        t = data.get("text", "")
        parent = data.get("parent_tool_use_id", "")
        if t and verbose:
            indent = "    " if parent else ""
            print(f"[{elapsed()}] {indent}\U0001f4ad {trunc(t, 200)}")

    elif evt == "tool_start":
        tool_seq += 1
        name = data.get("name", "?")
        tools[name] = tools.get(name, 0) + 1
        tid = data.get("tool_use_id", "")
        parent = data.get("parent_tool_use_id", "")
        inp = data.get("input", {})

        if name == "Skill":
            s = inp.get("skill", "?")
            skills[s] = skills.get(s, 0) + 1

        if tid:
            tool_starts[tid] = {"name": name, "seq": tool_seq, "parent": parent}

        if verbose:
            indent = "    " if parent else ""
            detail = ""
            if name == "Bash":
                detail = f" $ {trunc(data.get('command', inp.get('command', '')), 200)}"
            elif name == "Skill":
                detail = f" -> {inp.get('skill', '?')}"
            elif name in ("Read", "Write", "Edit"):
                detail = f" {data.get('file_path', inp.get('file_path', ''))}"
            elif name in ("Glob", "Grep"):
                detail = f" /{data.get('pattern', inp.get('pattern', ''))}/"
            elif name == "Task":
                detail = f" [{data.get('subagent_type', inp.get('subagent_type', '?'))}] {data.get('description', inp.get('description', ''))}"
            elif name == "think":
                detail = ""
            else:
                detail = f" {trunc(str(inp), 150)}"
            print(f"[{elapsed()}] {indent}\U0001f527 #{tool_seq} {name}{detail}")

    elif evt == "tool_end":
        name = data.get("name", "?")
        tid = data.get("tool_use_id", "")
        success = data.get("success", True)
        error = data.get("error", "")
        output = data.get("output", "")
        summary = data.get("summary", "")
        parent = data.get("parent_tool_use_id", "")

        start = tool_starts.pop(tid, None)
        seq = start["seq"] if start else "?"

        if not success:
            error_count += 1

        if verbose:
            indent = "    " if parent else ""
            status = "\u2705" if success else "\u274c"
            result_info = ""
            if error:
                result_info = f" ERROR: {trunc(error, 200)}"
            elif summary:
                result_info = f" {trunc(summary, 200)}"
            elif output:
                result_info = f" {trunc(output, 200)}"
            print(f"[{elapsed()}] {indent}  {status} #{seq} {name} done{result_info}")

    elif evt == "result":
        result_text = data.get("text", "")
        result_subtype = data.get("subtype", "")
        success = data.get("success", True)
        if verbose:
            status = "\u2705" if success else "\u274c"
            print(
                f"\n[{elapsed()}] \U0001f3c1 RESULT ({result_subtype or 'success'}) {status}"
            )

    elif evt == "error":
        error_count += 1
        msg = data.get("message", "")
        if verbose:
            print(f"[{elapsed()}] \u274c ERROR: {trunc(msg, 300)}")

total_elapsed = time.time() - start_time
minutes = int(total_elapsed // 60)
seconds = int(total_elapsed % 60)

print()
print("\u2550" * 60)
print(f"  Investigation Summary  ({minutes}m {seconds}s)")
print("\u2550" * 60)
print(f"Thoughts: {thought_count}")
print(f"Total tool calls: {sum(tools.values())}  (errors: {error_count})")
for t, c in sorted(tools.items(), key=lambda x: -x[1]):
    print(f"  {t}: {c}x")
if skills:
    print(f"Skills invoked: {len(skills)}")
    for s, c in sorted(skills.items(), key=lambda x: -x[1]):
        print(f"  {s}: {c}x")
if result_subtype:
    print(f"Result type: {result_subtype}")
if result_text:
    print(f"\n{'─' * 60}")
    print(f"Result ({len(result_text)} chars):")
    print(result_text[:1000])
    if len(result_text) > 1000:
        print("... (truncated)")
