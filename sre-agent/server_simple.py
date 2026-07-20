#!/usr/bin/env python3
"""
OpenSRE Investigation Server (Simple Mode)

Runs the agent in-process without K8s sandboxes.
For local testing and evaluation only - no isolation.

⚠️  Security Warning: This mode runs agent directly in the server process.
    - No filesystem isolation
    - No network isolation
    - No resource limits
    - Use only for trusted prompts on your own machine
    - For production, use server.py with K8s sandboxes

Usage:
    export USE_SIMPLE_MODE=true
    python server_simple.py
"""

import datetime
import logging
import os
import secrets
import time
import uuid
from typing import Dict, List, Optional

import httpx
import investigation_lifecycle as _il
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from memory.neo4j_conn import NEO4J_DATABASE, get_driver
from memory.retrieval import EpisodeRetriever
from memory.store import EpisodeStore
from pydantic import BaseModel
from report import extract_structured_report
from tool_output_sanitize import sanitize_tool_end_payload

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

load_dotenv()


# ---------------------------------------------------------------------------
# Post-investigation tool-call accumulator + finalizer
# ---------------------------------------------------------------------------


def _collect_tool_call(tool_calls: list, event: dict) -> None:
    """Accumulate tool_start/tool_end events into structured tool-call records."""
    etype = event.get("type")
    data = event.get("data", {})
    if etype == "tool_start":
        tool_calls.append(
            {
                "tool_name": data.get("name"),
                "tool_input": data.get("input", {}),
                "tool_use_id": data.get("tool_use_id"),
                "tool_output": None,
            }
        )
    elif etype == "tool_end":
        uid = data.get("tool_use_id")
        for tc in reversed(tool_calls):
            if tc.get("tool_use_id") == uid and tc["tool_output"] is None:
                tc["tool_output"] = data.get("output")
                break


