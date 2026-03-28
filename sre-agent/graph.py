"""
OpenSRE Investigation Graph — LangGraph-based agent orchestration.

Topology:
    init_context → [memory_lookup, kg_context] → planner → Send(subagents)
    → synthesizer → loop/writeup → memory_store → END

Phase 3 of the LangGraph migration. Wires all nodes from sre-agent/nodes/
into the master graph with correct edges, fan-out/fan-in, and loop control.
"""

import logging
from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from nodes.init_context import init_context
from nodes.kg_context import kg_context
from nodes.memory_lookup import memory_lookup
from nodes.memory_store import memory_store
from nodes.planner import planner
from nodes.subagent_executor import make_subagent_executor
from nodes.synthesizer import synthesizer
from nodes.writeup import writeup
from state import GraphState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Subagent executor — instantiated once via factory
# ---------------------------------------------------------------------------
_subagent_executor = make_subagent_executor()


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------


def _route_after_init(state: dict) -> list[str]:
    """After init_context, fan out to memory_lookup and kg_context in parallel."""
    return ["memory_lookup", "kg_context"]


def _route_to_subagents(state: dict) -> list[Send]:
    """Fan out to selected investigation subagents via Send().

    The planner sets ``selected_agents`` — each agent ID becomes a separate
    Send() dispatch so LangGraph runs them concurrently.  All results merge
    into ``agent_states`` via the ``merge_dicts`` reducer.

    If no agents were selected (edge case), send the current state directly
    to the synthesizer so the graph doesn't deadlock.
    """
    selected = state.get("selected_agents", [])
    if not selected:
        logger.warning("[GRAPH] Planner selected no agents — skipping to synthesizer")
        return [Send("synthesizer_node", state)]

    sends = []
    for agent_id in selected:
        payload = {
            "agent_id": agent_id,
            "alert": state.get("alert", {}),
            "hypotheses": state.get("hypotheses", []),
            "team_config": state.get("team_config", {}),
            "max_react_loops": state.get("max_react_loops", 25),
            "thread_id": state.get("thread_id", ""),
            "memory_context": state.get("memory_context", {}),
            "kg_context": state.get("kg_context", {}),
        }
        sends.append(Send("subagent", payload))

    logger.info(f"[GRAPH] Fanning out to {len(sends)} subagent(s): {selected}")
    return sends


def _route_after_synthesis(state: dict) -> Literal["planner", "writeup_node"]:
    """After synthesis, either loop back to planner or proceed to writeup.

    The synthesizer sets ``status``:
      - ``"completed"`` → enough evidence, go to writeup
      - anything else  → loop back to planner for another iteration

    The planner itself enforces ``max_iterations`` — if we've looped enough
    times it will set status to ``"completed"`` and force the writeup.
    """
    status = state.get("status", "running")
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 3)

    if status == "completed":
        logger.info("[GRAPH] Synthesis complete — routing to writeup")
        return "writeup_node"

    if iteration >= max_iterations:
        logger.warning(
            f"[GRAPH] Max iterations ({max_iterations}) reached — forcing writeup"
        )
        return "writeup_node"

    logger.info(f"[GRAPH] Iteration {iteration}/{max_iterations} — looping to planner")
    return "planner"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_graph(checkpointer=None):
    """Build and compile the investigation graph.

    Args:
        checkpointer: Optional checkpointer for state persistence.
            Defaults to MemorySaver (in-memory) if None.

    Returns:
        Compiled StateGraph ready for invocation via ``.invoke()``
        or ``.astream_events()``.
    """
    if checkpointer is None:
        checkpointer = MemorySaver()

    graph = StateGraph(GraphState)

    # ---- Nodes ----
    graph.add_node("init_context", init_context)
    graph.add_node("memory_lookup", memory_lookup)
    graph.add_node("kg_context", kg_context)
    graph.add_node("planner", planner)
    graph.add_node("subagent", _subagent_executor)
    graph.add_node("synthesizer_node", synthesizer)
    graph.add_node("writeup_node", writeup)
    graph.add_node("memory_store", memory_store)

    # ---- Edges ----

    # 1. Entry → init_context
    graph.add_edge(START, "init_context")

    # 2. init_context → parallel context enrichment
    graph.add_conditional_edges("init_context", _route_after_init)

    # 3. Both context nodes converge on planner (LangGraph waits for both)
    graph.add_edge("memory_lookup", "planner")
    graph.add_edge("kg_context", "planner")

    # 4. Planner → dynamic fan-out to subagents via Send()
    graph.add_conditional_edges("planner", _route_to_subagents)

    # 5. Subagents fan-in to synthesizer
    graph.add_edge("subagent", "synthesizer_node")

    # 6. Synthesizer → loop back to planner OR proceed to writeup
    graph.add_conditional_edges("synthesizer_node", _route_after_synthesis)

    # 7. Writeup → memory_store → END
    graph.add_edge("writeup_node", "memory_store")
    graph.add_edge("memory_store", END)

    # ---- Compile ----
    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("[GRAPH] Investigation graph compiled successfully")
    return compiled


# ---------------------------------------------------------------------------
# LangGraph Studio entry point
# ---------------------------------------------------------------------------


def create_app():
    """Create the graph app for LangGraph Studio (``langgraph dev``).

    Studio discovers this via ``langgraph.json`` → ``graph:create_app``.
    """
    return build_graph()


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_graph_instance = None


def get_graph(checkpointer=None):
    """Get or create the singleton graph instance.

    Use this from ``server.py`` to avoid rebuilding the graph on every request.
    """
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_graph(checkpointer=checkpointer)
    return _graph_instance
