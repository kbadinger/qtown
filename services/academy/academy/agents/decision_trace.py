"""
Decision trace — structured observability for each NPC decision cycle.

DecisionTrace records every node that ran, how long it took, and what
changed.  It is serialisable to a plain dict so it can be returned via
a gRPC GetDecisionTrace RPC or written to any log sink.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Node-level entry
# ---------------------------------------------------------------------------


@dataclass
class NodeExecution:
    """
    A single node's execution record within a decision cycle.

    Fields
    ------
    node_name:
        LangGraph node identifier (e.g. "assess_needs", "decide").
    duration_ms:
        Wall-clock milliseconds spent in the node.
    input_summary:
        Brief human-readable description of what entered the node.
    output_summary:
        Brief human-readable description of what the node produced.
    error:
        Non-None if the node raised an exception (before error_handler ran).
    """

    node_name: str
    duration_ms: float
    input_summary: str
    output_summary: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "node_name": self.node_name,
            "duration_ms": round(self.duration_ms, 3),
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
        }
        if self.error is not None:
            d["error"] = self.error
        return d


# ---------------------------------------------------------------------------
# Full-cycle trace
# ---------------------------------------------------------------------------


@dataclass
class DecisionTrace:
    """
    Complete observability record for one NPC decision cycle.

    Designed to be gRPC-compatible: to_dict() produces a JSON-serialisable
    structure that maps directly onto the GetDecisionTrace RPC response.

    Fields
    ------
    npc_id:
        Unique identifier of the NPC.
    tick:
        Simulation tick at which the decision was made.
    nodes_executed:
        Ordered list of node execution records (assess_needs first).
    final_decision:
        The action the NPC decided to take.
    total_duration_ms:
        Wall-clock milliseconds for the entire graph execution.
    confidence:
        Decision confidence score [0, 1].
    error:
        Non-None if the cycle ended in the error_handler node.
    """

    npc_id: str
    tick: int
    nodes_executed: list[NodeExecution] = field(default_factory=list)
    final_decision: str = "idle"
    total_duration_ms: float = 0.0
    confidence: float = 0.0
    error: str | None = None

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add_node(
        self,
        node_name: str,
        duration_ms: float,
        input_summary: str,
        output_summary: str,
        error: str | None = None,
    ) -> None:
        """Append a NodeExecution record."""
        self.nodes_executed.append(
            NodeExecution(
                node_name=node_name,
                duration_ms=duration_ms,
                input_summary=input_summary,
                output_summary=output_summary,
                error=error,
            )
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """
        Return a JSON-serialisable dict.

        Compatible with the GetDecisionTrace gRPC response envelope::

            {
              "npc_id": "...",
              "tick": 42,
              "final_decision": "work",
              "total_duration_ms": 123.4,
              "confidence": 0.87,
              "nodes_executed": [...],
              "error": null
            }
        """
        return {
            "npc_id": self.npc_id,
            "tick": self.tick,
            "final_decision": self.final_decision,
            "total_duration_ms": round(self.total_duration_ms, 3),
            "confidence": round(self.confidence, 4),
            "nodes_executed": [n.to_dict() for n in self.nodes_executed],
            "error": self.error,
        }

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def node_names(self) -> list[str]:
        """Ordered list of node names that were executed."""
        return [n.node_name for n in self.nodes_executed]

    @property
    def succeeded(self) -> bool:
        """True if the cycle completed without an unrecoverable error."""
        return self.error is None
