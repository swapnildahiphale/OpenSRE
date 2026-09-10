from src.api.routes.sso import (
    _apply_sso_display_name,
    _resolve_sso_email,
    _sso_client_secret,
    _sso_team_node_id,
    _sso_token_hash,
)
from src.core.security import hash_token
from src.db.models import TeamToken


def test_resolve_sso_email_prefers_email_claim():
    assert (
        _resolve_sso_email(
            {"email": "a@example.com", "preferred_username": "b@x.com"},
            None,
            "email",
        )
        == "a@example.com"
    )


def test_resolve_sso_email_falls_back_to_preferred_username():
    assert (
        _resolve_sso_email(
            {"preferred_username": "alice@example.com"},
            None,
            "email",
        )
        == "alice@example.com"
    )


def test_resolve_sso_email_skips_non_email_preferred_username():
    assert (
        _resolve_sso_email(
            {"preferred_username": "alice"},
            {"upn": "alice@example.com"},
            "email",
        )
        == "alice@example.com"
    )


def test_resolve_sso_email_none_when_no_at():
    assert _resolve_sso_email({"preferred_username": "alice"}, None, "email") is None


def test_sso_team_node_id_defaults_to_default(monkeypatch):
    monkeypatch.delenv("SSO_DEFAULT_TEAM_NODE_ID", raising=False)
    assert _sso_team_node_id() == "default"


def test_sso_team_node_id_reads_env(monkeypatch):
    monkeypatch.setenv("SSO_DEFAULT_TEAM_NODE_ID", "platform")
    assert _sso_team_node_id() == "platform"


def test_sso_token_hash_matches_auth_pepper(monkeypatch):
    monkeypatch.setenv("TOKEN_PEPPER", "test-pepper-must-be-32-chars!!")
    assert _sso_token_hash("secret") == hash_token(
        "secret", pepper="test-pepper-must-be-32-chars!!"
    )


def test_sso_client_secret_reads_env(monkeypatch):
    monkeypatch.setenv("SSO_CLIENT_SECRET", "  secret-value  ")
    assert _sso_client_secret() == "secret-value"


def test_sso_client_secret_empty_when_unset(monkeypatch):
    monkeypatch.delenv("SSO_CLIENT_SECRET", raising=False)
    assert _sso_client_secret() == ""


def test_sso_client_secret_empty_when_blank(monkeypatch):
    monkeypatch.setenv("SSO_CLIENT_SECRET", "   ")
    assert _sso_client_secret() == ""


def _token() -> TeamToken:
    return TeamToken(
        org_id="org1",
        team_node_id="default",
        token_id="sso_tok",
        token_hash="hash",
        label="sso:jane@example.com",
    )


def test_apply_sso_display_name_sets_stripped_name():
    token = _token()
    _apply_sso_display_name(token, "  Jane Doe  ")
    assert token.display_name == "Jane Doe"


def test_apply_sso_display_name_ignores_blank_and_non_string():
    token = _token()
    token.display_name = "Jane Doe"
    _apply_sso_display_name(token, "   ")
    _apply_sso_display_name(token, None)
    _apply_sso_display_name(token, 123)
    assert token.display_name == "Jane Doe"


def test_apply_sso_display_name_truncates_to_256():
    token = _token()
    _apply_sso_display_name(token, "x" * 300)
    assert token.display_name == "x" * 256
