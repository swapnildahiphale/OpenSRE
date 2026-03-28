#!/usr/bin/env python3
"""
OpenSRE Investigation Server (LangGraph Mode)

Runs the LangGraph investigation graph in-process.
Streams events via SSE using graph.astream_events().

Usage:
    python server.py
"""

import datetime
import json
import logging
import os
import secrets
import time
import uuid
from typing import Dict, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Config-service internal API for recording agent runs
_CONFIG_SERVICE_URL = os.getenv("CONFIG_SERVICE_URL", "")
_INTERNAL_SERVICE_HEADER = {"X-Internal-Service": "sre-agent"}

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

load_dotenv()

# File proxy: token -> download info mapping
_file_download_tokens: Dict[str, dict] = {}
_FILE_TOKEN_TTL_SECONDS = 3600  # 1 hour

import asyncio

# Thread ID -> background task mapping
_background_tasks: Dict[str, asyncio.Task] = {}
_message_queues: Dict[str, asyncio.Queue] = {}  # Queue for sending prompts
_response_queues: Dict[str, asyncio.Queue] = {}  # Queue for receiving events

app = FastAPI(
    title="OpenSRE Investigation Server (LangGraph)",
    description="AI SRE agent for incident investigation - LangGraph mode",
    version="0.4.0",
)


class ImageData(BaseModel):
    type: str = "base64"
    media_type: str
    data: str
    filename: Optional[str] = None


class FileAttachment(BaseModel):
    filename: str
    size: int
    media_type: str
    download_url: str
    auth_header: str


class InvestigateRequest(BaseModel):
    prompt: str
    thread_id: Optional[str] = None
    images: Optional[List[ImageData]] = None
    file_attachments: Optional[List[FileAttachment]] = None


class InterruptRequest(BaseModel):
    thread_id: str


class AnswerRequest(BaseModel):
    thread_id: str
    answers: Dict[str, str]


@app.get("/")
async def root():
    return {
        "service": "OpenSRE Investigation Server",
        "mode": "langgraph",
        "version": "0.4.0",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "mode": "langgraph",
        "active_sessions": len(_background_tasks),
    }


def _get_proxy_base_url() -> str:
    """Get the base URL for file proxy that agent can access."""
    if os.getenv("ROUTER_LOCAL_PORT"):
        return "http://host.docker.internal:8000"

    service_name = os.getenv("K8S_SERVICE_NAME", "opensre-server-svc")
    namespace = os.getenv("K8S_NAMESPACE", "default")
    return f"http://{service_name}.{namespace}.svc.cluster.local:8000"


@app.get("/proxy/files/{token}")
async def proxy_file(token: str, request: Request):
    """
    File proxy endpoint - streams files from external sources (e.g., Slack).
    Allows agents to download files without having credentials.
    """
    # Cleanup expired tokens
    now = time.time()
    expired = [
        t
        for t, info in _file_download_tokens.items()
        if now - info["created_at"] > _FILE_TOKEN_TTL_SECONDS
    ]
    for t in expired:
        del _file_download_tokens[t]

    if token not in _file_download_tokens:
        raise HTTPException(404, "Token not found or expired")

    info = _file_download_tokens[token]
    del _file_download_tokens[token]  # Single-use token

    async def stream_file():
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
                async with client.stream(
                    "GET",
                    info["download_url"],
                    headers={"Authorization": info["auth_header"]},
                ) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        yield chunk
        except Exception as e:
            logger.error(f"Failed to proxy file: {e}")
            raise HTTPException(500, f"Failed to download file: {e}")

    return StreamingResponse(
        stream_file(),
        media_type=info.get("media_type", "application/octet-stream"),
        headers={
            "Content-Disposition": f'attachment; filename="{info["filename"]}"',
        },
    )


# ---------------------------------------------------------------------------
# Alert parsing helper
# ---------------------------------------------------------------------------


def _parse_alert_from_prompt(prompt: str) -> dict:
    """Parse an alert dict from the investigation prompt.

    If the prompt looks like JSON, parse it. Otherwise wrap it as a description.
    """
    try:
        alert = json.loads(prompt)
        if isinstance(alert, dict):
            return alert
    except (json.JSONDecodeError, TypeError):
        pass

    # Wrap as description-only alert
    return {
        "name": "Investigation",
        "description": prompt,
        "service": "",
        "severity": "info",
    }


# ---------------------------------------------------------------------------
# LangGraph background task
# ---------------------------------------------------------------------------


