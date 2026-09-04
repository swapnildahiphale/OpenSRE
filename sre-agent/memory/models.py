"""Data models for the episodic memory system (Neo4j-backed)."""

from typing import List, Optional

from pydantic import BaseModel


class Component(BaseModel):
    """A typed affected subject. `type` is free-form (service, jenkins_job, deployment, ...)."""

    type: str
    name: str

    def key(self) -> str:
        return f"{self.type}:{self.name}"


class KeyFinding(BaseModel):
    skill: str = ""
    query: str = ""
    finding: str = ""


class Episode(BaseModel):
    """One investigation episode == one conversation (correlation_id). See spec §1.1."""

    episode_id: str
    correlation_id: str
    agent_run_id: Optional[str] = None

    org_id: str = "default"
    team_node_id: Optional[str] = None

    issue_type: str = "unknown"
    issue_description: str = ""
    severity: Optional[str] = None

    components: List[Component] = []

    skills_used: List[str] = []
    key_findings: List[KeyFinding] = []
    resolved: bool = False
    root_cause: Optional[str] = None
    summary: str = ""
    effectiveness_score: float = 0.1
    extraction_status: str = "ok"

    duration_seconds: Optional[float] = None
    created_at: str = ""
    updated_at: str = ""

    embedding: List[float] = []


class Strategy(BaseModel):
    strategy_id: str
    org_id: str = "default"
    team_node_id: Optional[str] = None
    issue_type: str = "unknown"
    component_key: str = ""
    strategy_text: str = ""
    source_episode_ids: List[str] = []
    episode_count: int = 0
    generated_at: str = ""
