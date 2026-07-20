#!/usr/bin/env python3
"""Query service topology and blast radius from the Neo4j knowledge graph."""

import argparse
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _find_sre_agent_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "tools" / "neo4j_semantic_layer.py").is_file():
            return parent
    fallback = Path("/app")
    return fallback if fallback.is_dir() else Path(__file__).resolve().parents[4]


_SRE_AGENT_ROOT = _find_sre_agent_root()
if str(_SRE_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRE_AGENT_ROOT))

from tools.neo4j_semantic_layer import KubernetesGraphTools  # noqa: E402


def _format_result(service: str, info: dict) -> dict:
    deploy = info.get("deployment") or {}
    upstream = info.get("upstream_dependents") or []
    downstream = info.get("downstream_dependencies") or []
    blast = info.get("blast_radius") or {}
    return {
        "service": service,
        "resolved_name": info.get("resolved_name", service),
        "deployment": deploy,
        "upstream_dependents": upstream,
        "downstream_dependencies": downstream,
        "blast_radius": {
            "upstream_count": blast.get("upstream_count", len(upstream)),
            "downstream_count": blast.get("downstream_count", len(downstream)),
            "affected_services": blast.get("affected_services")
            or [u.get("service") for u in upstream if u.get("service")],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Query KG topology for a service")
    parser.add_argument("--service", required=True, help="Service or deployment name")
    args = parser.parse_args()

    try:
        tools = KubernetesGraphTools()
        if not tools.driver:
            print(json.dumps({"success": False, "error": "Neo4j unavailable"}))
            return
        info = tools.get_service_information(args.service)
        if info.get("error"):
            print(json.dumps({"success": False, "error": info["error"]}))
            return
        result = _format_result(args.service, info)
        logger.info(
            "[KG-SEARCH] service=%s upstream=%d downstream=%d",
            result["resolved_name"],
            result["blast_radius"]["upstream_count"],
            result["blast_radius"]["downstream_count"],
        )
        print(json.dumps({"success": True, "result": result}, indent=2, default=str))
    except Exception as e:
        logger.warning("[KG-SEARCH] failed: %s", e)
        print(json.dumps({"success": False, "error": str(e)}))


if __name__ == "__main__":
    main()
