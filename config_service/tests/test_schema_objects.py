from src.db.models import NodeType


def test_node_type_enum_values():
    assert NodeType.org.value == "org"
    assert NodeType.team.value == "team"
