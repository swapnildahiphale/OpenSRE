#!/usr/bin/env python3
"""
Integration test for Enhanced Config-Driven Agent Building.

Tests the complete implementation:
1. Config loading with new fields (ModelConfig, max_turns)
2. Backward compatibility
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_config_loading():
    """Test that config loads correctly with new fields."""
    from config import AgentConfig, ModelConfig

    # Create an AgentConfig with all new fields
    agent = AgentConfig(
        enabled=True,
        name="test",
        model=ModelConfig(name="opus"),
        max_turns=50,
    )

    assert agent.model.name == "opus"
    assert agent.max_turns == 50
    print("✅ Config loading with new fields works!")


def test_backward_compatibility():
    """Test that old configs without new fields still work."""
    from config import AgentConfig, PromptConfig, ToolsConfig

    # Old-style config without model, max_turns
    agent = AgentConfig(
        name="old_agent",
        enabled=True,
        prompt=PromptConfig(system="Test prompt"),
        tools=ToolsConfig(enabled=["*"]),
    )

    # New fields should have defaults
    assert agent.model.name == "claude-sonnet-4-6"
    assert agent.max_turns is None

    print("✅ Backward compatibility maintained!")


def test_complete_integration():
    """Test complete integration with mock config."""
    print("\n🧪 Testing complete integration...")

    # Create a mock config as config_service would provide
    config_data = {
        "agents": {
            "planner": {
                "enabled": True,
                "model": {"name": "opus"},
                "max_turns": 50,
                "prompt": {
                    "system": "You are a planner agent",
                },
                "tools": {"enabled": ["*"]},
            },
            "investigation": {
                "enabled": True,
                "max_turns": 40,
                "prompt": {
                    "system": "You are an investigator",
                },
            },
            "k8s": {
                "enabled": True,
                "prompt": {
                    "system": "You are a k8s specialist",
                },
            },
            "metrics": {
                "enabled": True,
                "prompt": {
                    "system": "You are a metrics analyst",
                },
            },
        }
    }

    # Parse agents as config.py would
    from config import AgentConfig, ModelConfig, PromptConfig, ToolsConfig

    agents = {}
    for name, cfg in config_data["agents"].items():
        model_data = cfg.get("model", {})
        prompt_data = cfg.get("prompt", {})
        tools_data = cfg.get("tools", {})

        agents[name] = AgentConfig(
            enabled=cfg.get("enabled", True),
            name=name,
            model=ModelConfig(name=model_data.get("name", "claude-sonnet-4-6")),
            max_turns=cfg.get("max_turns"),
            prompt=PromptConfig(
                system=prompt_data.get("system", ""),
            ),
            tools=ToolsConfig(
                enabled=tools_data.get("enabled", ["*"]),
                disabled=tools_data.get("disabled", []),
            ),
        )

    # Verify agents were parsed correctly
    assert len(agents) == 4
    assert agents["planner"].model.name == "opus"
    assert agents["planner"].max_turns == 50
    assert agents["investigation"].max_turns == 40
    assert agents["k8s"].max_turns is None

    print(f"  ✅ Loaded {len(agents)} agents")
    print(f"  ✅ Planner has {agents['planner'].max_turns} max_turns")
    print(f"  ✅ Planner model: {agents['planner'].model.name}")

    print("\n✅ Complete integration test passed!")


if __name__ == "__main__":
    print("=" * 60)
    print("Enhanced Config Integration Tests")
    print("=" * 60)

    try:
        test_config_loading()
        test_backward_compatibility()
        test_complete_integration()

        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
