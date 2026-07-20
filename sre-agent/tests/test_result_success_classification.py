"""ResultMessage success/text classification (SDK 0.1.46/0.1.76 fields).

Regression guard for a real bug surfaced by the claude-agent-sdk upgrade: the
CLI can report ``subtype="success"`` while ``is_error=True`` when a mid-turn
API call fails (429/500/529) — see ``api_error_status`` in the SDK's
ResultMessage docstring. Checking ``subtype`` alone silently mislabels an
API-errored run as a successful investigation, which would then be persisted
as a successful memory episode. These tests replicate the two expressions
from ``InteractiveAgentSession.execute()`` rather than driving the full async
generator, matching the pattern in test_session_resume.py.
"""


class _FakeResultMessage:
    """Minimal stand-in for claude_agent_sdk.types.ResultMessage."""

    def __init__(
        self,
        subtype="success",
        is_error=False,
        api_error_status=None,
        stop_reason=None,
        result=None,
    ):
        self.subtype = subtype
        self.is_error = is_error
        self.api_error_status = api_error_status
        self.stop_reason = stop_reason
        self.result = result


def _classify_success(message):
    """Replicate the success expression from execute()."""
    return message.subtype == "success" and not message.is_error


def _resolve_text(final_text, message):
    """Replicate the text-fallback expression from execute()."""
    return final_text or message.result or ""


def test_success_true_for_clean_success():
    msg = _FakeResultMessage(subtype="success", is_error=False)
    assert _classify_success(msg) is True


def test_success_false_when_is_error_despite_success_subtype():
    """The bug: CLI can report subtype='success' with is_error=True on a
    mid-turn API failure. subtype alone must not be trusted."""
    msg = _FakeResultMessage(subtype="success", is_error=True, api_error_status=529)
    assert _classify_success(msg) is False


def test_success_false_for_non_success_subtype():
    msg = _FakeResultMessage(subtype="error_max_turns", is_error=False)
    assert _classify_success(msg) is False


def test_text_prefers_streamed_final_text():
    msg = _FakeResultMessage(result="fallback result text")
    assert _resolve_text("streamed final text", msg) == "streamed final text"


def test_text_falls_back_to_message_result_when_final_text_empty():
    """max_turns/error can cut a turn short before any assistant text block
    streams; message.result is the SDK's own summary of what happened."""
    msg = _FakeResultMessage(result="Reached maximum number of turns")
    assert _resolve_text("", msg) == "Reached maximum number of turns"


def test_text_empty_when_both_final_text_and_result_are_empty():
    msg = _FakeResultMessage(result=None)
    assert _resolve_text("", msg) == ""
