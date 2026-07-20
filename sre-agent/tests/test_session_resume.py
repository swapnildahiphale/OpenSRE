"""InteractiveAgentSession accepts a resume id and captures session_id."""

from agent import InteractiveAgentSession


def test_resume_id_is_stored_on_init():
    s = InteractiveAgentSession(thread_id="t1", resume="sess-prev")
    assert s.resume == "sess-prev"
    assert s.session_id is None


def test_no_resume_defaults_to_none():
    s = InteractiveAgentSession(thread_id="t1")
    assert s.resume is None
    assert s.session_id is None


class _FakeMsg:
    """Minimal stand-in for ResultMessage to test the capture expression."""

    def __init__(self, session_id):
        self.session_id = session_id


def _apply_capture(s, msg):
    """Replicate the capture expression from execute()."""
    s.session_id = getattr(msg, "session_id", None) or s.session_id


def test_session_id_captured_from_result_message():
    s = InteractiveAgentSession(thread_id="t1")
    _apply_capture(s, _FakeMsg("new-sess-123"))
    assert s.session_id == "new-sess-123"


def test_none_result_does_not_overwrite_existing_session_id():
    s = InteractiveAgentSession(thread_id="t1")
    s.session_id = "prev-sess"
    _apply_capture(s, _FakeMsg(None))
    assert s.session_id == "prev-sess"
