"""Custom LLM playbook synthesis, cached as a :Strategy node. Spec §6.4."""

import hashlib
import logging
from datetime import datetime, timezone
from typing import List

from .extraction import llm_text_completion
from .models import Component, Episode, Strategy
from .retrieval import ScoredEpisode

logger = logging.getLogger(__name__)


class StrategyGenerator:
    def __init__(self, store, min_episodes: int = 2):
        self._store = store
        self.min_episodes = min_episodes

    @staticmethod
    def build_prompt(
        issue_type: str, component_key: str, episodes: List[Episode]
    ) -> str:
        lines = []
        for i, ep in enumerate(episodes, 1):
            status = "RESOLVED" if ep.resolved else "UNRESOLVED"
            skills = ", ".join(ep.skills_used[:5]) or "none recorded"
            lines.append(
                f"Episode {i} [{status}] (effectiveness {ep.effectiveness_score:.1f}):\n"
                f"  Root cause: {ep.root_cause or 'not identified'}\n"
                f"  Skills used: {skills}\n"
                f"  Summary: {ep.summary}"
            )
        body = "\n\n".join(lines)
        return (
            f'Analyze these {len(episodes)} past investigations of "{issue_type}" affecting '
            f'"{component_key}" and produce a concise investigation strategy.\n\n{body}\n\n'
            "Return a markdown playbook with these sections:\n"
            "1. **Common Root Causes** — patterns across episodes\n"
            "2. **Recommended Investigation Steps** — ordered by effectiveness\n"
            "3. **Key Skills / Commands** — what worked\n"
            "4. **Anti-patterns** — approaches that did NOT help (draw from UNRESOLVED / low-effectiveness episodes)\n\n"
            "Be specific and actionable. Under 300 words.\nStrategy:"
        )

    def get_or_generate(
        self,
        org_id: str,
        team_node_id,
        issue_type: str,
        components: List[Component],
        episodes: List[ScoredEpisode],
    ) -> str:
        eps = [se.episode for se in episodes]
        if len(eps) < self.min_episodes:
            return ""
        component_key = components[0].key() if components else "unknown"
        strategy_text = llm_text_completion(
            self.build_prompt(issue_type, component_key, eps), max_tokens=500
        )
        if not strategy_text:
            return ""
        sid = hashlib.sha1(
            f"{org_id}|{team_node_id}|{issue_type}|{component_key}".encode()
        ).hexdigest()[:32]
        try:
            self._store.upsert_strategy(
                Strategy(
                    strategy_id=sid,
                    org_id=org_id,
                    team_node_id=team_node_id,
                    issue_type=issue_type,
                    component_key=component_key,
                    strategy_text=strategy_text,
                    source_episode_ids=[e.episode_id for e in eps],
                    episode_count=len(eps),
                    generated_at=datetime.now(timezone.utc).isoformat(),
                )
            )
        except Exception as e:
            logger.error("[MEMORY] strategy cache write failed: %s", e)
        return strategy_text
