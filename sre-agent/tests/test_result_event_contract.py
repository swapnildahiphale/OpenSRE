"""Regression guard for the result-event key contract.

The finalizer (episode store) and structured_report extraction in
server_simple.py read the result event's `text` field (produced by
events.result_event). A key mismatch (e.g. reading `result`) makes
run_result_text always empty, which silently disables episode storage —
the bug found during the SDK-migration local POC.
"""

import pathlib

from events import result_event


def test_result_event_exposes_text_and_success():
    data = result_event(
        "t1", "ROOT CAUSE: bad image tag. " * 4, success=True
    ).to_dict()["data"]
    assert "text" in data and "result" not in data
    assert data["text"].startswith("ROOT CAUSE")
    assert data.get("success") is True


def test_server_simple_reads_text_key_not_result():
    src = (
        pathlib.Path(__file__)
        .resolve()
        .parents[1]
        .joinpath("server_simple.py")
        .read_text()
    )
    assert 'data.get("result"' not in src, (
        "server_simple.py must read the result event's 'text' key, not 'result' "
        "(events.result_event uses 'text'); a mismatch disables memory storage"
    )