async def graph_background_task(thread_id: str):
    """
    Background task that runs LangGraph investigation and streams events.

    Processes messages from queue. For each message, runs the graph via
    astream_events() and maps LangGraph events to the existing SSE format.
    Records tool call traces and run completion to config-service.
    """
    from graph import get_graph

    logger.info(f"[BG] Starting LangGraph background task for thread {thread_id}")

    graph = get_graph()
    message_queue = _message_queues[thread_id]
    response_queue = _response_queues[thread_id]

    try:
        while True:
            # Wait for next message
            logger.info(f"[BG] Waiting for message on thread {thread_id}")
            message = await message_queue.get()

            if message is None:  # Shutdown signal
                logger.info(f"[BG] Shutdown signal received for thread {thread_id}")
                break

            prompt = message.get("prompt")
            images = message.get("images")
            run_id = message.get("run_id")
            run_start_time = message.get("start_time", time.time())
            logger.info(
                f"[BG] Processing message for thread {thread_id}: {prompt[:50]}..."
            )
            if images:
                logger.info(f"[BG] Including {len(images)} image(s) in message")

            # --- Memory Touch Point 1: Pre-investigation memory lookup ---
            original_prompt = prompt  # Preserve for episode storage
            try:
                from memory_service import get_memory_context_for_prompt

                prompt = get_memory_context_for_prompt(
                    prompt=prompt, thread_id=thread_id
                )
            except Exception as e:
                logger.warning(f"[BG] Memory lookup failed (continuing without): {e}")

            # Build initial graph state
            # Use original_prompt for alert parsing — memory context prepends text
            # that breaks JSON parsing of the raw alert payload.
            initial_state = {
                "alert": _parse_alert_from_prompt(original_prompt),
                "thread_id": thread_id,
                "images": images or [],
            }

            config = {"configurable": {"thread_id": thread_id}}

            # Stream events
            event_count = 0
            tool_calls_count = 0
            accumulated_text = ""
            output_summary = ""
            thoughts_buffer: List[dict] = []
            all_completed_tools: List[dict] = []
            pending_tools: Dict[str, dict] = {}
            tool_seq = 0

            async for event in graph.astream_events(
                initial_state, config=config, version="v2"
            ):
                event_kind = event.get("event", "")
                metadata = event.get("metadata", {})
                node_name = metadata.get("langgraph_node", "")

                if event_kind == "on_chat_model_stream":
                    # Extract text delta for thought events (streaming calls)
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        text = chunk.content if isinstance(chunk.content, str) else ""
                        if text:
                            agent_name = metadata.get("agent_id", node_name)
                            accumulated_text += text
                            await response_queue.put(
                                {
                                    "event": "thought",
                                    "data": {
                                        "text": text,
                                        "agent_name": agent_name,
                                    },
                                }
                            )
                            # (streaming tokens sent live via SSE above;
                            #  complete text recorded by on_chat_model_end)

                elif event_kind == "on_chat_model_end":
                    # Extract full response for thought events (invoke() calls)
                    output = event.get("data", {}).get("output")
                    if output and hasattr(output, "content") and output.content:
                        text = output.content if isinstance(output.content, str) else ""
                        if text:
                            tool_seq += 1
                            agent_name = metadata.get("agent_id", node_name)
                            accumulated_text += text
                            await response_queue.put(
                                {
                                    "event": "thought",
                                    "data": {
                                        "text": text,
                                        "agent_name": agent_name,
                                    },
                                }
                            )
                            if run_id:
                                thought_entry = {
                                    "text": text[:2000],
                                    "ts": datetime.datetime.now(
                                        datetime.timezone.utc
                                    ).isoformat(),
                                    "seq": tool_seq,
                                    "agent": agent_name,
                                }
                                thoughts_buffer.append(thought_entry)
                                await _record_thoughts(run_id, [thought_entry])

                elif event_kind == "on_tool_start":
                    tool_calls_count += 1
                    tool_seq += 1
                    tool_input = event.get("data", {}).get("input", {})
                    tool_name = event.get("name", "unknown")
                    tool_run_id = event.get("run_id", f"gen-{uuid.uuid4().hex[:8]}")
                    agent_name = metadata.get("agent_id", node_name)

                    await response_queue.put(
                        {
                            "event": "tool_start",
                            "data": {
                                "name": tool_name,
                                "tool_use_id": tool_run_id,
                                "input": (
                                    _truncate_dict_values(tool_input)
                                    if isinstance(tool_input, dict)
                                    else {"args": str(tool_input)[:500]}
                                ),
                                "agent_name": agent_name,
                            },
                        }
                    )

                    # Track pending tool
                    started_at_iso = datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat()
                    pending_tools[tool_run_id] = {
                        "id": tool_run_id,
                        "tool_name": tool_name,
                        "tool_input": (
                            _truncate_dict_values(tool_input)
                            if isinstance(tool_input, dict)
                            else {}
                        ),
                        "started_at": started_at_iso,
                        "sequence_number": tool_seq,
                        "_start_ts": time.time(),
                        "_agent_name": agent_name,
                    }

                    if run_id:
                        await _record_tool_calls(
                            run_id,
                            [
                                {
                                    "id": tool_run_id,
                                    "tool_name": tool_name,
                                    "agent_name": agent_name,
                                    "parent_agent": None,
                                    "tool_input": (
                                        _truncate_dict_values(tool_input)
                                        if isinstance(tool_input, dict)
                                        else {}
                                    ),
                                    "tool_output": None,
                                    "started_at": started_at_iso,
                                    "duration_ms": None,
                                    "status": "running",
                                    "error_message": None,
                                    "sequence_number": tool_seq,
                                }
                            ],
                        )

                elif event_kind == "on_tool_end":
                    tool_output = event.get("data", {}).get("output", "")
                    tool_run_id = event.get("run_id", "")
                    tool_name = event.get("name", "unknown")
                    agent_name = metadata.get("agent_id", node_name)

                    output_str = str(tool_output)[:5000] if tool_output else ""

                    await response_queue.put(
                        {
                            "event": "tool_end",
                            "data": {
                                "name": tool_name,
                                "tool_use_id": tool_run_id,
                                "success": True,
                                "output": output_str[:2000],
                                "agent_name": agent_name,
                            },
                        }
                    )

                    # Complete pending tool
                    pending = pending_tools.pop(tool_run_id, None)
                    if pending and run_id:
                        duration_ms = int(
                            (time.time() - pending.get("_start_ts", time.time())) * 1000
                        )
                        tool_call_item = {
                            "id": pending["id"],
                            "tool_name": pending["tool_name"],
                            "agent_name": pending.get("_agent_name", node_name),
                            "parent_agent": None,
                            "tool_input": pending.get("tool_input"),
                            "tool_output": output_str[:5000],
                            "started_at": pending["started_at"],
                            "duration_ms": duration_ms,
                            "status": "success",
                            "error_message": None,
                            "sequence_number": pending["sequence_number"],
                        }
                        await _record_tool_calls(run_id, [tool_call_item])
                        all_completed_tools.append(tool_call_item)

                event_count += 1

            # Graph completed - get final state
            final_state = graph.get_state(config)
            conclusion = final_state.values.get("conclusion", "")
            structured_report = final_state.values.get("structured_report", {})

            # Send result event
            result_text = conclusion or output_summary or accumulated_text[:2000]
            result_data: dict = {
                "text": result_text,
                "success": True,
            }
            if structured_report:
                result_data["structured_report"] = structured_report

            await response_queue.put({"event": "result", "data": result_data})

            # Record run completion
            if run_id:
                # Flush orphan pending tools
                orphan_items = []
                for orphan_id, orphan in pending_tools.items():
                    orphan.pop("_start_ts", None)
                    agent_name = orphan.pop("_agent_name", "sre-agent")
                    orphan_items.append(
                        {
                            "id": orphan["id"],
                            "tool_name": orphan["tool_name"],
                            "agent_name": agent_name,
                            "parent_agent": None,
                            "tool_input": orphan.get("tool_input"),
                            "tool_output": None,
                            "started_at": orphan["started_at"],
                            "duration_ms": None,
                            "status": "timeout",
                            "error_message": "No tool_end received",
                            "sequence_number": orphan["sequence_number"],
                        }
                    )
                if orphan_items:
                    logger.warning(
                        f"[TRACE] {len(orphan_items)} orphaned tool calls: "
                        f"{[(o['tool_name'], o['id'][:12]) for o in orphan_items]}"
                    )
                    await _record_tool_calls(run_id, orphan_items)

                duration = time.time() - run_start_time
                await _record_run_complete(
                    run_id=run_id,
                    status="completed",
                    duration_seconds=round(duration, 2),
                    tool_calls_count=tool_calls_count,
                    output_summary=result_text[:4000] if result_text else None,
                    output_json=structured_report or None,
                    thoughts=thoughts_buffer or None,
                )

            # --- Memory Touch Point 3: Post-investigation storage ---
            try:
                from memory_service import store_investigation

                store_investigation(
                    thread_id=thread_id,
                    prompt=original_prompt,
                    result_text=accumulated_text,
                    success=True,
                    agent_run_id=run_id,
                    tool_calls_data=all_completed_tools,
                    duration_seconds=(
                        round(time.time() - run_start_time, 2) if run_id else None
                    ),
                )
            except Exception as e:
                logger.warning(f"[BG] Memory storage failed (non-fatal): {e}")

            # Signal completion
            await response_queue.put(None)
            logger.info(
                f"[BG] Completed message processing. Total events: {event_count}, "
                f"tool_calls: {tool_calls_count}"
            )

    except Exception as e:
        logger.error(
            f"[BG] Background task failed for thread {thread_id}: {e}", exc_info=True
        )
        await response_queue.put({"error": str(e)})
    finally:
        logger.info(f"[BG] Background task ended for thread {thread_id}")


