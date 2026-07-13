"""
NPC agent — full LangGraph StateGraph implementation.

Decision cycle:

    assess_needs → check_memory → evaluate_options → decide → narrate

An error at any node routes to error_handler, which logs the failure and
returns a safe "idle" default so the simulation never stalls.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from langgraph.graph import END, StateGraph

from academy.agents.personality import PersonalityProfile, personality_weight
from academy.models.router import ModelRouter
from academy.rag.retriever import TownHistoryRetriever

logger = logging.getLogger("academy.agents.npc")

# ---------------------------------------------------------------------------
# Singletons (lazy-init so imports don't block)
# ---------------------------------------------------------------------------

_retriever: TownHistoryRetriever | None = None
_router: ModelRouter | None = None


def _get_retriever() -> TownHistoryRetriever:
    global _retriever
    if _retriever is None:
        _retriever = TownHistoryRetriever()
    return _retriever


def _get_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class NPCState:
    """Mutable state passed through every node of the NPC decision graph."""

    # Identity
    npc_id: str
    npc_name: str = "Unknown"
    personality: dict[str, float] = field(
        default_factory=lambda: {
            "risk_tolerance": 0.5,
            "sociability": 0.5,
            "ambition": 0.5,
            "creativity": 0.5,
            "aggression": 0.5,
        }
    )
    current_tick: int = 0
    neighborhood: str = "Town Square"

    # Raw stats used by assess_needs (0–1 scale)
    hunger: float = 0.0        # 1.0 = starving
    energy: float = 1.0        # 0.0 = exhausted
    gold_need: float = 0.0     # 1.0 = broke
    happiness: float = 0.5     # 0.0 = miserable
    social: float = 0.5        # 0.0 = isolated

    # Populated by assess_needs
    needs: dict[str, float] = field(default_factory=dict)
    # e.g. {"hunger": 0.9, "energy": 0.2, "gold_need": 0.6, ...}

    # Populated by check_memory
    relevant_memories: list[str] = field(default_factory=list)

    # Populated by evaluate_options
    options: list[dict[str, Any]] = field(default_factory=list)
    # e.g. [{"action": "eat", "score": 0.85, "reasoning": "hunger is critical"}]

    # Populated by decide
    decision: str = "idle"
    decision_confidence: float = 0.0
    decision_reasoning: str = ""

    # Populated by narrate
    narration: str = ""

    # Routing / error handling
    error: str | None = None

    # Observability — each node appends an entry
    trace: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

HUNGER_URGENT = 0.7
ENERGY_CRITICAL = 0.3
GOLD_NEED_HIGH = 0.6
HAPPINESS_LOW = 0.3
SOCIAL_LOW = 0.35

LOW_CONFIDENCE_THRESHOLD = 0.3

ALL_ACTIONS = ["eat", "sleep", "work", "travel", "socialize", "idle"]


# ---------------------------------------------------------------------------
# Node helpers
# ---------------------------------------------------------------------------


def _record(state: NPCState, node: str, start: float, summary_in: str, summary_out: str) -> None:
    """Append a trace entry to state.trace."""
    state.trace.append(
        {
            "node": node,
            "duration_ms": round((time.perf_counter() - start) * 1000, 2),
            "input_summary": summary_in,
            "output_summary": summary_out,
        }
    )


# ---------------------------------------------------------------------------
# Node 1: assess_needs
# ---------------------------------------------------------------------------


def assess_needs(state: NPCState) -> NPCState:
    """
    Score each NPC need on a 0–1 urgency scale and store in state.needs.

    Urgency rules
    -------------
    hunger      > 0.7  → urgent
    energy      < 0.3  → critical  (inverted: low energy = high urgency)
    gold_need   > 0.6  → high
    happiness   < 0.3  → low
    social      < 0.35 → isolated
    """
    t0 = time.perf_counter()
    logger.debug("assess_needs npc=%s tick=%d", state.npc_id, state.current_tick)

    needs: dict[str, float] = {}

    # Hunger urgency: direct mapping
    needs["hunger"] = state.hunger

    # Energy urgency: inverted (low energy = high urgency)
    needs["energy"] = 1.0 - state.energy

    # Gold need: direct mapping
    needs["gold_need"] = state.gold_need

    # Happiness: inverted (low happiness = high urgency)
    needs["happiness"] = 1.0 - state.happiness

    # Social: inverted (low social = high urgency)
    needs["social"] = 1.0 - state.social

    state.needs = dict(sorted(needs.items(), key=lambda kv: kv[1], reverse=True))

    top = next(iter(state.needs))
    _record(
        state, "assess_needs", t0,
        f"hunger={state.hunger:.2f} energy={state.energy:.2f} gold={state.gold_need:.2f}",
        f"top_need={top} ({state.needs[top]:.2f}), {len(state.needs)} needs scored",
    )
    return state


# ---------------------------------------------------------------------------
# Node 2: check_memory
# ---------------------------------------------------------------------------


async def check_memory(state: NPCState) -> NPCState:
    """
    Query TownHistoryRetriever for past situations similar to the NPC's top need.

    Retrieves the top-3 relevant memories and stores them as plain strings in
    state.relevant_memories.
    """
    t0 = time.perf_counter()
    top_need = next(iter(state.needs), "general")
    query = f"NPC {state.npc_id} faced {top_need} and chose"
    logger.debug("check_memory npc=%s query=%r", state.npc_id, query)

    try:
        docs = await _get_retriever().search(query, k=3)
        state.relevant_memories = [doc.content for doc in docs]
    except Exception as exc:
        logger.warning("check_memory retrieval failed: %s", exc)
        state.relevant_memories = []

    _record(
        state, "check_memory", t0,
        f"query={query!r}",
        f"retrieved {len(state.relevant_memories)} memories",
    )
    return state


# ---------------------------------------------------------------------------
# Node 3: evaluate_options
# ---------------------------------------------------------------------------


def evaluate_options(state: NPCState) -> NPCState:
    """
    Score all available actions against current needs and personality traits.

    Base score for each action is derived from how directly it addresses the
    highest-urgency needs.  Personality weights modulate the scores.
    """
    t0 = time.perf_counter()
    logger.debug("evaluate_options npc=%s", state.npc_id)

    needs = state.needs
    personality = state.personality

    # Build a PersonalityProfile from the dict for weighting
    profile = PersonalityProfile(
        risk_tolerance=personality.get("risk_tolerance", 0.5),
        sociability=personality.get("sociability", 0.5),
        ambition=personality.get("ambition", 0.5),
        creativity=personality.get("creativity", 0.5),
        aggression=personality.get("aggression", 0.5),
    )

    # Base need-to-action mapping: how much does this action address each need?
    action_need_map: dict[str, dict[str, float]] = {
        "eat":       {"hunger": 0.95, "happiness": 0.10},
        "sleep":     {"energy": 0.90, "happiness": 0.05},
        "work":      {"gold_need": 0.85, "energy": -0.15},
        "travel":    {"gold_need": 0.55, "happiness": 0.20, "social": 0.10},
        "socialize": {"social": 0.80, "happiness": 0.30},
        "idle":      {"energy": 0.20, "happiness": 0.05},
    }

    options: list[dict[str, Any]] = []

    # Memory bonus: if a memory mentions an action, add a small boost
    memory_mentions: dict[str, int] = {a: 0 for a in ALL_ACTIONS}
    for mem in state.relevant_memories:
        for action in ALL_ACTIONS:
            if action in mem.lower():
                memory_mentions[action] += 1

    for action in ALL_ACTIONS:
        need_contributions = action_need_map.get(action, {})

        base_score = 0.0
        for need_key, contribution in need_contributions.items():
            urgency = needs.get(need_key, 0.0)
            base_score += urgency * contribution

        # Memory bonus (small: +0.05 per mention, max 0.15)
        memory_bonus = min(0.15, memory_mentions[action] * 0.05)
        base_score += memory_bonus

        # Personality multiplier
        p_weight = personality_weight(action, profile)
        final_score = base_score * p_weight

        reasoning_parts: list[str] = []
        if need_contributions:
            dominant = max(need_contributions, key=lambda k: needs.get(k, 0) * need_contributions[k])
            reasoning_parts.append(f"{dominant} urgency {needs.get(dominant, 0):.2f}")
        if memory_bonus > 0:
            reasoning_parts.append(f"supported by {memory_mentions[action]} memories")
        reasoning_parts.append(f"personality weight {p_weight:.2f}")

        options.append(
            {
                "action": action,
                "score": round(final_score, 4),
                "reasoning": "; ".join(reasoning_parts),
            }
        )

    # Sort descending by score
    state.options = sorted(options, key=lambda o: o["score"], reverse=True)

    _record(
        state, "evaluate_options", t0,
        f"{len(needs)} needs, {len(state.relevant_memories)} memories",
        f"top option={state.options[0]['action']} score={state.options[0]['score']:.3f}",
    )
    return state


# ---------------------------------------------------------------------------
# Node 4: decide
# ---------------------------------------------------------------------------


async def decide(state: NPCState) -> NPCState:
    """
    Pick the best-scored action.

    If confidence is below LOW_CONFIDENCE_THRESHOLD (options are too similar),
    call ModelRouter with task_type='planning' for an LLM-assisted tiebreak.
    """
    t0 = time.perf_counter()
    logger.debug("decide npc=%s options=%d", state.npc_id, len(state.options))

    if not state.options:
        state.decision = "idle"
        state.decision_confidence = 1.0
        state.decision_reasoning = "No options generated; defaulting to idle."
        _record(state, "decide", t0, "no options", "idle (default)")
        return state

    best = state.options[0]
    second_best_score = state.options[1]["score"] if len(state.options) > 1 else 0.0

    top_score = best["score"]

    # Confidence: how much better is the top option vs the second?
    if top_score <= 0.0:
        confidence = 0.1
    else:
        gap = top_score - second_best_score
        confidence = min(1.0, gap / max(top_score, 0.01))

    if confidence < LOW_CONFIDENCE_THRESHOLD:
        # Ask LLM to help decide
        logger.info(
            "decide npc=%s confidence=%.2f below threshold, escalating to LLM",
            state.npc_id,
            confidence,
        )
        try:
            options_text = "\n".join(
                f"- {o['action']} (score {o['score']:.3f}): {o['reasoning']}"
                for o in state.options[:4]
            )
            prompt = (
                f"NPC '{state.npc_name}' (id={state.npc_id}) must choose an action.\n"
                f"Current needs (urgency 0-1): {state.needs}\n"
                f"Options:\n{options_text}\n\n"
                f"Reply with ONLY the action name from this list: "
                f"{', '.join(o['action'] for o in state.options)}."
            )
            result = await _get_router().route(
                "planning",
                {"prompt": prompt, "temperature": 0.3, "max_tokens": 20},
            )
            llm_choice = result.response.strip().lower().split()[0]
            # Validate the LLM returned a real action
            if llm_choice in {o["action"] for o in state.options}:
                best = next(o for o in state.options if o["action"] == llm_choice)
                confidence = 0.5  # LLM-assisted confidence floor
                state.decision_reasoning = (
                    f"LLM tiebreak selected '{llm_choice}' from low-confidence options. "
                    f"Original top: {state.options[0]['action']}."
                )
            else:
                logger.warning("LLM returned unknown action %r; keeping top option", llm_choice)
                state.decision_reasoning = best["reasoning"]
        except Exception as exc:
            logger.warning("LLM decision assist failed: %s", exc)
            state.decision_reasoning = best["reasoning"] + " (LLM assist failed)"
    else:
        state.decision_reasoning = best["reasoning"]

    state.decision = best["action"]
    state.decision_confidence = round(confidence, 4)

    _record(
        state, "decide", t0,
        f"top={state.options[0]['action']} score={top_score:.3f}",
        f"decision={state.decision} confidence={state.decision_confidence:.3f}",
    )
    return state


# ---------------------------------------------------------------------------
# Node 5: narrate
# ---------------------------------------------------------------------------


async def narrate(state: NPCState) -> NPCState:
    """
    Generate 1–2 sentences of flavor text describing the NPC's decision.

    Uses ModelRouter with task_type='narration'.
    """
    t0 = time.perf_counter()
    logger.debug("narrate npc=%s decision=%s", state.npc_id, state.decision)

    top_need = next(iter(state.needs), "unknown")
    prompt = (
        f"Based on {top_need}, {state.npc_name} decided to {state.decision} "
        f"because {state.decision_reasoning}. "
        f"Write 1-2 sentences of vivid, in-world narration describing this decision. "
        f"Town: Qtown. Neighborhood: {state.neighborhood}. "
        f"Tick: {state.current_tick}. Keep it grounded and specific."
    )

    try:
        result = await _get_router().route(
            "narration",
            {"prompt": prompt, "temperature": 0.75, "max_tokens": 80},
        )
        state.narration = result.response.strip()
    except Exception as exc:
        logger.warning("narrate LLM call failed: %s", exc)
        state.narration = (
            f"{state.npc_name} chose to {state.decision} "
            f"in response to their {top_need} in {state.neighborhood}."
        )

    _record(
        state, "narrate", t0,
        f"decision={state.decision} need={top_need}",
        f"narration='{state.narration[:60]}...'",
    )
    return state


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------


def error_handler(state: NPCState) -> NPCState:
    """
    Safe fallback: log the error and return an idle decision.

    Clears state.error so downstream callers can detect the recovery.
    """
    logger.error(
        "error_handler npc=%s error=%r — returning idle default",
        state.npc_id,
        state.error,
    )
    state.decision = "idle"
    state.decision_confidence = 0.0
    state.decision_reasoning = f"Error recovery: {state.error}"
    state.narration = (
        f"{state.npc_name} paused, uncertain what to do, and decided to wait."
    )
    state.trace.append(
        {
            "node": "error_handler",
            "duration_ms": 0.0,
            "input_summary": f"error={state.error!r}",
            "output_summary": "idle default applied",
        }
    )
    state.error = None  # mark as recovered
    return state


# ---------------------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------------------


def _route_after_node(state: NPCState) -> str:
    """Conditional router: if error is set, divert to error_handler."""
    return "error_handler" if state.error else "__next__"


def _wrap_with_error_handling(node_fn):
    """
    Wrap a node function so that any unhandled exception is caught,
    stored in state.error, and routed to error_handler.
    """
    import asyncio
    import functools

    if asyncio.iscoroutinefunction(node_fn):
        @functools.wraps(node_fn)
        async def async_wrapper(state: NPCState) -> NPCState:
            try:
                return await node_fn(state)
            except Exception as exc:
                logger.exception("node %s raised: %s", node_fn.__name__, exc)
                state.error = f"{node_fn.__name__}: {exc}"
                return state
        return async_wrapper
    else:
        @functools.wraps(node_fn)
        def sync_wrapper(state: NPCState) -> NPCState:
            try:
                return node_fn(state)
            except Exception as exc:
                logger.exception("node %s raised: %s", node_fn.__name__, exc)
                state.error = f"{node_fn.__name__}: {exc}"
                return state
        return sync_wrapper


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

_PIPELINE: list[tuple[str, Any]] = [
    ("assess_needs", assess_needs),
    ("check_memory", check_memory),
    ("evaluate_options", evaluate_options),
    ("decide", decide),
    ("narrate", narrate),
]


def build_npc_graph() -> StateGraph:
    """
    Wire up the five-node NPC decision graph with error-handling edges.

    Each node is wrapped so that exceptions set state.error and trigger
    routing to error_handler rather than propagating to the caller.

    Returns a compiled LangGraph StateGraph.
    """
    graph: StateGraph = StateGraph(NPCState)

    node_names = [name for name, _ in _PIPELINE]

    # Register nodes (wrapped for error safety)
    for name, fn in _PIPELINE:
        graph.add_node(name, _wrap_with_error_handling(fn))
    graph.add_node("error_handler", error_handler)

    graph.set_entry_point("assess_needs")

    # Add conditional edges: if error → error_handler, else → next node
    for i, name in enumerate(node_names):
        next_node = node_names[i + 1] if i + 1 < len(node_names) else END
        graph.add_conditional_edges(
            name,
            lambda s, _next=next_node: "error_handler" if s.error else _next,
            {
                "error_handler": "error_handler",
                next_node: next_node,
            }
        )

    graph.add_edge("error_handler", END)

    return graph


# Compiled graph — import this in callers.
npc_graph = build_npc_graph().compile()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def run_npc_cycle(
    npc_id: str,
    npc_name: str,
    personality: dict[str, float],
    hunger: float = 0.0,
    energy: float = 1.0,
    gold_need: float = 0.0,
    happiness: float = 0.5,
    social: float = 0.5,
    current_tick: int = 0,
    neighborhood: str = "Town Square",
) -> NPCState:
    """
    Execute one full decision cycle for an NPC.

    Returns the final NPCState with decision, confidence, narration, and trace.
    """
    initial_state = NPCState(
        npc_id=npc_id,
        npc_name=npc_name,
        personality=personality,
        hunger=hunger,
        energy=energy,
        gold_need=gold_need,
        happiness=happiness,
        social=social,
        current_tick=current_tick,
        neighborhood=neighborhood,
    )
    result: NPCState = await npc_graph.ainvoke(initial_state)  # type: ignore[assignment]
    return result
