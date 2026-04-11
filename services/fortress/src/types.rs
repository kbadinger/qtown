//! Core domain types shared across Fortress modules.
//!
//! `TownEvent` is the canonical inbound event produced by Qtown services.
//! `ValidationResult` is the verdict emitted after each rule is applied.

use serde::{Deserialize, Serialize};

// ─── Inbound ─────────────────────────────────────────────────────────────────

/// A single game-world event submitted by an NPC or player action.
///
/// Events arrive from Kafka (`qtown.town-events`) or directly via gRPC.
/// The `amount` field carries the quantity of the resource being transacted
/// (gold, lumber, stone, etc.). Negative amounts signal debits.
#[derive(Debug, Clone, Deserialize)]
pub struct TownEvent {
    /// Discriminator: "trade", "purchase", "harvest", "taxation", …
    pub event_type: String,

    /// ID of the NPC (or player) that originated the event.
    pub npc_id: i64,

    /// Quantity of the primary resource involved. Must be finite.
    pub amount: f64,

    /// Optional resource tag ("gold", "lumber", "stone"). Defaults to "gold"
    /// when absent and the event type implies a currency transaction.
    pub resource: Option<String>,

    /// Arbitrary extra payload for rule extensions and audit logging.
    pub metadata: Option<serde_json::Value>,
}

// ─── Outbound ─────────────────────────────────────────────────────────────────

/// The verdict produced after applying a single rule to a `TownEvent`.
///
/// Multiple `ValidationResult`s are produced per event (one per rule).
/// A batch is considered fully valid only when all results have `valid = true`.
#[derive(Debug, Clone, Serialize)]
pub struct ValidationResult {
    /// `true` if the event passed this rule; `false` if rejected.
    pub valid: bool,

    /// Machine-readable name of the rule that produced this result.
    /// Matches `Rule::name()` exactly for easy filtering.
    pub rule_name: String,

    /// Human-readable explanation. `None` on success; set on rejection or
    /// soft-warning so operators can act without reading source code.
    pub message: Option<String>,
}

impl ValidationResult {
    /// Convenience constructor for a passing result.
    pub fn pass(rule_name: impl Into<String>) -> Self {
        Self {
            valid: true,
            rule_name: rule_name.into(),
            message: None,
        }
    }

    /// Convenience constructor for a failing result.
    pub fn fail(rule_name: impl Into<String>, message: impl Into<String>) -> Self {
        Self {
            valid: false,
            rule_name: rule_name.into(),
            message: Some(message.into()),
        }
    }
}
