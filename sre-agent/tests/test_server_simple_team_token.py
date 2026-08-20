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
