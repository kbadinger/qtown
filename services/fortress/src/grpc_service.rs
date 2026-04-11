//! gRPC service implementation for the Fortress.
//!
//! Implements ValidateEvent, ValidateBatch, ListRules, ExecutePolicy,
//! RunBenchmark, and the Health RPC.
//!
//! Since proto codegen is deferred to a later phase, this module exposes
//! the service logic as plain methods on `FortressService`. The tonic
//! service trait implementations will wrap these once `build.rs` emits
//! the generated stubs from `proto/qtown/fortress.proto`.

use std::sync::Arc;
use std::time::Instant;

use tracing::{info, warn};

use crate::rules::default_engine;
use crate::types::{TownEvent, ValidationResult};
use crate::validation::ValidationEngine;
use crate::wasm_sandbox::WasmSandbox;

// ─────────────────────────────────────────────────────────────────────────────

/// Holds the shared, thread-safe state for all gRPC handlers.
///
/// `FortressService` is designed to be wrapped in an `Arc` and shared across
/// async tasks, Rayon worker threads, and Kafka consumers without cloning the
/// underlying engine or sandbox.
pub struct FortressService {
    /// Validation engine pre-loaded with all production rules.
    engine: Arc<ValidationEngine>,
    /// WASM sandbox for executing user-submitted policy modules.
    sandbox: Arc<WasmSandbox>,
}

impl FortressService {
    /// Creates a `FortressService` with the default production rule set and
    /// a 64 MiB WASM memory cap.
    pub fn new() -> Self {
        Self {
            engine: Arc::new(default_engine()),
            sandbox: Arc::new(WasmSandbox::new(64 * 1024 * 1024)),
        }
    }

    // ── Single-event validation ───────────────────────────────────────────────

    /// Validate a single event against all registered rules.
    ///
    /// Returns one `ValidationResult` per rule; callers should treat the event
    /// as accepted only when every result has `valid == true`.
    pub fn validate_event(&self, event: &TownEvent) -> Vec<ValidationResult> {
        let results = self.engine.validate_one(event);
        info!(
            npc_id = %event.npc_id,
            event_type = %event.event_type,
            rule_count = results.len(),
            all_valid = results.iter().all(|r| r.valid),
            "validate_event"
        );
        results
    }

    // ── Batch validation ──────────────────────────────────────────────────────

    /// Validate a batch of events using Rayon parallelism.
    ///
    /// Results are returned in the same order as the input slice. Each inner
    /// `Vec<ValidationResult>` contains one entry per registered rule.
    pub fn validate_batch(&self, events: &[TownEvent]) -> Vec<Vec<ValidationResult>> {
        let results = self.engine.validate_batch(events);
        let total_invalid: usize = results
            .iter()
            .filter(|ev_results| ev_results.iter().any(|r| !r.valid))
            .count();

        info!(
            batch_size = events.len(),
            total_invalid,
            "validate_batch"
        );
        results
    }

    // ── Rule enumeration ──────────────────────────────────────────────────────

    /// List all registered rules by running a zero-event probe batch and
    /// returning the rule names from the engine's rule count.
    ///
    /// This uses the engine's `rule_count` to build placeholder `RuleInfo`
    /// entries. Once proto codegen lands, the `Rule::name()` accessors are
    /// exposed via `ValidationEngine::rule_names()`.
    pub fn list_rules(&self) -> Vec<RuleInfo> {
        // Build the rule list from the known production rule names. These
        // match the names returned by each rule's `Rule::name()` impl.
        let known_rules = [
            ("GoldSufficientRule", "Validates NPC has non-negative gold balance"),
            ("TravelPermittedRule", "Validates travel permit for restricted districts"),
            ("TradeVolumeRule", "Validates trade volume is within accepted bounds"),
        ];

        // Return only as many entries as the engine actually has registered.
        let rule_count = self.engine.rule_count();
        known_rules
            .iter()
            .take(rule_count)
            .map(|(name, description)| RuleInfo {
                name: name.to_string(),
                description: description.to_string(),
                enabled: true,
            })
            .collect()
    }

    // ── Policy execution ──────────────────────────────────────────────────────

    /// Execute a user-submitted WASM policy module against a single event.
    ///
    /// Delegates to the `WasmSandbox` with full fuel metering and memory
    /// isolation. Returns `Ok(true)` if the policy accepted the event,
    /// `Ok(false)` if rejected, or an error string on trap/fuel exhaustion.
    pub fn execute_policy(&self, wasm_bytes: &[u8], event: &TownEvent) -> Result<bool, String> {
        self.sandbox
            .execute_policy(wasm_bytes, event)
            .map_err(|e| {
                warn!(
                    npc_id = %event.npc_id,
                    error = %e,
                    "execute_policy: sandbox error"
                );
                e.to_string()
            })
    }

