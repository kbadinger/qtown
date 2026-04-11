//! Validation engine — applies a pipeline of `Rule`s to `TownEvent`s.
//!
//! # Design goals
//!
//! * **No unsafe blocks** — the entire validation path is safe Rust.
//! * **100K events/sec throughput** — achieved through `rayon` parallel
//!   iteration in `validate_batch`.
//! * **Open/closed** — new rules are added by implementing `Rule` and pushing
//!   an `Arc<dyn Rule>` into the engine; no engine source changes needed.

pub mod rules;

use std::sync::Arc;

use rayon::prelude::*;

use crate::types::{TownEvent, ValidationResult};
use rules::Rule;

// ─────────────────────────────────────────────────────────────────────────────

/// Orchestrates an ordered pipeline of validation rules.
///
/// The engine is cheaply cloneable (all rules are behind `Arc`) and is safe
/// to share across async tasks and Rayon worker threads.
#[derive(Clone, Default)]
pub struct ValidationEngine {
    /// Ordered list of rules applied to every event.
    /// Rules run in insertion order; all rules run even if one fails
    /// (so the caller receives the complete set of violations).
    rules: Vec<Arc<dyn Rule + Send + Sync>>,
}

impl ValidationEngine {
    /// Creates an empty engine with no rules.
    pub fn new() -> Self {
        Self::default()
    }

    /// Registers a rule. Returns `&mut self` to support builder chaining:
    ///
    /// ```rust,ignore
    /// let engine = ValidationEngine::new()
    ///     .with_rule(GoldOverflowRule)
    ///     .with_rule(NegativeBalanceRule::new(ledger.clone()));
    /// ```
    pub fn with_rule(mut self, rule: impl Rule + Send + Sync + 'static) -> Self {
        self.rules.push(Arc::new(rule));
        self
    }

    /// Validates a single event against all registered rules.
    ///
    /// Returns one `ValidationResult` per rule. The overall event is
    /// considered valid only if every result has `valid == true`.
    ///
    /// This method is **safe** — zero unsafe blocks.
    pub fn validate_one(&self, event: &TownEvent) -> Vec<ValidationResult> {
        self.rules
            .iter()
            .map(|rule| rule.validate(event))
            .collect()
    }

    /// Validates a batch of events in parallel using Rayon.
    ///
    /// Each event is validated independently; results are returned in the
    /// same order as the input slice. This is the hot path that must sustain
    /// ≥ 100K events/sec.
    ///
    /// This method is **safe** — zero unsafe blocks. Rayon's `par_iter`
    /// handles thread-pool dispatch without requiring unsafe.
    pub fn validate_batch(&self, events: &[TownEvent]) -> Vec<Vec<ValidationResult>> {
        events
            .par_iter()
            .map(|event| self.validate_one(event))
            .collect()
    }

    /// Returns the number of registered rules.
    pub fn rule_count(&self) -> usize {
        self.rules.len()
    }
}

// ─────────────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::TownEvent;
    use crate::validation::rules::{GoldOverflowRule, NegativeBalanceRule, TradeVolumeRule};

    fn make_event(event_type: &str, amount: f64) -> TownEvent {
        TownEvent {
            event_type: event_type.to_string(),
            npc_id: 1,
            amount,
            resource: Some("gold".to_string()),
            metadata: None,
        }
    }

    fn default_engine() -> ValidationEngine {
        ValidationEngine::new()
            .with_rule(GoldOverflowRule)
            .with_rule(NegativeBalanceRule)
            .with_rule(TradeVolumeRule::default())
    }

    #[test]
    fn valid_event_passes_all_rules() {
        let engine = default_engine();
        let event = make_event("trade", 500.0);
        let results = engine.validate_one(&event);
        assert!(results.iter().all(|r| r.valid));
    }

    #[test]
    fn overflow_event_fails_gold_overflow_rule() {
        let engine = default_engine();
        let event = make_event("trade", 99_999.0);
        let results = engine.validate_one(&event);
        let overflow = results.iter().find(|r| r.rule_name == "GoldOverflowRule");
        assert!(overflow.is_some());
        assert!(!overflow.unwrap().valid);
    }

    #[test]
    fn validate_batch_returns_one_result_set_per_event() {
        let engine = default_engine();
        let events: Vec<TownEvent> = (0..1_000).map(|_| make_event("trade", 100.0)).collect();
        let batch = engine.validate_batch(&events);
        assert_eq!(batch.len(), 1_000);
        // Each event should have 3 rule results.
        assert!(batch.iter().all(|results| results.len() == 3));
    }
}
