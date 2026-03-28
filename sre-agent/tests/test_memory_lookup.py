"""Tests for nodes/memory_lookup.py — episodic memory search node."""

from unittest.mock import patch

from nodes.memory_lookup import memory_lookup


class TestMemoryLookup:
    @patch("nodes.memory_lookup.enhance_investigation_with_memory")
    def test_similar_episodes_found(self, mock_enhance):
        """When memory returns enhanced prompt, has_similar_episodes should be True."""
        original = "HighErrorRate: Error rate above 5%"
        enhanced = f"## Past Episodes\n- Episode 1: similar issue\n\n{original}"
        mock_enhance.return_value = enhanced

        state = {
            "alert": {
                "name": "HighErrorRate",
                "service": "payment-service",
                "description": "Error rate above 5%",
            }
        }
        result = memory_lookup(state)

        assert result["memory_context"]["has_similar_episodes"] is True
        assert result["memory_context"]["enhanced_prompt"] == enhanced
        mock_enhance.assert_called_once_with(
            prompt="HighErrorRate: Error rate above 5%",
            service_name="payment-service",
            alert_type="HighErrorRate",
        )

    @patch("nodes.memory_lookup.enhance_investigation_with_memory")
    def test_no_similar_episodes(self, mock_enhance):
        """When memory returns same prompt (no enhancement), has_similar_episodes should be False."""
        search_text = "LowDiskSpace: Disk usage above 90%"
        mock_enhance.return_value = search_text  # Returns unchanged prompt

        state = {
            "alert": {
                "name": "LowDiskSpace",
                "service": "storage",
                "description": "Disk usage above 90%",
            }
        }
        result = memory_lookup(state)

        assert result["memory_context"]["has_similar_episodes"] is False
        assert result["memory_context"]["enhanced_prompt"] == ""

    @patch("nodes.memory_lookup.enhance_investigation_with_memory")
    def test_memory_service_failure(self, mock_enhance):
        """When memory service throws, node should handle gracefully."""
        mock_enhance.side_effect = Exception("Connection refused to config-service")

        state = {
            "alert": {
                "name": "HighCPU",
                "service": "compute",
                "description": "CPU above 95%",
            }
        }
        result = memory_lookup(state)

        assert result["memory_context"]["has_similar_episodes"] is False
        assert result["memory_context"]["enhanced_prompt"] == ""
        assert "error" in result["memory_context"]
        assert "Connection refused" in result["memory_context"]["error"]

    @patch("nodes.memory_lookup.enhance_investigation_with_memory")
    def test_empty_alert(self, mock_enhance):
        """With empty alert, should still call memory with empty strings."""
        # Empty alert: name="" and description="" (falsy), so search_text = str({}) = "{}"
        mock_enhance.return_value = "{}"

        state = {"alert": {}}
        result = memory_lookup(state)

        mock_enhance.assert_called_once_with(
            prompt="{}",
            service_name="",
            alert_type="",
        )

    @patch("nodes.memory_lookup.enhance_investigation_with_memory")
    def test_alert_without_description_uses_str(self, mock_enhance):
        """Alert without description falls back to str(alert)."""
        alert = {"name": "CustomAlert", "service": "my-svc"}
        search_text = str(alert)
        mock_enhance.return_value = search_text

        state = {"alert": alert}
        result = memory_lookup(state)

        # The node uses the formatted string: name + ": " + description
        # When description is empty, it does f"{alert_type}: {description}" which is "CustomAlert: "
        # But description="" is falsy, so it goes to str(alert) branch
        # Actually checking: description = alert.get("description", "") => ""
        # "" is falsy, so search_text = str(alert)
        mock_enhance.assert_called_once_with(
            prompt=str(alert),
            service_name="my-svc",
            alert_type="CustomAlert",
        )

    @patch("nodes.memory_lookup.enhance_investigation_with_memory")
    def test_returns_dict_with_memory_context_key(self, mock_enhance):
        """Return value should be a dict with exactly 'memory_context' key."""
        mock_enhance.return_value = "unchanged"

        state = {"alert": {"name": "test", "description": "unchanged"}}
        result = memory_lookup(state)

        assert set(result.keys()) == {"memory_context"}
        assert isinstance(result["memory_context"], dict)
