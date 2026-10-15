"""Unit tests for recall tie-break (no Neo4j required)."""

from memory.models import Episode
from memory.retrieval import ScoredEpisode, recall_tie_break_rank


def _ep(**kwargs) -> Episode:
    defaults = dict(
        episode_id="e",
        correlation_id="c",
        issue_type="db",
        issue_description="",
        summary="",
        created_at="2026-09-16T00:00:00Z",
        updated_at="2026-09-16T00:00:00Z",
    )
    defaults.update(kwargs)
    return Episode(**defaults)


def test_recall_tie_break_confirmed_beats_diagnosis_resolved():
    confirmed = _ep(resolution_status="confirmed", resolved=True)
    diagnosis = _ep(resolution_status="open", resolved=True)
    open_unresolved = _ep(resolution_status="open", resolved=False)
    assert recall_tie_break_rank(confirmed) > recall_tie_break_rank(diagnosis)
    assert recall_tie_break_rank(diagnosis) > recall_tie_break_rank(open_unresolved)


def test_equal_score_sort_puts_confirmed_first():
    a = ScoredEpisode(_ep(correlation_id="diag", resolved=True), 0.9, [])
    b = ScoredEpisode(
        _ep(correlation_id="fix", resolved=True, resolution_status="confirmed"),
        0.9,
        [],
    )
    c = ScoredEpisode(_ep(correlation_id="open", resolved=False), 0.9, [])
    ranked = sorted(
        [a, c, b],
        key=lambda se: (se.score, recall_tie_break_rank(se.episode)),
        reverse=True,
    )
    assert [se.episode.correlation_id for se in ranked] == ["fix", "diag", "open"]


def test_strategy_prompt_marks_confirmed_and_abandoned():
    from memory.strategy import StrategyGenerator

    confirmed = _ep(
        resolution_status="confirmed",
        resolved=True,
        fix_summary="restarted redis",
        recommended_actions=["bump pool"],
    )
    abandoned = _ep(resolution_status="abandoned", resolved=False)
    prompt = StrategyGenerator.build_prompt("db", "checkout", [confirmed, abandoned])
    assert "CONFIRMED_FIX" in prompt
    assert "restarted redis" in prompt
    assert "bump pool" in prompt
    # abandoned labeled UNRESOLVED for anti-pattern section guidance
    assert prompt.count("UNRESOLVED") >= 1
    assert "never treat abandoned as a successful remediation" in prompt
