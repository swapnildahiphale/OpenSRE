def test_component_key():
    from memory.models import Component

    assert (
        Component(type="service", name="payment-service").key()
        == "service:payment-service"
    )


def test_episode_minimal_and_defaults():
    from memory.models import Component, Episode

    ep = Episode(
        episode_id="e1",
        correlation_id="c1",
        org_id="acme",
        issue_type="latency-spike",
        issue_description="checkout slow",
        components=[Component(type="service", name="checkout")],
        resolved=False,
        summary="investigating",
        effectiveness_score=0.1,
        created_at="2026-07-04T00:00:00Z",
        updated_at="2026-07-04T00:00:00Z",
        embedding=[0.0] * 384,
    )
    assert ep.correlation_id == "c1"
    assert ep.components[0].name == "checkout"
    assert ep.severity is None and ep.root_cause is None


def test_agent_experience_is_gone():
    import memory.models as m

    assert not hasattr(m, "AgentExperience")
