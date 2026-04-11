//! gRPC service implementation for the Fortress.
//!
//! Implements:
//! - ValidateEvent       — validate a single event against all rules
//! - ValidateBatch       — validate a batch of events (Rayon-parallel)
//! - ListRules           — enumerate registered validation rules
//! - ExecuteWASM         — submit WASM bytes + event, get PolicyResult
//! - CompilePolicy       — submit Rust source, get compiled WASM bytes
//! - RegisterPolicy      — register a named policy from WASM bytes
//! - ListPolicies        — list all registered policies with stats
//! - UnregisterPolicy    — remove a named policy
//! - RunBenchmark        — in-process synthetic benchmark
//!
//! Proto codegen is deferred to a later phase; service logic is exposed as
//! plain methods on `FortressService` so the Tonic trait impls can wrap them
//! once `build.rs` emits generated stubs.

use std::sync::Arc;
use std::time::Instant;

use tracing::{info, warn};

use crate::rules::default_engine;
use crate::types::{TownEvent, ValidationResult};
use crate::validation::ValidationEngine;
use crate::wasm::compiler::{compile_policy, CompileError, CompileResult};
use crate::wasm::policy_registry::{PolicyRegistry, PolicySummary};
use crate::wasm_sandbox::{NpcState, PolicyInput, PolicyResult, WasmSandbox, WorldState};

// ─── FortressService ─────────────────────────────────────────────────────────

/// Holds the shared, thread-safe state for all gRPC handlers.
pub struct FortressService {
    /// Validation engine pre-loaded with all production rules.
    engine: Arc<ValidationEngine>,

    /// WASM sandbox — shared engine for compilation + execution.
    sandbox: Arc<WasmSandbox>,

    /// In-memory policy registry (hot-reload capable).
    policy_registry: PolicyRegistry,
}

impl FortressService {
    /// Creates a `FortressService` with the default production rule set and
    /// a 64 MiB WASM memory cap.
    pub fn new() -> Self {
        let sandbox = Arc::new(WasmSandbox::new(64 * 1024 * 1024));
        Self {
            engine: Arc::new(default_engine()),
            sandbox: Arc::clone(&sandbox),
            policy_registry: PolicyRegistry::new(sandbox),
        }
    }

    // ── Single-event validation ───────────────────────────────────────────────

    /// Validate a single event against all registered rules.
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
    pub fn validate_batch(&self, events: &[TownEvent]) -> Vec<Vec<ValidationResult>> {
        let results = self.engine.validate_batch(events);
        let total_invalid: usize = results
            .iter()
            .filter(|ev_results| ev_results.iter().any(|r| !r.valid))
            .count();
        info!(batch_size = events.len(), total_invalid, "validate_batch");
        results
    }

    // ── Rule enumeration ──────────────────────────────────────────────────────

