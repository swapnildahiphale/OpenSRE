# sre-agent/tests/test_no_legacy_branding.py
import base64
import pathlib
import subprocess

# repo root = two levels up from sre-agent/tests/
REPO = pathlib.Path(__file__).resolve().parents[2]

_THIS_FILE = pathlib.Path(__file__).name

# Patterns are base64-encoded so this guard test does not reintroduce banned strings.
_LEGACY_PATTERNS = [
    base64.b64decode("aW5jaWRlbnRmb3g=").decode(),
    base64.b64decode("aW5jaWRlbnQtZm94").decode(),
]

_EXCLUDES = [
    "--exclude-dir=.git",
    "--exclude-dir=node_modules",
    "--exclude-dir=.next",
    "--exclude-dir=.venv",
    "--exclude-dir=venv",
    "--exclude-dir=worktrees",
    "--exclude-dir=__pycache__",
    "--exclude-dir=.pytest_cache",
    "--exclude-dir=superpowers",  # eng design docs are exempt (named dir)
    "--exclude-dir=.superpowers",  # eng design docs (dotdir variant)
    "--exclude-dir=.claude",  # internal harness dir
    "--exclude-dir=.entire",  # internal scratch dir
    "--exclude=*.lock",
    "--exclude=uv.lock",
    "--exclude=package-lock.json",
    f"--exclude={_THIS_FILE}",
]


def test_no_legacy_branding_in_content():
    grep_args = ["grep", "-rIli"]
    for pattern in _LEGACY_PATTERNS:
        grep_args.extend(["-e", pattern])
    grep_args.extend([*_EXCLUDES, "."])

    res = subprocess.run(
        grep_args,
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    hits = [line for line in res.stdout.splitlines() if line.strip()]
    assert not hits, "Legacy branding in file contents:\n" + "\n".join(hits)


def test_no_legacy_branding_in_paths():
    path_globs = " -o ".join(f"-iname '*{p}*'" for p in _LEGACY_PATTERNS)
    find_cmd = (
        "find . \\( -path ./.git -o -path '*/node_modules/*' -o -path '*/worktrees/*' "
        f"-o -path '*/.venv/*' -o -path '*/.pytest_cache/*' -o -name '{_THIS_FILE}' "
        f"-o -name '{_THIS_FILE.replace('.py', '')}*.pyc' \\) -prune "
        f"-o {path_globs} -print"
    )
    res = subprocess.run(
        ["bash", "-lc", find_cmd],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    hits = [line for line in res.stdout.splitlines() if line.strip()]
    assert not hits, "Legacy branding in path names:\n" + "\n".join(hits)
