# sre-agent/tests/test_memory_e2e_conversation.py
import os

import pytest

pytest.importorskip("neo4j")
pytestmark = pytest.mark.skipif(not os.getenv("NEO4J_URI"), reason="needs Neo4j")


def test_multiturn_produces_one_episode_latest_wins(monkeypatch):
    import investigation_lifecycle as il
    from memory.extraction import Extraction
    from memory.models import Component
    from memory.neo4j_conn import NEO4J_DATABASE, get_driver

    with get_driver().session(database=NEO4J_DATABASE) as s:
        s.run("MATCH (e:Episode {correlation_id:'e2e-1'}) DETACH DELETE e")
    il.ensure_memory_schema()

    turns = iter(
        [
            Extraction(
                issue_type="latency-spike",
                issue_description="checkout slow",
                components=[Component(type="service", name="checkout")],
                root_cause="redis cache",
                resolved=False,
                summary="suspect redis",
            ),
            Extraction(
                issue_type="latency-spike",
                issue_description="checkout slow",
                components=[Component(type="service", name="checkout")],
                root_cause="missing DB index",
                resolved=True,
                summary="fixed via index",
            ),
        ]
    )
    monkeypatch.setattr(il, "extract_investigation", lambda *a, **k: next(turns))
    monkeypatch.setattr(il, "_embed_episode_text", lambda ep: [0.02] * 384)

    il.finalize_investigation(
        "e2e-1",
        "run1",
        "checkout slow",
        "looking at redis " * 5,
        [],
        org_id="acme",
        team_node_id="t1",
    )
    il.finalize_investigation(
        "e2e-1",
        "run2",
        "checkout slow",
        "added the index and it is fixed " * 3,
        [],
        org_id="acme",
        team_node_id="t1",
    )

    with get_driver().session(database=NEO4J_DATABASE) as s:
        rows = s.run(
            "MATCH (e:Episode {correlation_id:'e2e-1'}) "
            "RETURN e.root_cause AS rc, e.resolved AS r, e.effectiveness_score AS sc, "
            "e.agent_run_id AS run"
        ).data()
    assert len(rows) == 1
    assert rows[0]["rc"] == "missing DB index"
    assert rows[0]["r"] is True
    assert rows[0]["sc"] == 0.8
    assert rows[0]["run"] == "run2"  # latest turn's trace
