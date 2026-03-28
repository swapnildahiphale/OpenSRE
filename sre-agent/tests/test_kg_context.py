"""Tests for the kg_context node."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def sample_alert():
    return {"name": "HighLatency", "service": "cart-service", "severity": "warning"}


class TestKgContext:
    """Tests for nodes.kg_context.kg_context."""

    def test_available_neo4j_returns_context(self, sample_alert):
        """When Neo4j is available, returns context with available=True."""
        mock_kg = MagicMock()
        mock_kg.graph = MagicMock()  # non-None => available
        mock_kg.get_alert_context.return_value = {
            "service_name": "cart-service",
            "dependencies": ["redis", "postgres"],
        }
        mock_kg_cls = MagicMock(return_value=mock_kg)
        mock_module = MagicMock()
        mock_module.KubernetesGraphTools = mock_kg_cls

        with patch.dict("sys.modules", {"tools.neo4j_semantic_layer": mock_module}):
            from nodes.kg_context import kg_context

            result = kg_context({"alert": sample_alert})

        assert result["kg_context"]["available"] is True
        assert result["kg_context"]["service_name"] == "cart-service"
        assert result["kg_context"]["dependencies"] == ["redis", "postgres"]

    def test_unavailable_neo4j_returns_false(self, sample_alert):
        """When Neo4j graph is None, returns available=False gracefully."""
        mock_kg = MagicMock()
        mock_kg.graph = None
        mock_kg_cls = MagicMock(return_value=mock_kg)
        mock_module = MagicMock()
        mock_module.KubernetesGraphTools = mock_kg_cls

        with patch.dict("sys.modules", {"tools.neo4j_semantic_layer": mock_module}):
            from nodes.kg_context import kg_context

            result = kg_context({"alert": sample_alert})

        assert result["kg_context"]["available"] is False

    def test_handles_import_exception_gracefully(self, sample_alert):
        """When Neo4j import or connection raises, returns available=False."""
        with patch.dict("sys.modules", {"tools.neo4j_semantic_layer": None}):
            from nodes.kg_context import kg_context

            result = kg_context({"alert": sample_alert})

        assert result["kg_context"]["available"] is False
        assert "error" in result["kg_context"]

    def test_handles_runtime_exception_gracefully(self, sample_alert):
        """When get_alert_context raises, returns available=False with error."""
        mock_kg = MagicMock()
        mock_kg.graph = MagicMock()  # non-None
        mock_kg.get_alert_context.side_effect = RuntimeError("connection refused")
        mock_kg_cls = MagicMock(return_value=mock_kg)
        mock_module = MagicMock()
        mock_module.KubernetesGraphTools = mock_kg_cls

        with patch.dict("sys.modules", {"tools.neo4j_semantic_layer": mock_module}):
            from nodes.kg_context import kg_context

            result = kg_context({"alert": sample_alert})

        assert result["kg_context"]["available"] is False
        assert "connection refused" in result["kg_context"]["error"]
