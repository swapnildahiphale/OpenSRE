"""Drive sre-agent SSE and map events to Teams stream/cards."""

import logging
import re
import time
from typing import Awaitable, Callable, Optional

import aiohttp
from card_builder import (
    build_final_card,
    build_final_text,
    build_question_card,
    build_timeout_card,
)
from config import Config
from progress_text import build_progress_text
from run_links import build_agent_run_url
from state import (
    InvestigationState,
    active_investigations,
    pending_questions,
    question_activity_ids,
)
from stream_handler import handle_stream_event, parse_sse_event

logger = logging.getLogger(__name__)

UPDATE_INTERVAL_SECONDS = 0.5
# aiohttp ClientSession defaults to total=300s. Channel investigations await
# the SSE stream in-handler; a 5-minute cut cancelled the handler (TimeoutError)
# after the "Working on it" ack and before the final card. Agent wall-clock cap
# is AGENT_TIMEOUT_SECONDS (600s) — keep SSE total above that plus buffer.
SSE_CLIENT_TIMEOUT = aiohttp.ClientTimeout(total=900, sock_connect=30)

StreamUpdate = Callable[[str], Awaitable[None]]
StreamClose = Callable[[], Awaitable[None]]
SendCard = Callable[[dict], Awaitable[Optional[str]]]  # returns activity id
SendText = Callable[[str], Awaitable[None]]
UpdateCard = Callable[[str, dict], Awaitable[None]]  # activity_id, card


def _run_url(cfg: Config, state: InvestigationState) -> Optional[str]:
    if not state.run_id:
        return None
    return build_agent_run_url(cfg.WEB_UI_PUBLIC_BASE_URL, state.run_id)


def sanitize_thread_id(conversation_id: str) -> str:
    # Keep enough of the Teams conversation id to stay unique. Channel threads
    # include ;messageid=… and personal chats are long a:… ids — both exceeded
    # the old 80-char cap / varchar(64) column.
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", (conversation_id or "unknown").lower())
    cleaned = cleaned.strip("-")[:240]
    return f"teams-{cleaned}"


def shape_answers_from_card_data(
    data: dict, questions: list[dict]
) -> tuple[str, dict[str, str]]:
    thread_id = data.get("answer_thread_id") or ""
    answers: dict[str, str] = {}
    for idx, _ in enumerate(questions):
        choice = data.get(f"answer_{idx}") or ""
        comment = (data.get(f"comment_{idx}") or "").strip()
        if comment and choice:
            value = f"{choice} // {comment}"
        else:
            value = choice or comment
        answers[f"question_{idx}"] = value
    return thread_id, answers


def _headers(cfg: Config) -> dict[str, str]:
    headers = {"Accept": "text/event-stream"}
    if cfg.INVESTIGATE_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {cfg.INVESTIGATE_AUTH_TOKEN}"
    return headers


async def queue_message(*, thread_id: str, text: str) -> dict:
    cfg = Config()
    url = f"{cfg.SRE_AGENT_URL.rstrip('/')}/threads/{thread_id}/queue-message"
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url, json={"text": text}, headers=_headers(cfg)
        ) as resp:
            resp.raise_for_status()
            return await resp.json()


async def submit_answers(*, thread_id: str, answers: dict[str, str]) -> None:
    cfg = Config()
    url = f"{cfg.SRE_AGENT_URL.rstrip('/')}/answer"
    payload = {"thread_id": thread_id, "answers": answers}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=_headers(cfg)) as resp:
            resp.raise_for_status()


async def run_investigation(
    *,
    thread_id: str,
    prompt: str,
    stream_update: StreamUpdate,
    stream_close: StreamClose,
    send_card: SendCard,
    send_text: SendText,
    update_card: UpdateCard,
    plain_text_final: bool = False,
) -> None:
    active_investigations.add(thread_id)
    try:
        await _run_investigation_body(
            thread_id=thread_id,
            prompt=prompt,
            stream_update=stream_update,
            stream_close=stream_close,
            send_card=send_card,
            send_text=send_text,
            update_card=update_card,
            plain_text_final=plain_text_final,
        )
    finally:
        active_investigations.discard(thread_id)


async def _run_investigation_body(
    *,
    thread_id: str,
    prompt: str,
    stream_update: StreamUpdate,
    stream_close: StreamClose,
    send_card: SendCard,
    send_text: SendText,
    update_card: UpdateCard,
    plain_text_final: bool,
) -> None:
    cfg = Config()
    state = InvestigationState(thread_id=thread_id)
    url = f"{cfg.SRE_AGENT_URL.rstrip('/')}/investigate"
    payload = {
        "prompt": prompt,
        "thread_id": thread_id,
        "trigger_source": "teams",
    }
    last_update = 0.0

    async def send_final_reply() -> None:
        run_url = _run_url(cfg, state)
        if plain_text_final:
            await send_text(
                build_final_text(
                    result_text=state.final_result,
                    error=state.error,
                    run_url=run_url,
                )
            )
            return
        await send_card(
            build_final_card(
                result_text=state.final_result,
                error=state.error,
                run_url=run_url,
            )
        )

    async def process_sse_line(line: str) -> bool:
        nonlocal last_update
        line = line.strip()
        event = parse_sse_event(line)
        if not event:
            return False
        step = handle_stream_event(state, event)

        if step.update_progress:
            now = time.monotonic()
            if now - last_update >= UPDATE_INTERVAL_SECONDS:
                await stream_update(build_progress_text(state))
                last_update = now

        if step.post_question is not None:
            pending_questions[thread_id] = step.post_question
            await stream_close()
            activity_id = await send_card(
                build_question_card(thread_id=thread_id, questions=step.post_question)
            )
            if activity_id:
                question_activity_ids[thread_id] = activity_id

        if step.question_timed_out:
            activity_id = question_activity_ids.pop(thread_id, None)
            pending_questions.pop(thread_id, None)
            if activity_id:
                await update_card(activity_id, build_timeout_card())

        if step.finished:
            if state.error:
                # error is terminal — backend sends nothing after this.
                await stream_close()
                await send_final_reply()
                return True
            # result: backend may continue if a message was queued mid-run.
            # Let the stream drain; the bottom handler sends the final card.
            return False
        return False

    try:
        async with aiohttp.ClientSession(timeout=SSE_CLIENT_TIMEOUT) as session:
            async with session.post(url, json=payload, headers=_headers(cfg)) as resp:
                resp.raise_for_status()
                buffer = ""
                async for raw in resp.content.iter_any():
                    buffer += raw.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        if await process_sse_line(line):
                            return
                if buffer.strip() and await process_sse_line(buffer):
                    return
    except TimeoutError:
        logger.exception("SSE timed out for thread %s", thread_id)
        await stream_close()
        if not state.final_result:
            state.error = (
                "Timed out waiting for the agent. Reply in this thread to continue."
            )
        await send_final_reply()
        return

    # Stream closed — send the final reply with whatever result we accumulated.
    await stream_close()
    if state.final_result or state.error:
        await send_final_reply()
