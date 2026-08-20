from progress_text import build_progress_text
from state import InvestigationState, ThoughtSection, ToolCall


def test_empty_state_shows_investigating():
    text = build_progress_text(InvestigationState(thread_id="t"))
    assert "Investigating" in text


def test_current_thought_is_last():
    state = InvestigationState(thread_id="t")
    state.thoughts.append(ThoughtSection(text="Older thought", completed=True))
    state.thoughts.append(ThoughtSection(text="Live thought", completed=False))
    text = build_progress_text(state)
    assert text.index("Older thought") < text.index("Live thought")
    assert (
        text.rstrip().endswith("Live thought")
        or "Live thought" in text.split("\n")[-1]
        or (text.rfind("Live thought") > text.rfind("Older thought"))
    )


def test_nests_bash_under_skill_not_raw_command():
    state = InvestigationState(thread_id="t")
    th = ThoughtSection(text="Using k8s skill", completed=False)
    th.tools.append(
        ToolCall(
            name="Skill",
            input={"skill": "infrastructure-kubernetes"},
            running=False,
            success=True,
        )
    )
    th.tools.append(
        ToolCall(
            name="Bash",
            input={
                "command": (
                    "python /tmp/x/.claude/skills/infrastructure-kubernetes/"
                    "scripts/list_pods.py -n default"
                )
            },
            running=False,
            success=True,
        )
    )
    state.thoughts.append(th)
    text = build_progress_text(state)
    assert "infrastructure-kubernetes" in text
    assert (
        "list_pods.py" not in text or "↳" in text
    )  # nested as count, not top-level script dump
    assert "python /tmp" not in text
    # Top-level should not show a bare Bash line with full path
    assert "Bash `python" not in text


def test_plan_tools_collapsed_to_plan_line():
    state = InvestigationState(thread_id="t")
    th = ThoughtSection(text="Creating both tasks now.", completed=True)
    th.tools.append(
        ToolCall(
            name="TaskCreate",
            input={"subject": "Run kubectl get pods in the default namespace"},
            running=False,
            success=True,
        )
    )
    th.tools.append(
        ToolCall(
            name="TaskCreate",
            input={"subject": "Run kubectl get services in the default namespace"},
            running=False,
            success=True,
        )
    )
    state.thoughts.append(th)
    text = build_progress_text(state)
    assert "Plan:" in text
    assert "TaskCreate" not in text


def test_completed_thought_collapses_many_tools():
    state = InvestigationState(thread_id="t")
    th = ThoughtSection(text="Done exploring", completed=True)
    for i, name in enumerate(["Glob", "Read", "Grep"]):
        th.tools.append(
            ToolCall(
                name=name,
                input={"pattern": f"*.{i}", "file_path": f"/a/{i}.md"},
                running=False,
                success=True,
            )
        )
    state.thoughts.append(th)
    text = build_progress_text(state)
    assert "Used 3 tools" in text
    assert "Glob" not in text


def _done(name, **inp):
    return ToolCall(name=name, input=inp, running=False, success=True)


def test_progress_collapses_like_one_on_one():
    """Channel UpdateActivity uses the same string as 1:1: collapse old, nest Bash."""
    older = ThoughtSection(text="I'll validate Kubernetes connectivity", completed=True)
    older.tools = [
        _done("Skill", skill="infrastructure-kubernetes", args="list namespaces"),
        _done("Bash", command="python .claude/skills/k8s/scripts/list_namespaces.py"),
    ]
    live = ThoughtSection(text="Checking cluster-info", completed=False)
    live.tools = [
        _done("Skill", skill="infrastructure-kubernetes", args="e2e"),
        *[
            _done("Bash", command=c)
            for c in (
                "python .claude/skills/k8s/scripts/list_namespaces.py",
                "kubectl auth can-i --list",
                "kubectl version --short",
                "kubectl cluster-info",
            )
        ],
    ]
    text = build_progress_text(
        InvestigationState(thread_id="t", thoughts=[older, live])
    )
    assert "list_namespaces.py" not in text
    assert "kubectl auth can-i" not in text
    assert "Used 1 tool" in text
    assert "↳ 4 commands" in text

    many = ThoughtSection(text="Still working", completed=False)
    many.tools = [_done("Read", file_path=f"/tmp/file{i}.md") for i in range(5)]
    clipped = build_progress_text(InvestigationState(thread_id="t", thoughts=[many]))
    assert "+2 more" in clipped
    assert "file0.md" not in clipped
    assert "file4.md" in clipped


def test_shows_background_waiting_label():
    state = InvestigationState(thread_id="t")
    state.thoughts.append(ThoughtSection(text="Delegating work", completed=False))
    state.background_waiting_label = "Waiting on 2 background agent(s)…"
    text = build_progress_text(state)
    assert "Waiting on 2 background agent(s)…" in text


def test_shows_background_notification():
    state = InvestigationState(thread_id="t")
    state.thoughts.append(ThoughtSection(text="Delegating work", completed=False))
    state.background_notification = "Background agent finished: Redis healthy"
    text = build_progress_text(state)
    assert "Background agent finished: Redis healthy" in text


def test_live_clutter_scenario_readable():
    """Regression shape from Web Chat live test."""
    state = InvestigationState(thread_id="t")
    t1 = ThoughtSection(text="Creating both tasks now.", completed=True)
    t1.tools.append(
        ToolCall(
            name="TaskCreate", input={"subject": "pods"}, running=False, success=True
        )
    )
    t1.tools.append(
        ToolCall(
            name="TaskCreate",
            input={"subject": "services"},
            running=False,
            success=True,
        )
    )
    t2 = ThoughtSection(
        text="Delegating to the Kubernetes subagent now.", completed=False
    )
    t2.tools.append(
        ToolCall(
            name="Skill",
            input={"skill": "infrastructure-kubernetes", "args": "list resources"},
            running=False,
            success=True,
        )
    )
    t2.tools.append(
        ToolCall(
            name="Bash",
            input={
                "command": (
                    "python3 << 'EOF'\nfrom kubernetes import client\n"
                    "print('long')\nEOF"
                )
            },
            running=False,
            success=False,
        )
    )
    t2.tools.append(
        ToolCall(
            name="Agent",
            input={"subagent_type": "kubernetes", "description": "Check pods"},
            running=True,
        )
    )
    state.thoughts.extend([t1, t2])
    text = build_progress_text(state)
    assert "Creating both tasks now." in text
    assert "Delegating to the Kubernetes subagent now." in text
    assert text.rfind("Delegating") > text.rfind("Creating both")
    assert "TaskCreate" not in text
    assert "from kubernetes import client" not in text
    assert "infrastructure-kubernetes" in text
    assert "kubernetes: Check pods" in text
