"""Timeout message formatting and session_id capture helpers."""

from agent import capture_session_id_from_result, format_investigation_timeout_message


class _FakeResultMessage:
    def __init__(self, session_id):
        self.session_id = session_id


def test_timeout_message_uses_minutes_for_600_seconds():
    msg = format_investigation_timeout_message(600)
    assert "10 minutes" in msg
    assert "time limit" in msg.lower()


def test_timeout_message_uses_seconds_for_odd_values():
    msg = format_investigation_timeout_message(90)
    assert "90 seconds" in msg


def test_capture_session_id_from_result_message():
    sid = capture_session_id_from_result(None, _FakeResultMessage("sess-abc"))
    assert sid == "sess-abc"


def test_capture_session_id_does_not_overwrite_existing():
    sid = capture_session_id_from_result("prev-sess", _FakeResultMessage(None))
    assert sid == "prev-sess"
