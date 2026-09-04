"""Tests for enhanced config loading (ModelConfig, max_turns)."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import AgentConfig, ModelConfig, PromptConfig, ToolsConfig


def test_model_config_defaults():
    """Test ModelConfig with default values."""
    model = ModelConfig()
    assert model.name == "claude-sonnet-4-6"


def test_agent_config_with_max_turns():
    """Test AgentConfig with max_turns."""
    agent = AgentConfig(
        name="test",
        enabled=True,
        max_turns=50,
    )
    assert agent.max_turns == 50


def test_agent_config_backward_compatibility():
    """Test that AgentConfig works without new fields (backward compatibility)."""
    # Old config without model, max_turns
    agent = AgentConfig(
        name="test",
        enabled=True,
        prompt=PromptConfig(system="You are a test agent"),
        tools=ToolsConfig(enabled=["*"], disabled=[]),
    )

    # New fields should have sensible defaults
    assert agent.model.name == "claude-sonnet-4-6"
    assert agent.max_turns is None


def test_agent_config_full_example():
    """Test AgentConfig with all fields populated."""
    agent = AgentConfig(
        enabled=True,
        name="investigator",
        prompt=PromptConfig(
            system="You are an SRE investigator",
        ),
        tools=ToolsConfig(
            enabled=["*"],
            disabled=["Write", "Edit"],
        ),
        model=ModelConfig(name="claude-sonnet-4-6"),
        max_turns=50,
    )

    assert agent.enabled is True
    assert agent.name == "investigator"
    assert agent.prompt.system == "You are an SRE investigator"
    assert agent.tools.disabled == ["Write", "Edit"]
    assert agent.model.name == "claude-sonnet-4-6"
    assert agent.max_turns == 50


def test_agent_config_max_turns_positive():
    """Test AgentConfig with positive max_turns."""
    agent = AgentConfig(name="test", max_turns=100)
    assert agent.max_turns == 100


def test_multiple_agents_with_different_configs():
    """Test creating multiple agents with different configurations."""
    # Planner with a non-default model
    planner = AgentConfig(
        name="planner",
        enabled=True,
        model=ModelConfig(name="opus"),
        max_turns=50,
    )

    # Investigation agent with default settings
    investigation = AgentConfig(
        name="investigation",
        enabled=True,
        max_turns=40,
    )

    # Specialized agents
    k8s = AgentConfig(name="k8s", enabled=True)
    metrics = AgentConfig(name="metrics", enabled=True)

    # Verify each agent has independent config
    assert planner.model.name == "opus"
    assert investigation.model.name == "claude-sonnet-4-6"
    assert k8s.max_turns is None
    assert metrics.max_turns is None


if __name__ == "__main__":
    print("=" * 60)
    print("Enhanced Config Tests")
    print("=" * 60)

    tests = [
        test_model_config_defaults,
        test_agent_config_with_max_turns,
        test_agent_config_backward_compatibility,
        test_agent_config_full_example,
        test_agent_config_max_turns_positive,
        test_multiple_agents_with_different_configs,
    ]

    for test in tests:
        try:
            test()
            print(f"✅ {test.__name__}")
        except AssertionError as e:
            print(f"❌ {test.__name__}: {e}")
            exit(1)

    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED!")
    print("=" * 60)
