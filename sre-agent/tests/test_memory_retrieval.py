import os
import uuid

import pytest

pytest.importorskip("neo4j")
pytest.importorskip("neo4j_graphrag")
pytestmark = pytest.mark.skipif(not os.getenv("NEO4J_URI"), reason="needs Neo4j")


@pytest.fixture
def seeded():
    from memory.embeddings import get_default_embedder
    from memory.models import Component, Episode
    from memory.neo4j_conn import NEO4J_DATABASE, get_driver
    from memory.store import EpisodeStore

    drv = get_driver()
    with drv.session(database=NEO4J_DATABASE) as s:
        s.run("MATCH (e:Episode) DETACH DELETE e")
        s.run(
            "MERGE (:Service {name: 'checkout'})"
        )  # topology node for :AFFECTED linking
    store = EpisodeStore()
    store.ensure_schema()
    emb = get_default_embedder()

    def mk(cid, org, desc):
        return Episode(
            episode_id=str(uuid.uuid4()),
            correlation_id=cid,
            org_id=org,
            team_node_id="t1",
            issue_type="db",
            issue_description=desc,
            components=[Component(type="service", name="checkout")],
            resolved=True,
            root_cause="rc",
            summary=desc,
            effectiveness_score=0.8,
            created_at="2026-07-04T00:00:00Z",
            updated_at="2026-07-04T00:00:00Z",
            embedding=emb.embed(desc),
        )

    store.upsert_episode(
        mk("c-pool", "acme", "database connection pool exhausted on checkout")
    )
    store.upsert_episode(mk("c-dns", "acme", "dns resolution failure for upstream"))
    store.upsert_episode(
        mk("c-other", "globex", "database connection pool exhausted")
    )  # other tenant
    return store


def test_semantic_search_surfaces_shape_similar(seeded):
    from memory.retrieval import EpisodeRetriever

    r = EpisodeRetriever()
    hits = r.search("connection pool exhaustion", org_id="acme", team_node_id="t1", k=2)
    assert hits, "expected at least one hit"
    assert hits[0].episode.correlation_id == "c-pool"
    assert "checkout" in hits[0].services


def test_tenant_isolation(seeded):
    from memory.retrieval import EpisodeRetriever

    r = EpisodeRetriever()
    hits = r.search("connection pool exhausted", org_id="acme", team_node_id="t1", k=10)
    assert all(h.episode.org_id == "acme" for h in hits)
    assert "c-other" not in [h.episode.correlation_id for h in hits]


def test_self_exclusion(seeded):
    from memory.retrieval import EpisodeRetriever

    r = EpisodeRetriever()
    hits = r.search(
        "connection pool exhausted",
        org_id="acme",
        team_node_id="t1",
        exclude_correlation_id="c-pool",
        k=10,
    )
    assert "c-pool" not in [h.episode.correlation_id for h in hits]
