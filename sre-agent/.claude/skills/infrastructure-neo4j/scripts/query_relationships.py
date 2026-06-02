#!/usr/bin/env python3
"""Query service relationships from Neo4j knowledge graph."""

import json
import os
import sys

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
    ),
)
from tools.neo4j_semantic_layer import KubernetesGraphTools


def main():
    service_name = sys.argv[1] if len(sys.argv) > 1 else None
    if not service_name:
        print(json.dumps({"error": "Usage: query_relationships.py <service-name>"}))
        sys.exit(1)

    try:
        tools = KubernetesGraphTools()
        result = tools.get_component_relationships(service_name)
        print(json.dumps({"success": True, "result": result}, indent=2, default=str))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