def _download_file_attachments(file_downloads: list, thread_id: str):
    """
    Download file attachments directly using stored token info.

    In simple mode there's no sandbox, so we download files in-process
    using the credentials stored in _file_download_tokens. Files are saved
    to the agent's session directory at /tmp/sessions/{thread_id}/attachments/
    to match what the enriched prompt tells the agent.
    """
    from pathlib import Path

    # Must match agent.py's session directory for simple mode
    attachments_dir = Path(f"/tmp/sessions/{thread_id}/attachments")
    attachments_dir.mkdir(parents=True, exist_ok=True)

    for download in file_downloads:
        token = download["token"]
        token_info = _file_download_tokens.pop(token, None)
        if not token_info:
            logger.warning(f"Token not found for file {download['filename']}, skipping")
            continue

        safe_filename = Path(download["filename"]).name or "unnamed_file"
        file_path = attachments_dir / safe_filename

        # Handle duplicate filenames
        counter = 1
        original_stem = file_path.stem
        original_suffix = file_path.suffix
        while file_path.exists():
            file_path = attachments_dir / f"{original_stem}_{counter}{original_suffix}"
            counter += 1

        try:
            logger.info(
                f"Downloading {safe_filename} ({download.get('size', '?')} bytes) from Slack..."
            )
            with httpx.Client(timeout=httpx.Timeout(300.0)) as client:
                with client.stream(
                    "GET",
                    token_info["download_url"],
                    headers={"Authorization": token_info["auth_header"]},
                ) as response:
                    response.raise_for_status()
                    with open(file_path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=65536):
                            f.write(chunk)

            logger.info(f"Saved: {file_path}")
        except Exception as e:
            logger.error(f"Failed to download {safe_filename}: {e}")
            # Write error file so agent knows what happened
            error_path = attachments_dir / f"{file_path.name}.error"
            error_path.write_text(
                f"Download failed for: {safe_filename}\n"
                f"Error: {e}\n"
                f"\nThe file could not be downloaded from Slack. "
                f"Please ask the user to re-upload or share the content directly.\n"
            )


