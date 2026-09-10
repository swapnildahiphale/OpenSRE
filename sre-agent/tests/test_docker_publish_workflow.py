"""Static checks for .github/workflows/docker-publish.yml supply-chain hardening."""

import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "docker-publish.yml"

USES_SHA_RE = re.compile(
    r"^\s+uses:\s+[\w-]+/[\w-]+@[0-9a-f]{40}(?:\s+#.*)?$"
)
PERM_KEY_RE = re.compile(r"^  ([\w-]+):\s+(\w+)\s*$")


def _workflow_text() -> str:
    assert WORKFLOW.is_file(), f"missing workflow: {WORKFLOW}"
    return WORKFLOW.read_text()


def _permissions_block(text: str) -> dict[str, str]:
    perms: dict[str, str] = {}
    in_perms = False
    for line in text.splitlines():
        if line.strip() == "permissions:":
            in_perms = True
            continue
        if not in_perms:
            continue
        match = PERM_KEY_RE.match(line)
        if match:
            perms[match.group(1)] = match.group(2)
            continue
        if line.strip():
            break
    return perms


def _build_push_step_block(text: str) -> str:
    lines = text.splitlines()
    start = next(
        i for i, line in enumerate(lines) if line.strip() == "- name: Build and push"
    )
    block: list[str] = [lines[start]]
    for line in lines[start + 1 :]:
        if line.startswith("      - name:"):
            break
        block.append(line)
    return "\n".join(block)


def test_all_uses_pinned_to_full_sha():
    text = _workflow_text()
    uses_lines = [
        (i + 1, line)
        for i, line in enumerate(text.splitlines())
        if re.search(r"\buses:", line)
    ]
    assert uses_lines, "expected at least one uses: line"
    for line_no, line in uses_lines:
        assert USES_SHA_RE.match(line), (
            f"line {line_no}: unpinned or invalid uses: {line.strip()}"
        )


def test_permissions_limited_for_publish():
    perms = _permissions_block(_workflow_text())
    assert perms.get("contents") == "read"
    assert perms.get("id-token") == "write"
    assert perms.get("attestations") == "write"
    assert "actions" not in perms


def test_build_push_enables_provenance():
    block = _build_push_step_block(_workflow_text())
    assert re.search(r"^\s+id:\s+push\s*$", block, re.MULTILINE)
    assert re.search(r"^\s+provenance:\s+true\s*$", block, re.MULTILINE)


def test_attest_build_provenance_step_exists():
    text = _workflow_text()
    assert "actions/attest-build-provenance@" in text
    assert "subject-digest: ${{ steps.push.outputs.digest }}" in text
    assert "push-to-registry: true" in text
