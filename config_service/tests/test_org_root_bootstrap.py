"""Unit tests for org root auto-bootstrap on first team create."""

from unittest.mock import MagicMock, patch

import pytest
from src.db.models import NodeType, OrgNode
from src.db.repository import _resolve_team_parent_id, ensure_org_root_node


def _scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def test_ensure_org_root_node_creates_when_missing():
    session = MagicMock()
    session.execute.return_value = _scalar_result(None)

    with patch("src.db.config_repository.get_or_create_node_configuration") as mock_cfg:
        root = ensure_org_root_node(session, org_id="pilot")

    assert root.node_id == "root"
    assert root.parent_id is None
    assert root.node_type == NodeType.org
    session.add.assert_called_once()
    mock_cfg.assert_called_once()


def test_ensure_org_root_node_idempotent_when_exists():
    existing = OrgNode(
        org_id="pilot",
        node_id="root",
        parent_id=None,
        node_type=NodeType.org,
        name="Root Org",
    )
    session = MagicMock()
    session.execute.return_value = _scalar_result(existing)

    root = ensure_org_root_node(session, org_id="pilot")

    assert root is existing
    session.add.assert_not_called()


def test_resolve_team_parent_id_bootstraps_root_for_parent_root():
    session = MagicMock()

    with patch("src.db.repository.ensure_org_root_node") as mock_ensure:
        parent_id = _resolve_team_parent_id(
            session,
            org_id="pilot",
            parent_id="root",
            node_type=NodeType.team,
        )

    assert parent_id == "root"
    mock_ensure.assert_called_once_with(session, org_id="pilot", root_id="root")


def test_resolve_team_parent_id_null_team_parents_under_root():
    session = MagicMock()
    root = OrgNode(
        org_id="pilot",
        node_id="root",
        parent_id=None,
        node_type=NodeType.org,
        name="Root Org",
    )

    with patch(
        "src.db.repository.ensure_org_root_node", return_value=root
    ) as mock_ensure:
        parent_id = _resolve_team_parent_id(
            session,
            org_id="pilot",
            parent_id=None,
            node_type=NodeType.team,
        )

    assert parent_id == "root"
    mock_ensure.assert_called_once_with(session, org_id="pilot", root_id="root")


def test_resolve_team_parent_id_raises_for_missing_non_root_parent():
    session = MagicMock()
    session.execute.return_value = _scalar_result(None)

    with pytest.raises(ValueError, match="Parent not found: missing"):
        _resolve_team_parent_id(
            session,
            org_id="pilot",
            parent_id="missing",
            node_type=NodeType.team,
        )