async def _record_run_start(
    run_id: str,
    thread_id: str,
    prompt: str,
    trigger_source: str = "api",
    agent_name: str = "sre-agent",
) -> bool:
    """Record agent run start with config-service. Returns True on success."""
    if not _CONFIG_SERVICE_URL:
        return False
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.post(
                f"{_CONFIG_SERVICE_URL}/api/v1/internal/agent-runs",
                headers=_INTERNAL_SERVICE_HEADER,
                json={
                    "run_id": run_id,
                    "org_id": os.getenv("OPENSRE_TENANT_ID", "local"),
                    "team_node_id": os.getenv("OPENSRE_TEAM_ID", "default"),
                    "correlation_id": thread_id,
                    "agent_name": agent_name,
                    "trigger_source": trigger_source,
                    "trigger_message": prompt[:500] if prompt else None,
                },
            )
            resp.raise_for_status()
            logger.info(f"Recorded agent run start: {run_id}")
            return True
    except Exception as e:
        logger.warning(f"Failed to record run start (non-fatal): {e}")
        return False


def _truncate_dict_values(d: dict, max_len: int = 500) -> dict:
    """Truncate string values in a dict for safe storage."""
    result = {}
    for k, v in d.items():
        if isinstance(v, str) and len(v) > max_len:
            result[k] = v[:max_len] + "..."
        elif isinstance(v, dict):
            result[k] = _truncate_dict_values(v, max_len)
        else:
            result[k] = v
    return result


async def _record_tool_calls(run_id: str, tool_calls: list) -> bool:
    """Submit tool call traces to config-service. Returns True on success."""
    if not _CONFIG_SERVICE_URL or not tool_calls:
        return False
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.post(
                f"{_CONFIG_SERVICE_URL}/api/v1/internal/agent-runs/{run_id}/tool-calls",
                headers=_INTERNAL_SERVICE_HEADER,
                json={
                    "run_id": run_id,
                    "tool_calls": tool_calls,
                },
            )
            resp.raise_for_status()
            logger.info(f"Recorded {len(tool_calls)} tool calls for run {run_id}")
            return True
    except Exception as e:
        logger.warning(f"Failed to record tool calls (non-fatal): {e}")
        return False


async def _record_thoughts(run_id: str, thoughts: list) -> bool:
    """Append thoughts to a running agent run (incremental). Returns True on success."""
    if not _CONFIG_SERVICE_URL or not thoughts:
        return False
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.put(
                f"{_CONFIG_SERVICE_URL}/api/v1/internal/agent-runs/{run_id}/thoughts",
                headers=_INTERNAL_SERVICE_HEADER,
                json={"thoughts": thoughts},
            )
            resp.raise_for_status()
            return True
    except Exception as e:
        logger.debug(f"Failed to record thoughts (non-fatal): {e}")
        return False


async def _record_run_complete(
    run_id: str,
    status: str,
    duration_seconds: float,
    tool_calls_count: int = 0,
    output_summary: str | None = None,
    output_json: dict | None = None,
    error_message: str | None = None,
    thoughts: list | None = None,
) -> bool:
    """Record agent run completion with config-service. Returns True on success."""
    if not _CONFIG_SERVICE_URL:
        return False
    try:
        body: dict = {
            "status": status,
            "duration_seconds": duration_seconds,
            "tool_calls_count": tool_calls_count,
            "output_summary": (output_summary[:4000] if output_summary else None),
            "error_message": (error_message[:1000] if error_message else None),
            "thoughts": thoughts,
        }
        if output_json:
            body["output_json"] = output_json
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.patch(
                f"{_CONFIG_SERVICE_URL}/api/v1/internal/agent-runs/{run_id}",
                headers=_INTERNAL_SERVICE_HEADER,
                json=body,
            )
            resp.raise_for_status()
            logger.info(f"Recorded agent run complete: {run_id} ({status})")
            return True
    except Exception as e:
        logger.warning(f"Failed to record run completion (non-fatal): {e}")
        return False


