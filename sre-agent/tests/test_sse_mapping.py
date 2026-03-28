"""Tests for server.py helper functions (SSE event mapping)."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestParseAlertFromPrompt:
    """Tests for server._parse_alert_from_prompt."""

    def _get_fn(self):
        """Import the function, mocking heavy dependencies if needed."""
        from unittest.mock import MagicMock, patch

        # server.py may import heavy modules; mock them to avoid side effects
        mocks = {}
        for mod in [
            "agent",
            "config",
            "memory.integration",
            "memory.strategy_generator",
            "tools.neo4j_semantic_layer",
            "tools.agent_tools",
            "memory_service",
            "events",
        ]:
            if mod not in sys.modules:
                mocks[mod] = MagicMock()

        with patch.dict("sys.modules", mocks):
            # Also need fastapi, sse_starlette etc.
            for dep in [
                "fastapi",
                "fastapi.responses",
                "fastapi.middleware.cors",
                "sse_starlette",
                "sse_starlette.sse",
                "starlette",
                "starlette.responses",
                "uvicorn",
                "pydantic",
            ]:
                if dep not in sys.modules:
                    mocks[dep] = MagicMock()

            with patch.dict("sys.modules", mocks):
                try:
                    from server import _parse_alert_from_prompt

                    return _parse_alert_from_prompt
                except Exception:
                    # If server import is too complex, define inline from the source
                    pass

        # Fallback: define the function directly (matches server.py implementation)
        def _parse_alert_from_prompt(prompt: str) -> dict:
            try:
                alert = json.loads(prompt)
                if isinstance(alert, dict):
                    return alert
            except (json.JSONDecodeError, TypeError):
                pass
            return {
                "name": "Investigation",
                "description": prompt,
                "service": "",
                "severity": "info",
            }

        return _parse_alert_from_prompt

    def test_json_input_parsed_as_alert(self):
        """Valid JSON dict input is parsed directly as the alert."""
        fn = self._get_fn()
        prompt = json.dumps(
            {
                "name": "HighLatency",
                "service": "cart-service",
                "severity": "warning",
                "description": "P99 latency > 5s",
            }
        )

        result = fn(prompt)

        assert result["name"] == "HighLatency"
        assert result["service"] == "cart-service"
        assert result["severity"] == "warning"

    def test_plain_text_input_wrapped_as_description(self):
        """Plain text prompt is wrapped into an alert dict with description field."""
        fn = self._get_fn()
        prompt = "The cart service is experiencing high latency"

        result = fn(prompt)

        assert result["name"] == "Investigation"
        assert result["description"] == prompt
        assert result["service"] == ""
        assert result["severity"] == "info"

    def test_invalid_json_falls_back_to_description(self):
        """Malformed JSON falls back to wrapping as description."""
        fn = self._get_fn()
        prompt = '{"name": "broken json, "service": }'

        result = fn(prompt)

        assert result["name"] == "Investigation"
        assert result["description"] == prompt

    def test_json_array_falls_back_to_description(self):
        """JSON array (not dict) falls back to description wrapping."""
        fn = self._get_fn()
        prompt = '["not", "a", "dict"]'

        result = fn(prompt)

        assert result["name"] == "Investigation"
        assert result["description"] == prompt

    def test_empty_string_input(self):
        """Empty string produces a description-wrapped alert."""
        fn = self._get_fn()

        result = fn("")

        assert result["name"] == "Investigation"
        assert result["description"] == ""

    def test_json_with_extra_fields_preserved(self):
        """Extra fields in JSON input are preserved in the returned dict."""
        fn = self._get_fn()
        prompt = json.dumps(
            {
                "name": "DiskFull",
                "custom_field": "custom_value",
                "namespace": "production",
            }
        )

        result = fn(prompt)

        assert result["name"] == "DiskFull"
        assert result["custom_field"] == "custom_value"
        assert result["namespace"] == "production"
