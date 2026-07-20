"""Task 2: Verify direct Anthropic env and no LiteLLM/LangChain in engine."""

import os
import pathlib


def test_no_litellm_imports_in_engine():
    """The SDK engine must not depend on LiteLLM/LangChain provider plumbing."""
    import agent
    import config

    src = open(agent.__file__).read() + open(config.__file__).read()
    assert "litellm" not in src.lower()
    assert "langchain" not in src.lower()
    assert "build_llm" not in src


def test_no_langchain_in_memory_package():
    """
    No file under sre-agent/memory/ may import langchain, build_llm, or litellm.

    langchain-neo4j lives in tools/neo4j_semantic_layer.py and is out of scope here.
    """
    memory_dir = pathlib.Path(__file__).parent.parent / "memory"
    assert memory_dir.is_dir(), f"memory/ directory not found at {memory_dir}"

    violations: list[str] = []
    for py_file in sorted(memory_dir.rglob("*.py")):
        src = py_file.read_text()
        src_lower = src.lower()
        if "langchain" in src_lower:
            violations.append(f"{py_file.name}: contains 'langchain'")
        if "build_llm" in src:
            violations.append(f"{py_file.name}: contains 'build_llm'")
        if "litellm" in src_lower:
            violations.append(f"{py_file.name}: contains 'litellm'")

    assert not violations, "Forbidden tokens found in memory/ package:\n" + "\n".join(
        violations
    )


def test_anthropic_key_documented():
    # Path relative to sre-agent root (cwd when tests run)
    env_example = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..",
        ".env.example",
    )
    text = open(os.path.normpath(env_example)).read()
    assert "ANTHROPIC_API_KEY" in text
    assert "LITELLM_BASE_URL" not in text
