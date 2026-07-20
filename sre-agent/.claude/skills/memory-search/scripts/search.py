"""CLI: search memory. Prints JSON to stdout."""

import argparse
import json
import logging
import os
import sys
from pathlib import Path


# Skill scripts run from thread workspace copies; memory package lives at sre-agent root (/app).
def _find_sre_agent_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "memory" / "store.py").is_file():
            return parent
    fallback = Path("/app")
    return fallback if fallback.is_dir() else Path(__file__).resolve().parents[4]


_SRE_AGENT_ROOT = _find_sre_agent_root()
if str(_SRE_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRE_AGENT_ROOT))

logger = logging.getLogger(__name__)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--exclude-correlation-id", default=None)
    args = ap.parse_args()

    org = os.getenv("OPENSRE_TENANT_ID", "local")
    team = os.getenv("OPENSRE_TEAM_ID", "default")
    exclude = args.exclude_correlation_id or os.getenv("OPENSRE_CORRELATION_ID")

    try:
        from memory.extraction import extract_investigation
        from memory.retrieval import EpisodeRetriever
        from memory.store import EpisodeStore
        from memory.strategy import StrategyGenerator

        hits = EpisodeRetriever().search(
            args.query,
            org_id=org,
            team_node_id=team,
            exclude_correlation_id=exclude,
            k=args.limit,
        )
        logger.info("[MEMORY-SEARCH] query=%r hits=%d", args.query, len(hits))

        episodes = [
            {
                "correlation_id": h.episode.correlation_id,
                "issue_type": h.episode.issue_type,
                "root_cause": h.episode.root_cause,
                "resolved": h.episode.resolved,
                "summary": h.episode.summary,
                "skills_used": h.episode.skills_used,
                "services": h.services,
                "score": round(h.score, 4),
            }
            for h in hits
        ]

        strategy = ""
        if len(hits) >= 2:
            ext = extract_investigation(args.query, "", [])
            strategy = StrategyGenerator(store=EpisodeStore()).get_or_generate(
                org,
                team,
                ext.issue_type,
                ext.components,
                hits,
            )

        print(
            json.dumps(
                {
                    "success": True,
                    "result": {"episodes": episodes, "strategy": strategy},
                }
            )
        )
        return 0
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        return 0  # never hard-fail the agent's tool call


if __name__ == "__main__":
    sys.exit(main())