    /// List all registered rules.
    pub fn list_rules(&self) -> Vec<RuleInfo> {
        let known_rules = [
            ("GoldSufficientRule", "Validates NPC has non-negative gold balance"),
            ("TravelPermittedRule", "Validates travel permit for restricted districts"),
            ("TradeVolumeRule", "Validates trade volume is within accepted bounds"),
        ];
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

    // ── ExecuteWASM RPC ───────────────────────────────────────────────────────

    /// Execute a user-submitted WASM policy module against a single event
    /// with full context (NPC state + world state).
    ///
    /// This is the primary RPC for ad-hoc WASM execution without registering
    /// a policy permanently. The module is compiled on the fly and executed
    /// once; no caching occurs.
    pub fn execute_wasm(
        &self,
        wasm_bytes: &[u8],
        event: &TownEvent,
        npc_state: Option<NpcState>,
        world_state: Option<WorldState>,
    ) -> Result<PolicyResult, String> {
        let module = self.sandbox.compile(wasm_bytes).map_err(|e| e.to_string())?;
        let input = PolicyInput {
            event: event.clone(),
            npc_state,
            world_state,
        };
        self.sandbox
            .execute_module(&module, &input, None)
            .map_err(|e| {
                warn!(error = %e, "execute_wasm: sandbox error");
                e.to_string()
            })
    }

    // ── CompilePolicy RPC ─────────────────────────────────────────────────────

    /// Compile Rust source code to WASM bytes.
    ///
    /// Applies source-level security checks (unsafe, forbidden imports) before
    /// invoking `rustc`. Returns the compiled bytes + metadata on success, or
    /// a structured `CompileError` on failure.
    ///
    /// Requires `rustc` on `$PATH` with `wasm32-unknown-unknown` target.
    pub fn compile_policy(&self, rust_source: &str) -> Result<CompileResult, CompileError> {
        let start = Instant::now();
        let result = compile_policy(rust_source);
        let elapsed_ms = start.elapsed().as_millis();
        match &result {
            Ok(r) => info!(
                wasm_bytes = r.wasm_bytes.len(),
                compile_ms = elapsed_ms,
                "compile_policy: success"
            ),
            Err(e) => warn!(error = %e, compile_ms = elapsed_ms, "compile_policy: error"),
        }
        result
    }

    // ── RegisterPolicy RPC ────────────────────────────────────────────────────

    /// Register a named policy from pre-compiled WASM bytes.
    ///
    /// If a policy with the same name already exists, it is hot-reloaded
    /// (replaced in-place without restarting the service). The version counter
    /// is incremented.
    ///
    /// Returns the `PolicySummary` of the registered entry on success.
    pub fn register_policy(
        &self,
        name: impl Into<String>,
        wasm_bytes: Vec<u8>,
        author: impl Into<String>,
    ) -> Result<PolicySummary, String> {
        let name_str = name.into();
        let result = self.policy_registry.register(&name_str, wasm_bytes, author);
        match &result {
            Ok(summary) => info!(
                policy_name = %name_str,
                version = summary.version,
                wasm_bytes = summary.wasm_size_bytes,
                "register_policy: success"
            ),
            Err(e) => warn!(
                policy_name = %name_str,
                error = %e,
                "register_policy: error"
            ),
        }
        result
    }

    // ── ListPolicies RPC ──────────────────────────────────────────────────────

    /// List all registered policies with their statistics.
    ///
    /// Results are sorted by policy name for stable ordering.
    pub fn list_policies(&self) -> Vec<PolicySummary> {
        let policies = self.policy_registry.list();
        info!(count = policies.len(), "list_policies");
        policies
    }

    // ── UnregisterPolicy RPC ──────────────────────────────────────────────────

    /// Remove a named policy from the registry.
    ///
    /// Returns `true` if the policy was found and removed, `false` if it did
    /// not exist (idempotent).
    pub fn unregister_policy(&self, name: &str) -> bool {
        let removed = self.policy_registry.unregister(name);
        if removed {
            info!(policy_name = %name, "unregister_policy: removed");
        } else {
            warn!(policy_name = %name, "unregister_policy: not found");
        }
        removed
    }

    // ── ExecutePolicy (named) ─────────────────────────────────────────────────

    /// Execute a registered policy by name.
    ///
    /// Unlike `execute_wasm`, this uses the pre-compiled cached module from the
    /// registry, making it significantly faster for repeated calls.
    pub fn execute_named_policy(
        &self,
        policy_name: &str,
        event: &TownEvent,
        npc_state: Option<NpcState>,
        world_state: Option<WorldState>,
    ) -> Result<PolicyResult, String> {
        let input = PolicyInput {
            event: event.clone(),
            npc_state,
            world_state,
        };
        self.policy_registry.execute(policy_name, &input)
    }

    // ── ExecuteChain ──────────────────────────────────────────────────────────

    /// Execute a chain of named policies against one event.
    ///
    /// Policies are applied in order. The first rejection short-circuits the
    /// chain. Event modifications accumulate across policies.
    pub fn execute_policy_chain(
        &self,
        policy_names: &[String],
        event: &TownEvent,
        npc_state: Option<NpcState>,
        world_state: Option<WorldState>,
    ) -> crate::wasm_sandbox::ChainResult {
        let input = PolicyInput {
            event: event.clone(),
            npc_state,
            world_state,
        };
        self.policy_registry.execute_chain(policy_names, &input)
    }

    // ── Legacy execute_policy (backwards-compat) ──────────────────────────────

    /// Execute a user-submitted WASM policy against a single event (legacy).
    ///
    /// Returns `Ok(true)` = allow, `Ok(false)` = reject. Use `execute_wasm`
    /// for the new protocol with `PolicyResult`.
    pub fn execute_policy(&self, wasm_bytes: &[u8], event: &TownEvent) -> Result<bool, String> {
        self.sandbox
            .execute_policy(wasm_bytes, event)
            .map_err(|e| {
                warn!(npc_id = %event.npc_id, error = %e, "execute_policy: sandbox error");
                e.to_string()
            })
    }

    // ── Benchmark ─────────────────────────────────────────────────────────────

    /// Run a synthetic in-process benchmark.
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
            .filter(|ev| ev.iter().all(|r| r.valid))
            .count();
        let total_invalid = results.len() - total_valid;
        let elapsed_ms = elapsed.as_secs_f64() * 1000.0;
        let events_per_sec = if elapsed.as_secs_f64() > 0.0 {
            num_events as f64 / elapsed.as_secs_f64()
        } else {
            f64::INFINITY
        };

        info!(num_events, total_valid, total_invalid, elapsed_ms, events_per_sec, "run_benchmark");

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

// ─── Auxiliary types ──────────────────────────────────────────────────────────

/// Describes a single registered validation rule.
#[derive(Debug, Clone)]
pub struct RuleInfo {
    pub name: String,
    pub description: String,
    pub enabled: bool,
}

/// Timing and throughput statistics from a synthetic benchmark run.
#[derive(Debug, Clone)]
pub struct BenchmarkResult {
    pub total_events: usize,
    pub total_valid: usize,
    pub total_invalid: usize,
    pub elapsed_ms: f64,
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

    #[test]
    fn list_policies_initially_empty() {
        let svc = FortressService::new();
        assert!(svc.list_policies().is_empty());
    }

    #[test]
    fn unregister_nonexistent_policy_returns_false() {
        let svc = FortressService::new();
        assert!(!svc.unregister_policy("ghost"));
    }

    #[test]
    fn execute_named_policy_unknown_returns_error() {
        let svc = FortressService::new();
        let event = trade_event(1, 100.0);
        let result = svc.execute_named_policy("nonexistent", &event, None, None);
        assert!(result.is_err());
    }

    #[test]
    fn compile_policy_rejects_unsafe_source() {
        let svc = FortressService::new();
        let src = "unsafe fn f() {}";
        let result = svc.compile_policy(src);
        assert!(
            matches!(result, Err(CompileError::UnsafeCode)),
            "should reject unsafe code"
        );
    }

    #[test]
    fn execute_wasm_with_invalid_bytes_returns_error() {
        let svc = FortressService::new();
        let event = trade_event(1, 50.0);
        let result = svc.execute_wasm(b"not wasm", &event, None, None);
        assert!(result.is_err());
    }

    #[test]
    fn execute_policy_chain_empty_is_allowed() {
        let svc = FortressService::new();
        let event = trade_event(1, 50.0);
        let result = svc.execute_policy_chain(&[], &event, None, None);
        assert!(result.allowed);
    }
}