def _is_inconclusive_output(text: str) -> bool:
    """
    Check if output_summary looks like an initial planning message rather
    than a real investigation conclusion.  Returns True when the output
    should be replaced by a generated summary.
    """
    if not text or len(text.strip()) < 50:
        return True
    lower = text.lower().strip()
    planning_prefixes = [
        "i'll investigate",
        "i will investigate",
        "let me start",
        "let me investigate",
        "i'll start",
        "i'll begin",
        "let me begin",
        "let me assess",
        "i'll assess",
        "i'll look into",
        "let me look into",
    ]
    return any(lower.startswith(p) for p in planning_prefixes)


async def _generate_timeout_summary(
    prompt: str,
    evidence_items: list,
    writeup_system_prompt: str | None = None,
    max_evidence_chars: int = 8000,
) -> str | None:
    """
    Generate a structured summary from accumulated evidence when an investigation
    hits max_turns. Uses a one-shot LLM call (Haiku-class) to synthesize findings.

    Returns None on failure so the caller can fall back to the existing output.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    model = os.getenv("SUMMARY_LLM_MODEL", "claude-haiku-4-5-20251001")

    if not api_key or api_key.startswith("sk-ant-placeholder"):
        logger.warning(
            "[TIMEOUT-SUMMARY] No valid API key, skipping summary generation"
        )
        return None

    # Format evidence, newest items first (most relevant findings are usually latest)
    formatted_parts = []
    total_chars = 0
    for item in reversed(evidence_items):
        if item["type"] == "tool":
            part = f"[Tool: {item['tool']}]\n{item['output']}"
        else:
            part = f"[Agent reasoning]\n{item['text']}"
        if total_chars + len(part) > max_evidence_chars:
            break
        formatted_parts.append(part)
        total_chars += len(part)

    if not formatted_parts:
        return None

    formatted_evidence = "\n---\n".join(reversed(formatted_parts))

    user_message = (
        f"The investigation ran out of its turn budget before completing.\n"
        f'Original question: "{prompt[:500]}"\n\n'
        f"Evidence gathered during investigation:\n{formatted_evidence}\n\n"
        f"Based on this evidence, write a structured summary covering:\n"
        f"1. What was investigated and what tools/commands were run\n"
        f"2. Key findings from the evidence\n"
        f"3. Current assessment (healthy/degraded/unknown)\n"
        f"4. What remained unfinished"
    )

    messages = [{"role": "user", "content": user_message}]
    request_body: dict = {
        "model": model,
        "max_tokens": 800,
        "messages": messages,
    }
    if writeup_system_prompt:
        request_body["system"] = writeup_system_prompt[:4000]

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            resp = await client.post(
                f"{base_url}/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=request_body,
            )
            resp.raise_for_status()
            data = resp.json()
            # Find the text block (MiniMax may prepend a "thinking" block)
            summary = next(
                (b["text"] for b in data.get("content", []) if b.get("type") == "text"),
                None,
            )
            if not summary:
                logger.warning("[TIMEOUT-SUMMARY] No text block in LLM response")
                return None
            logger.info(
                f"[TIMEOUT-SUMMARY] Generated {len(summary)}-char summary from "
                f"{len(evidence_items)} evidence items"
            )
            return summary
    except Exception as e:
        logger.warning(
            f"[TIMEOUT-SUMMARY] LLM call failed (non-fatal): "
            f"{type(e).__name__}: {e}",
            exc_info=True,
        )
        return None


def _json_report_to_markdown(report: dict) -> str:
    """Convert a structured JSON investigation report to readable markdown."""
    lines = []

    title = report.get("title", "Investigation Report")
    severity = report.get("severity", "").upper()
    status = report.get("status", "").replace("_", " ").title()
    lines.append(f"# {title}")
    if severity or status:
        lines.append(f"**Severity:** {severity}  |  **Status:** {status}")

    services = report.get("affected_services", [])
    if services:
        lines.append(f"**Affected Services:** {', '.join(services)}")

    lines.append("")

    summary = report.get("executive_summary")
    if summary:
        lines.append(f"## Executive Summary\n{summary}\n")

    impact = report.get("impact")
    if impact:
        lines.append("## Impact")
        if impact.get("user_facing"):
            lines.append(f"- **User-Facing:** {impact['user_facing']}")
        if impact.get("service_impact"):
            lines.append(f"- **Service Impact:** {impact['service_impact']}")
        if impact.get("blast_radius"):
            lines.append(f"- **Blast Radius:** {impact['blast_radius']}")
        lines.append("")

    timeline = report.get("timeline", [])
    if timeline:
        lines.append("## Timeline")
        for entry in timeline:
            lines.append(f"- **{entry.get('time', '?')}** - {entry.get('event', '')}")
        lines.append("")

    root_cause = report.get("root_cause")
    if root_cause:
        lines.append("## Root Cause Analysis")
        confidence = root_cause.get("confidence", "")
        if confidence:
            lines.append(f"*Confidence: {confidence}*\n")
        lines.append(root_cause.get("summary", ""))
        details = root_cause.get("details")
        if details:
            lines.append(f"\n{details}")
        lines.append("")

    actions = report.get("action_items", [])
    if actions:
        lines.append("## Action Items")
        for item in actions:
            priority = item.get("priority", "")
            action = item.get("action", "")
            lines.append(f"- [{priority}] {action}")
        lines.append("")

    lessons = report.get("lessons_learned", [])
    if lessons:
        lines.append("## Lessons Learned")
        for lesson in lessons:
            lines.append(f"- {lesson}")
        lines.append("")

    return "\n".join(lines)


async def _generate_investigation_writeup(
    prompt: str,
    output_summary: str,
    evidence_items: list,
    all_completed_tools: list,
    thoughts_buffer: list,
    writeup_system_prompt: str | None = None,
    max_evidence_chars: int = 12000,
) -> tuple[str | None, dict | None]:
    """
    Generate a structured investigation writeup from the completed investigation.
    Runs after every investigation (not just timeouts) to produce a postmortem-style report.

    Returns (markdown_text, json_dict) on success, (None, None) on failure.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    model = os.getenv(
        "WRITEUP_LLM_MODEL",
        os.getenv("SUMMARY_LLM_MODEL", "claude-haiku-4-5-20251001"),
    )

    if not api_key or api_key.startswith("sk-ant-placeholder"):
        logger.warning("[WRITEUP] No valid API key, skipping writeup generation")
        return None, None

    # --- Build evidence sections ---
    sections = []

    # 1. Investigation conclusion (the agent's own synthesis)
    if output_summary:
        sections.append(f"## Investigation Conclusion\n{output_summary[:3000]}")

    # 2. Tool call summary (names + counts)
    if all_completed_tools:
        tool_counts: dict[str, int] = {}
        for tc in all_completed_tools:
            name = tc.get("tool_name", "unknown")
            tool_counts[name] = tool_counts.get(name, 0) + 1
        tool_summary = ", ".join(
            f"{n}: {c}x" for n, c in sorted(tool_counts.items(), key=lambda x: -x[1])
        )
        sections.append(
            f"## Tools Used ({len(all_completed_tools)} total)\n{tool_summary}"
        )

    # 3. Agent reasoning from thoughts buffer (key thinking steps)
    if thoughts_buffer:
        thought_texts = [t.get("text", "")[:300] for t in thoughts_buffer[-10:]]
        sections.append(
            f"## Agent Reasoning (last {len(thought_texts)} thoughts)\n"
            + "\n---\n".join(thought_texts)
        )

    # 4. Tool outputs from evidence_items (newest first, up to max_evidence_chars)
    formatted_parts = []
    total_chars = 0
    for item in reversed(evidence_items):
        if item["type"] == "tool":
            part = f"[Tool: {item['tool']}]\n{item['output']}"
        else:
            part = f"[Agent reasoning]\n{item['text']}"
        if total_chars + len(part) > max_evidence_chars:
            break
        formatted_parts.append(part)
        total_chars += len(part)

    if formatted_parts:
        formatted_evidence = "\n---\n".join(reversed(formatted_parts))
        sections.append(f"## Evidence Gathered\n{formatted_evidence}")

    if not sections:
        return None, None

    combined_evidence = "\n\n".join(sections)

    user_message = (
        f'Original investigation request: "{prompt[:500]}"\n\n'
        f"{combined_evidence}\n\n"
        f"Based on all the evidence above, produce a structured investigation report as a JSON object.\n"
        f"Respond ONLY with the JSON object, no markdown fences, no extra text.\n\n"
        f"Schema:\n"
        f"{{\n"
        f'  "version": 1,\n'
        f'  "title": "Short descriptive title",\n'
        f'  "severity": "critical | high | medium | low | info",\n'
        f'  "status": "resolved | mitigated | ongoing | inconclusive",\n'
        f'  "affected_services": ["service1"],\n'
        f'  "executive_summary": "2-3 sentence overview",\n'
        f'  "impact": {{\n'
        f'    "user_facing": "what users experienced",\n'
        f'    "service_impact": "which services degraded",\n'
        f'    "blast_radius": "single service | namespace-wide | cluster-wide"\n'
        f"  }},\n"
        f'  "timeline": [{{"time": "14:05", "event": "description"}}],\n'
        f'  "root_cause": {{\n'
        f'    "summary": "one-paragraph root cause",\n'
        f'    "confidence": "confirmed | probable | hypothesis",\n'
        f'    "details": "optional deeper explanation or null"\n'
        f"  }},\n"
        f'  "action_items": [{{"priority": "immediate | short_term | long_term", "action": "description"}}],\n'
        f'  "lessons_learned": ["lesson 1"]\n'
        f"}}\n\n"
        f"Be concise and factual. Use the evidence provided, do not invent details."
    )

    messages = [{"role": "user", "content": user_message}]
    request_body: dict = {
        "model": model,
        "max_tokens": 3000,
        "messages": messages,
    }
    if writeup_system_prompt:
        request_body["system"] = writeup_system_prompt[:4000]

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0)) as client:
            resp = await client.post(
                f"{base_url}/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=request_body,
            )
            resp.raise_for_status()
            data = resp.json()
            raw_text = next(
                (b["text"] for b in data.get("content", []) if b.get("type") == "text"),
                None,
            )
            if not raw_text:
                logger.warning("[WRITEUP] No text block in LLM response")
                return None, None

            # Try to parse as JSON
            report_json = None
            try:
                report_json = json.loads(raw_text)
            except json.JSONDecodeError:
                # Strip markdown code fences and retry
                stripped = raw_text.strip()
                if stripped.startswith("```"):
                    # Remove opening fence (```json or ```)
                    first_nl = (
                        stripped.index("\n") if "\n" in stripped else len(stripped)
                    )
                    stripped = stripped[first_nl + 1 :]
                if stripped.endswith("```"):
                    stripped = stripped[:-3].rstrip()
                try:
                    report_json = json.loads(stripped)
                except json.JSONDecodeError:
                    pass

            if report_json and isinstance(report_json, dict):
                markdown_text = _json_report_to_markdown(report_json)
                logger.info(
                    f"[WRITEUP] Generated structured JSON report ({len(raw_text)} chars) "
                    f"from {len(evidence_items)} evidence items"
                )
                return markdown_text, report_json
            else:
                # Fallback: return raw text as markdown, no JSON
                logger.info(
                    f"[WRITEUP] Generated {len(raw_text)}-char writeup (plain text) from "
                    f"{len(evidence_items)} evidence items"
                )
                return raw_text, None
    except Exception as e:
        logger.warning(
            f"[WRITEUP] LLM call failed (non-fatal): {type(e).__name__}: {e}",
            exc_info=True,
        )
        return None, None


