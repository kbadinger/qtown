"""
NPC agent — LangGraph StateGraph skeleton.

The graph models an NPC's decision cycle:

    assess_needs → check_memory → evaluate_options → decide → narrate

Each node is a placeholder stub; implementations will call into ModelRouter,
the RAG retriever, and the world-state service.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from langgraph.graph import END, StateGraph

logger = logging.getLogger("academy.agents.npc")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

@dataclass
class NPCState:
    """Mutable state passed through every node of the NPC decision graph."""

    npc_id: str
    current_event: dict[str, Any] = field(default_factory=dict)

    # Populated by assess_needs
    needs: list[str] = field(default_factory=list)

    # Populated by check_memory
    relevant_memories: list[str] = field(default_factory=list)

    # Populated by evaluate_options
    options: list[str] = field(default_factory=list)

    # Populated by decide
    decision: str = ""
    decision_confidence: float = 0.0

    # Populated by narrate
    narration: str = ""

    # Internal routing
    error: str | None = None


# ---------------------------------------------------------------------------
# Node implementations (stubs)
# ---------------------------------------------------------------------------

def assess_needs(state: NPCState) -> NPCState:
    """
    Determine what the NPC currently needs based on world state and event.

    TODO: call ModelRouter with task_type='planning' and the NPC's current
    stats (hunger, gold, mood, goals) to produce a ranked needs list.
    """
    logger.debug("assess_needs npc=%s event=%s", state.npc_id, state.current_event)
    # Placeholder: hardcode a generic need set.
    state.needs = ["food", "safety", "gold"]
    return state


def check_memory(state: NPCState) -> NPCState:
    """
    Query the RAG retriever for memories relevant to the current needs.

    TODO: call TownHistoryRetriever.search() for each need and merge results.
    """
    logger.debug("check_memory npc=%s needs=%s", state.npc_id, state.needs)
    # Placeholder: no real memories yet.
    state.relevant_memories = [
        f"[stub] memory related to '{need}'" for need in state.needs
    ]
    return state


def evaluate_options(state: NPCState) -> NPCState:
    """
    Generate a list of possible actions the NPC could take.

    TODO: call ModelRouter with task_type='planning', passing needs and memories.
    """
    logger.debug("evaluate_options npc=%s memories=%d", state.npc_id, len(state.relevant_memories))
    # Placeholder options derived mechanically from needs.
    state.options = [f"action_for_{need}" for need in state.needs]
    return state


def decide(state: NPCState) -> NPCState:
    """
    Pick the best option and record a confidence score.

    TODO: call ModelRouter with task_type='planning' + options list.
    """
    logger.debug("decide npc=%s options=%s", state.npc_id, state.options)
    if state.options:
        state.decision = state.options[0]
        state.decision_confidence = 0.75  # placeholder
    else:
        state.decision = "idle"
        state.decision_confidence = 1.0
    return state


def narrate(state: NPCState) -> NPCState:
    """
    Produce a human-readable narration of the NPC's decision.

    TODO: call ModelRouter with task_type='narration' + decision + context.
    """
    logger.debug("narrate npc=%s decision=%s", state.npc_id, state.decision)
    state.narration = (
        f"{state.npc_id} decided to '{state.decision}' "
        f"(confidence: {state.decision_confidence:.0%})."
    )
    return state


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_npc_graph() -> StateGraph:
    """
    Wire up the five-node NPC decision graph and compile it.

    Returns an uncompiled StateGraph ready for `.compile()`.
    """
    graph: StateGraph = StateGraph(NPCState)

    graph.add_node("assess_needs", assess_needs)
    graph.add_node("check_memory", check_memory)
    graph.add_node("evaluate_options", evaluate_options)
    graph.add_node("decide", decide)
    graph.add_node("narrate", narrate)

    graph.set_entry_point("assess_needs")

    graph.add_edge("assess_needs", "check_memory")
    graph.add_edge("check_memory", "evaluate_options")
    graph.add_edge("evaluate_options", "decide")
    graph.add_edge("decide", "narrate")
    graph.add_edge("narrate", END)

    return graph


# Compiled graph — import this in callers.
npc_graph = build_npc_graph().compile()


async def run_npc_cycle(npc_id: str, event: dict[str, Any]) -> NPCState:
    """
    Execute one full decision cycle for an NPC given a triggering event.

    Returns the final NPCState after all five nodes have run.
    """
    initial_state = NPCState(npc_id=npc_id, current_event=event)
    result: NPCState = await npc_graph.ainvoke(initial_state)  # type: ignore[assignment]
    return result
