# memory/models.py
"""Data models for episodic memory system."""

from typing import List, Optional

from pydantic import BaseModel


class InvestigationEpisode(BaseModel):
    """Investigation episode record."""

    episode_id: str
    alert_type: str = "unknown"
    service_name: str = "unknown"  # kept for backward compat, primary is 'services'
    agents_used: List[str] = []
    resolved: bool = False
    root_cause: Optional[str] = None
    effectiveness_score: float = 0.0

    # New fields for persistent storage
    agent_run_id: Optional[str] = None
    alert_description: Optional[str] = None
    severity: Optional[str] = None  # critical, warning, info
    services: List[str] = []  # replaces single service_name
    skills_used: List[str] = []
    key_findings: List[dict] = []  # [{skill, query, finding}]
    summary: Optional[str] = None
    confidence: Optional[float] = None
    duration_seconds: Optional[float] = None
    org_id: str = "default"
    team_node_id: Optional[str] = None
    created_at: Optional[str] = None


class AgentExperience(BaseModel):
    """Agent experience record."""

    experience_id: str
    agent_id: str
    service_name: str
    alert_type: str
    search_strategy: Optional[str] = None
    successful_queries: List[str] = []
    found_root_cause: bool
    root_cause_query: Optional[str] = None
    evidence_quality: str
    execution_time_seconds: float
    iterations: int
    confidence: float
