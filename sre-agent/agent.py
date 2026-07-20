#!/usr/bin/env python3
"""
OpenSRE AI SRE Agent

Provides InteractiveAgentSession for persistent LLM sessions with interrupt support.
Used by sandbox_server.py for production deployments.

Architecture (Skills + Scripts + Subagents):
- Skills: Progressive disclosure of knowledge in .claude/skills/
- Scripts: API integrations executed via Bash (output only in context)
- Subagents: Context isolation for deep-dive work (log-analyst, k8s-debugger, remediator)

No MCP tools - all integrations use skills with scripts for:
- Minimal context bloat (skill metadata ~100 tokens, loaded on-demand)
- Progressive disclosure (syntax/methodology loaded when needed)
- Clean main context (subagent output stays isolated)

LLM Provider:
- Claude Agent SDK with direct Anthropic access (ANTHROPIC_API_KEY).
- Optional multi-provider routing via a proxy: point
  ANTHROPIC_BASE_URL at the proxy to use OpenRouter/other providers.

Observability:
- Configurable backend via OBSERVABILITY_BACKEND env var: "laminar", "langfuse", or "none"
- Laminar: Sessions grouped by thread_id, metadata for filtering, outcome tags
- Langfuse: Trace/span/generation tracking with Claude SDK callback integration
- Backend selection is a deployment config (Helm values), not per-tenant
"""

import asyncio
import base64
import json
import logging
import mimetypes
import os
import re
import time
from pathlib import Path
from typing import AsyncIterator

# Claude SDK imports
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookMatcher,
    ResultMessage,
    TaskNotificationMessage,
    TaskProgressMessage,
    TaskStartedMessage,
    TextBlock,
)
from dotenv import load_dotenv
from events import (
    StreamEvent,
    background_waiting_event,
    error_event,
    message_queued_event,
    question_event,
    result_event,
    task_notification_event,
    task_started_event,
    thought_event,
    tool_end_event,
    tool_start_event,
)
from message_queue import MESSAGE_QUEUE_DEBOUNCE_SECONDS, format_merged_messages
from tool_output_sanitize import sanitize_tool_end_payload

# Max image size to embed (5MB)
MAX_IMAGE_SIZE = 5 * 1024 * 1024

# Max file size to share (1GB - Slack limit for all plans)
MAX_FILE_SIZE = 1 * 1024 * 1024 * 1024  # 1 GB

# Max number of files to share per message (Slack best practice)
MAX_FILES_PER_MESSAGE = 10


def _serialize_tool_output(tool_response) -> str | None:
    """Normalize PostToolUse tool_response for SSE + DB persistence.

    The SDK may pass dict/list objects. str(dict) produces Python repr (single
    quotes), which breaks JSON.parse in the web UI todo reducer. Emit JSON for
    structured values; pass strings through unchanged.
    """
    if tool_response is None:
        return None
    if isinstance(tool_response, str):
        return tool_response
    if isinstance(tool_response, (dict, list)):
        return json.dumps(tool_response)
    return str(tool_response)


def _extract_images_from_text(text: str) -> tuple[str, list]:
    """
    Extract local image references from markdown text.

    Finds markdown image syntax: ![alt](path)
    where path is a local file (starts with ./, /, /workspace/, or attachments/)

    Args:
        text: Markdown text that may contain image references

    Returns:
        Tuple of (text_with_placeholders, images_list)
        - text stays the same (slack-bot will replace based on path)
        - images_list: [{path, data (base64), media_type, alt}, ...]
    """
    # Match markdown images: ![alt text](path)
    # Path must look local (not http/https)
    pattern = r"!\[([^\]]*)\]\(([^)]+)\)"

    images = []

    for match in re.finditer(pattern, text):
        alt = match.group(1)
        path_str = match.group(2)

        # Skip external URLs
        if path_str.startswith(("http://", "https://", "data:")):
            continue

        # Resolve path — always relative to /workspace
        # Reject absolute paths that don't start with /workspace
        workspace = Path("/workspace")
        if path_str.startswith("./"):
            full_path = workspace / path_str[2:]
        elif path_str.startswith("/workspace/"):
            full_path = Path(path_str)
        elif path_str.startswith("/"):
            # Reject other absolute paths (e.g. /var/run/secrets)
            print(f"⚠️ [IMAGE] Rejecting absolute path: {path_str}")
            continue
        else:
            full_path = workspace / path_str

        # Security: resolve symlinks and verify path is within /workspace
        try:
            resolved = full_path.resolve(strict=False)
            # Use Path containment check (not string prefix) to prevent
            # bypass via paths like /workspacefoo
            if (
                workspace.resolve() not in resolved.parents
                and resolved != workspace.resolve()
            ):
                print(f"⚠️ [IMAGE] Skipping path outside workspace: {path_str}")
                continue
        except Exception:
            continue

        # Check if file exists and is an image
        if not resolved.exists():
            print(f"⚠️ [IMAGE] File not found: {path_str}")
            continue

        # Check size
        file_size = resolved.stat().st_size
        if file_size > MAX_IMAGE_SIZE:
            print(
                f"⚠️ [IMAGE] File too large ({file_size} bytes > {MAX_IMAGE_SIZE}): {path_str}"
            )
            continue

        # Determine media type
        media_type, _ = mimetypes.guess_type(str(resolved))
        if not media_type or not media_type.startswith("image/"):
            print(f"⚠️ [IMAGE] Not an image type ({media_type}): {path_str}")
            continue

        # Read and encode
        try:
            image_data = resolved.read_bytes()
            base64_data = base64.b64encode(image_data).decode("utf-8")

            images.append(
                {
                    "path": path_str,  # Original path from markdown
                    "data": base64_data,
                    "media_type": media_type,
                    "alt": alt or resolved.name,
                }
            )
            print(
                f"✅ [IMAGE] Extracted: {path_str} ({len(image_data)} bytes, {media_type})"
            )

        except Exception as e:
            print(f"⚠️ [IMAGE] Failed to read {path_str}: {e}")
            continue

    return text, images


