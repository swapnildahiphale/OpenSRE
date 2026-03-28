import operator
from typing import Annotated, Any
from typing import Literal as TypingLiteral

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


def merge_dicts(left: dict, right: dict) -> dict:
    """Shallow merge — right overwrites left keys."""
    merged = left.copy()
    merged.update(right)
    return merged


def take_latest(left: Any, right: Any) -> Any:
    """Always take the newer value."""
    return right


class GraphState(TypedDict):
    """Complete investigation state flowing through the graph."""

    # --- Input ---
    alert: dict
    thread_id: str
    images: list[dict]
    # --- Context (set by early nodes) ---
    memory_context: Annotated[dict, take_latest]
    kg_context: Annotated[dict, take_latest]
    team_config: dict
    # --- Investigation tracking ---
    investigation_id: str
    agent_states: Annotated[dict, merge_dicts]
    messages: Annotated[list, operator.add]
    # --- Planner ---
    hypotheses: list[dict]
    selected_agents: list[str]
    # --- Results ---
    conclusion: str
    structured_report: dict
    # --- Control flow ---
    iteration: Annotated[int, take_latest]
    max_iterations: int
    max_react_loops: int
    status: Annotated[str, take_latest]


class Hypothesis(BaseModel):
    """A single investigation hypothesis."""

    hypothesis: str = Field(description="Description of potential root cause")
    priority: TypingLiteral["high", "medium", "low"] = Field(
        description="Priority level"
    )
    agents_to_test: list[str] = Field(
        description="Which agents should test this hypothesis"
    )


class InvestigationPlan(BaseModel):
    """Structured output from the planner."""

    hypotheses: list[Hypothesis] = Field(description="Ranked hypotheses to test")
    selected_agents: list[str] = Field(
        description="Agents to dispatch for investigation"
    )
    reasoning: str = Field(description="Brief explanation of investigation strategy")


class SynthesisDecision(BaseModel):
    """Structured output from the synthesizer."""

    sufficient_evidence: bool = Field(
        description="Whether there is enough evidence to conclude"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence level 0.0-1.0")
    summary: str = Field(description="Brief summary of combined findings")
    gaps: list[str] = Field(
        default_factory=list, description="Information gaps if insufficient"
    )
    feedback: str = Field(
        default="", description="Guidance for next investigation round"
    )


class AlertInput(BaseModel):
    """LangGraph Studio input schema."""

    alert: dict = Field(
        default={
            "name": "HighErrorRate",
            "service": "payment-service",
            "severity": "critical",
            "timestamp": "2026-03-18T10:00:00Z",
            "description": "Payment service error rate above 5% for 10 minutes",
        },
        description="Alert JSON to investigate",
    )
    thread_id: str = Field(default="studio-test", description="Session ID for tracking")
