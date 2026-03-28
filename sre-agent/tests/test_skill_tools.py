"""Tests for tools/skill_tools.py — load_skill and run_script factories."""

import stat

import pytest
from tools.skill_tools import _resolve_skill_dir, make_load_skill, make_run_script


@pytest.fixture
def skills_dir(tmp_path):
    """Create a temporary skills directory with two fake skills."""
    # Skill 1: infra-k8s with frontmatter and scripts
    skill1 = tmp_path / "infra-k8s"
    skill1.mkdir()
    (skill1 / "SKILL.md").write_text(
        "---\nname: kubernetes-debug\ndescription: Debug K8s issues\n---\n\n# Kubernetes Debug\nUse this skill to debug k8s."
    )
    scripts1 = skill1 / "scripts"
    scripts1.mkdir()
    script_file = scripts1 / "list_pods.sh"
    script_file.write_text("#!/bin/bash\necho 'pod-1 Running'")
    script_file.chmod(script_file.stat().st_mode | stat.S_IEXEC)

    # Skill 2: observability with no scripts
    skill2 = tmp_path / "observability-grafana"
    skill2.mkdir()
    (skill2 / "SKILL.md").write_text(
        "---\nname: grafana-dashboards\ndescription: Grafana analysis\n---\n\n# Grafana\nQuery dashboards."
    )

    return str(tmp_path)


class TestResolveSkillDir:
    def test_resolve_by_directory_name(self, skills_dir):
        result = _resolve_skill_dir("infra-k8s", skills_dir)
        assert result is not None
        assert result.name == "infra-k8s"

    def test_resolve_by_frontmatter_name(self, skills_dir):
        result = _resolve_skill_dir("kubernetes-debug", skills_dir)
        assert result is not None
        assert result.name == "infra-k8s"

    def test_resolve_nonexistent(self, skills_dir):
        result = _resolve_skill_dir("does-not-exist", skills_dir)
        assert result is None


class TestMakeLoadSkill:
    def test_loads_skill_md_content(self, skills_dir):
        load_skill = make_load_skill(None, skills_dir)
        result = load_skill.invoke({"skill_name": "infra-k8s"})
        assert "Kubernetes Debug" in result
        assert "Debug K8s issues" in result

    def test_lists_available_scripts(self, skills_dir):
        load_skill = make_load_skill(None, skills_dir)
        result = load_skill.invoke({"skill_name": "infra-k8s"})
        assert "Available Scripts" in result
        assert "list_pods.sh" in result

    def test_skill_without_scripts(self, skills_dir):
        load_skill = make_load_skill(None, skills_dir)
        result = load_skill.invoke({"skill_name": "observability-grafana"})
        assert "Grafana" in result
        assert "Available Scripts" not in result

    def test_rejects_disabled_skill(self, skills_dir):
        load_skill = make_load_skill({"other-skill"}, skills_dir)
        result = load_skill.invoke({"skill_name": "infra-k8s"})
        assert "not enabled" in result

    def test_none_enabled_skills_allows_all(self, skills_dir):
        load_skill = make_load_skill(None, skills_dir)
        result = load_skill.invoke({"skill_name": "infra-k8s"})
        assert "Kubernetes Debug" in result

    def test_enabled_skills_allows_listed(self, skills_dir):
        load_skill = make_load_skill({"infra-k8s"}, skills_dir)
        result = load_skill.invoke({"skill_name": "infra-k8s"})
        assert "Kubernetes Debug" in result

    def test_nonexistent_skill_returns_error(self, skills_dir):
        load_skill = make_load_skill(None, skills_dir)
        result = load_skill.invoke({"skill_name": "nonexistent"})
        assert "not found" in result


class TestMakeRunScript:
    def test_executes_command(self, skills_dir):
        run_script = make_run_script(None, skills_dir)
        result = run_script.invoke({"command": "echo hello"})
        assert "hello" in result

    def test_captures_stdout(self, skills_dir):
        run_script = make_run_script(None, skills_dir)
        result = run_script.invoke({"command": "echo stdout_output"})
        assert "stdout_output" in result

    def test_captures_stderr(self, skills_dir):
        run_script = make_run_script(None, skills_dir)
        result = run_script.invoke({"command": "echo stderr_output >&2"})
        assert "stderr_output" in result

    def test_handles_timeout(self, skills_dir):
        run_script = make_run_script(None, skills_dir)
        result = run_script.invoke({"command": "sleep 10", "timeout": 1})
        assert "timed out" in result

    def test_rejects_script_from_disabled_skill(self, skills_dir):
        run_script = make_run_script({"other-skill"}, skills_dir)
        cmd = f"bash {skills_dir}/.claude/skills/infra-k8s/scripts/list_pods.sh"
        # Build a command that references the skill via the .claude/skills path
        cmd = "bash .claude/skills/infra-k8s/scripts/list_pods.sh"
        result = run_script.invoke({"command": cmd})
        assert "not enabled" in result

    def test_no_output_returns_sentinel(self, skills_dir):
        run_script = make_run_script(None, skills_dir)
        result = run_script.invoke({"command": "true"})
        assert result == "(no output)"

    def test_nonzero_exit_code_reported(self, skills_dir):
        run_script = make_run_script(None, skills_dir)
        result = run_script.invoke({"command": "exit 42"})
        assert "exit code: 42" in result
