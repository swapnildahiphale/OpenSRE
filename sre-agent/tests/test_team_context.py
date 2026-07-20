from config import TeamConfig, TeamContextSection
from team_context import render_team_context_block


def test_empty_returns_empty_string():
    tc = TeamConfig(raw_config={})
    assert render_team_context_block(tc) == ""


def test_renders_sections_in_array_order():
    tc = TeamConfig(
        team_context=[
            TeamContextSection(
                id="vcs", title="Source Control", content="Primary VCS: **Bitbucket**"
            ),
            TeamContextSection(
                id="aws", title="AWS & EKS", content="Cluster `my-cluster`"
            ),
        ],
        raw_config={},
    )
    out = render_team_context_block(tc)
    assert "## Team Context" in out
    assert "### Source Control" in out
    assert "Bitbucket" in out
    assert "### AWS & EKS" in out
    assert out.index("Source Control") < out.index("AWS & EKS")


def test_skips_empty_content():
    tc = TeamConfig(
        team_context=[
            TeamContextSection(id="empty", title="Empty", content=""),
            TeamContextSection(id="x", title="Only", content="Has content"),
        ],
        raw_config={},
    )
    out = render_team_context_block(tc)
    assert "### Empty" not in out
    assert "### Only" in out


def test_custom_title_not_id():
    tc = TeamConfig(
        team_context=[
            TeamContextSection(
                id="helm_charts", title="Helm charts", content="Repo path `charts/`"
            ),
        ],
        raw_config={},
    )
    out = render_team_context_block(tc)
    assert "### Helm charts" in out


def test_legacy_business_context_fallback():
    tc = TeamConfig(team_context=[], raw_config={"business_context": "Legacy catalog"})
    out = render_team_context_block(tc)
    assert "Legacy catalog" in out
    assert "## Team Context" in out


def test_explicit_empty_sections_skips_legacy():
    tc = TeamConfig(
        team_context=[],
        raw_config={
            "team_context": {"sections": []},
            "business_context": "Legacy catalog",
        },
    )
    assert render_team_context_block(tc) == ""


def test_truncation_at_6000_chars():
    tc = TeamConfig(
        team_context=[
            TeamContextSection(id="big", title="Notes", content="x" * 7000),
        ],
        raw_config={},
    )
    out = render_team_context_block(tc)
    assert len(out) <= 6000 + len("...[truncated]")
    assert out.endswith("...[truncated]")
