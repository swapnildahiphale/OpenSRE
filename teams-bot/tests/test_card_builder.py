from card_builder import (
    build_final_card,
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
