def test_effectiveness_three_tiers():
    from memory.extraction import compute_effectiveness

    assert compute_effectiveness(True, "root cause found") == 0.8
    assert compute_effectiveness(True, None) == 0.4
    assert compute_effectiveness(True, "") == 0.4
    assert compute_effectiveness(False, "guess") == 0.1
    assert compute_effectiveness(False, None) == 0.1


def test_extract_skills_used_dedupes_and_orders():
    from memory.extraction import extract_skills_used

    calls = [
        {"tool_name": "Skill", "tool_input": {"skill": "metrics-analysis"}},
        {"tool_name": "Skill", "tool_input": {"skill": "infrastructure-kubernetes"}},
        {"tool_name": "Skill", "tool_input": {"skill": "metrics-analysis"}},
        {"tool_name": "Bash", "tool_input": {"command": "kubectl get pods"}},
    ]
    skills = extract_skills_used(calls)
    assert skills == ["metrics-analysis", "infrastructure-kubernetes"]


def test_extract_key_findings_shape():
    from memory.extraction import extract_key_findings

    calls = [
        {
            "tool_name": "Skill",
            "tool_input": {"skill": "metrics-analysis", "query": "cpu"},
            "tool_output": "CPU at 98% on node-3",
        }
    ]
    finds = extract_key_findings(calls)
    assert finds and finds[0].skill == "metrics-analysis" and "98%" in finds[0].finding
