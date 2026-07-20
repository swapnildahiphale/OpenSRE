"""Semantic retrieval over :Episode via neo4j-graphrag VectorCypherRetriever.

Uses post-filtering in the retrieval_query (tenant scope + self-exclusion): fetch a larger
top_k from the vector index, then filter + traverse. Reliable on Neo4j 2026.02 today; when
neo4j-graphrag exposes the Cypher 25 SEARCH clause (upstream issue #485) this can move to
in-index pre-filtering with the same public interface.
"""

import json
import logging
from typing import Optional

from neo4j_graphrag.retrievers import VectorCypherRetriever
from neo4j_graphrag.types import RetrieverResultItem

from .embeddings import Embedder, get_default_embedder
from .models import Component, Episode, KeyFinding
from .neo4j_conn import get_driver

logger = logging.getLogger(__name__)

_RETRIEVAL_QUERY = """
WITH node AS e, score
WHERE e.org_id = $org_id
  AND ($team_node_id IS NULL OR e.team_node_id = $team_node_id)
  AND ($exclude_cid IS NULL OR e.correlation_id <> $exclude_cid)
  AND ($issue_type IS NULL OR e.issue_type = $issue_type)
OPTIONAL MATCH (e)-[:AFFECTED]->(s:Service)
RETURN e.correlation_id AS correlation_id, e.episode_id AS episode_id,
       e.agent_run_id AS agent_run_id, e.org_id AS org_id, e.team_node_id AS team_node_id,
       e.issue_type AS issue_type, e.issue_description AS issue_description,
       e.severity AS severity, e.components_json AS components_json,
       e.skills_used AS skills_used, e.key_findings_json AS key_findings_json,
       e.resolved AS resolved, e.root_cause AS root_cause, e.summary AS summary,
       e.effectiveness_score AS effectiveness_score, e.duration_seconds AS duration_seconds,
       e.created_at AS created_at, e.updated_at AS updated_at,
       collect(s.name) AS services, score AS vscore
ORDER BY vscore DESC
"""


class ScoredEpisode:
    def __init__(self, episode: Episode, score: float, services: list[str]):
        self.episode = episode
        self.score = score
        self.services = services


class EpisodeRetriever:
    def __init__(
        self, embedder: Optional[Embedder] = None, index_name: str = "episode_embedding"
    ):
        self._embedder = embedder or get_default_embedder()
        self._retriever = VectorCypherRetriever(
            driver=get_driver(),
            index_name=index_name,
            retrieval_query=_RETRIEVAL_QUERY,
            # Return each record as a dict on .content (avoids repr/JSON round-tripping).
            result_formatter=lambda record: RetrieverResultItem(
                content=dict(record), metadata=None
            ),
        )

    def search(
        self,
        query_text: str,
        org_id: str,
        team_node_id: Optional[str],
        exclude_correlation_id: Optional[str] = None,
        issue_type: Optional[str] = None,
        k: int = 3,
        fetch_multiplier: int = 10,
    ) -> list["ScoredEpisode"]:
        try:
            qvec = self._embedder.embed(query_text)
            res = self._retriever.search(
                query_vector=qvec,
                top_k=max(k * fetch_multiplier, k),
                query_params={
                    "org_id": org_id,
                    "team_node_id": team_node_id,
                    "exclude_cid": exclude_correlation_id,
                    "issue_type": issue_type,
                },
            )
        except Exception as e:  # memory must never break the caller
            logger.error("[MEMORY] retrieval failed: %s", e)
            return []

        out: list[ScoredEpisode] = []
        for item in res.items:
            # result_formatter guarantees item.content is a dict.
            out.append(_to_scored(dict(item.content)))
            if len(out) >= k:
                break
        return out


def _to_scored(rec: dict) -> ScoredEpisode:
    comps = [Component(**c) for c in json.loads(rec.get("components_json") or "[]")]
    finds = [KeyFinding(**k) for k in json.loads(rec.get("key_findings_json") or "[]")]
    ep = Episode(
        episode_id=rec.get("episode_id", ""),
        correlation_id=rec.get("correlation_id", ""),
        agent_run_id=rec.get("agent_run_id"),
        org_id=rec.get("org_id", "default"),
        team_node_id=rec.get("team_node_id"),
        issue_type=rec.get("issue_type", "unknown"),
        issue_description=rec.get("issue_description", ""),
        severity=rec.get("severity"),
        components=comps,
        skills_used=list(rec.get("skills_used") or []),
        key_findings=finds,
        resolved=bool(rec.get("resolved", False)),
        root_cause=rec.get("root_cause"),
        summary=rec.get("summary", ""),
        effectiveness_score=float(rec.get("effectiveness_score", 0.1)),
        duration_seconds=rec.get("duration_seconds"),
        created_at=rec.get("created_at", ""),
        updated_at=rec.get("updated_at", ""),
        embedding=[],
    )
    services = [s for s in (rec.get("services") or []) if s]
    return ScoredEpisode(ep, float(rec.get("vscore", 0.0)), services)
