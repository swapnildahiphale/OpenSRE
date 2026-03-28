"""Deep-merge utilities for configuration objects.

Implements N-level left-to-right deep merge where later entries override earlier ones.
"""

from typing import Any, Dict, List


def deep_merge_dicts(configs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Deep-merge a list of dicts left-to-right.

    For lists, the later list replaces the earlier one entirely (no set-union semantics).
    For dicts, keys are merged recursively. Scalars are overwritten by later values.
    """
    result: Dict[str, Any] = {}
    for config in configs:
        if not isinstance(config, dict):
            continue
        _merge_into(result, config)
    return result


def _merge_into(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _merge_into(base[key], value)
        else:
            # Lists and scalars: replace entirely
            base[key] = value
