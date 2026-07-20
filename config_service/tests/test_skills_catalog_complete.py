"""
Completeness + drift-guard tests for the built-in skills catalog.

These tests verify:
1. Catalog count matches on-disk skill directories (dynamic, not hardcoded).
2. Set of catalog IDs matches set of on-disk skill dir names containing SKILL.md.
3. Every skill has a non-empty category from the allowed category set.
4. Drift guard: running the generator's build_catalog() in-memory equals the
   committed BUILT_IN_SKILLS_METADATA (so the catalog can never silently fall
   behind the skills on disk).
"""

import importlib
from pathlib import Path

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

# Repo root is 2 levels above config_service/tests/ (i.e. the worktree root)
REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "sre-agent" / ".claude" / "skills"
GENERATOR_PATH = REPO_ROOT / "config_service" / "scripts" / "gen_skills_catalog.py"


def _on_disk_skill_ids():
    """Return the set of skill directory names that contain a SKILL.md file."""
    ids = set()
    for entry in SKILLS_DIR.iterdir():
        if entry.is_dir() and (entry / "SKILL.md").exists():
            ids.add(entry.name)
    return ids


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

ALLOWED_CATEGORIES = {
    "Core Methodology",
    "Memory",
    "Observability",
    "Infrastructure & Cloud",
    "Databases",
    "Incident Management",
    "Alerting & On-call",
    "Ticketing & Project",
    "Code & Version Control",
    "Docs & Knowledge",
    "Other Integrations",
}


def test_catalog_count_matches_disk():
    """get_skills_catalog() count equals number of on-disk skill dirs with SKILL.md."""
    from src.core.skills_catalog import get_skills_catalog

    on_disk = _on_disk_skill_ids()
    catalog = get_skills_catalog()
    assert catalog["count"] == len(on_disk), (
        f"Catalog has {catalog['count']} skills but {len(on_disk)} dirs on disk. "
        f"Missing: {on_disk - {s['id'] for s in catalog['skills']}}, "
        f"Extra: {{s['id'] for s in catalog['skills']}} - on_disk"
    )


def test_catalog_ids_match_disk():
    """Set of catalog ids equals set of on-disk skill dir names containing SKILL.md."""
    from src.core.skills_catalog import get_skills_catalog

    on_disk = _on_disk_skill_ids()
    catalog = get_skills_catalog()
    catalog_ids = {s["id"] for s in catalog["skills"]}

    missing = on_disk - catalog_ids
    extra = catalog_ids - on_disk

    assert not missing and not extra, (
        f"Catalog/disk mismatch. Missing from catalog: {sorted(missing)}. "
        f"In catalog but not on disk: {sorted(extra)}."
    )


def test_all_skills_have_valid_category():
    """Every skill in the catalog has a non-empty category from the allowed set."""
    from src.core.skills_catalog import get_skills_catalog

    catalog = get_skills_catalog()
    bad = []
    for skill in catalog["skills"]:
        cat = skill.get("category", "")
        if not cat or cat not in ALLOWED_CATEGORIES:
            bad.append((skill["id"], cat))

    assert not bad, (
        f"Skills with invalid/missing category: {bad}. "
        f"Allowed: {sorted(ALLOWED_CATEGORIES)}"
    )


def test_drift_guard():
    """Re-running the generator in-memory equals BUILT_IN_SKILLS_METADATA (drift guard)."""
    # Dynamically import the generator
    spec = importlib.util.spec_from_file_location("gen_skills_catalog", GENERATOR_PATH)
    gen_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen_module)

    generated = gen_module.build_catalog()

    from src.core.skills_catalog import BUILT_IN_SKILLS_METADATA

    gen_ids = {s["id"] for s in generated}
    committed_ids = {s["id"] for s in BUILT_IN_SKILLS_METADATA}

    missing = committed_ids - gen_ids
    extra = gen_ids - committed_ids

    assert not missing and not extra, (
        f"Drift detected. In committed but not generated: {sorted(missing)}. "
        f"Generated but not in committed: {sorted(extra)}."
    )

    # Compare field by field for each skill
    gen_by_id = {s["id"]: s for s in generated}
    committed_by_id = {s["id"]: s for s in BUILT_IN_SKILLS_METADATA}

    diffs = []
    for skill_id in sorted(gen_ids & committed_ids):
        g = gen_by_id[skill_id]
        c = committed_by_id[skill_id]
        for key in ("name", "description", "category", "required_integrations"):
            if g.get(key) != c.get(key):
                diffs.append(
                    f"  {skill_id}.{key}: generated={g.get(key)!r} vs committed={c.get(key)!r}"
                )

    assert not diffs, "Generator output differs from committed catalog:\n" + "\n".join(
        diffs
    )
