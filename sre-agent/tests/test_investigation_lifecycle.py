def test_investigation_guidance_append_always():
    import investigation_lifecycle as il

    block = il.investigation_guidance_append()
    assert "memory-search" in block
    assert "infrastructure-neo4j" in block
    assert "todo" in block.lower()
    assert "episodic" not in block.lower()
    assert len(block) > 100


def test_memory_system_prompt_append_always():
    import investigation_lifecycle as il

    block = il.memory_system_prompt_append()
    assert "memory-search" in block
    assert "infrastructure-neo4j" in block


def test_build_enhanced_prompt_removed():
    import investigation_lifecycle as il

    assert not hasattr(il, "build_enhanced_prompt")


def test_finalize_consolidates_via_prior(monkeypatch):
    import investigation_lifecycle as il
    from memory.models import Episode

    captured = {}

    class FakeStore:
        def get_by_correlation(self, cid):
            return Episode(
                episode_id="e1",
                correlation_id=cid,
                org_id="acme",
                issue_type="db",
                issue_description="d",
                root_cause="redis",
                resolved=False,
                summary="s",
                effectiveness_score=0.1,
                created_at="t",
                updated_at="t",
            )

        def upsert_episode(self, ep):
            captured["ep"] = ep

    from memory.extraction import Extraction

    monkeypatch.setattr(il, "_store", FakeStore())
    monkeypatch.setattr(
        il,
        "extract_investigation",
        lambda *a, **k: Extraction(
            issue_type="db", root_cause="missing index", resolved=True, summary="fixed"
        ),
    )
    monkeypatch.setattr(il, "_embed_episode_text", lambda ep: [0.0] * 384)
    il.finalize_investigation(
        "c1",
        "run9",
        "checkout slow",
        "it was a missing index " * 5,
        [],
        org_id="acme",
        team_node_id="t1",
    )
    ep = captured["ep"]
    assert (
        ep.correlation_id == "c1"
        and ep.root_cause == "missing index"
        and ep.resolved is True
    )
    assert ep.effectiveness_score == 0.8 and ep.agent_run_id == "run9"
