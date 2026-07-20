from agent import TextSegmentBuffer


def test_text_only_turn_is_result_only():
    buf = TextSegmentBuffer()
    buf.append("Here is the summary.")
    # Text-only turns: finalize directly; flush_thought is never called in execute().
    assert buf.finalize_result() == "Here is the summary."
    assert buf.flush_thought() is None


def test_mid_turn_text_flushes_as_thought_before_tool():
    buf = TextSegmentBuffer()
    buf.append("I'll pull the Jira ticket.")
    thought = buf.flush_thought()
    buf.mark_tool()
    assert thought == "I'll pull the Jira ticket."
    buf.append("Root cause: stale IAM key.")
    assert buf.finalize_result() == "Root cause: stale IAM key."


def test_multiple_text_blocks_join_before_flush():
    buf = TextSegmentBuffer()
    buf.append("First.")
    buf.append("Second.")
    assert buf.flush_thought() == "First.\n\nSecond."


def test_empty_flush_and_fallback_result():
    buf = TextSegmentBuffer()
    assert buf.flush_thought() is None
    assert buf.finalize_result(fallback="sdk fallback") == "sdk fallback"


def test_thought_text_never_returned_again_as_result():
    buf = TextSegmentBuffer()
    buf.append("plan")
    assert buf.flush_thought() == "plan"
    buf.mark_tool()
    # No more text after tools → empty buffer uses fallback
    assert buf.finalize_result(fallback="") == ""


def test_whitespace_only_append_ignored():
    buf = TextSegmentBuffer()
    buf.append("   ")
    buf.append("")
    assert buf.flush_thought() is None
    assert buf.finalize_result(fallback="x") == "x"


def test_full_turn_sequence_matches_spec():
    """Simulate: narrate → tool → narrate → tool → final answer."""
    buf = TextSegmentBuffer()
    buf.append("I'll start by pulling Jira.")
    t1 = buf.flush_thought()
    buf.mark_tool()
    buf.append("Delegating to investigation.")
    t2 = buf.flush_thought()
    buf.mark_tool()
    buf.append("Root cause confirmed: stale IAM key.")
    result = buf.finalize_result()
    assert t1 == "I'll start by pulling Jira."
    assert t2 == "Delegating to investigation."
    assert result == "Root cause confirmed: stale IAM key."
    assert t1 not in result and t2 not in result
