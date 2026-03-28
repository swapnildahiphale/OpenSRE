"""Skill tools for LangGraph agents — load_skill and run_script."""

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Base skills directory (inside container or local dev)
DEFAULT_SKILLS_DIR = os.getenv(
    "SKILLS_DIR",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), ".claude", "skills"),
)


def _resolve_skill_dir(skill_name: str, skills_dir: str) -> Optional[Path]:
    """Find the skill directory by name (directory name or frontmatter name)."""
    skills_path = Path(skills_dir)
    # Direct directory match
    direct = skills_path / skill_name
    if direct.is_dir() and (direct / "SKILL.md").is_file():
        return direct
    # Search by frontmatter name
    for skill_dir in skills_path.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            text = skill_md.read_text(encoding="utf-8")
            import re

            match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
            if match:
                for line in match.group(1).splitlines():
                    if line.startswith("name:"):
                        fm_name = line.split(":", 1)[1].strip()
                        if fm_name == skill_name:
                            return skill_dir
        except Exception:
            continue
    return None


def make_load_skill(
    enabled_skills: set[str] | None, skills_dir: str = DEFAULT_SKILLS_DIR
):
    """Create a scoped load_skill tool that only loads allowed skills.

    Args:
        enabled_skills: Set of allowed skill names, or None for all skills.
        skills_dir: Path to skills directory.
    """

    @tool
    def load_skill(skill_name: str) -> str:
        """Load a skill's SKILL.md documentation to learn its methodology and available scripts.

        Use this tool to learn about a skill before running its scripts.
        Returns the full SKILL.md content with methodology, scripts list, and usage examples.

        Args:
            skill_name: Name of the skill to load (e.g., 'infrastructure-kubernetes').
        """
        # Check if skill is allowed
        if enabled_skills is not None and skill_name not in enabled_skills:
            return f"Error: Skill '{skill_name}' is not enabled for this agent."

        skill_dir = _resolve_skill_dir(skill_name, skills_dir)
        if not skill_dir:
            return f"Error: Skill '{skill_name}' not found in {skills_dir}."

        skill_md = skill_dir / "SKILL.md"
        try:
            content = skill_md.read_text(encoding="utf-8")
            # List available scripts
            scripts_dir = skill_dir / "scripts"
            scripts = []
            if scripts_dir.is_dir():
                scripts = sorted(f.name for f in scripts_dir.iterdir() if f.is_file())

            if scripts:
                content += "\n\n## Available Scripts\n"
                for s in scripts:
                    content += f"- `{scripts_dir / s}`\n"

            return content
        except Exception as e:
            return f"Error loading skill '{skill_name}': {e}"

    return load_skill


def make_run_script(
    enabled_skills: set[str] | None, skills_dir: str = DEFAULT_SKILLS_DIR
):
    """Create a scoped run_script tool that only runs scripts from allowed skills.

    Args:
        enabled_skills: Set of allowed skill names, or None for all skills.
        skills_dir: Path to skills directory.
    """

    @tool
    def run_script(command: str, timeout: int = 120) -> str:
        """Execute a skill script or shell command and return its output.

        Use this to run skill scripts (Python/Bash) that interact with infrastructure,
        APIs, and monitoring systems. Scripts are located in skill directories under
        .claude/skills/{skill-name}/scripts/.

        Args:
            command: The full command to execute (e.g., 'python .claude/skills/infrastructure-kubernetes/scripts/list_pods.py -n default').
            timeout: Maximum execution time in seconds (default 120).
        """
        # Validate the command references an allowed skill if it's a skill script
        skills_path = Path(skills_dir)
        if str(skills_path) in command or ".claude/skills/" in command:
            # Extract skill directory name from command
            import re

            match = re.search(r"\.claude/skills/([^/]+)/", command)
            if match:
                skill_dir_name = match.group(1)
                # Check if this skill is allowed
                if enabled_skills is not None:
                    # Check both directory name and resolved frontmatter name
                    skill_dir = _resolve_skill_dir(skill_dir_name, skills_dir)
                    if skill_dir is None:
                        return f"Error: Skill '{skill_dir_name}' not found."
                    # Check against enabled set using directory name or frontmatter name
                    skill_md = skill_dir / "SKILL.md"
                    fm_name = skill_dir_name
                    try:
                        text = skill_md.read_text(encoding="utf-8")
                        fm_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
                        if fm_match:
                            for line in fm_match.group(1).splitlines():
                                if line.startswith("name:"):
                                    fm_name = line.split(":", 1)[1].strip()
                                    break
                    except Exception:
                        pass
                    if (
                        fm_name not in enabled_skills
                        and skill_dir_name not in enabled_skills
                    ):
                        return f"Error: Skill '{skill_dir_name}' is not enabled for this agent."

        try:
            # Determine cwd: use the app root so relative paths like
            # .claude/skills/... resolve correctly. skills_dir is typically
            # /app/.claude/skills — we want /app as cwd.
            cwd = None
            skills_path_obj = Path(skills_dir)
            if skills_path_obj.is_dir():
                # Walk up from skills_dir to find the app root (parent of .claude)
                for parent in [skills_path_obj] + list(skills_path_obj.parents):
                    if parent.name == ".claude":
                        cwd = str(parent.parent)
                        break
                if cwd is None:
                    # Fallback: two levels up from skills dir (.claude/skills -> app root)
                    cwd = str(skills_path_obj.parent.parent)

            # Fix "python" → "python3" for systems without unversioned python
            import shutil

            actual_command = command
            if (
                command.startswith("python ") or " python " in command
            ) and not shutil.which("python"):
                actual_command = command.replace("python ", "python3 ", 1)

            result = subprocess.run(
                actual_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}" if output else result.stderr
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            return output if output else "(no output)"
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout} seconds."
        except Exception as e:
            return f"Error executing command: {e}"

    return run_script
