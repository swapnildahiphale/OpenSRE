from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def test_investigate_stores_team_token_for_thread(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import server_simple

    captured = {}

    async def fake_bg(thread_id, resume_session_id=None):
        captured["thread_id"] = thread_id
        captured["token"] = server_simple._team_token_by_thread.get(thread_id)

    monkeypatch.setattr(server_simple, "agent_background_task", fake_bg)
    monkeypatch.setattr(server_simple, "_background_tasks", {})
    monkeypatch.setattr(server_simple, "_message_queues", {})
    monkeypatch.setattr(server_simple, "_response_queues", {})
    monkeypatch.setattr(
        server_simple,
        "_resolve_team_identity",
        lambda _t: ("pilot", "SRE"),
    )

    client = TestClient(server_simple.app)
    with patch.object(
        server_simple, "create_investigation_stream", return_value=iter([])
    ):
        resp = client.post(
            "/investigate",
            json={"prompt": "test"},
            headers={"Authorization": "Bearer team-token-abc"},
        )
    assert resp.status_code == 200
    assert captured.get("token") == "team-token-abc"


def test_investigate_resolves_team_identity(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import server_simple

    async def fake_bg(thread_id, resume_session_id=None):
        pass

    monkeypatch.setattr(server_simple, "agent_background_task", fake_bg)
    monkeypatch.setattr(server_simple, "_background_tasks", {})
    monkeypatch.setattr(server_simple, "_message_queues", {})
    monkeypatch.setattr(server_simple, "_response_queues", {})
    monkeypatch.setattr(server_simple, "_team_identity_by_thread", {})
    monkeypatch.setattr(
        server_simple,
        "_resolve_team_identity",
        lambda _t: ("pilot", "SRE"),
    )

    client = TestClient(server_simple.app)
    with patch.object(
        server_simple, "create_investigation_stream", return_value=iter([])
    ):
        resp = client.post(
            "/investigate",
            json={"prompt": "test", "thread_id": "thread-identity-test"},
            headers={"Authorization": "Bearer team-token-abc"},
        )
    assert resp.status_code == 200
    assert server_simple._team_identity_by_thread["thread-identity-test"] == (
        "pilot",
        "SRE",
    )


def test_create_agent_run_uses_resolved_identity(monkeypatch):
    monkeypatch.setenv("OPENSRE_TENANT_ID", "local")
    monkeypatch.setenv("OPENSRE_TEAM_ID", "default")
    import server_simple

    server_simple._team_identity_by_thread["thread-run-test"] = ("pilot", "SRE")
    posted = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        posted["url"] = url
        posted["body"] = json
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        return resp

    with patch.object(server_simple.httpx, "post", side_effect=fake_post):
        run_id = server_simple._create_agent_run(
            thread_id="thread-run-test",
            prompt="check pods",
        )

    assert run_id is not None
    assert posted["body"]["org_id"] == "pilot"
    assert posted["body"]["team_node_id"] == "SRE"
    assert posted["body"]["trigger_source"] == "web_ui"


def test_create_agent_run_uses_teams_trigger_source(monkeypatch):
    monkeypatch.setenv("OPENSRE_TENANT_ID", "local")
    monkeypatch.setenv("OPENSRE_TEAM_ID", "default")
    import server_simple

    server_simple._team_identity_by_thread["thread-teams-src"] = ("pilot", "SRE")
    server_simple._trigger_source_by_thread["thread-teams-src"] = "teams"
    posted = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        posted["body"] = json
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        return resp

    with patch.object(server_simple.httpx, "post", side_effect=fake_post):
        run_id = server_simple._create_agent_run(
            thread_id="thread-teams-src",
            prompt="oc-1234",
        )

    assert run_id is not None
    assert posted["body"]["trigger_source"] == "teams"
    assert posted["body"]["correlation_id"] == "thread-teams-src"


def test_memory_stats_resolves_tenancy_from_request_header(monkeypatch):
    monkeypatch.setenv("OPENSRE_TENANT_ID", "local")
    monkeypatch.setenv("OPENSRE_TEAM_ID", "default")
    import server_simple

    tenancy_calls = []

    def fake_tenancy(request):
        tenancy_calls.append(request)
        return "pilot", "SRE"

    cypher_params = {}

    class FakeResult:
        def single(self):
            return {"total": 3, "resolved": 1, "issue_types": ["oom"]}

    class FakeSession:
        def run(self, q, **params):
            cypher_params.update(params)
            return FakeResult()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(server_simple, "_tenancy_from_request", fake_tenancy)
    monkeypatch.setattr(
        server_simple,
        "get_driver",
        lambda: MagicMock(session=lambda **kw: FakeSession()),
    )

    client = TestClient(server_simple.app)
    resp = client.get(
        "/memory/stats",
        headers={"Authorization": "Bearer team-token-abc"},
    )

    assert resp.status_code == 200
    assert len(tenancy_calls) == 1
    assert cypher_params["org"] == "pilot"
    assert cypher_params["team"] == "SRE"


def test_resolve_team_identity_calls_auth_me(monkeypatch):
    monkeypatch.setenv("OPENSRE_TENANT_ID", "local")
    monkeypatch.setenv("OPENSRE_TEAM_ID", "default")
    import server_simple

    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"org_id": "pilot", "team_node_id": "SRE"}
        return resp

    with patch.object(server_simple.httpx, "get", side_effect=fake_get):
        org_id, team_node_id = server_simple._resolve_team_identity("my-token")

    assert org_id == "pilot"
    assert team_node_id == "SRE"
    assert captured["url"].endswith("/api/v1/auth/me")
    assert captured["headers"]["Authorization"] == "Bearer my-token"


def test_resolve_team_identity_falls_back_on_failure(monkeypatch):
    monkeypatch.setenv("OPENSRE_TENANT_ID", "local")
    monkeypatch.setenv("OPENSRE_TEAM_ID", "default")
    import server_simple

    with patch.object(
        server_simple.httpx,
        "get",
        side_effect=Exception("auth/me unavailable"),
    ):
        org_id, team_node_id = server_simple._resolve_team_identity("bad-token")

    assert org_id == "local"
    assert team_node_id == "default"


def test_finalize_investigation_strips_fence_and_attaches_structured_report(monkeypatch):
    monkeypatch.setenv("OPENSRE_TENANT_ID", "local")
    monkeypatch.setenv("OPENSRE_TEAM_ID", "default")
    import server_simple

    server_simple._run_id_by_thread["thread-report-test"] = "run-123"
    monkeypatch.setattr(server_simple._il, "finalize_investigation", lambda **kw: None)

    patched = {}

    def fake_patch(url, json=None, headers=None, timeout=None):
        patched["body"] = json
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        return resp

    result_text = '**Headline**\n\nbody\n\n```json\n{"title": "Headline"}\n```\n'
    with patch.object(server_simple.httpx, "patch", side_effect=fake_patch):
        server_simple.finalize_investigation(
            thread_id="thread-report-test",
            prompt="check pods",
            result_text=result_text,
            success=True,
            tool_calls=[],
        )

    assert patched["body"]["output_json"] == {"title": "Headline"}
    assert "```json" not in patched["body"]["output_summary"]
    assert patched["body"]["output_summary"] == "**Headline**\n\nbody"


def test_normalize_trigger_actor():
    import server_simple

    assert server_simple._normalize_trigger_actor(None) is None
    assert server_simple._normalize_trigger_actor("   ") is None
    assert server_simple._normalize_trigger_actor("  Jane Doe  ") == "Jane Doe"
    assert server_simple._normalize_trigger_actor("x" * 200) == "x" * 128


def test_actor_from_auth_me_prefers_name():
    import server_simple

    assert server_simple._actor_from_auth_me({"name": "Jane", "email": "j@x.com"}) == "Jane"
    assert server_simple._actor_from_auth_me({"email": "j@x.com"}) == "j@x.com"
    assert server_simple._actor_from_auth_me({}) is None
    assert server_simple._actor_from_auth_me({"name": "  "}) is None


def test_create_agent_run_uses_per_thread_actor(monkeypatch):
    monkeypatch.setenv("OPENSRE_TENANT_ID", "local")
    monkeypatch.setenv("OPENSRE_TEAM_ID", "default")
    import server_simple

    server_simple._team_identity_by_thread["thread-actor"] = ("pilot", "SRE")
    server_simple._trigger_actor_by_thread["thread-actor"] = "Jane Doe"
    posted = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        posted["body"] = json
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        return resp

    with patch.object(server_simple.httpx, "post", side_effect=fake_post):
        run_id = server_simple._create_agent_run(
            thread_id="thread-actor",
            prompt="check pods",
        )

    assert run_id is not None
    assert posted["body"]["trigger_actor"] == "Jane Doe"


def test_create_agent_run_actor_none_when_unset(monkeypatch):
    monkeypatch.setenv("OPENSRE_TENANT_ID", "local")
    monkeypatch.setenv("OPENSRE_TEAM_ID", "default")
    import server_simple

    server_simple._team_identity_by_thread["thread-no-actor"] = ("pilot", "SRE")
    server_simple._trigger_actor_by_thread.pop("thread-no-actor", None)
    posted = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        posted["body"] = json
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        return resp

    with patch.object(server_simple.httpx, "post", side_effect=fake_post):
        server_simple._create_agent_run(thread_id="thread-no-actor", prompt="x")

    assert posted["body"]["trigger_actor"] is None


def test_investigate_explicit_trigger_actor_wins(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import server_simple

    async def fake_bg(thread_id, resume_session_id=None):
        pass

    monkeypatch.setattr(server_simple, "agent_background_task", fake_bg)
    monkeypatch.setattr(server_simple, "_background_tasks", {})
    monkeypatch.setattr(server_simple, "_message_queues", {})
    monkeypatch.setattr(server_simple, "_response_queues", {})
    monkeypatch.setattr(server_simple, "_team_identity_by_thread", {})
    monkeypatch.setattr(server_simple, "_trigger_actor_by_thread", {})
    monkeypatch.setattr(
        server_simple,
        "_resolve_team_identity",
        lambda _t: ("pilot", "SRE"),
    )
    monkeypatch.setattr(
        server_simple,
        "_actor_from_auth_me",
        lambda _d: "Service Token User",
    )
    monkeypatch.setattr(
        server_simple,
        "_fetch_auth_me",
        lambda _t: {"name": "Service Token User", "email": "bot@example.com"},
    )

    client = TestClient(server_simple.app)
    with patch.object(
        server_simple, "create_investigation_stream", return_value=iter([])
    ):
        resp = client.post(
            "/investigate",
            json={
                "prompt": "oc-1234",
                "thread_id": "thread-teams-actor",
                "trigger_source": "teams",
                "trigger_actor": "Jane Doe",
            },
            headers={"Authorization": "Bearer service-token"},
        )
    assert resp.status_code == 200
    assert server_simple._trigger_actor_by_thread["thread-teams-actor"] == "Jane Doe"


def test_investigate_infers_actor_from_auth_me(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import server_simple

    async def fake_bg(thread_id, resume_session_id=None):
        pass

    monkeypatch.setattr(server_simple, "agent_background_task", fake_bg)
    monkeypatch.setattr(server_simple, "_background_tasks", {})
    monkeypatch.setattr(server_simple, "_message_queues", {})
    monkeypatch.setattr(server_simple, "_response_queues", {})
    monkeypatch.setattr(server_simple, "_team_identity_by_thread", {})
    monkeypatch.setattr(server_simple, "_trigger_actor_by_thread", {})
    monkeypatch.setattr(
        server_simple,
        "_resolve_team_identity",
        lambda _t: ("pilot", "SRE"),
    )
    monkeypatch.setattr(
        server_simple,
        "_fetch_auth_me",
        lambda _t: {"name": "Jane Doe", "email": "jane@example.com"},
    )

    client = TestClient(server_simple.app)
    with patch.object(
        server_simple, "create_investigation_stream", return_value=iter([])
    ):
        resp = client.post(
            "/investigate",
            json={"prompt": "test", "thread_id": "thread-web-actor"},
            headers={"Authorization": "Bearer sso-token"},
        )
    assert resp.status_code == 200
    assert server_simple._trigger_actor_by_thread["thread-web-actor"] == "Jane Doe"


def test_investigate_empty_actor_clears_thread(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import server_simple

    async def fake_bg(thread_id, resume_session_id=None):
        pass

    monkeypatch.setattr(server_simple, "agent_background_task", fake_bg)
    monkeypatch.setattr(server_simple, "_background_tasks", {})
    monkeypatch.setattr(server_simple, "_message_queues", {})
    monkeypatch.setattr(server_simple, "_response_queues", {})
    monkeypatch.setattr(server_simple, "_team_identity_by_thread", {})
    monkeypatch.setattr(
        server_simple, "_trigger_actor_by_thread", {"thread-clear-actor": "Old"}
    )
    monkeypatch.setattr(
        server_simple,
        "_resolve_team_identity",
        lambda _t: ("pilot", "SRE"),
    )
    monkeypatch.setattr(server_simple, "_fetch_auth_me", lambda _t: {})

    client = TestClient(server_simple.app)
    with patch.object(
        server_simple, "create_investigation_stream", return_value=iter([])
    ):
        resp = client.post(
            "/investigate",
            json={
                "prompt": "test",
                "thread_id": "thread-clear-actor",
                "trigger_actor": "   ",
            },
            headers={"Authorization": "Bearer minted-token"},
        )
    assert resp.status_code == 200
    assert "thread-clear-actor" not in server_simple._trigger_actor_by_thread