def finalize_investigation(
    thread_id: str,
    prompt: str,
    result_text: str,
    success: bool,
    tool_calls: list,
    duration_seconds: Optional[float] = None,
    org_id: str = "",
    sdk_session_id: Optional[str] = None,
    tool_calls_count: Optional[int] = None,
    run_status: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Store episode via shared lifecycle module; mark agent run complete."""
    run_id = _run_id_by_thread.get(thread_id)
    try:
        tid_org, tid_team = _thread_tenancy(thread_id)
        _il.finalize_investigation(
            correlation_id=thread_id,
            agent_run_id=run_id,
            prompt=prompt,
            result_text=result_text,
            tool_calls=tool_calls or [],
            duration_seconds=duration_seconds,
            org_id=(org_id or tid_org),
            team_node_id=(tid_team),
        )
    except Exception as e:
        logger.error("[MEMORY] finalize failed: %s", e)
    _complete_agent_run(
        thread_id=thread_id,
        success=success,
        result_text=result_text,
        tool_calls=tool_calls,
        duration_seconds=duration_seconds,
        output_json=extract_structured_report(result_text or ""),
        sdk_session_id=sdk_session_id,
        tool_calls_count=tool_calls_count,
        run_status=run_status,
        error_message=error_message,
    )


# Durable session store for SDK resume. Defaults to a path that compose/Helm
# back with a persistent volume; falls back to the SDK default if unset.
os.environ.setdefault("CLAUDE_CONFIG_DIR", "/data/agent-sessions")

# ---------------------------------------------------------------------------
# Agent run persistence helpers (best-effort; never raise)
# ---------------------------------------------------------------------------

_CONFIG_SERVICE_URL = os.getenv("CONFIG_SERVICE_URL", "http://config-service:8080")
_INTERNAL_HEADERS = {"X-Internal-Service": "sre-agent"}
_ORG_ID = os.getenv("OPENSRE_TENANT_ID", "local")
_TEAM_NODE_ID = os.getenv("OPENSRE_TEAM_ID", "default")


def _resolve_team_identity(token: str) -> tuple[str, str]:
    """Resolve org_id and team_node_id from config-service auth/me; env fallback on failure."""
    try:
        resp = httpx.get(
            f"{_CONFIG_SERVICE_URL}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        resp.raise_for_status()
        data = resp.json()
        org_id = (data.get("org_id") or "").strip() or _ORG_ID
        team_node_id = (data.get("team_node_id") or "").strip() or _TEAM_NODE_ID
        return org_id, team_node_id
    except Exception as e:
        logger.warning("[AUTH] resolve_team_identity failed, using env fallback: %s", e)
        return _ORG_ID, _TEAM_NODE_ID


def _thread_tenancy(thread_id: str) -> tuple[str, str]:
    """Per-thread org/team from investigate token; env fallback if unset."""
    return _team_identity_by_thread.get(thread_id, (_ORG_ID, _TEAM_NODE_ID))


def _tenancy_from_request(request: Request) -> tuple[str, str]:
    """Resolve tenancy from request Authorization / X-OpenSRE-Team-Token; env fallback."""
    token = _extract_team_token(request)
    if token:
        return _resolve_team_identity(token)
    return _ORG_ID, _TEAM_NODE_ID


def _create_agent_run(
    thread_id: str, prompt: str, agent_name: str = "sre-agent"
) -> Optional[str]:
    """POST to config-service to create an agent run record. Returns run_id or None."""
    org_id, team_node_id = _thread_tenancy(thread_id)
    try:
        run_id = uuid.uuid4().hex
        body = {
            "run_id": run_id,
            "org_id": org_id,
            "team_node_id": team_node_id,
            "correlation_id": thread_id,
            "trigger_source": "web_ui",
            "trigger_actor": None,
            "trigger_message": prompt,
            "trigger_channel_id": None,
            "agent_name": agent_name,
            "metadata": None,
        }
        resp = httpx.post(
            f"{_CONFIG_SERVICE_URL}/api/v1/internal/agent-runs",
            json=body,
            headers=_INTERNAL_HEADERS,
            timeout=5.0,
        )
        resp.raise_for_status()
        logger.info(f"[RUNS] Created agent run {run_id} for thread {thread_id}")
        return run_id
    except Exception as e:
        logger.warning(f"[RUNS] create_agent_run failed (non-fatal): {e}")
        return None


def _complete_agent_run(
    thread_id: str,
    success: bool,
    result_text: str,
    tool_calls: list,
    duration_seconds: Optional[float] = None,
    output_json: Optional[dict] = None,
    sdk_session_id: Optional[str] = None,
    tool_calls_count: Optional[int] = None,
    run_status: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """PATCH config-service to mark an agent run complete. No-op if no run_id on record."""
    run_id = _run_id_by_thread.pop(thread_id, None)
    if not run_id:
        return
    try:
        # Prefer the persisted-row count (one per tool_end event) when provided;
        # fall back to len(tool_calls) only for callers that don't pass it.
        effective_count = (
            tool_calls_count if tool_calls_count is not None else len(tool_calls or [])
        )
        if run_status == "interrupted":
            status = "interrupted"
        elif run_status == "timeout":
            status = "timeout"
        else:
            status = "completed" if success else "failed"
        body = {
            "status": status,
            "duration_seconds": (
                duration_seconds if duration_seconds is not None else 0.0
            ),
            "tool_calls_count": effective_count,
            "output_summary": result_text or None,  # full, untruncated
            "output_json": output_json,  # structured report
            "error_message": error_message,
            "confidence": None,
            "thoughts": None,  # thoughts persisted incrementally (Task 3)
            "sdk_session_id": sdk_session_id,  # for durable resume
        }
        resp = httpx.patch(
            f"{_CONFIG_SERVICE_URL}/api/v1/internal/agent-runs/{run_id}",
            json=body,
            headers=_INTERNAL_HEADERS,
            timeout=5.0,
        )
        resp.raise_for_status()
        logger.info(f"[RUNS] Completed agent run {run_id} (success={success})")
    except Exception as e:
        logger.warning(f"[RUNS] complete_agent_run {run_id} failed (non-fatal): {e}")


def _persist_tool_call(run_id: str, tc: dict) -> None:
    """Best-effort POST of a single completed tool call to config-service."""
    try:
        resp = httpx.post(
            f"{_CONFIG_SERVICE_URL}/api/v1/internal/agent-runs/{run_id}/tool-calls",
            json={"run_id": run_id, "tool_calls": [tc]},
            headers=_INTERNAL_HEADERS,
            timeout=5.0,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"[RUNS] persist_tool_call {run_id} failed (non-fatal): {e}")


def _tool_call_record(
    data: dict,
    started: Optional[dict],
    root_agent: str,
    task_agents: dict,
    fallback_seq: int,
) -> dict:
    """Build a persistable tool-call record from a tool_end event + its captured tool_start.

    Attribution (agent_name/parent_agent/depth/agent_id) comes directly from the
    SDK-hook-derived fields on `data` (agent_type/parent_agent_type/depth/
    agent_id — see events.py), not from message-stream parent_tool_use_id
    parsing. This correctly attributes grandchild tool calls to their real
    subagent parent at any nesting depth. `task_agents` is now unused here but
    kept as a parameter for call-site compatibility with the SSE consumer loop.

    `started` is the dict stashed at tool_start (seq, t, input, name); it may be
    None if the matching start wasn't seen. `started_at` is ALWAYS set
    (config-service's agent_tool_calls.started_at is NOT NULL), and `tool_input`
    falls back to the value captured at tool_start (tool_end events don't carry
    input), so historical DB replay shows the same input/output as the live
    stream.
    """
    started = started or {}
    depth = data.get("depth", 0)
    agent_name = data.get("agent_type") or root_agent
    # depth 0 == root agent's own call -> no parent. Otherwise the real parent
    # agent type (e.g. "investigation" for a grandchild under it), falling back
    # to root_agent if the hook somehow didn't populate it.
    if depth == 0:
        parent_agent = None
    else:
        parent_agent = data.get("parent_agent_type") or root_agent
    start_t = started.get("t")
    started_at = datetime.datetime.fromtimestamp(
        start_t if start_t is not None else time.time(), datetime.timezone.utc
    ).isoformat()
    tool_name = data.get("name") or started.get("name") or "unknown"
    tool_input = data.get("input") or started.get("input")
    tool_output = data.get("output") or data.get("summary")
    error_message = data.get("error")
    tool_output, error_message = sanitize_tool_end_payload(
        tool_name, tool_input, tool_output, error_message
    )
    return {
        "id": data.get("tool_use_id") or f"tool-{fallback_seq}",
        "tool_name": tool_name,
        "agent_name": agent_name,
        "parent_agent": parent_agent,
        "agent_id": data.get("agent_id"),
        "parent_agent_id": data.get("parent_agent_id"),
        "depth": depth,
        "tool_input": tool_input,
        "tool_output": tool_output,
        "started_at": started_at,
        "duration_ms": (
            int((time.time() - start_t) * 1000) if start_t is not None else None
        ),
        "status": "success" if data.get("success", True) else "error",
        "error_message": error_message,
        "sequence_number": started.get("seq", fallback_seq),
    }


def _agent_for(
    task_agents: dict, root_agent: str, parent_tool_use_id: Optional[str]
) -> dict:
    """Resolve the agent attribution (type/depth/invocation ids) for a "thought" event.

    `task_agents` maps a dispatching Task/Agent tool's tool_use_id to the subagent it
    spawned (populated at tool_start — see agent_background_task). `parent_tool_use_id`
    is the SDK-reported parent_tool_use_id on the thought event; when absent, or when it
    doesn't match anything in `task_agents` (e.g. a stale/unknown id), this falls back to
    attributing the thought to the root agent at depth 0.
    """
    root_info = {
        "agent_type": root_agent,
        "depth": 0,
        "invocation_id": None,
        "parent_invocation_id": None,
    }
    if not parent_tool_use_id:
        return root_info
    return task_agents.get(parent_tool_use_id, root_info)


def _flush_thoughts(run_id: str, thoughts: list) -> None:
    """Best-effort PUT to append thoughts to a running agent run."""
    if not thoughts:
        return
    try:
        resp = httpx.put(
            f"{_CONFIG_SERVICE_URL}/api/v1/internal/agent-runs/{run_id}/thoughts",
            json={"thoughts": thoughts},
            headers=_INTERNAL_HEADERS,
            timeout=5.0,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"[RUNS] flush_thoughts {run_id} failed (non-fatal): {e}")


# ---------------------------------------------------------------------------
# File proxy: token -> download info mapping
_file_download_tokens: Dict[str, dict] = {}
_FILE_TOKEN_TTL_SECONDS = 3600  # 1 hour

import asyncio

# Thread ID -> background task mapping
_background_tasks: Dict[str, asyncio.Task] = {}
_message_queues: Dict[str, asyncio.Queue] = {}  # Queue for sending prompts
_response_queues: Dict[str, asyncio.Queue] = {}  # Queue for receiving events
# Per-thread team token from Authorization header (multi-user pilot)
_team_token_by_thread: Dict[str, str] = {}
# Per-thread resolved org/team from auth/me (agent runs + episode finalize)
_team_identity_by_thread: Dict[str, tuple[str, str]] = {}
# Thread ID -> agent run ID (populated at run start; consumed at finalize)
_run_id_by_thread: Dict[str, str] = {}
_active_sessions: Dict[str, object] = (
    {}
)  # Thread ID -> agent session (for interrupt/answer)

app = FastAPI(
    title="OpenSRE Investigation Server (Simple Mode)",
    description="AI SRE agent for incident investigation - in-process mode (no sandboxes)",
    version="0.3.0",
)


@app.on_event("startup")
async def _bootstrap_memory_schema():
    try:
        _il.ensure_memory_schema()
    except Exception as e:
        logger.error("[MEMORY] schema bootstrap failed: %s", e)


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
    resume_session_id: Optional[str] = None


class InterruptRequest(BaseModel):
    thread_id: str


class AnswerRequest(BaseModel):
    thread_id: str
    answers: Dict[str, str]


class QueueMessageRequest(BaseModel):
    text: str


class QueueMessageResponse(BaseModel):
    queued: bool = True
    pending_count: int


@app.get("/")
async def root():
    return {
        "service": "OpenSRE Investigation Server",
        "mode": "simple",
        "version": "0.3.0",
        "warning": "No isolation - for local testing only",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "mode": "simple",
        "active_sessions": len(_background_tasks),
        "interruptible_sessions": len(_active_sessions),
    }


@app.get("/threads/{thread_id}/active")
async def thread_active(thread_id: str):
    """Whether an in-process background session can accept follow-up messages."""
    session = _active_sessions.get(thread_id)
    return {
        "active": thread_id in _background_tasks,
        "sdk_session_id": getattr(session, "session_id", None) if session else None,
    }


def _extract_team_token(request: Request) -> Optional[str]:
    """Parse per-request team token from Authorization or X-OpenSRE-Team-Token."""
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return token
    header_token = request.headers.get("X-OpenSRE-Team-Token")
    if header_token:
        return header_token.strip() or None
    return None


async def _ensure_background_task(
    thread_id: str,
    resume_session_id: Optional[str] = None,
) -> None:
    """Start the per-thread background agent task if not already running."""
    if thread_id in _background_tasks:
        return
    logger.info(f"Creating background task for thread {thread_id}")
    _message_queues[thread_id] = asyncio.Queue()
    _response_queues[thread_id] = asyncio.Queue()
    task = asyncio.create_task(
        agent_background_task(thread_id, resume_session_id=resume_session_id)
    )
    _background_tasks[thread_id] = task
    # Give the task a moment to start before the first message is queued.
    await asyncio.sleep(0.1)


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


async def agent_background_task(
    thread_id: str, resume_session_id: Optional[str] = None
):
    """
    Background task that keeps ClaudeSDKClient alive for multi-turn conversations.
    Processes messages from queue and sends responses back.
    """

    from agent import InteractiveAgentSession

    logger.info(f"[BG] Starting background agent task for thread {thread_id}")

    # Per-request team token overrides static env for config-service auth.
    prev_team_token = os.environ.get("TEAM_TOKEN")
    thread_token = _team_token_by_thread.get(thread_id)
    if thread_token:
        os.environ["TEAM_TOKEN"] = thread_token

    # Optionally load team config from config-service
    team_config = None
    if os.getenv("CONFIG_SERVICE_URL"):
        try:
            from config import load_team_config

            team_config = load_team_config()
            logger.info(
                f"[BG] Loaded team config: {len(team_config.agents)} agents, "
                f"{sum(len(s.content) for s in (team_config.team_context or []))} chars team context"
            )
        except Exception as e:
            logger.warning(f"[BG] Failed to load team config (continuing without): {e}")

    session = InteractiveAgentSession(
        thread_id=thread_id, team_config=team_config, resume=resume_session_id
    )
    await session.start()
    logger.info(f"[BG] Session started for thread {thread_id}")
    _active_sessions[thread_id] = session

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
            original_prompt = message.get("original_prompt") or prompt
            images = message.get("images")
            logger.info(
                f"[BG] Processing message for thread {thread_id}: {prompt[:50]}..."
            )
            if images:
                logger.info(f"[BG] Including {len(images)} image(s) in message")

            # Best-effort: create agent run record in config-service
            _agent_name = "sre-agent"
            try:
                from config import get_root_agent_config

                _ra = get_root_agent_config(team_config) if team_config else None
                if _ra and getattr(_ra, "name", None):
                    _agent_name = _ra.name
            except Exception:
                _agent_name = "sre-agent"
            _rid = _create_agent_run(
                thread_id=thread_id, prompt=original_prompt, agent_name=_agent_name
            )
            if _rid:
                _run_id_by_thread[thread_id] = _rid
                await response_queue.put(
                    {
                        "event": "run_started",
                        "data": {"run_id": _rid, "agent": _agent_name},
                    }
                )

            run_tool_calls: list = []
            run_result_text: str = ""
            run_success: bool = True
            run_status: Optional[str] = None
            run_error_message: Optional[str] = None
            run_start = time.time()

            seq = 0  # shared ordering across thoughts + tools
            task_agents: dict = {}  # Task tool_use_id -> subagent_type
            tool_started: dict = {}  # tool_use_id -> {seq, started_at(float)}
            thought_buffer: list = []
            root_agent = _agent_name
            # Count of tool calls actually persisted to config-service (one per
            # tool_end event with a run_id). Used for the final tool_calls_count
            # on the completion PATCH, so it matches the real agent_tool_calls
            # row count instead of the raw SSE-event count (which double-counts
            # tool_start+tool_end and includes thoughts).
            persisted_tool_call_count = 0

            event_count = 0
            async for event in session.execute(prompt, images=images):
                event_count += 1
                event_type = event.type
                data = event.data if isinstance(event.data, dict) else {}

                _collect_tool_call(run_tool_calls, {"type": event_type, "data": data})

                if event_type == "thought":
                    text = (data.get("text") or "").strip()
                    if text and text != "(no content)":
                        agent_info = _agent_for(
                            task_agents, root_agent, data.get("parent_tool_use_id")
                        )
                        thought_buffer.append(
                            {
                                "text": text,
                                "ts": datetime.datetime.now(
                                    datetime.timezone.utc
                                ).isoformat(),
                                "seq": seq,
                                "agent": agent_info["agent_type"],
                                "depth": agent_info["depth"],
                                "agentId": agent_info["invocation_id"],
                                "parentAgentId": agent_info["parent_invocation_id"],
                            }
                        )
                        seq += 1
                        if _rid:
                            _flush_thoughts(_rid, thought_buffer)
                            thought_buffer = []

                elif event_type == "tool_start":
                    tuid = data.get("tool_use_id") or f"tool-{seq}"
                    if data.get("name") in ("Task", "Agent") and data.get(
                        "subagent_type"
                    ):
                        # The dispatching call's own attribution (data["depth"]/["agent_id"])
                        # tells us the NEW subagent's depth (+1) and parent invocation id.
                        # invocation_id for the new subagent is this Task/Agent call's own
                        # tool_use_id (tuid) — stable, matches agent.py's registry (Task 1).
                        task_agents[tuid] = {
                            "agent_type": data["subagent_type"],
                            "depth": data.get("depth", 0) + 1,
                            "invocation_id": tuid,
                            "parent_invocation_id": data.get("agent_id"),
                        }
                    tool_started[tuid] = {
                        "seq": seq,
                        "t": time.time(),
                        "input": data.get("input"),
                        "name": data.get("name"),
                    }
                    seq += 1

                elif event_type == "tool_end" and _rid:
                    tuid = data.get("tool_use_id")
                    started = tool_started.pop(tuid, None) if tuid else None
                    _persist_tool_call(
                        _rid,
                        _tool_call_record(data, started, root_agent, task_agents, seq),
                    )
                    persisted_tool_call_count += 1

                if event_type == "result":
                    run_result_text = data.get("text", "")
                    run_success = data.get("success", True)
                    if getattr(session, "_was_interrupted", False):
                        run_status = "interrupted"
                        data = {
                            **data,
                            "subtype": "interrupted",
                            "success": True,
                            "text": run_result_text
                            or "Task interrupted. Send a new message to continue.",
                        }
                    elif data.get("subtype") == "interrupted":
                        run_status = "interrupted"

                elif event_type == "error":
                    msg = (data.get("message") or "").strip()
                    run_success = False
                    run_error_message = msg or "Investigation failed"
                    if "time limit" in msg.lower():
                        run_status = "timeout"

                await response_queue.put({"event": event_type, "data": data})

            if _rid and thought_buffer:
                _flush_thoughts(_rid, thought_buffer)

            run_duration = time.time() - run_start
            finalize_investigation(
                thread_id=thread_id,
                prompt=prompt,
                result_text=run_result_text,
                success=run_success,
                tool_calls=run_tool_calls,
                duration_seconds=run_duration,
                sdk_session_id=session.session_id,
                tool_calls_count=persisted_tool_call_count,
                run_status=run_status,
                error_message=run_error_message,
            )
            await response_queue.put(None)
            logger.info(
                f"[BG] Completed message processing. Total events: {event_count}"
            )

    except Exception as e:
        logger.error(
            f"[BG] Background task failed for thread {thread_id}: {e}", exc_info=True
        )
        # Finalize any in-flight run as failed so it doesn't hang in "running".
        _complete_agent_run(
            thread_id=thread_id,
            success=False,
            result_text=f"Investigation failed: {e}",
            tool_calls=[],
            duration_seconds=0.0,
        )
        await response_queue.put({"error": str(e)})
    finally:
        if thread_token:
            if prev_team_token is None:
                os.environ.pop("TEAM_TOKEN", None)
            else:
                os.environ["TEAM_TOKEN"] = prev_team_token
        _active_sessions.pop(thread_id, None)
        # Cleanup
        if session.client:
            await session.cleanup()
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


async def create_investigation_stream(
    thread_id: str,
    prompt: str,
    is_new: bool,
    images: Optional[List[dict]] = None,
    file_downloads: Optional[List[dict]] = None,
    resume_session_id: Optional[str] = None,
):
    """
    Create SSE stream by communicating with background agent task.
    """
    import datetime
    import json

    try:
        # Create background task if needed
        await _ensure_background_task(thread_id, resume_session_id=resume_session_id)

        # Download file attachments directly (no sandbox, so download in-process)
        if file_downloads:
            _download_file_attachments(file_downloads, thread_id)

        # Send message to background task
        message_queue = _message_queues[thread_id]
        response_queue = _response_queues[thread_id]

        logger.info(f"Sending message to background task for thread {thread_id}")
        await message_queue.put(
            {"prompt": prompt, "original_prompt": prompt, "images": images}
        )

        # Stream responses
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

            # Task 6: attach structured_report to result events when present
            if event_type == "result" and isinstance(data, dict):
                result_text_for_report = data.get("text", "")
                structured = extract_structured_report(result_text_for_report)
                if structured is not None:
                    data = {**data, "structured_report": structured}

            # Emit SSE event in same format as sandbox mode
            # Format: data: {"type": "...", "data": {...}, "thread_id": "...", "timestamp": "..."}
            logger.info(f"Yielding event #{event_count}: {event_type}")
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
async def investigate(investigate_request: InvestigateRequest, http_request: Request):
    """
    Start or continue an investigation.

    Runs agent in-process (no sandbox isolation).
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(500, "ANTHROPIC_API_KEY not configured")

    thread_id = investigate_request.thread_id or f"thread-{uuid.uuid4().hex[:8]}"
    is_new = thread_id not in _background_tasks

    team_token = _extract_team_token(http_request)
    if team_token:
        _team_token_by_thread[thread_id] = team_token
        _team_identity_by_thread[thread_id] = _resolve_team_identity(team_token)

    print(f"🔍 Investigation: thread={thread_id}, new={is_new}")

    if is_new:
        await _ensure_background_task(
            thread_id, resume_session_id=investigate_request.resume_session_id
        )

    # Handle file attachments
    file_downloads = None
    if investigate_request.file_attachments:
        file_downloads = []
        proxy_base_url = _get_proxy_base_url()

        for attachment in investigate_request.file_attachments:
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
    if investigate_request.images:
        images = [
            {
                "type": img.type,
                "media_type": img.media_type,
                "data": img.data,
                "filename": img.filename,
            }
            for img in investigate_request.images
        ]

    stream = create_investigation_stream(
        thread_id,
        investigate_request.prompt,
        is_new,
        images,
        file_downloads,
        resume_session_id=investigate_request.resume_session_id,
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

    Drains session.interrupt() so the SDK stop signal is sent; the background
    task's execute() loop emits the interrupted result event to the active
    /investigate SSE stream.
    """
    if request.thread_id not in _active_sessions:
        raise HTTPException(404, f"No active session for thread {request.thread_id}")

    session = _active_sessions[request.thread_id]
    logger.info(f"Interrupting thread {request.thread_id}")

    try:
        async for _event in session.interrupt():
            pass
    except Exception as e:
        logger.error(f"Interrupt failed: {e}", exc_info=True)
        raise HTTPException(500, f"Interrupt failed: {e}") from e

    return {"status": "ok", "thread_id": request.thread_id}


@app.post("/threads/{thread_id}/queue-message", response_model=QueueMessageResponse)
async def queue_message(thread_id: str, body: QueueMessageRequest):
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(400, "text is required")

    session = _active_sessions.get(thread_id)
    if session is None:
        raise HTTPException(404, f"No active session for thread {thread_id}")

    if not getattr(session, "is_running", False):
        raise HTTPException(
            409, "Investigation is not executing; send a normal message instead"
        )

    try:
        pending_count = session.enqueue_message(text)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    response_queue = _response_queues.get(thread_id)
    if response_queue is not None:
        from events import message_queued_event

        ev = message_queued_event(thread_id, pending_count=pending_count)
        await response_queue.put({"event": ev.type, "data": ev.data})

    return QueueMessageResponse(pending_count=pending_count)


@app.post("/answer")
async def answer(request: AnswerRequest):
    """
    Send answer to agent's AskUserQuestion.
    """
    if request.thread_id not in _active_sessions:
        raise HTTPException(404, f"No active session for thread {request.thread_id}")

    print(f"📬 Forwarding answer to thread {request.thread_id}")

    _active_sessions[request.thread_id]
    # TODO: Implement answer forwarding when InteractiveAgentSession supports it

    return {"status": "ok", "thread_id": request.thread_id}


# ---------------------------------------------------------------------------
# Memory endpoints (Neo4j-backed)
# ---------------------------------------------------------------------------

_mem_retriever = None


def _memret():
    global _mem_retriever
    if _mem_retriever is None:
        _mem_retriever = EpisodeRetriever()
    return _mem_retriever


def _episode_row(r: dict) -> dict:
    import json as _json

    e = dict(r["e"])
    return {
        "episode_id": e.get("episode_id"),
        "correlation_id": e.get("correlation_id"),
        "agent_run_id": e.get("agent_run_id"),
        "issue_type": e.get("issue_type"),
        "issue_description": e.get("issue_description"),
        "severity": e.get("severity"),
        "components": _json.loads(e.get("components_json", "[]")),
        "services": r.get("services", []),
        "resolved": e.get("resolved"),
        "root_cause": e.get("root_cause"),
        "summary": e.get("summary"),
        "effectiveness_score": e.get("effectiveness_score"),
        "skills_used": e.get("skills_used", []),
        "created_at": e.get("created_at"),
        "updated_at": e.get("updated_at"),
    }


@app.get("/memory/episodes")
async def memory_episodes(request: Request, limit: int = 50):
    org_id, team_node_id = _tenancy_from_request(request)
    q = (
        "MATCH (e:Episode {org_id:$org, team_node_id:$team}) "
        "OPTIONAL MATCH (e)-[:AFFECTED]->(s:Service) "
        "RETURN e AS e, collect(s.name) AS services "
        "ORDER BY e.updated_at DESC LIMIT $limit"
    )
    with get_driver().session(database=NEO4J_DATABASE) as sess:
        rows = sess.run(q, org=org_id, team=team_node_id, limit=limit).data()
    return {"success": True, "result": {"episodes": [_episode_row(r) for r in rows]}}


@app.get("/memory/stats")
async def memory_stats(request: Request):
    org_id, team_node_id = _tenancy_from_request(request)
    q = (
        "MATCH (e:Episode {org_id:$org, team_node_id:$team}) "
        "RETURN count(e) AS total, "
        "sum(CASE WHEN e.resolved THEN 1 ELSE 0 END) AS resolved, "
        "collect(DISTINCT e.issue_type) AS issue_types"
    )
    with get_driver().session(database=NEO4J_DATABASE) as sess:
        rec = sess.run(q, org=org_id, team=team_node_id).single()
    total = rec["total"] if rec else 0
    return {
        "success": True,
        "result": {
            "total_episodes": total,
            "resolved": rec["resolved"] if rec else 0,
            "issue_types": rec["issue_types"] if rec else [],
        },
    }


def _overview_episode_row(r: dict) -> dict:
    e = dict(r["e"])
    services = [s for s in (r.get("services") or []) if s]
    return {
        "episode_id": e.get("episode_id"),
        "issue_type": e.get("issue_type"),
        "issue_description": e.get("issue_description"),
        "resolved": e.get("resolved"),
        "summary": e.get("summary"),
        "services": services,
        "updated_at": e.get("updated_at") or e.get("created_at"),
    }


def _overview_strategy_row(r: dict) -> dict:
    st = dict(r["st"])
    return {
        "strategy_id": st.get("strategy_id"),
        "issue_type": st.get("issue_type"),
        "component_key": st.get("component_key"),
    }


@app.get("/memory/overview")
async def memory_overview(request: Request):
    """Aggregated dashboard data for the Memory overview tab."""
    org_id, team_node_id = _tenancy_from_request(request)
    week_ago = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
    ).isoformat()

    with get_driver().session(database=NEO4J_DATABASE) as sess:
        stats_rec = sess.run(
            """
            MATCH (e:Episode {org_id:$org, team_node_id:$team})
            RETURN count(e) AS total,
                   sum(CASE WHEN e.resolved THEN 1 ELSE 0 END) AS resolved
            """,
            org=org_id,
            team=team_node_id,
        ).single()

        issue_type_rows = sess.run(
            """
            MATCH (e:Episode {org_id:$org, team_node_id:$team})
            WHERE e.issue_type IS NOT NULL AND e.issue_type <> ''
            RETURN e.issue_type AS issue_type, count(*) AS count
            ORDER BY count DESC
            """,
            org=org_id,
            team=team_node_id,
        ).data()

        recent_rows = sess.run(
            """
            MATCH (e:Episode {org_id:$org, team_node_id:$team})
            OPTIONAL MATCH (e)-[:AFFECTED]->(s:Service)
            RETURN e AS e, collect(s.name) AS services
            ORDER BY coalesce(e.updated_at, e.created_at) DESC
            LIMIT 5
            """,
            org=org_id,
            team=team_node_id,
        ).data()

        week_rec = sess.run(
            """
            MATCH (e:Episode {org_id:$org, team_node_id:$team})
            WHERE coalesce(e.updated_at, e.created_at) >= $week_ago
            RETURN count(e) AS count
            """,
            org=org_id,
            team=team_node_id,
            week_ago=week_ago,
        ).single()

        strat_rec = sess.run(
            """
            MATCH (st:Strategy {org_id:$org, team_node_id:$team})
            RETURN count(st) AS strategy_count
            """,
            org=org_id,
            team=team_node_id,
        ).single()

        latest_strats = sess.run(
            """
            MATCH (st:Strategy {org_id:$org, team_node_id:$team})
            RETURN st AS st
            ORDER BY coalesce(st.episode_count, 0) DESC,
                     coalesce(st.generated_at, st.updated_at) DESC
            LIMIT 2
            """,
            org=org_id,
            team=team_node_id,
        ).data()

    total = stats_rec["total"] if stats_rec else 0
    resolved = stats_rec["resolved"] if stats_rec else 0
    unresolved = total - (resolved or 0)
    resolution_rate = round((resolved / total) * 100) if total else 0

    return {
        "success": True,
        "result": {
            "total_episodes": total,
            "resolved": resolved,
            "unresolved": unresolved,
            "resolution_rate": resolution_rate,
            "episodes_this_week": week_rec["count"] if week_rec else 0,
            "issue_type_counts": [
                {"issue_type": r["issue_type"], "count": r["count"]}
                for r in issue_type_rows
            ],
            "recent_episodes": [_overview_episode_row(r) for r in recent_rows],
            "strategy_count": strat_rec["strategy_count"] if strat_rec else 0,
            "latest_strategies": [_overview_strategy_row(r) for r in latest_strats],
        },
    }


@app.post("/memory/search")
async def memory_search(request: Request, payload: dict):
    org_id, team_node_id = _tenancy_from_request(request)
    query = payload.get("query") or payload.get("prompt") or ""
    hits = _memret().search(
        query, org_id=org_id, team_node_id=team_node_id, k=payload.get("limit", 5)
    )
    return {
        "success": True,
        "result": {
            "episodes": [
                {
                    **h.episode.model_dump(exclude={"embedding"}),
                    "services": h.services,
                    "score": h.score,
                }
                for h in hits
            ]
        },
    }


@app.get("/memory/strategies")
async def memory_strategies(request: Request):
    org_id, team_node_id = _tenancy_from_request(request)
    q = (
        "MATCH (st:Strategy {org_id:$org, team_node_id:$team}) "
        "RETURN st AS st ORDER BY st.generated_at DESC"
    )
    with get_driver().session(database=NEO4J_DATABASE) as sess:
        rows = sess.run(q, org=org_id, team=team_node_id).data()
    return {"success": True, "result": {"strategies": [dict(r["st"]) for r in rows]}}


@app.patch("/memory/strategies/{strategy_id}")
async def update_memory_strategy(request: Request, strategy_id: str, payload: dict):
    org_id, team_node_id = _tenancy_from_request(request)
    strategy_text = (payload.get("strategy_text") or "").strip()
    if not strategy_text:
        raise HTTPException(status_code=400, detail="strategy_text is required")

    updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    store = EpisodeStore()
    ok = store.update_strategy_text(
        strategy_id,
        strategy_text,
        org_id=org_id,
        team_node_id=team_node_id,
        updated_at=updated_at,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="strategy not found")

    return {
        "success": True,
        "result": {
            "strategy_id": strategy_id,
            "strategy_text": strategy_text,
            "updated_at": updated_at,
            "manually_edited": True,
        },
    }


@app.delete("/memory/strategies/{strategy_id}")
async def delete_memory_strategy(request: Request, strategy_id: str):
    org_id, team_node_id = _tenancy_from_request(request)
    store = EpisodeStore()
    ok = store.delete_strategy(
        strategy_id,
        org_id=org_id,
        team_node_id=team_node_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="strategy not found")

    return {"success": True, "result": {"strategy_id": strategy_id}}


if __name__ == "__main__":
    import uvicorn

    print("=" * 70)
    print("⚠️  WARNING: Running in SIMPLE MODE (no sandboxes)")
    print("=" * 70)
    print()
    print("This mode runs the agent directly in the server process.")
    print("Use only for local testing with trusted prompts.")
    print()
    print("For production deployment, use server.py with K8s sandboxes.")
    print("=" * 70)
    print()

    uvicorn.run(app, host="0.0.0.0", port=8000)