    // ── Benchmark ─────────────────────────────────────────────────────────────

    /// Run a synthetic in-process benchmark with `num_events` synthetic trade
    /// events and return timing statistics.
    ///
    /// Used by the `RunBenchmark` RPC to give operators a live throughput
    /// measurement without external load tooling.
    pub fn run_benchmark(&self, num_events: usize) -> BenchmarkResult {
        let events: Vec<TownEvent> = (0..num_events)
            .map(|i| TownEvent {
                event_type: "trade".to_string(),
                npc_id: i as i64,
                amount: 50.0 + (i as f64 % 100.0),
                resource: Some("wood".to_string()),
                metadata: None,
            })
            .collect();

        let start = Instant::now();
        let results = self.engine.validate_batch(&events);
        let elapsed = start.elapsed();

        let total_valid = results
            .iter()
            .filter(|ev_results| ev_results.iter().all(|r| r.valid))
            .count();
        let total_invalid = results.len() - total_valid;
        let elapsed_ms = elapsed.as_secs_f64() * 1000.0;
        let events_per_sec = if elapsed.as_secs_f64() > 0.0 {
            num_events as f64 / elapsed.as_secs_f64()
        } else {
            f64::INFINITY
        };

        info!(
            num_events,
            total_valid,
            total_invalid,
            elapsed_ms,
            events_per_sec,
            "run_benchmark completed"
        );

        BenchmarkResult {
            total_events: num_events,
            total_valid,
            total_invalid,
            elapsed_ms,
            events_per_sec,
        }
    }
}

impl Default for FortressService {
    fn default() -> Self {
        Self::new()
    }
}

// ─────────────────────────────────────────────────────────────────────────────

/// Describes a single registered validation rule.
///
/// Returned by `FortressService::list_rules` and serialised as part of the
/// `ListRulesResponse` proto message.
#[derive(Debug, Clone)]
pub struct RuleInfo {
    /// Machine-readable rule name (matches `Rule::name()` exactly).
    pub name: String,
    /// Human-readable rule description for operator dashboards.
    pub description: String,
    /// Whether the rule is currently active in the engine.
    pub enabled: bool,
}

// ─────────────────────────────────────────────────────────────────────────────

/// Timing and throughput statistics from a synthetic benchmark run.
///
/// Returned by `FortressService::run_benchmark` and serialised as part of the
/// `BenchmarkResponse` proto message.
#[derive(Debug, Clone)]
pub struct BenchmarkResult {
    /// Total events generated and validated.
    pub total_events: usize,
    /// Events where every rule returned `valid = true`.
    pub total_valid: usize,
    /// Events where at least one rule returned `valid = false`.
    pub total_invalid: usize,
    /// Wall-clock time in milliseconds for the full batch.
    pub elapsed_ms: f64,
    /// Derived throughput in events per second.
    pub events_per_sec: f64,
}

// ─────────────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn trade_event(npc_id: i64, amount: f64) -> TownEvent {
        TownEvent {
            event_type: "trade".to_string(),
            npc_id,
            amount,
            resource: Some("gold".to_string()),
            metadata: None,
        }
    }

    #[test]
    fn service_constructs() {
        let svc = FortressService::new();
        // 3 production rules registered
        assert_eq!(svc.engine.rule_count(), 3);
    }

    #[test]
    fn validate_event_returns_per_rule_results() {
        let svc = FortressService::new();
        let event = trade_event(1, 100.0);
        let results = svc.validate_event(&event);
        assert_eq!(results.len(), 3, "one result per registered rule");
    }

    #[test]
    fn validate_batch_returns_one_result_set_per_event() {
        let svc = FortressService::new();
        let events: Vec<TownEvent> = (0..100).map(|i| trade_event(i, 50.0)).collect();
        let batch = svc.validate_batch(&events);
        assert_eq!(batch.len(), 100);
        assert!(batch.iter().all(|ev| ev.len() == 3));
    }

    #[test]
    fn list_rules_returns_all_registered_rules() {
        let svc = FortressService::new();
        let rules = svc.list_rules();
        assert_eq!(rules.len(), 3);
        assert!(rules.iter().all(|r| r.enabled));
    }

    #[test]
    fn run_benchmark_returns_sensible_stats() {
        let svc = FortressService::new();
        let result = svc.run_benchmark(1_000);
        assert_eq!(result.total_events, 1_000);
        assert_eq!(result.total_valid + result.total_invalid, 1_000);
        assert!(result.elapsed_ms >= 0.0);
        assert!(result.events_per_sec > 0.0);
    }
}
