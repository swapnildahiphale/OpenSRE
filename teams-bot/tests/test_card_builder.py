from card_builder import (
    build_final_card,
    build_final_text,
    build_question_card,
    build_welcome_card,
)


def test_welcome_card_mentions_opensre():
    card = build_welcome_card()
    body = str(card)
    assert "OpenSRE" in body


def test_question_card_has_execute_action_and_thread_id():
    questions = [
        {
            "header": "Environment",
            "question": "Which env?",
            "options": [{"label": "prod"}, {"label": "staging"}],
        }
    ]
    card = build_question_card(thread_id="teams-abc", questions=questions)
    assert card["type"] == "AdaptiveCard"
    assert card["version"] == "1.5"
    actions = card.get("actions") or []
    assert any(a.get("type") == "Action.Execute" for a in actions)
    data_blob = str(card)
    assert "teams-abc" in data_blob


def test_final_card_shows_result():
    card = build_final_card(result_text="Root cause: OOM", error=None)
    assert "OOM" in str(card)
    assert "Investigation complete" not in str(card)


def test_final_card_shows_error():
    card = build_final_card(result_text=None, error="Agent timed out")
    assert "timed out" in str(card).lower()
    assert "Investigation failed" not in str(card)


def test_final_card_converts_markdown_report_into_multiple_blocks():
    text = "**Root cause**\n\n- one\n- two\n"
    card = build_final_card(result_text=text, error=None)
    assert card["body"] == [
        {"type": "TextBlock", "text": "**Root cause**", "wrap": True},
        {"type": "TextBlock", "text": "• one", "wrap": True, "spacing": "None"},
        {"type": "TextBlock", "text": "• two", "wrap": True, "spacing": "None"},
    ]


def test_final_card_error_path_is_a_single_text_block():
    card = build_final_card(result_text=None, error="Agent timed out")
    assert card["body"] == [{"type": "TextBlock", "text": "Agent timed out", "wrap": True}]


def test_final_card_appends_run_link_footer():
    run_url = "https://opensre.example.com/team/agent-runs/abc123"
    card = build_final_card(result_text="Done", error=None, run_url=run_url)
    assert card["body"][-1]["text"] == f"[View in OpenSRE]({run_url})"


def test_final_card_omits_link_without_run_url():
    card = build_final_card(result_text="Done", error=None, run_url=None)
    assert "View in OpenSRE" not in str(card)


def test_final_text_includes_run_link():
    run_url = "https://opensre.example.com/team/agent-runs/abc123"
    text = build_final_text(result_text="Done", error=None, run_url=run_url)
    assert "Done" in text
    assert f"[View in OpenSRE]({run_url})" in text


def test_final_text_omits_link_without_run_url():
    text = build_final_text(result_text="Done", error=None, run_url=None)
    assert text == "Done"
