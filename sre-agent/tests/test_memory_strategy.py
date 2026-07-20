from memory.models import Component, Episode


def _ep(cid, rc, resolved):
    return Episode(
        episode_id=cid,
        correlation_id=cid,
        org_id="acme",
        issue_type="db-pool",
        issue_description="d",
        components=[Component(type="service", name="checkout")],
        resolved=resolved,
        root_cause=rc,
        summary="s",
        effectiveness_score=0.8,
        created_at="t",
        updated_at="t",
    )


def test_build_prompt_has_required_sections():
    from memory.strategy import StrategyGenerator

    p = StrategyGenerator.build_prompt(
        "db-pool",
        "service:checkout",
        [_ep("a", "rc1", True), _ep("b", "rc2", True)],
    )
    for section in [
        "Common Root Causes",
        "Recommended Investigation Steps",
        "Key Skills",
        "Anti-patterns",
    ]:
        assert section in p


def test_get_or_generate_returns_empty_below_min(monkeypatch):
    from memory.strategy import StrategyGenerator

    gen = StrategyGenerator(store=object(), min_episodes=2)
    from memory.retrieval import ScoredEpisode

    one = [ScoredEpisode(_ep("a", "rc", True), 0.9, ["checkout"])]
    assert (
        gen.get_or_generate(
            "acme",
            "t1",
            "db-pool",
            [Component(type="service", name="checkout")],
            one,
        )
        == ""
    )