async def create_investigation_stream(
    thread_id: str,
    prompt: str,
    is_new: bool,
    images: Optional[List[dict]] = None,
    file_downloads: Optional[List[dict]] = None,
    trigger_source_hint: Optional[str] = None,
):
    """
    Create SSE stream by communicating with background LangGraph task.

    Recording of tool calls and run completion is handled by the background
    task (graph_background_task), NOT here. This ensures recording works
    even if the SSE client disconnects mid-stream.
    """
    # Generate a run ID for tracking
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    start_time = time.time()

    # Determine trigger source from request context
    trigger_source = "api"
    if trigger_source_hint:
        trigger_source = trigger_source_hint

    # Record run start (non-blocking)
    await _record_run_start(run_id, thread_id, prompt, trigger_source)

    try:
        # Create background task if needed
        if thread_id not in _background_tasks:
            logger.info(f"Creating background task for thread {thread_id}")
            _message_queues[thread_id] = asyncio.Queue()
            _response_queues[thread_id] = asyncio.Queue()

            task = asyncio.create_task(graph_background_task(thread_id))
            _background_tasks[thread_id] = task

            # Give it a moment to start
            await asyncio.sleep(0.1)

        # Download file attachments directly (no sandbox, so download in-process)
        if file_downloads:
            _download_file_attachments(file_downloads, thread_id)

        # Send message to background task (include run_id for recording)
        message_queue = _message_queues[thread_id]
        response_queue = _response_queues[thread_id]

        logger.info(f"Sending message to background task for thread {thread_id}")
        await message_queue.put(
            {
                "prompt": prompt,
                "images": images,
                "run_id": run_id,
                "start_time": start_time,
            }
        )

        # Stream responses as SSE events
        event_count = 0
        while True:
            response = await response_queue.get()

            if response is None:  # Completion signal
                break

            if "error" in response:
                error_payload = {
                    "type": "error",
                    "data": {"message": response["error"]},
                    "thread_id": thread_id,
                    "timestamp": datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                }
                yield f"data: {json.dumps(error_payload)}\n\n"
                break

            event_count += 1
            event_type = response["event"]
            data = response["data"]

            # Emit SSE event in same format as before
            event_payload = {
                "type": event_type,
                "data": data,
                "thread_id": thread_id,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            yield f"data: {json.dumps(event_payload)}\n\n"

        logger.info(f"Stream completed. Total events: {event_count}")

    except Exception as e:
        logger.error(f"Stream failed: {e}", exc_info=True)
        error_payload = {
            "type": "error",
            "data": {"message": str(e)},
            "thread_id": thread_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        yield f"data: {json.dumps(error_payload)}\n\n"


@app.post("/investigate")
async def investigate(request: InvestigateRequest, raw_request: Request):
    """
    Start or continue an investigation.

    Runs LangGraph investigation graph in-process.
    """
    thread_id = request.thread_id or f"thread-{uuid.uuid4().hex[:8]}"
    is_new = thread_id not in _background_tasks

    # Detect trigger source from headers
    trigger_source = "api"
    if raw_request.headers.get("X-OpenSRE-Team-Token"):
        trigger_source = "web_ui"
    elif raw_request.headers.get("X-Trigger-Source"):
        trigger_source = raw_request.headers["X-Trigger-Source"]

    logger.info(f"Investigation: thread={thread_id}, new={is_new}")

    # Handle file attachments
    file_downloads = None
    if request.file_attachments:
        file_downloads = []
        proxy_base_url = _get_proxy_base_url()

        for attachment in request.file_attachments:
            token = secrets.token_urlsafe(32)
            _file_download_tokens[token] = {
                "download_url": attachment.download_url,
                "auth_header": attachment.auth_header,
                "filename": attachment.filename,
                "media_type": attachment.media_type,
                "created_at": time.time(),
            }

            file_downloads.append(
                {
                    "token": token,
                    "filename": attachment.filename,
                    "size": attachment.size,
                    "proxy_url": f"{proxy_base_url}/proxy/files/{token}",
                }
            )

    # Convert images
    images = None
    if request.images:
        images = [
            {
                "type": img.type,
                "media_type": img.media_type,
                "data": img.data,
                "filename": img.filename,
            }
            for img in request.images
        ]

    stream = create_investigation_stream(
        thread_id,
        request.prompt,
        is_new,
        images,
        file_downloads,
        trigger_source_hint=trigger_source,
    )

    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/interrupt")
async def interrupt(request: InterruptRequest):
    """
    Interrupt a running investigation.

    With LangGraph, we cancel the background task for the thread.
    """
    if request.thread_id not in _background_tasks:
        raise HTTPException(404, f"No active task for thread {request.thread_id}")

    logger.info(f"Interrupting thread {request.thread_id}")

    async def stream():
        try:
            task = _background_tasks.get(request.thread_id)
            if task and not task.done():
                task.cancel()

            yield "event: interrupted\n"
            yield f"data: {json.dumps({'thread_id': request.thread_id})}\n\n"
        except Exception as e:
            logger.error(f"Interrupt failed: {e}", exc_info=True)
            yield "event: error\n"
            yield f"data: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/answer")
async def answer(request: AnswerRequest):
    """
    Send answer to agent's question.

    With LangGraph, this would update the graph state via the thread's
    checkpointer. Currently a placeholder for future human-in-the-loop support.
    """
    if request.thread_id not in _background_tasks:
        raise HTTPException(404, f"No active task for thread {request.thread_id}")

    logger.info(f"Answer received for thread {request.thread_id}")
    # TODO: Implement via LangGraph's interrupt/resume mechanism
    # graph.update_state(config, {"human_answer": request.answers})

    return {"status": "ok", "thread_id": request.thread_id}


# -------------------------------------------------------------------------
# Memory API endpoints
# -------------------------------------------------------------------------


class MemorySearchRequest(BaseModel):
    prompt: str
    service_name: Optional[str] = ""
    alert_type: Optional[str] = ""


@app.get("/memory/stats")
async def memory_stats():
    """Get memory system statistics."""
    from memory_service import get_memory_stats

    return get_memory_stats()


@app.get("/memory/episodes")
async def memory_episodes():
    """List all stored investigation episodes."""
    from memory_service import get_all_episodes

    return {"episodes": get_all_episodes()}


@app.post("/memory/search")
async def memory_search(request: MemorySearchRequest):
    """Search for similar past investigations."""
    from memory_service import search_similar

    results = search_similar(
        prompt=request.prompt,
        service_name=request.service_name,
        alert_type=request.alert_type,
    )
    return {"results": results}


@app.get("/memory/strategies")
async def memory_strategies(alert_type: str = "", service_name: str = ""):
    """Get investigation strategies."""
    from memory_service import get_strategies

    return {
        "strategies": get_strategies(alert_type=alert_type, service_name=service_name)
    }


# -------------------------------------------------------------------------
# Knowledge Graph API endpoints
# -------------------------------------------------------------------------


@app.get("/knowledge-graph/service/{name}")
async def kg_service(name: str):
    """Get service topology from Neo4j knowledge graph."""
    try:
        from tools.neo4j_semantic_layer import KubernetesGraphTools

        tools = KubernetesGraphTools()
        result = tools.get_service_information(name)
        return {"success": True, "result": result}
    except Exception as e:
        logger.warning(f"KG query failed for {name}: {e}")
        return {"success": False, "error": str(e)}


@app.get("/knowledge-graph/status/{name}")
async def kg_status(name: str):
    """Get Kubernetes status from Neo4j knowledge graph."""
    try:
        from tools.neo4j_semantic_layer import KubernetesGraphTools

        tools = KubernetesGraphTools()
        result = tools.get_kubernetes_status(name)
        return {"success": True, "result": result}
    except Exception as e:
        logger.warning(f"KG K8s status query failed for {name}: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import uvicorn

    print("=" * 70)
    print("OpenSRE Investigation Server (LangGraph)")
    print("=" * 70)
    print()

    uvicorn.run(app, host="0.0.0.0", port=8000)
