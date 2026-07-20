"""Unit tests for the canonical prompt-change -> config-patch builder.

The builder is the single shape consumer shared by both approve paths
(team.py HTTP endpoint and repository.approve_pending_change). It must accept
the canonical proposed_value shape that real producers emit
({"agent", "prompt", ...metadata}) and never crash / never write phantom
agents for malformed input.
"""

from src.db.config_repository import build_agent_prompt_patch


def test_canonical_single_agent():
    result = build_agent_prompt_patch({"agent": "investigator", "prompt": "NEW"})
    assert result == {"agents": {"investigator": {"prompt": {"system": "NEW"}}}}


def test_ignores_ai_pipeline_metadata_keys():
    # The AI pipeline (and the team UI) attach metadata alongside agent/prompt.
    # Only agent + prompt may influence the written config — never title/
    # confidence/evidence (which would otherwise become phantom agent entries).
    result = build_agent_prompt_patch(
        {
            "agent": "kubernetes",
            "prompt": "Be concise.",
            "title": "Tighten k8s prompt",
            "confidence": 0.9,
            "evidence": [{"quote": "x"}],
            "source": "ai_pipeline",
        }
    )
    assert result == {"agents": {"kubernetes": {"prompt": {"system": "Be concise."}}}}


def test_null_prompt_passes_through_as_system_none():
    # A reset/delete proposes a null prompt; it must reach system=None, not crash.
    result = build_agent_prompt_patch({"agent": "investigator", "prompt": None})
    assert result == {"agents": {"investigator": {"prompt": {"system": None}}}}


def test_bare_string_is_safe_noop():
    # The legacy admin gate stored a bare string; approving it must not raise.
    assert build_agent_prompt_patch("just a string") == {"agents": {}}


def test_missing_agent_is_safe_noop():
    assert build_agent_prompt_patch({"prompt": "no agent id"}) == {"agents": {}}


def test_blank_agent_is_safe_noop():
    assert build_agent_prompt_patch({"agent": "", "prompt": "x"}) == {"agents": {}}


def test_none_is_safe_noop():
    assert build_agent_prompt_patch(None) == {"agents": {}}


def test_empty_dict_is_safe_noop():
    assert build_agent_prompt_patch({}) == {"agents": {}}


def test_no_flat_or_legacy_keys_leak():
    result = build_agent_prompt_patch({"agent": "investigator", "prompt": "P"})
    assert "agent_prompts" not in result
    assert "custom_prompts" not in result
    # legacy {agent_id: text} map shape is no longer treated as agent ids
    assert "custom_prompt" not in result["agents"]
