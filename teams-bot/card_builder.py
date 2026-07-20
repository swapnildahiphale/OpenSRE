"""Adaptive Card JSON for questions, finals, and welcome."""

from typing import Any, Optional


def _text_block(
    text: str, *, weight: str | None = None, size: str | None = None
) -> dict:
    block: dict[str, Any] = {"type": "TextBlock", "text": text, "wrap": True}
    if weight:
        block["weight"] = weight
    if size:
        block["size"] = size
    return block


def build_welcome_card() -> dict:
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": [
            _text_block("OpenSRE", weight="Bolder", size="Large"),
            _text_block(
                "AI incident investigation for your team. "
                "@mention me in a channel or message me here to start. "
                "Reply in the same thread to continue."
            ),
            _text_block("Commands: `help`, `status`", weight="Lighter"),
        ],
    }


def build_question_card(*, thread_id: str, questions: list[dict]) -> dict:
    body: list[dict] = [
        _text_block("OpenSRE needs your input", weight="Bolder", size="Medium")
    ]
    for idx, q in enumerate(questions):
        header = q.get("header") or f"Question {idx + 1}"
        body.append(_text_block(f"**{header}**"))
        body.append(_text_block(q.get("question") or ""))
        options = q.get("options") or []
        choices = [
            {
                "title": opt.get("label") or str(opt),
                "value": opt.get("label") or str(opt),
            }
            for opt in options
        ]
        if choices:
            body.append(
                {
                    "type": "Input.ChoiceSet",
                    "id": f"answer_{idx}",
                    "style": "expanded",
                    "isMultiSelect": bool(q.get("multi_select")),
                    "choices": choices,
                }
            )
        body.append(
            {
                "type": "Input.Text",
                "id": f"comment_{idx}",
                "placeholder": "Optional comment",
                "isMultiline": True,
            }
        )

    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": body,
        "actions": [
            {
                "type": "Action.Execute",
                "title": "Submit",
                "verb": "opensre.submit_answers",
                "data": {"answer_thread_id": thread_id},
            }
        ],
    }


def build_final_card(*, result_text: Optional[str], error: Optional[str]) -> dict:
    # No boilerplate title — show agent result or error only.
    if error:
        body = [_text_block(error)]
    else:
        body = [_text_block(result_text or "_No summary returned._")]
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": body,
    }


def build_timeout_card() -> dict:
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.5",
        "body": [
            _text_block("Question timed out", weight="Bolder"),
            _text_block("The agent continued without an answer."),
        ],
    }