def _extract_files_from_text(text: str) -> tuple[str, list]:
    """
    Extract local file references from markdown text.

    Finds markdown link syntax: [description](path)
    where path is a local file (NOT an image, NOT a URL)

    Args:
        text: Markdown text that may contain file references

    Returns:
        Tuple of (text, files_list)
        - text stays the same (slack-bot will replace based on path)
        - files_list: [{path, data (base64), media_type, filename, description}, ...]
    """
    # Match markdown links: [text](path)
    # But NOT images which start with !
    # We use negative lookbehind to exclude ![...](...)
    pattern = r"(?<!!)\[([^\]]+)\]\(([^)]+)\)"

    files = []

    # Find all matches first for debugging
    all_matches = list(re.finditer(pattern, text))
    if all_matches:
        print(f"📎 [FILE] Found {len(all_matches)} potential file link(s) in text")
        for m in all_matches:
            print(f"   - [{m.group(1)}]({m.group(2)})")

    # Image extensions to skip (handled by _extract_images_from_text)
    image_extensions = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".svg",
        ".bmp",
        ".ico",
    }

    for match in re.finditer(pattern, text):
        description = match.group(1)
        path_str = match.group(2)

        # Skip external URLs
        if path_str.startswith(("http://", "https://", "mailto:", "tel:", "data:")):
            continue

        # Skip anchor links
        if path_str.startswith("#"):
            continue

        # Resolve path — always relative to /workspace
        # Reject absolute paths that don't start with /workspace
        workspace = Path("/workspace")
        if path_str.startswith("./"):
            full_path = workspace / path_str[2:]
        elif path_str.startswith("/workspace/"):
            full_path = Path(path_str)
        elif path_str.startswith("/"):
            # Reject other absolute paths (e.g. /var/run/secrets, /tmp/sandbox-jwt)
            print(f"⚠️ [FILE] Rejecting absolute path: {path_str}")
            continue
        elif path_str.startswith("attachments/"):
            full_path = workspace / path_str
        else:
            full_path = workspace / path_str

        # Security: resolve symlinks and verify path is within /workspace
        try:
            resolved = full_path.resolve(strict=False)
            # Use Path containment check (not string prefix) to prevent
            # bypass via paths like /workspacefoo
            if (
                workspace.resolve() not in resolved.parents
                and resolved != workspace.resolve()
            ):
                print(f"⚠️ [FILE] Skipping path outside workspace: {path_str}")
                continue
        except Exception:
            continue

        # Check if file exists
        if not resolved.exists():
            print(f"⚠️ [FILE] File not found: {path_str} (resolved to: {resolved})")
            continue

        # Skip directories
        if resolved.is_dir():
            print(f"⚠️ [FILE] Skipping directory: {path_str}")
            continue

        # Skip images (handled separately)
        if resolved.suffix.lower() in image_extensions:
            continue

        # Check size
        file_size = resolved.stat().st_size
        if file_size > MAX_FILE_SIZE:
            print(
                f"⚠️ [FILE] File too large ({file_size} bytes > {MAX_FILE_SIZE}): {path_str}"
            )
            continue

        # Check if we've hit the limit
        if len(files) >= MAX_FILES_PER_MESSAGE:
            print(
                f"⚠️ [FILE] Max files limit reached ({MAX_FILES_PER_MESSAGE}), skipping: {path_str}"
            )
            continue

        # Determine media type
        media_type, _ = mimetypes.guess_type(str(resolved))
        if not media_type:
            media_type = "application/octet-stream"

        # Read and encode
        try:
            file_data = resolved.read_bytes()
            base64_data = base64.b64encode(file_data).decode("utf-8")

            files.append(
                {
                    "path": path_str,  # Original path from markdown
                    "data": base64_data,
                    "media_type": media_type,
                    "filename": resolved.name,
                    "description": description,
                    "size": file_size,
                }
            )
            print(f"✅ [FILE] Extracted: {path_str} ({file_size} bytes, {media_type})")

        except Exception as e:
            print(f"⚠️ [FILE] Failed to read {path_str}: {e}")
            continue

    return text, files


load_dotenv()

# ---------------------------------------------------------------------------
# Observability backend initialization
# ---------------------------------------------------------------------------
# Configured via OBSERVABILITY_BACKEND env var: "laminar" | "langfuse" | "none"
# Falls back to auto-detection for backward compatibility:
#   - LMNR_PROJECT_API_KEY set → laminar
#   - LANGFUSE_PUBLIC_KEY set  → langfuse
#   - neither                  → none
# ---------------------------------------------------------------------------
_observability_backend = "none"
_observability_initialized = False

# Laminar helpers (lazy-imported)
_Laminar = None
_observe = None

# Langfuse helpers (lazy-imported)
_langfuse_client = None


def _detect_observability_backend() -> str:
    """Detect which observability backend to use."""
    backend = os.getenv("OBSERVABILITY_BACKEND", "").lower().strip()
    if backend in ("laminar", "langfuse", "none"):
        return backend
    # Auto-detect from available credentials
    if os.getenv("LMNR_PROJECT_API_KEY"):
        return "laminar"
    if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        return "langfuse"
    return "none"


def init_observability() -> None:
    """Initialize the configured observability backend. Call once at process startup."""
    global _observability_backend, _observability_initialized
    global _Laminar, _observe, _langfuse_client

    if _observability_initialized:
        return

    _observability_backend = _detect_observability_backend()

    if _observability_backend == "laminar":
        try:
            from lmnr import Laminar, observe

            _Laminar = Laminar
            _observe = observe
            Laminar.initialize()
            _observability_initialized = True
            print("[OBSERVABILITY] Laminar initialized (key present)")
        except Exception as e:
            print(f"[OBSERVABILITY] Laminar init failed: {e}")
            _observability_backend = "none"

    elif _observability_backend == "langfuse":
        try:
            from langfuse import Langfuse

            _langfuse_client = Langfuse(
                public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
                secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
                host=os.getenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com"),
            )
            _observability_initialized = True
            print(
                f"[OBSERVABILITY] Langfuse initialized (host: {os.getenv('LANGFUSE_HOST', 'https://us.cloud.langfuse.com')})"
            )
        except Exception as e:
            print(f"[OBSERVABILITY] Langfuse init failed: {e}")
            _observability_backend = "none"

    else:
        print("[OBSERVABILITY] No backend configured")
        _observability_initialized = True


def observability_set_session(thread_id: str, metadata: dict | None = None) -> None:
    """Set session/trace context for the current thread."""
    if _observability_backend == "laminar" and _Laminar:
        _Laminar.set_trace_session_id(thread_id)
        if metadata:
            _Laminar.set_trace_metadata(metadata)
    elif _observability_backend == "langfuse" and _langfuse_client:
        # Langfuse session context is set per-trace at creation time
        pass


def observability_set_tags(tags: list[str]) -> None:
    """Set outcome tags on the current span."""
    if _observability_backend == "laminar" and _Laminar:
        _Laminar.set_span_tags(tags)


def observability_observe():
    """Decorator for tracing a function. Returns identity decorator if backend doesn't support it."""
    if _observability_backend == "laminar" and _observe:
        return _observe()

    # No-op decorator
    def identity(fn):
        return fn

    return identity


# Initialize at import time
init_observability()


def get_environment() -> str:
    """Detect if running in local/dev or production."""
    # Check for explicit env var
    env = os.getenv("ENVIRONMENT")
    if env:
        return env.lower()

    # Auto-detect: Check for K8s namespace
    namespace = os.getenv("SANDBOX_NAMESPACE", os.getenv("NAMESPACE", "default"))
    if namespace == "opensre-prod":
        return "production"
    elif os.getenv("KUBERNETES_SERVICE_HOST"):
        return "staging"  # In K8s but not prod namespace
    else:
        return "local"


def format_investigation_timeout_message(timeout_seconds: int) -> str:
    """User-facing message when AGENT_TIMEOUT_SECONDS is reached."""
    if timeout_seconds >= 3600 and timeout_seconds % 3600 == 0:
        n = timeout_seconds // 3600
        unit = "hour" if n == 1 else "hours"
        limit = f"{n} {unit}"
    elif timeout_seconds >= 60 and timeout_seconds % 60 == 0:
        n = timeout_seconds // 60
        unit = "minute" if n == 1 else "minutes"
        limit = f"{n} {unit}"
    else:
        limit = f"{timeout_seconds} seconds"
    return (
        f"Investigation stopped after {limit} (time limit). "
        "Work may be incomplete — send a follow-up to summarize or continue."
    )


