import os

import pytest

pytest.importorskip("neo4j")
pytestmark = pytest.mark.skipif(not os.getenv("NEO4J_URI"), reason="needs Neo4j")


def test_memory_stats_endpoint_shape():
    import server_simple
    from fastapi.testclient import TestClient

    client = TestClient(server_simple.app)
    r = client.get("/memory/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "total_episodes" in body["result"]


def test_memory_overview_endpoint_shape():
    import server_simple
    from fastapi.testclient import TestClient

    client = TestClient(server_simple.app)
    r = client.get("/memory/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    result = body["result"]
    for key in (
        "total_episodes",
        "resolved",
        "unresolved",
        "resolution_rate",
        "episodes_this_week",
        "issue_type_counts",
        "recent_episodes",
        "strategy_count",
        "latest_strategies",
    ):
        assert key in result
