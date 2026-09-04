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


def test_safe_json_strips_fence_and_trailing_comma():
    from memory.extraction import _safe_json

    raw = '```json\n{"issue_type": "crashloop-backoff", "resolved": false,}\n```'
    assert _safe_json(raw)["issue_type"] == "crashloop-backoff"


def test_safe_json_empty_is_empty_dict():
    from memory.extraction import _safe_json

    assert _safe_json("") == {}
    assert _safe_json("not json") == {}


def test_extract_investigation_marks_failed_when_llm_returns_garbage(monkeypatch):
    import memory.extraction as ex

    monkeypatch.setattr(ex, "llm_text_completion", lambda *a, **k: "Expecting comma")
    out = ex.extract_investigation("prompt here", "result text " * 20, [])
    assert out.status == "failed"
    assert out.issue_type == "unknown"
    assert out.root_cause is None


def test_extract_investigation_ok_when_json_parses(monkeypatch):
    import memory.extraction as ex

    monkeypatch.setattr(
        ex,
        "llm_text_completion",
        lambda *a, **k: '{"issue_type":"crashloop-backoff","issue_description":"pods down","severity":"warning","components":[],"root_cause":"oom","resolved":true,"summary":"oom"}',
    )
    out = ex.extract_investigation("pods crashing", "OOMKilled " * 10, [])
    assert out.status == "ok"
    assert out.issue_type == "crashloop-backoff"
    assert out.root_cause == "oom"


def test_llm_uses_output_config_on_anthropic(monkeypatch):
    import memory.extraction as ex

    captured = {}

    class FakeMsg:
        content = [type("B", (), {"type": "text", "text": '{"issue_type":"x"}'})()]

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return FakeMsg()

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(ex, "_structured_cap", "json_schema")
    monkeypatch.setenv("MEMORY_LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(ex, "_anthropic_client", lambda: FakeClient())
    ex.llm_text_completion("p", json_schema=ex.EXTRACTION_JSON_SCHEMA)
    assert captured["output_config"]["format"]["type"] == "json_schema"


def test_llm_demotes_after_unsupported_format(monkeypatch):
    import memory.extraction as ex

    class Boom(Exception):
        status_code = 400

    calls = {"n": 0}

    class FakeMessages:
        def create(self, **kwargs):
            calls["n"] += 1
            if "output_config" in kwargs:
                raise Boom("output_config not supported")
            return type(
                "M",
                (),
                {"content": [type("B", (), {"type": "text", "text": '{"ok":true}'})()]},
            )()

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(ex, "_structured_cap", "json_schema")
    monkeypatch.setenv("MEMORY_LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(ex, "_anthropic_client", lambda: FakeClient())
    text = ex.llm_text_completion("p", json_schema=ex.EXTRACTION_JSON_SCHEMA)
    assert calls["n"] == 2
    assert ex._structured_cap == "prompt"
    assert "ok" in text


def test_llm_demotes_after_extra_body_rejected(monkeypatch):
    import memory.extraction as ex

    class Bad400(Exception):
        status_code = 400

    calls = {"n": 0}

    class FakeMessages:
        def create(self, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise TypeError("unexpected keyword argument 'output_config'")
            if calls["n"] == 2:
                if "extra_body" not in kwargs:
                    raise AssertionError("expected extra_body on second call")
                raise Bad400("output_config not supported")
            if "output_config" in kwargs or "extra_body" in kwargs:
                raise AssertionError("demoted call must not use structured output")
            return type(
                "M",
                (),
                {"content": [type("B", (), {"type": "text", "text": '{"ok":true}'})()]},
            )()

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(ex, "_structured_cap", "json_schema")
    monkeypatch.setenv("MEMORY_LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(ex, "_anthropic_client", lambda: FakeClient())
    text = ex.llm_text_completion("p", json_schema=ex.EXTRACTION_JSON_SCHEMA)
    assert calls["n"] == 3
    assert ex._structured_cap == "prompt"
    assert "ok" in text


def test_extract_retries_once_on_empty(monkeypatch):
    import memory.extraction as ex

    n = {"c": 0}

    def fake(prompt, max_tokens=300, json_schema=None):
        n["c"] += 1
        if n["c"] == 1:
            return ""
        return '{"issue_type":"latency-spike","issue_description":"slow","severity":null,"components":[],"root_cause":"idx","resolved":true,"summary":"index"}'

    monkeypatch.setattr(ex, "llm_text_completion", fake)
    out = ex.extract_investigation("slow checkout", "missing index " * 10, [])
    assert n["c"] == 2
    assert out.status == "ok"
    assert out.root_cause == "idx"


def test_extract_does_not_retry_on_broken_json(monkeypatch):
    import memory.extraction as ex

    n = {"c": 0}

    def fake(*a, **k):
        n["c"] += 1
        return "not-json {"

    monkeypatch.setattr(ex, "llm_text_completion", fake)
    out = ex.extract_investigation("p", "result " * 20, [])
    assert n["c"] == 1
    assert out.status == "failed"
