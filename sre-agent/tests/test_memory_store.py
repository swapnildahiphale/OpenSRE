import os
import uuid

import pytest

pytest.importorskip("neo4j")
pytestmark = pytest.mark.skipif(not os.getenv("NEO4J_URI"), reason="needs Neo4j")


@pytest.fixture
def clean_store():
    from memory.neo4j_conn import NEO4J_DATABASE, get_driver
    from memory.store import EpisodeStore

    drv = get_driver()
    with drv.session(database=NEO4J_DATABASE) as s:
        s.run("MATCH (e:Episode) DETACH DELETE e")
        s.run("MATCH (st:Strategy) DETACH DELETE st")
        s.run("MERGE (:Service {name: 'checkout'})")
    store = EpisodeStore()
    store.ensure_schema()
    return store


def _episode(correlation_id, root_cause, resolved, score):
    from memory.models import Component, Episode

    return Episode(
        episode_id=str(uuid.uuid4()),
        correlation_id=correlation_id,
        org_id="acme",
        team_node_id="team1",
        issue_type="latency-spike",
        issue_description="checkout slow",
        components=[Component(type="service", name="checkout")],
        resolved=resolved,
        root_cause=root_cause,
        summary="s",
        effectiveness_score=score,
        created_at="2026-07-04T00:00:00Z",
        updated_at="2026-07-04T00:00:00Z",
        embedding=[0.01] * 384,
    )


def test_upsert_creates_one_episode_and_links_service(clean_store):
    from memory.neo4j_conn import NEO4J_DATABASE, get_driver

    clean_store.upsert_episode(_episode("c1", "redis", False, 0.4))
    with get_driver().session(database=NEO4J_DATABASE) as s:
        n = s.run(
            "MATCH (e:Episode {correlation_id:'c1'}) RETURN count(e) AS n"
        ).single()["n"]
        linked = s.run(
            "MATCH (:Episode {correlation_id:'c1'})-[:AFFECTED]->(x:Service {name:'checkout'}) "
            "RETURN count(x) AS n"
        ).single()["n"]
    assert n == 1 and linked == 1


def test_upsert_same_correlation_overwrites_not_appends(clean_store):
    from memory.neo4j_conn import NEO4J_DATABASE, get_driver

    clean_store.upsert_episode(_episode("c1", "redis", False, 0.4))
    clean_store.upsert_episode(_episode("c1", "missing DB index", True, 0.8))
    with get_driver().session(database=NEO4J_DATABASE) as s:
        rows = s.run(
            "MATCH (e:Episode {correlation_id:'c1'}) RETURN e.root_cause AS rc, e.resolved AS r"
        ).data()
    assert len(rows) == 1
    assert rows[0]["rc"] == "missing DB index" and rows[0]["r"] is True


def test_get_by_correlation_roundtrip(clean_store):
    clean_store.upsert_episode(_episode("c9", "dns", True, 0.8))
    got = clean_store.get_by_correlation("c9")
    assert (
        got is not None
        and got.root_cause == "dns"
        and got.issue_type == "latency-spike"
    )


def test_extraction_status_roundtrip(clean_store):
    ep = _episode("c-fail", None, False, 0.1)
    ep.extraction_status = "failed"
    clean_store.upsert_episode(ep)
    got = clean_store.get_by_correlation("c-fail")
    assert got is not None and got.extraction_status == "failed"
