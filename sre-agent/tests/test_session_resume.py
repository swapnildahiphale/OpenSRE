"""InteractiveAgentSession accepts a resume id and captures session_id."""

from claude_agent_sdk import SystemMessage

from agent import InteractiveAgentSession, session_id_event_if_changed


def test_resume_id_is_stored_on_init():
    s = InteractiveAgentSession(thread_id="t1", resume="sess-prev")
    assert s.resume == "sess-prev"
    assert s.session_id is None


def test_no_resume_defaults_to_none():
    s = InteractiveAgentSession(thread_id="t1")
    assert s.resume is None
    assert s.session_id is None


class _FakeResultMessage:
    def __init__(self, session_id):
        self.session_id = session_id


def test_first_system_message_yields_sdk_session_event():
    new_id, ev = session_id_event_if_changed(
        "t1", None, SystemMessage(subtype="init", data={"session_id": "sess-1"})
    )
    assert new_id == "sess-1"
    assert ev is not None
    assert ev.type == "sdk_session"
    assert ev.data["session_id"] == "sess-1"


def test_duplicate_same_id_does_not_yield():
    msg = SystemMessage(subtype="init", data={"session_id": "sess-1"})
    new_id, ev = session_id_event_if_changed("t1", "sess-1", msg)
    assert new_id == "sess-1"
    assert ev is None


def test_result_message_yields_only_when_id_changes():
    new_id, ev = session_id_event_if_changed(
        "t1", "sess-1", _FakeResultMessage("sess-1")
    )
    assert new_id == "sess-1"
    assert ev is None
    new_id, ev = session_id_event_if_changed(
        "t1", "sess-1", _FakeResultMessage("sess-2")
    )
    assert new_id == "sess-2"
    assert ev is not None
    assert ev.data["session_id"] == "sess-2"
