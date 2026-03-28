"""Knowledge graph context node -- queries Neo4j for service topology."""

import logging

logger = logging.getLogger(__name__)


def kg_context(state: dict) -> dict:
    """Query Neo4j knowledge graph for service topology and dependencies.

    Graceful degradation if Neo4j is unavailable.
    """
    alert = state.get("alert", {})

    try:
        from tools.neo4j_semantic_layer import KubernetesGraphTools

        kg = KubernetesGraphTools()
        if kg.graph is None:
            logger.warning("[KG] Neo4j not available, skipping context enrichment")
            return {"kg_context": {"available": False}}

        context = kg.get_alert_context(alert)
        logger.info(
            f"[KG] Retrieved context for service: {context.get('service_name', 'unknown')}"
        )

        return {"kg_context": {"available": True, **context}}

    except Exception as e:
        logger.warning(f"[KG] Failed to query knowledge graph: {e}")
        return {"kg_context": {"available": False, "error": str(e)}}
