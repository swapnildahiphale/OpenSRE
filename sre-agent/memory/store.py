"""Neo4j writer for :Episode / :Strategy. The ONLY module that writes episodic nodes."""

import json
import logging
from typing import Optional

from .models import Component, Episode, KeyFinding, Strategy
from .neo4j_conn import NEO4J_DATABASE, get_driver

logger = logging.getLogger(__name__)


class EpisodeStore:
    def __init__(self, embedding_dim: int = 384):
        self.embedding_dim = embedding_dim

    def _session(self):
        return get_driver().session(database=NEO4J_DATABASE)

    def ensure_schema(self) -> None:
        # neo4j-graphrag VectorCypherRetriever uses the Cypher 25 SEARCH clause.
        with self._session() as s:
            try:
                s.run(
                    f"ALTER DATABASE `{NEO4J_DATABASE}` SET DEFAULT LANGUAGE CYPHER 25"
                )
            except Exception as e:
                logger.warning(
                    "[MEMORY] could not set CYPHER 25 default language: %s", e
                )
            s.run(
                "CREATE CONSTRAINT episode_correlation IF NOT EXISTS "
                "FOR (e:Episode) REQUIRE e.correlation_id IS UNIQUE"
            )
            s.run(
                "CREATE CONSTRAINT strategy_id IF NOT EXISTS "
                "FOR (st:Strategy) REQUIRE st.strategy_id IS UNIQUE"
            )
            s.run(
                f"CREATE VECTOR INDEX episode_embedding IF NOT EXISTS "
                f"FOR (e:Episode) ON e.embedding "
                f"OPTIONS {{ indexConfig: {{ "
                f"`vector.dimensions`: {self.embedding_dim}, "
                f"`vector.similarity_function`: 'cosine' }} }}"
            )
        logger.info("[MEMORY] Neo4j schema ensured (constraint + vector index)")

    def upsert_episode(self, ep: Episode) -> None:
        props = {
            "episode_id": ep.episode_id,
            "agent_run_id": ep.agent_run_id,
            "org_id": ep.org_id,
            "team_node_id": ep.team_node_id,
            "issue_type": ep.issue_type,
            "issue_description": ep.issue_description,
            "severity": ep.severity,
            "components_json": json.dumps([c.model_dump() for c in ep.components]),
            "skills_used": ep.skills_used,
            "key_findings_json": json.dumps([k.model_dump() for k in ep.key_findings]),
            "resolved": ep.resolved,
            "root_cause": ep.root_cause,
            "summary": ep.summary,
            "effectiveness_score": ep.effectiveness_score,
            "duration_seconds": ep.duration_seconds,
            "extraction_status": ep.extraction_status or "ok",
            "created_at": ep.created_at,
            "updated_at": ep.updated_at,
            "embedding": ep.embedding,
        }
        service_names = [c.name for c in ep.components if c.type == "service"]
        with self._session() as s:
            s.run(
                """
                MERGE (e:Episode {correlation_id: $correlation_id})
                ON CREATE SET e.created_at = $props.created_at
                SET e += $props
                WITH e
                CALL (e) {
                    OPTIONAL MATCH (e)-[r:AFFECTED]->(:Service) DELETE r
                }
                WITH e
                UNWIND $service_names AS sname
                MATCH (svc:Service {name: sname})
                MERGE (e)-[:AFFECTED]->(svc)
                """,
                correlation_id=ep.correlation_id,
                props=props,
                service_names=service_names,
            )
        logger.info(
            "[MEMORY] upserted episode corr=%s services=%s",
            ep.correlation_id,
            service_names,
        )

    def get_by_correlation(self, correlation_id: str) -> Optional[Episode]:
        with self._session() as s:
            rec = s.run(
                "MATCH (e:Episode {correlation_id: $cid}) RETURN e AS e",
                cid=correlation_id,
            ).single()
        if not rec:
            return None
        return self._node_to_episode(dict(rec["e"]), correlation_id)

    def get_by_episode_id(
        self, episode_id: str, org_id: str, team_node_id: str
    ) -> Optional[Episode]:
        with self._session() as s:
            rec = s.run(
                """
                MATCH (e:Episode {episode_id: $eid, org_id: $org, team_node_id: $team})
                RETURN e AS e
                """,
                eid=episode_id,
                org=org_id,
                team=team_node_id,
            ).single()
        if not rec:
            return None
        n = dict(rec["e"])
        return self._node_to_episode(n, n.get("correlation_id", ""))

    @staticmethod
    def _node_to_episode(n: dict, correlation_id: str) -> Episode:
        comps = [Component(**c) for c in json.loads(n.get("components_json", "[]"))]
        finds = [KeyFinding(**k) for k in json.loads(n.get("key_findings_json", "[]"))]
        return Episode(
            episode_id=n.get("episode_id", ""),
            correlation_id=correlation_id,
            agent_run_id=n.get("agent_run_id"),
            org_id=n.get("org_id", "default"),
            team_node_id=n.get("team_node_id"),
            issue_type=n.get("issue_type", "unknown"),
            issue_description=n.get("issue_description", ""),
            severity=n.get("severity"),
            components=comps,
            skills_used=list(n.get("skills_used", [])),
            key_findings=finds,
            resolved=bool(n.get("resolved", False)),
            root_cause=n.get("root_cause"),
            summary=n.get("summary", ""),
            effectiveness_score=float(n.get("effectiveness_score", 0.1)),
            extraction_status=n.get("extraction_status") or "ok",
            duration_seconds=n.get("duration_seconds"),
            created_at=n.get("created_at", ""),
            updated_at=n.get("updated_at", ""),
            embedding=[],
        )

    def upsert_strategy(self, strat: Strategy) -> None:
        props = {
            "org_id": strat.org_id,
            "team_node_id": strat.team_node_id,
            "issue_type": strat.issue_type,
            "component_key": strat.component_key,
            "strategy_text": strat.strategy_text,
            "episode_count": strat.episode_count,
            "generated_at": strat.generated_at,
            "manually_edited": False,
            "updated_at": None,
        }
        with self._session() as s:
            s.run(
                """
                MERGE (st:Strategy {strategy_id: $sid})
                SET st += $props
                WITH st
                CALL (st) { OPTIONAL MATCH (st)-[r:DERIVED_FROM]->(:Episode) DELETE r }
                WITH st
                UNWIND $episode_ids AS eid
                MATCH (e:Episode {episode_id: eid})
                MERGE (st)-[:DERIVED_FROM]->(e)
                """,
                sid=strat.strategy_id,
                props=props,
                episode_ids=strat.source_episode_ids,
            )
        logger.info(
            "[MEMORY] upserted strategy %s (%d sources)",
            strat.strategy_id,
            strat.episode_count,
        )

    def update_strategy_text(
        self,
        strategy_id: str,
        strategy_text: str,
        *,
        org_id: str,
        team_node_id: Optional[str],
        updated_at: str,
    ) -> bool:
        """Update playbook text for a team strategy. Returns False if not found."""
        with self._session() as s:
            rec = s.run(
                """
                MATCH (st:Strategy {strategy_id: $sid, org_id: $org, team_node_id: $team})
                SET st.strategy_text = $text,
                    st.updated_at = $updated_at,
                    st.manually_edited = true
                RETURN st.strategy_id AS sid
                """,
                sid=strategy_id,
                org=org_id,
                team=team_node_id,
                text=strategy_text,
                updated_at=updated_at,
            ).single()
        if not rec:
            return False
        logger.info("[MEMORY] updated strategy text %s", strategy_id)
        return True

    def delete_strategy(
        self,
        strategy_id: str,
        *,
        org_id: str,
        team_node_id: Optional[str],
    ) -> bool:
        """Delete a strategy node and its relationships. Returns False if not found."""
        with self._session() as s:
            rec = s.run(
                """
                MATCH (st:Strategy {strategy_id: $sid, org_id: $org, team_node_id: $team})
                DETACH DELETE st
                RETURN $sid AS sid
                """,
                sid=strategy_id,
                org=org_id,
                team=team_node_id,
            ).single()
        if not rec:
            return False
        logger.info("[MEMORY] deleted strategy %s", strategy_id)
        return True
