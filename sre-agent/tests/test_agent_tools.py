"""Tests for tools/agent_tools.py — tool registry and skill catalog."""

import pytest
from tools.agent_tools import get_skill_catalog, resolve_tools


@pytest.fixture
def skills_dir(tmp_path):
    """Create a temporary skills directory with fake skills."""
    skill1 = tmp_path / "infra-k8s"
    skill1.mkdir()
    (skill1 / "SKILL.md").write_text(
        "---\nname: kubernetes-debug\ndescription: Debug Kubernetes clusters\n---\n\n# K8s Debug"
    )
    scripts1 = skill1 / "scripts"
    scripts1.mkdir()
    (scripts1 / "list_pods.sh").write_text("#!/bin/bash\necho pods")

    skill2 = tmp_path / "observability-grafana"
    skill2.mkdir()
    (skill2 / "SKILL.md").write_text(
        "---\nname: grafana-dashboards\ndescription: Query Grafana dashboards\n---\n\n# Grafana"
    )

    skill3 = tmp_path / "metrics-prom"
    skill3.mkdir()
    (skill3 / "SKILL.md").write_text(
        "---\nname: prometheus-metrics\n---\n\n# Prometheus"
    )

    return str(tmp_path)


class TestResolveTools:
    def test_returns_two_tools(self, skills_dir):
        tools = resolve_tools("test-agent", None, skills_dir)
        assert len(tools) == 2

    def test_tool_names(self, skills_dir):
        tools = resolve_tools("test-agent", None, skills_dir)
        names = {t.name for t in tools}
        assert "load_skill" in names
        assert "run_script" in names

    def test_scoped_with_enabled_skills(self, skills_dir):
        tools = resolve_tools("test-agent", {"kubernetes-debug"}, skills_dir)
        assert len(tools) == 2  # Always returns both tools (scoping is internal)

    def test_returns_base_tool_instances(self, skills_dir):
        from langchain_core.tools import BaseTool

        tools = resolve_tools("test-agent", None, skills_dir)
        for t in tools:
            assert isinstance(t, BaseTool)


class TestGetSkillCatalog:
    def test_catalog_contains_all_skills(self, skills_dir):
        catalog = get_skill_catalog(None, skills_dir)
        assert "kubernetes-debug" in catalog
        assert "grafana-dashboards" in catalog
        assert "prometheus-metrics" in catalog

    def test_catalog_contains_descriptions(self, skills_dir):
        catalog = get_skill_catalog(None, skills_dir)
        assert "Debug Kubernetes clusters" in catalog
        assert "Query Grafana dashboards" in catalog

    def test_catalog_filters_by_enabled_skills(self, skills_dir):
        catalog = get_skill_catalog({"kubernetes-debug"}, skills_dir)
        assert "kubernetes-debug" in catalog
        assert "grafana-dashboards" not in catalog
        assert "prometheus-metrics" not in catalog

    def test_catalog_with_dir_name_in_enabled(self, skills_dir):
        catalog = get_skill_catalog({"infra-k8s"}, skills_dir)
        assert "kubernetes-debug" in catalog

    def test_catalog_header(self, skills_dir):
        catalog = get_skill_catalog(None, skills_dir)
        assert "Available Skills" in catalog
        assert "load_skill" in catalog

    def test_catalog_nonexistent_dir(self, tmp_path):
        catalog = get_skill_catalog(None, str(tmp_path / "nonexistent"))
        assert "No skills available" in catalog

    def test_catalog_empty_dir(self, tmp_path):
        empty = tmp_path / "empty_skills"
        empty.mkdir()
        catalog = get_skill_catalog(None, str(empty))
        # Should have header but no skill entries
        assert "Available Skills" in catalog