def capture_session_id_from_result(session_id: str | None, message) -> str | None:
    """Replicate ResultMessage session_id capture from execute()."""
    return getattr(message, "session_id", None) or session_id


class TextSegmentBuffer:
    """Buffer assistant TextBlocks into thoughts (pre-tool) vs final result.

    Mid-turn narration is flushed via flush_thought() when a tool is about to
    start. Leftover buffer at ResultMessage becomes result only — never both.
    """

    def __init__(self) -> None:
        self._parts: list[str] = []
        self._tools_seen = False

    @property
    def tools_seen(self) -> bool:
        return self._tools_seen

    def mark_tool(self) -> None:
        self._tools_seen = True

    def append(self, text: str) -> None:
        cleaned = (text or "").strip()
        if not cleaned or cleaned == "(no content)":
            return
        self._parts.append(cleaned)

    def _join_and_clear(self) -> str | None:
        if not self._parts:
            return None
        joined = "\n\n".join(self._parts).strip()
        self._parts.clear()
        return joined or None

    def flush_thought(self) -> str | None:
        return self._join_and_clear()

    def finalize_result(self, fallback: str = "") -> str:
        leftover = self._join_and_clear()
        if leftover:
            return leftover
        return (fallback or "").strip()


class InteractiveAgentSession:
    """
    Manages a persistent ClaudeSDKClient session that supports interrupts.

    Follows Claude SDK best practices:
    - Use connect()/disconnect() for session lifecycle
    - Use query() then receive_response() for each turn
    - Session maintains conversation context across multiple turns

    Each sandbox maintains one session per thread_id.
    """

    # Default tools when no team config overrides
    DEFAULT_TOOLS = [
        "Read",
        "Write",
        "Edit",
        "Bash",
        "Glob",
        "Grep",
        "WebSearch",
        "WebFetch",
        "AskUserQuestion",
        "Task",
        "TaskCreate",
        "TaskUpdate",
        "TaskList",
        "TaskGet",
    ]

    def __init__(self, thread_id: str, team_config=None, resume: str | None = None):
        self.thread_id = thread_id
        self.team_config = team_config
        self.resume = resume
        # Captured from the SDK ResultMessage; persisted so the conversation can
        # be resumed after this process recycles.
        self.session_id: str | None = None

        self.client: ClaudeSDKClient | None = None
        self.is_running: bool = False
        self._was_interrupted: bool = False
        self._pending_messages: list[str] = []
        self._message_event: asyncio.Event = asyncio.Event()
        self._input_closed: bool = False
        self._force_flush: bool = False
        self._pending_consumed_event: asyncio.Event = asyncio.Event()
        self._queued_message_count: int = (
            0  # messages yielded to SDK this turn (for tests)
        )

        # Agent registry built from SDK SubagentStart hooks.
        # Maps SDK agent_id -> {agent_type, parent_agent_id, parent_agent_type, depth}.
        # The root/main thread has no agent_id (None), so it is never stored here;
        # _resolve_agent() handles None as depth 0.
        self._agent_registry: dict = {}
        # Open Task/Agent dispatches awaiting their SubagentStart announcement.
        # Each entry: {tool_use_id, dispatching_agent_id, started_at, ended}.
        # Used to resolve a new subagent's parent via the most-recent-open heuristic.
        self._open_dispatches: list = []
        self._pending_tool_starts: list = []  # Queue of tool_start records to emit
        self._pending_tool_ends: list = []  # Queue of tool_end records to emit
        self._outstanding_background_tasks: set[str] = set()

        # NOTE: The hook callables (_on_pre_tool_use, _on_post_tool_use,
        # _on_subagent_start, _on_subagent_stop) are defined as regular methods
        # below so they exist on instances created via __new__ (the unit tests
        # construct sessions that way, bypassing __init__). They are sync so the
        # tests can call them directly without awaiting. At SDK registration time
        # (options_kwargs.hooks below) they are wrapped in async trampolines
        # because the SDK's HookCallback type requires an Awaitable return.

        # Callback for tool permission requests (handles AskUserQuestion)
        async def can_use_tool_handler(tool_name: str, input_data: dict, context):
            """Handle tool permission requests, including AskUserQuestion."""
            if tool_name == "AskUserQuestion":
                import asyncio
                import logging

                from claude_agent_sdk.types import (
                    PermissionResultAllow,
                    PermissionResultDeny,
                )

                logger = logging.getLogger(__name__)
                questions = input_data.get("questions", [])
                logger.info(
                    f"[AskUserQuestion] Agent asked {len(questions)} question(s)"
                )

                # Store event on session instance (sandbox-local state)
                event = asyncio.Event()
                self._pending_answer_event = event
                self._pending_answer = None

                logger.info("[AskUserQuestion] Waiting up to 60s for answer...")

                # Wait up to 60 seconds for user response
                try:
                    await asyncio.wait_for(event.wait(), timeout=60.0)
                    answer = self._pending_answer

                    # Cleanup
                    delattr(self, "_pending_answer_event")
                    delattr(self, "_pending_answer")

                    logger.info(f"[AskUserQuestion] Received answer: {answer}")
                    return PermissionResultAllow(
                        updated_input={"questions": questions, "answers": answer}
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "[AskUserQuestion] Timeout - continuing without answer"
                    )

                    # Emit timeout event so Slack can update the UI
                    from events import question_timeout_event

                    if hasattr(self, "_pending_events"):
                        self._pending_events.append(
                            question_timeout_event(self.thread_id)
                        )

                    # Cleanup
                    if hasattr(self, "_pending_answer_event"):
                        delattr(self, "_pending_answer_event")
                    if hasattr(self, "_pending_answer"):
                        delattr(self, "_pending_answer")

                    return PermissionResultDeny(
                        message="User did not respond. Continue without this information."
                    )

            # Auto-approve other tools
            from claude_agent_sdk.types import PermissionResultAllow

            return PermissionResultAllow(updated_input=input_data)

        # Import AgentDefinition for subagent configuration
        from claude_agent_sdk import AgentDefinition

        subagents = {}

        # Build options for streaming input mode
        # Determine working directory based on mode
        # - Sandbox mode: Use /app (each sandbox is isolated, has .claude/ skills)
        # - Simple mode: Use per-thread workspace for session persistence
        if os.path.exists("/workspace"):
            # Sandbox mode - use canonical /app directory where .claude/ lives
            cwd = "/app"
        else:
            # Simple mode - use per-thread workspace for multi-turn conversations
            thread_workspace = f"/tmp/sessions/{self.thread_id}"
            os.makedirs(thread_workspace, exist_ok=True)

            # Copy .claude/ skills to thread workspace if it doesn't exist yet
            import shutil

            thread_claude_dir = os.path.join(thread_workspace, ".claude")
            if not os.path.exists(thread_claude_dir):
                source_claude_dir = "/app/.claude"
                if os.path.exists(source_claude_dir):
                    shutil.copytree(source_claude_dir, thread_claude_dir)

                # Skills filtering (team-level): delete disabled skill dirs from
                # this session's copy BEFORE the SDK scans .claude/skills/. Never
                # touches the /app source. Resolution: env > team config.
                if self.team_config:
                    from config import (
                        build_skill_name_map,
                        parse_enabled_skills_env,
                        remove_disabled_skill_dirs,
                        resolve_enabled_skills,
                    )

                    workspace_skills_dir = os.path.join(thread_claude_dir, "skills")
                    name_map = build_skill_name_map(workspace_skills_dir)
                    enabled = resolve_enabled_skills(
                        parse_enabled_skills_env(),
                        self.team_config.skills,
                        name_map,
                    )
                    removed = remove_disabled_skill_dirs(
                        workspace_skills_dir, enabled, name_map
                    )
                    if removed:
                        print(
                            f"🧹 [AGENT] Skills filtered out {len(removed)}: {', '.join(removed)}"
                        )

            cwd = thread_workspace

        # --- Dynamic config from team config service ---
        system_prompt = None
        root_config = None
        if self.team_config:
            from config import (
                build_delegation_addendum,
                get_root_agent_config,
                resolve_agent_tools,
                resolve_model,
                resolve_registered_agents,
            )

            root_config = get_root_agent_config(self.team_config)

            # Set system prompt directly (Method 4 from SDK docs)
            if root_config and root_config.prompt.system:
                system_prompt = root_config.prompt.system
                print(
                    f"📝 [AGENT] System prompt ({len(system_prompt)} chars) "
                    f"from root agent '{root_config.name}'"
                )

            from team_context import render_team_context_block

            ctx_block = (
                render_team_context_block(self.team_config) if self.team_config else ""
            )

            # Build subagents: reachability over sub_agents edges (KI-1 fix).
            # resolve_registered_agents already excludes the root and any agent
            # that is disabled, unreachable, or has no system prompt.
            for name, agent_cfg in resolve_registered_agents(self.team_config).items():
                sub_prompt = agent_cfg.prompt.system or ""
                if ctx_block:
                    sub_prompt = sub_prompt + ctx_block
                subagents[name] = AgentDefinition(
                    description=agent_cfg.prompt.prefix or f"{name} specialist",
                    prompt=sub_prompt,
                    model=resolve_model(agent_cfg.model.name),
                    tools=resolve_agent_tools(agent_cfg.tools),
                )

            # Authoritative delegation list: overrides any stale static
            # sub-agent table in the root prompt.
            if system_prompt and subagents:
                system_prompt = system_prompt + build_delegation_addendum(
                    list(subagents.keys())
                )

            if ctx_block:
                system_prompt = (system_prompt or "") + ctx_block
                print(f"📝 [AGENT] Appended team context ({len(ctx_block)} chars)")

            from investigation_lifecycle import investigation_guidance_append

            system_prompt = (system_prompt or "") + investigation_guidance_append()
            print(
                "📝 [AGENT] Appended investigation guidance (memory + KG) to system prompt"
            )

            print(
                f"🤖 [AGENT] Registered {len(subagents)} subagents: "
                f"{', '.join(subagents.keys())}"
            )

        # Resolve allowed tools from config or defaults.
        # resolve_agent_tools returns None for wildcard/bogus (LangGraph) names,
        # or a real SDK-tool subset when the config explicitly names valid tools.
        allowed_tools = self.DEFAULT_TOOLS
        if root_config:
            resolved = resolve_agent_tools(root_config.tools)
            if resolved is not None:
                # A real SDK-tool subset was configured — honour it.
                allowed_tools = resolved
            else:
                # Wildcard or stale LangGraph names → full DEFAULT_TOOLS minus
                # any explicitly disabled entries.
                tc = root_config.tools
                allowed_tools = [t for t in self.DEFAULT_TOOLS if t not in tc.disabled]

        options_kwargs = dict(
            cwd=cwd,
            allowed_tools=allowed_tools,
            permission_mode="acceptEdits",
            can_use_tool=can_use_tool_handler,
            include_partial_messages=True,  # Needed to get parent_tool_use_id for subagent tracking
            setting_sources=["user", "project"],  # Loads .claude/skills/
            # Enables the Skill tool + auto-allows it (replaces deprecated "Skill"
            # in allowed_tools). "all" is correct, not a widening: team-level
            # filtering already deleted disabled skill dirs from the thread
            # workspace above, so "all" only enables what's left on disk.
            skills="all",
            agents=subagents,
            hooks={
                "PreToolUse": [HookMatcher(hooks=[self._async_pre_tool_use])],
                "PostToolUse": [HookMatcher(hooks=[self._async_post_tool_use])],
                "PostToolUseFailure": [
                    HookMatcher(hooks=[self._async_post_tool_use_failure])
                ],
                "SubagentStart": [HookMatcher(hooks=[self._async_subagent_start])],
                "SubagentStop": [HookMatcher(hooks=[self._async_subagent_stop])],
            },
            # Truthy guard is intentional: empty/blank id must never be forwarded
            # as --resume (empty string and None both mean "no prior session").
            **({"resume": self.resume} if self.resume else {}),
        )

        # Apply model settings and execution limits from root agent config
        if root_config:
            # Apply max_turns to prevent infinite loops
            if root_config.max_turns:
                options_kwargs["max_turns"] = root_config.max_turns
                print(f"🔧 [AGENT] Max turns: {root_config.max_turns}")

            # Apply model settings globally via environment variables
            # Note: These apply to all subagents (Claude SDK limitation)
            if root_config.model.temperature is not None:
                os.environ["LLM_TEMPERATURE"] = str(root_config.model.temperature)
                print(f"🔧 [AGENT] Temperature: {root_config.model.temperature}")

            if root_config.model.max_tokens is not None:
                os.environ["LLM_MAX_TOKENS"] = str(root_config.model.max_tokens)
                print(f"🔧 [AGENT] Max tokens: {root_config.model.max_tokens}")

            if root_config.model.top_p is not None:
                os.environ["LLM_TOP_P"] = str(root_config.model.top_p)
                print(f"🔧 [AGENT] Top-p: {root_config.model.top_p}")

        if system_prompt:
            # Method 3: Append custom prompt to claude_code preset
            # Preserves built-in tool instructions, safety, and env context
            options_kwargs["system_prompt"] = {
                "type": "preset",
                "preset": "claude_code",
                "append": system_prompt,
            }

        self.options = ClaudeAgentOptions(**options_kwargs)

    # ------------------------------------------------------------------
    # Agent registry + tool capture hooks
    # ------------------------------------------------------------------
    # These build the nested-agent registry from SDK SubagentStart hooks and
    # capture tool_start/tool_end symmetrically from PreToolUse/PostToolUse
    # hooks (replacing the old AssistantMessage-block parsing + tool-parent map).
    #
    # The four `_on_*` methods are intentionally SYNC so the unit tests can
    # construct a session via __new__ and call them directly without awaiting.
    # The SDK's HookCallback type requires an Awaitable return, so the four
    # `_async_*` trampolines below wrap the sync methods for registration.

    def _resolve_agent(self, agent_id):
        """Return (agent_type, invocation_id, parent_invocation_id, parent_agent_type, depth).

        invocation_id is the tool_use_id of the Task/Agent dispatch that spawned this
        agent — stable and never reused, unlike the SDK's own agent_id (confirmed live:
        the SDK reuses agent_id across unrelated sequential dispatches within one run).
        None/empty agent_id means the root/main thread: depth 0, no invocation/parent.
        An unknown agent_id (tool call announced before SubagentStart) is reported as
        "unknown-subagent" at depth 1 with no invocation_id (we have no dispatch to
        attribute it to yet) so its tool events still stream.
        """
        if not agent_id:
            return None, None, None, None, 0
        info = self._agent_registry.get(agent_id)
        if not info:
            return "unknown-subagent", None, None, None, 1
        return (
            info["agent_type"],
            info["invocation_id"],
            info["parent_invocation_id"],
            info["parent_agent_type"],
            info["depth"],
        )

    def _on_pre_tool_use(self, input_data, tool_use_id, context):
        """PreToolUse hook: queue a tool_start record with resolved agent context.

        For Task/Agent dispatches we also record an open dispatch entry so the
        subsequent SubagentStart hook can resolve its parent via the
        most-recently-started still-open dispatch.
        """
        tool_name = input_data.get("tool_name", "Unknown")
        agent_id = input_data.get("agent_id")
        agent_type, invocation_id, parent_invocation_id, parent_agent_type, depth = (
            self._resolve_agent(agent_id)
        )
        if tool_name in ("Task", "Agent"):
            self._open_dispatches.append(
                {
                    "tool_use_id": tool_use_id,
                    "dispatching_agent_id": agent_id,
                    "started_at": time.time(),
                    "ended": False,
                }
            )
        self._pending_tool_starts.append(
            {
                "name": tool_name,
                "tool_use_id": tool_use_id,
                "input": input_data.get("tool_input"),
                "agent_id": invocation_id,
                "agent_type": agent_type,
                "parent_agent_id": parent_invocation_id,
                "parent_agent_type": parent_agent_type,
                "depth": depth,
            }
        )
        return {}

    def _lookup_tool_input(self, tool_use_id: str, input_data: dict):
        """Resolve tool_input from PostToolUse payload or the matching tool_start."""
        tool_input = input_data.get("tool_input")
        if tool_input is not None:
            return tool_input
        for start in self._pending_tool_starts:
            if start.get("tool_use_id") == tool_use_id:
                return start.get("input")
        return None

    def _on_post_tool_use(self, input_data, tool_use_id, context):
        """PostToolUse hook: queue a tool_end record and close any open dispatch.

        Tool output is sourced exclusively here (no more AssistantMessage parsing).
        For Task/Agent tools, mark the matching open dispatch as ended so later
        SubagentStart calls do not pick it up as a parent candidate.
        """
        import logging

        logger = logging.getLogger(__name__)

        # Only invoked for PostToolUse events (registered as such), but guard
        # against being called with a different event name. Treat a missing key
        # as PostToolUse so direct unit-test calls (which omit the key) work.
        if input_data.get("hook_event_name") not in (None, "PostToolUse"):
            return {}

        tool_name = input_data.get("tool_name", "Unknown")
        tool_response = input_data.get("tool_response", "")
        agent_id = input_data.get("agent_id")
        agent_type, invocation_id, parent_invocation_id, parent_agent_type, depth = (
            self._resolve_agent(agent_id)
        )
        logger.info(
            f"[Hook] PostToolUse: tool={tool_name}, id={tool_use_id}, agent_id={agent_id}"
        )

        if tool_name in ("Task", "Agent"):
            for d in self._open_dispatches:
                if d["tool_use_id"] == tool_use_id:
                    d["ended"] = True
                    break

        # Truncate large outputs to avoid SDK buffer issues (SDK has ~1MB limit).
        MAX_OUTPUT_LEN = 50000  # 50KB - plenty for display, safe for buffers
        output_str = _serialize_tool_output(tool_response)
        if output_str and len(output_str) > MAX_OUTPUT_LEN:
            raw_len = len(output_str)
            output_str = (
                output_str[:MAX_OUTPUT_LEN] + f"... [truncated, {raw_len} total chars]"
            )

        tool_input = self._lookup_tool_input(tool_use_id, input_data)
        output_str, _ = sanitize_tool_end_payload(
            tool_name, tool_input, output_str, None
        )

        self._pending_tool_ends.append(
            {
                "name": tool_name,
                "tool_use_id": tool_use_id,
                "output": output_str,
                "agent_id": invocation_id,
                "agent_type": agent_type,
                "parent_agent_id": parent_invocation_id,
                "parent_agent_type": parent_agent_type,
                "depth": depth,
            }
        )
        return {}

    def _on_post_tool_use_failure(self, input_data, tool_use_id, context):
        """PostToolUseFailure hook: the SDK fires this INSTEAD OF PostToolUse when a
        tool call errors (confirmed via claude_agent_sdk.types — PostToolUse and
        PostToolUseFailure are mutually exclusive hook_event_name variants). Without
        this, failed tool calls never got a tool_end, were never persisted, and never
        counted toward tool_calls_count.
        """
        if input_data.get("hook_event_name") not in (None, "PostToolUseFailure"):
            return {}

        tool_name = input_data.get("tool_name", "Unknown")
        error = input_data.get("error") or "Tool execution failed"
        agent_id = input_data.get("agent_id")
        agent_type, invocation_id, parent_invocation_id, parent_agent_type, depth = (
            self._resolve_agent(agent_id)
        )

        if tool_name in ("Task", "Agent"):
            for d in self._open_dispatches:
                if d["tool_use_id"] == tool_use_id:
                    d["ended"] = True
                    break

        tool_input = self._lookup_tool_input(tool_use_id, input_data)
        _, error = sanitize_tool_end_payload(tool_name, tool_input, None, str(error))

        self._pending_tool_ends.append(
            {
                "name": tool_name,
                "tool_use_id": tool_use_id,
                "output": None,
                "success": False,
                "error": str(error),
                "agent_id": invocation_id,
                "agent_type": agent_type,
                "parent_agent_id": parent_invocation_id,
                "parent_agent_type": parent_agent_type,
                "depth": depth,
            }
        )
        return {}

    def _on_subagent_start(self, input_data, tool_use_id, context):
        """SubagentStart hook: register the new subagent and resolve its parent.

        The SDK does NOT provide a parent link on SubagentStart, so we use the
        timing-interval heuristic: the parent is whichever Task/Agent dispatch is
        still open (not ended) and most recently started. depth = parent depth + 1.

        invocation_id is set to that dispatch's own tool_use_id — the stable identity
        for this subagent invocation, since the SDK's agent_id (input_data["agent_id"])
        gets reused across unrelated dispatches within one run (confirmed live).
        """
        agent_id = input_data.get("agent_id")
        agent_type = input_data.get("agent_type")
        if not agent_id:
            return {}
        # Parent = whichever Task/Agent dispatch is still open, most recently started
        open_candidates = [d for d in self._open_dispatches if not d["ended"]]
        dispatching_agent_id = None
        invocation_id = None
        if open_candidates:
            newest = max(open_candidates, key=lambda d: d["started_at"])
            dispatching_agent_id = newest["dispatching_agent_id"]
            invocation_id = newest["tool_use_id"]
        _, _, _, _, parent_depth = self._resolve_agent(dispatching_agent_id)
        parent_agent_type = None
        parent_invocation_id = None
        if dispatching_agent_id:
            parent_info = self._agent_registry.get(dispatching_agent_id)
            if parent_info:
                parent_agent_type = parent_info["agent_type"]
                parent_invocation_id = parent_info["invocation_id"]
            else:
                parent_agent_type = "unknown-subagent"
        self._agent_registry[agent_id] = {
            "agent_type": agent_type,
            "invocation_id": invocation_id,
            "parent_invocation_id": parent_invocation_id,
            "parent_agent_type": parent_agent_type,
            "depth": parent_depth + 1,
        }
        return {}

    def _on_subagent_stop(self, input_data, tool_use_id, context):
        """SubagentStop hook: no-op for now (registry entries are retained)."""
        return {}

    # --- async trampolines for SDK registration (HookCallback requires Awaitable) ---

    async def _async_pre_tool_use(self, input_data, tool_use_id, context):
        return self._on_pre_tool_use(input_data, tool_use_id, context)

    async def _async_post_tool_use(self, input_data, tool_use_id, context):
        return self._on_post_tool_use(input_data, tool_use_id, context)

    async def _async_post_tool_use_failure(self, input_data, tool_use_id, context):
        return self._on_post_tool_use_failure(input_data, tool_use_id, context)

    async def _async_subagent_start(self, input_data, tool_use_id, context):
        return self._on_subagent_start(input_data, tool_use_id, context)

    async def _async_subagent_stop(self, input_data, tool_use_id, context):
        return self._on_subagent_stop(input_data, tool_use_id, context)

    def _build_user_yield(self, content):
        """Return SDK user message dict for the streaming input generator."""
        return {
            "type": "user",
            "message": {"role": "user", "content": content},
        }

    def enqueue_message(self, text: str) -> int:
        if not self.is_running:
            raise RuntimeError("Session is not executing")
        cleaned = (text or "").strip()
        if not cleaned:
            raise ValueError("text must not be empty")
        self._pending_messages.append(cleaned)
        self._message_event.set()
        return len(self._pending_messages)

    async def start(self):
        """Initialize the Claude client session for streaming input mode."""
        if self.client is None:
            # Don't use async with here - we need to keep the client alive
            # across multiple execute() calls. We'll manage lifecycle manually.
            self.client = ClaudeSDKClient(options=self.options)
            # Manually enter the async context manager
            await self.client.__aenter__()

            # Set up observability session context
            metadata = {
                "environment": get_environment(),
                "thread_id": self.thread_id,
            }
            if os.getenv("SANDBOX_NAME"):
                metadata["sandbox_name"] = os.getenv("SANDBOX_NAME")
            observability_set_session(self.thread_id, metadata)

    async def cleanup(self):
        """Clean up the client session. Alias for close()."""
        await self.close()

    @observability_observe()
    async def execute(
        self, prompt: str, images: list = None
    ) -> AsyncIterator[StreamEvent]:
        """
        Execute a query and stream structured events.

        Follows SDK pattern: query() sends the message, then receive_messages()
        drains the stream until a terminal ResultMessage (no outstanding
        background tasks). Unlike receive_response(), receive_messages() does
        not stop on ResultMessage — execute() breaks explicitly after the
        terminal result so turn-end pending-message flush can run.

        Args:
            prompt: User prompt to send to Claude
            images: Optional list of image dicts with {type, media_type, data, filename}

        Yields:
            StreamEvent objects for each agent action
        """
        if self.client is None:
            raise RuntimeError("Session not started. Call start() first.")

        if self.is_running:
            raise RuntimeError(
                "Session already executing. Wait for current execution to complete."
            )

        self.is_running = True
        self._was_interrupted = False
        self._input_closed = False
        self._pending_messages.clear()
        self._message_event.clear()
        self._force_flush = False
        self._pending_consumed_event.clear()
        self._queued_message_count = 0
        self._pending_tool_starts = []  # Reset pending tool starts
        self._pending_tool_ends = []  # Reset pending tool ends
        self._pending_events = []  # For timeout events, etc.
        self._outstanding_background_tasks.clear()
        success = False
        error_occurred = False
        # Concurrent query(AsyncIterable) task — see note at create_task below.
        query_task: asyncio.Task | None = None
        # Split mid-turn narration (thought) from final answer (result).
        # See TextSegmentBuffer + docs/superpowers/specs/2026-07-10-thinking-vs-result-dedupe-design.md
        segments = TextSegmentBuffer()

        # Timeout for receive_messages drain (10 minutes for complex investigations)
        # This prevents hanging forever if interrupted from another request
        # Configurable via AGENT_TIMEOUT_SECONDS env var
        RESPONSE_TIMEOUT = int(
            os.getenv("AGENT_TIMEOUT_SECONDS", "600")
        )  # 10 min default

        try:
            # Build message - can be simple string or multimodal content
            # Always use generator pattern for consistency (even for simple text)
            # This is the recommended SDK pattern per the streaming input docs
            if images:
                # Multimodal message: text + images
                initial_content = [{"type": "text", "text": prompt}]
                for img in images:
                    initial_content.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": img["media_type"],
                                "data": img["data"],
                            },
                        }
                    )
                print(
                    f"📷 [AGENT] Sending multimodal message with {len(images)} image(s)"
                )
            else:
                initial_content = prompt

            async def message_generator():
                yield self._build_user_yield(initial_content)

                # Stay open for mid-run queue-message yields until the turn ends.
                while not self._input_closed:
                    try:
                        await asyncio.wait_for(self._message_event.wait(), timeout=1.0)
                    except asyncio.TimeoutError:
                        if not (self._force_flush and self._pending_messages):
                            continue
                    self._message_event.clear()

                    # Debounce unless force-flushing at a turn boundary.
                    if not self._force_flush:
                        while True:
                            await asyncio.sleep(MESSAGE_QUEUE_DEBOUNCE_SECONDS)
                            if not self._message_event.is_set():
                                break
                            self._message_event.clear()

                    if self._pending_messages and not self._was_interrupted:
                        merged = format_merged_messages(self._pending_messages)
                        self._pending_messages.clear()
                        self._queued_message_count += 1
                        self._pending_consumed_event.set()
                        yield self._build_user_yield(merged)

                    if self._force_flush:
                        self._force_flush = False

                # Never drop messages accepted by enqueue_message (e.g. debounce race at turn end).
                if self._pending_messages and not self._was_interrupted:
                    merged = format_merged_messages(self._pending_messages)
                    self._pending_messages.clear()
                    self._queued_message_count += 1
                    self._pending_consumed_event.set()
                    yield self._build_user_yield(merged)

            # CRITICAL: ClaudeSDKClient.query(AsyncIterable) drains the iterable to
            # completion before returning. Our generator stays open for mid-run
            # queue-message yields until _input_closed, so awaiting query() first
            # deadlocks forever and receive_messages() never starts.
            # Run query concurrently with receive_messages instead.
            print(
                f"🔍 [DEBUG] Starting concurrent client.query() for thread {self.thread_id}"
            )
            query_task = asyncio.create_task(
                self.client.query(message_generator()),
                name=f"sdk-query-{self.thread_id}",
            )

            # Receive response with timeout
            try:
                print(
                    f"🔍 [DEBUG] Starting receive_messages() with timeout {RESPONSE_TIMEOUT}s for thread {self.thread_id}"
                )
                message_count = 0
                async with asyncio.timeout(RESPONSE_TIMEOUT):
                    while True:
                        async for message in self.client.receive_messages():
                            message_count += 1
                            if self._pending_consumed_event.is_set():
                                self._pending_consumed_event.clear()
                                yield message_queued_event(
                                    self.thread_id, pending_count=0
                                )
                            print(
                                f"🔍 [DEBUG] Received message #{message_count}: {type(message).__name__} for thread {self.thread_id}"
                            )
                            # Get parent_tool_use_id if this message is from a subagent
                            parent_tool_use_id = getattr(
                                message, "parent_tool_use_id", None
                            )

                            # Emit any pending tool_start events (from PreToolUse hook).
                            # Flush buffered assistant text as a thought before tools so narration
                            # is not folded into the final result.
                            if self._pending_tool_starts:
                                thought_text = segments.flush_thought()
                                if thought_text:
                                    yield thought_event(
                                        self.thread_id,
                                        thought_text,
                                        parent_tool_use_id=parent_tool_use_id,
                                    )
                                segments.mark_tool()
                            while self._pending_tool_starts:
                                pending = self._pending_tool_starts.pop(0)
                                yield tool_start_event(
                                    self.thread_id,
                                    pending["name"],
                                    pending.get("input"),
                                    tool_use_id=pending.get("tool_use_id"),
                                    agent_id=pending.get("agent_id"),
                                    agent_type=pending.get("agent_type"),
                                    parent_agent_id=pending.get("parent_agent_id"),
                                    parent_agent_type=pending.get("parent_agent_type"),
                                    depth=pending.get("depth", 0),
                                )

                            # Emit any pending tool_end events (from PostToolUse hook)
                            while self._pending_tool_ends:
                                pending = self._pending_tool_ends.pop(0)
                                yield tool_end_event(
                                    self.thread_id,
                                    pending["name"],
                                    success=pending.get("success", True),
                                    error=pending.get("error"),
                                    output=pending.get("output"),
                                    tool_use_id=pending.get("tool_use_id"),
                                    agent_id=pending.get("agent_id"),
                                    agent_type=pending.get("agent_type"),
                                    parent_agent_id=pending.get("parent_agent_id"),
                                    parent_agent_type=pending.get("parent_agent_type"),
                                    depth=pending.get("depth", 0),
                                )

                            # Emit any pending events (timeout events, etc.)
                            while self._pending_events:
                                yield self._pending_events.pop(0)

                            if isinstance(message, TaskStartedMessage):
                                self._outstanding_background_tasks.add(message.task_id)
                                yield task_started_event(
                                    self.thread_id,
                                    task_id=message.task_id,
                                    description=message.description,
                                    tool_use_id=message.tool_use_id,
                                    task_type=message.task_type,
                                )
                            elif isinstance(message, TaskProgressMessage):
                                # Consume progress updates; no SSE emission.
                                pass
                            elif isinstance(message, TaskNotificationMessage):
                                if (
                                    message.task_id
                                    not in self._outstanding_background_tasks
                                ):
                                    logging.getLogger(__name__).warning(
                                        "TaskNotification for unknown task_id=%s",
                                        message.task_id,
                                    )
                                else:
                                    self._outstanding_background_tasks.discard(
                                        message.task_id
                                    )
                                yield task_notification_event(
                                    self.thread_id,
                                    task_id=message.task_id,
                                    status=message.status,
                                    summary=message.summary,
                                )
                            elif isinstance(message, AssistantMessage):
                                for block in message.content:
                                    if isinstance(block, TextBlock):
                                        # Buffer only — flushed as thought before tools, or as result at end.
                                        segments.append(block.text)
                                    elif hasattr(block, "name"):
                                        # Same-message tool-use: flush narration before the tool boundary
                                        # even if PreToolUse already queued (or not yet drained).
                                        thought_text = segments.flush_thought()
                                        if thought_text:
                                            yield thought_event(
                                                self.thread_id,
                                                thought_text,
                                                parent_tool_use_id=parent_tool_use_id,
                                            )
                                        segments.mark_tool()
                                        if block.name == "AskUserQuestion":
                                            tool_input = {}
                                            if hasattr(block, "input"):
                                                tool_input = (
                                                    block.input
                                                    if isinstance(block.input, dict)
                                                    else {}
                                                )
                                            questions = tool_input.get("questions", [])
                                            yield question_event(
                                                self.thread_id, questions
                                            )
                            elif isinstance(message, ResultMessage):
                                # Capture the SDK session id for durable resume.
                                self.session_id = capture_session_id_from_result(
                                    self.session_id, message
                                )
                                # Pending tool_end events are already drained at the top
                                # of the loop on every iteration, so nothing extra to do
                                # here.

                                # Fall back to the SDK's own result text when nothing was
                                # streamed (e.g. max_turns/error cut the turn short before
                                # any assistant text block was emitted).
                                text_for_extraction = segments.finalize_result(
                                    fallback=message.result or ""
                                )

                                # Extract any local images referenced in the final text
                                result_text, extracted_images = (
                                    _extract_images_from_text(text_for_extraction)
                                )
                                if extracted_images:
                                    print(
                                        f"📷 [AGENT] Extracted {len(extracted_images)} image(s) from result"
                                    )

                                # Extract any local files referenced in the final text
                                _, extracted_files = _extract_files_from_text(
                                    text_for_extraction
                                )
                                if extracted_files:
                                    print(
                                        f"📎 [AGENT] Extracted {len(extracted_files)} file(s) from result"
                                    )

                                if self._outstanding_background_tasks:
                                    if result_text.strip():
                                        yield thought_event(
                                            self.thread_id,
                                            result_text,
                                            parent_tool_use_id=parent_tool_use_id,
                                        )
                                    pending_ids = sorted(self._outstanding_background_tasks)
                                    yield background_waiting_event(
                                        self.thread_id,
                                        pending_count=len(pending_ids),
                                        pending_task_ids=pending_ids,
                                    )
                                    continue

                                # Emit result event with images and files.
                                # message.subtype can be "success" even when a mid-turn
                                # API call failed (429/500/529) — the CLI still reports
                                # is_error=True in that case, so subtype alone is not a
                                # reliable success signal. api_error_status carries the
                                # HTTP status when that happens; log it for observability.
                                success = (
                                    message.subtype == "success"
                                    and not message.is_error
                                )
                                if message.is_error and message.api_error_status:
                                    print(
                                        f"⚠️ [AGENT] API error during run: status={message.api_error_status}, "
                                        f"stop_reason={message.stop_reason}"
                                    )
                                yield result_event(
                                    self.thread_id,
                                    result_text,
                                    success=success,
                                    subtype=message.subtype,
                                    images=(
                                        extracted_images if extracted_images else None
                                    ),
                                    files=extracted_files if extracted_files else None,
                                )
                                # receive_messages() does not stop on ResultMessage
                                # (unlike receive_response()). Break so the outer
                                # loop can run pending-message force-flush / exit.
                                break

                        if self._pending_consumed_event.is_set():
                            self._pending_consumed_event.clear()
                            yield message_queued_event(self.thread_id, pending_count=0)

                        if self._was_interrupted or not self._pending_messages:
                            break

                        # Turn ended with pending guidance still in the buffer — force-flush
                        # and continue receive_messages so the SDK gets a real next turn.
                        self._force_flush = True
                        self._message_event.set()
                        deadline = time.monotonic() + 2.0
                        while self._pending_messages and time.monotonic() < deadline:
                            await asyncio.sleep(0.05)
                        if self._pending_consumed_event.is_set():
                            self._pending_consumed_event.clear()
                            yield message_queued_event(self.thread_id, pending_count=0)
                print(
                    f"✅ [DEBUG] receive_messages() completed. Total messages: {message_count} for thread {self.thread_id}"
                )
            except asyncio.TimeoutError:
                print(
                    f"❌ [DEBUG] receive_messages() TIMEOUT after {RESPONSE_TIMEOUT}s, messages received: {message_count} for thread {self.thread_id}"
                )
                # Drop any unflushed narration; timeout messaging is the user-facing signal.
                segments.finalize_result()
                # Stop in-flight SDK/subagent work and try to capture session_id
                # for cold resume before yielding the timeout error to the client.
                try:
                    await self.client.interrupt()
                except Exception as interrupt_err:
                    print(
                        f"⚠️ [AGENT] interrupt after timeout failed for {self.thread_id}: {interrupt_err}"
                    )
                try:
                    async with asyncio.timeout(5):
                        async for message in self.client.receive_response():
                            if isinstance(message, ResultMessage):
                                self.session_id = capture_session_id_from_result(
                                    self.session_id, message
                                )
                                break
                except (asyncio.TimeoutError, Exception):
                    pass
                yield error_event(
                    self.thread_id,
                    format_investigation_timeout_message(RESPONSE_TIMEOUT),
                    recoverable=True,
                )
                error_occurred = True

        except Exception as e:
            error_occurred = True
            observability_set_tags(["error", "exception"])
            import traceback

            error_msg = str(e)
            print(f"❌ [AGENT] Exception during execute: {error_msg}")
            traceback.print_exc()

            # Provide user-friendly messages for known issues; default to generic
            if "buffer size" in error_msg.lower() or "1048576" in error_msg:
                error_msg = "Subagent produced too much output (SDK buffer limit). Try a simpler task."
            elif "decode" in error_msg.lower() and "json" in error_msg.lower():
                error_msg = (
                    "SDK JSON parsing error. The response was too large or malformed."
                )
            elif "rate" in error_msg.lower() and "limit" in error_msg.lower():
                error_msg = (
                    "API rate limit reached. Please wait a moment and try again."
                )
            else:
                # Don't leak internal details (file paths, DB strings, SDK state)
                error_msg = "An internal error occurred during the investigation."

            yield error_event(self.thread_id, error_msg, recoverable=False)
            # Don't re-raise - let the error event be sent cleanly
        finally:
            # Close the input generator so the concurrent query task can finish.
            self._input_closed = True
            self._message_event.set()  # unblock generator
            if query_task is not None:
                if not query_task.done():
                    try:
                        await asyncio.wait_for(query_task, timeout=2.0)
                        print(
                            f"✅ [DEBUG] concurrent client.query() completed for thread {self.thread_id}"
                        )
                    except asyncio.TimeoutError:
                        print(
                            f"⚠️ [DEBUG] query task still open after turn end; cancelling for thread {self.thread_id}"
                        )
                        query_task.cancel()
                        try:
                            await query_task
                        except (asyncio.CancelledError, Exception):
                            pass
                    except Exception as query_err:
                        print(
                            f"⚠️ [DEBUG] query task ended with error for thread {self.thread_id}: {query_err}"
                        )
                elif not query_task.cancelled():
                    # Surface transport/write failures that finished before we cleaned up.
                    query_exc = query_task.exception()
                    if query_exc is not None:
                        print(
                            f"⚠️ [DEBUG] query task failed for thread {self.thread_id}: {query_exc}"
                        )
            self.is_running = False
            self._outstanding_background_tasks.clear()
            # Add outcome tags
            if success:
                observability_set_tags(["success"])
            elif not error_occurred:
                observability_set_tags(["incomplete"])

    async def interrupt(self) -> AsyncIterator[StreamEvent]:
        """
        Interrupt current execution and stop.

        This sends an interrupt signal to Claude to stop the current task.
        After interrupt, the session is ready for new messages.

        Note: This does NOT automatically execute a new prompt. New messages
        should be sent separately via execute(). This matches Cursor's UX where
        interrupt just stops, and new messages are sent normally.

        Important: Claude SDK's interrupt() doesn't kill running bash subprocesses,
        so long-running scripts may continue in the background. This is a known
        limitation of the SDK.

        KNOWN ISSUE: If an execute() is running in a separate async context (e.g.,
        different HTTP request), its receive_response() may hang and not properly
        terminate. The interrupted task will stop in Claude, but the HTTP streaming
        response may not close immediately. This is a limitation of having separate
        HTTP requests for execute and interrupt.

        Yields:
            StreamEvent objects for interrupt status
        """
        if self.client is None:
            raise RuntimeError("Session not started. Call start() first.")

        try:
            yield thought_event(self.thread_id, "Interrupting current task...")
            self._outstanding_background_tasks.clear()
            self._input_closed = True
            self._force_flush = False
            self._pending_messages.clear()
            self._message_event.set()
            await self.client.interrupt()
            self._was_interrupted = True
            self.is_running = False
            yield result_event(
                self.thread_id,
                "Task interrupted. Send a new message to continue.",
                success=True,
                subtype="interrupted",
            )
        except Exception as e:
            print(f"❌ [AGENT] Interrupt failed: {str(e)}")
            yield error_event(
                self.thread_id, "Interrupt failed. Please try again.", recoverable=False
            )
            raise

    async def close(self):
        """Clean up the client session."""
        if self.client is not None:
            try:
                await self.client.disconnect()
            except Exception:
                pass  # Ignore cleanup errors
            self.client = None

    async def provide_answer(self, answers: dict) -> None:
        """Provide answer to pending AskUserQuestion."""
        if (
            hasattr(self, "_pending_answer_event")
            and self._pending_answer_event is not None
        ):
            self._pending_answer = answers
            self._pending_answer_event.set()


def create_agent_session(thread_id: str, team_config=None):
    """
    Factory function to create agent session.

    Returns InteractiveAgentSession (Claude Agent SDK, direct Anthropic).
    Optional multi-provider routing is available via a proxy
    (set ANTHROPIC_BASE_URL to the proxy endpoint).

    Args:
        thread_id: Unique identifier for the session
        team_config: Optional TeamConfig from config_service

    Returns:
        InteractiveAgentSession
    """
    print("🔄 [AGENT] Using Claude Agent SDK (direct Anthropic)")
    return InteractiveAgentSession(thread_id, team_config)
