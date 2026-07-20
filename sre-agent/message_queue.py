"""Merge mid-run user messages into one SDK user turn at turn boundaries."""

MESSAGE_QUEUE_DEBOUNCE_SECONDS = 0.3

MESSAGE_QUEUE_HEADER = (
    "Additional guidance from the user (queued during investigation):"
)


def format_merged_messages(messages: list[str]) -> str:
    """Format queued user messages as a single numbered guidance block."""
    cleaned = [m.strip() for m in messages if m and m.strip()]
    if not cleaned:
        raise ValueError("messages must not be empty")
    lines = [f"{i}. {text}" for i, text in enumerate(cleaned, start=1)]
    return MESSAGE_QUEUE_HEADER + "\n" + "\n".join(lines)
