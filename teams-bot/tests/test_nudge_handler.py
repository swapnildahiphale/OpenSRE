"""Unit tests for POST /internal/nudge."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _clear_app_binding():
    import nudge_handler

    nudge_handler._app = None
    yield
    nudge_handler._app = None


@pytest.mark.asyncio
async def test_nudge_missing_header_unauthorized(monkeypatch):
    monkeypatch.setenv("INTERNAL_SERVICE_SECRET", "s3cret")
    from nudge_handler import handle_nudge

    resp = await handle_nudge({"body": {}, "headers": {}})
    assert resp["status"] == 401


@pytest.mark.asyncio
async def test_nudge_wrong_secret_unauthorized(monkeypatch):
    monkeypatch.setenv("INTERNAL_SERVICE_SECRET", "s3cret")
    from nudge_handler import handle_nudge

    resp = await handle_nudge(
        {
            "body": {
                "conversation_ref": {
                    "conversation_id": "19:abc",
                    "service_url": "https://smba.example/",
                    "channel_id": "msteams",
                },
                "text": "Has this been fixed?",
            },
            "headers": {"x-internal-service": "wrong"},
        }
    )
    assert resp["status"] == 401


@pytest.mark.asyncio
async def test_nudge_without_mention_posts_plain_text(monkeypatch):
    monkeypatch.setenv("INTERNAL_SERVICE_SECRET", "s3cret")
    from nudge_handler import handle_nudge

    sent = {}

    async def fake_send(conversation_ref, message):
        sent["ref"] = conversation_ref
        sent["message"] = message

    with patch("nudge_handler.send_to_conversation_ref", side_effect=fake_send):
        resp = await handle_nudge(
            {
                "body": {
                    "conversation_ref": {
                        "conversation_id": "19:abc",
                        "service_url": "https://smba.example/",
                        "channel_id": "msteams",
                        "tenant_id": "tenant-1",
                    },
                    "text": "Has this been fixed yet?",
                },
                "headers": {"x-internal-service": "s3cret"},
            }
        )
    assert resp["status"] == 200
    assert resp["body"]["ok"] is True
    assert sent["message"].text == "Has this been fixed yet?"
    entities = getattr(sent["message"], "entities", None) or []
    assert entities == [] or all(
        getattr(e, "type", None) != "mention" for e in entities
    )


@pytest.mark.asyncio
async def test_nudge_with_mention_id_adds_mention_entity(monkeypatch):
    monkeypatch.setenv("INTERNAL_SERVICE_SECRET", "s3cret")
    from nudge_handler import handle_nudge

    sent = {}

    async def fake_send(conversation_ref, message):
        sent["message"] = message

    with patch("nudge_handler.send_to_conversation_ref", side_effect=fake_send):
        resp = await handle_nudge(
            {
                "body": {
                    "conversation_ref": {
                        "conversation_id": "19:abc",
                        "service_url": "https://smba.example/",
                        "channel_id": "msteams",
                    },
                    "text": "Has this been fixed yet?",
                    "mention_id": "29:jane",
                },
                "headers": {"X-Internal-Service": "s3cret"},
            }
        )
    assert resp["status"] == 200
    entities = list(sent["message"].entities or [])
    assert any(getattr(e, "type", None) == "mention" for e in entities)
    mention = next(e for e in entities if getattr(e, "type", None) == "mention")
    assert mention.mentioned.id == "29:jane"


@pytest.mark.asyncio
async def test_nudge_registers_route_on_app(monkeypatch):
    monkeypatch.setenv("INTERNAL_SERVICE_SECRET", "s3cret")
    from nudge_handler import register_nudge_route

    app = MagicMock()
    app.server.adapter.register_route = MagicMock()
    register_nudge_route(app)
    app.server.adapter.register_route.assert_called_once()
    args = app.server.adapter.register_route.call_args.args
    assert args[0] == "POST"
    assert args[1] == "/internal/nudge"
