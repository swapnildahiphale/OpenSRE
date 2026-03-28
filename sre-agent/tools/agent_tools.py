"""Tool registry — maps config tool names to LangChain tool objects."""

import logging

from langchain_core.tools import BaseTool

from .skill_tools import DEFAULT_SKILLS_DIR, make_load_skill, make_run_script

logger = logging.getLogger(__name__)


def resolve_tools(
    agent_name: str,
    enabled_skills: set[str] | None,
    skills_dir: str = DEFAULT_SKILLS_DIR,
) -> list[BaseTool]:
    """Build the tool list for a subagent based on its config.

    Every agent gets load_skill + run_script (scoped to their enabled skills).
    These two tools replace Claude SDK's Skill + Bash tools.

    Args:
        agent_name: Agent identifier (for logging).
        enabled_skills: Set of allowed skill names for this agent, or None for all.
        skills_dir: Path to skills directory.

    Returns:
        List of LangChain BaseTool objects.
    """
    tools: list[BaseTool] = []

    # Core tools every agent gets: load_skill + run_script
    load_skill = make_load_skill(enabled_skills, skills_dir)
    run_script = make_run_script(enabled_skills, skills_dir)
    tools.append(load_skill)
    tools.append(run_script)

    logger.info(
        f"[TOOLS] Resolved {len(tools)} tools for agent '{agent_name}' "
        f"(skills: {'all' if enabled_skills is None else len(enabled_skills)})"
    )

    return tools


def get_skill_catalog(
    enabled_skills: set[str] | None,
    skills_dir: str = DEFAULT_SKILLS_DIR,
) -> str:
    """Build a text catalog of available skills for inclusion in system prompts.

    Lists skill names and descriptions so the agent knows what to load_skill.

    Args:
        enabled_skills: Set of allowed skill names, or None for all.
        skills_dir: Path to skills directory.

    Returns:
        Markdown-formatted skill catalog string.
    """
    import re
    from pathlib import Path

    skills_path = Path(skills_dir)
    if not skills_path.is_dir():
        return "No skills available."

    lines = [
        "## Available Skills\n",
        "Use `load_skill(name)` to load a skill's methodology, then `run_script(command)` to execute its scripts.\n",
    ]

    for skill_dir in sorted(skills_path.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue

        dir_name = skill_dir.name
        fm_name = dir_name
        description = ""

        try:
            text = skill_md.read_text(encoding="utf-8")
            match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
            if match:
                for line in match.group(1).splitlines():
                    if line.startswith("name:"):
                        fm_name = line.split(":", 1)[1].strip()
                    elif line.startswith("description:"):
                        description = line.split(":", 1)[1].strip()
        except Exception:
            pass

        # Filter by enabled skills
        if enabled_skills is not None:
            if fm_name not in enabled_skills and dir_name not in enabled_skills:
                continue

        if description:
            lines.append(f"- **{fm_name}**: {description}")
        else:
            lines.append(f"- **{fm_name}**")

    return "\n".join(lines)
