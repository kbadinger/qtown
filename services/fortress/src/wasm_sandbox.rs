//! WASM sandbox — executes user-submitted policy modules via Wasmtime.
//!
//! # Purpose
//!
//! Town operators can upload custom validation logic as `.wasm` modules. The
//! sandbox isolates that code from the host process: each invocation runs with
//! a strict memory cap and a fuel budget (Wasmtime's instruction-counting
//! mechanism). An exhausted fuel budget or a memory trap causes the policy to
//! return an error rather than crashing the engine.
//!
//! # Security model
//!
//! * **Memory isolation** — each call uses a fresh `Store`; no state leaks
//!   between policy invocations.
//! * **Fuel metering** — caps CPU work at `MAX_FUEL` units per call.
//! * **No WASI** — modules have no access to the file system, network, or
//!   environment variables unless explicitly linked (none are).
//! * **No unsafe in the hot path** — Wasmtime's safe API is used throughout.
//!
//! # Policy result protocol
//!
//! The WASM module exports `evaluate(ptr: i32, len: i32) -> i32` where:
//! - Input: JSON-encoded `PolicyInput` (TownEvent + NPCState + WorldState)
//! - Output ptr: written to WASM memory at the returned i32 offset
//! - The output is a JSON-encoded `PolicyResult`
//!
//! Legacy `validate` export (returns i32 1/0) is still supported for compat.

use std::fmt;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::Instant;

use serde::{Deserialize, Serialize};
use serde_json;
use wasmtime::{Engine, Linker, Module, Store};

use crate::types::TownEvent;

// ─── Constants ────────────────────────────────────────────────────────────────

/// Default memory cap for a sandbox instance (64 MiB).
pub const DEFAULT_MEMORY_LIMIT_BYTES: usize = 64 * 1024 * 1024;

/// Maximum fuel (approximate instruction budget) per policy call.
/// Wasmtime consumes 1 unit per WebAssembly instruction.
pub const MAX_FUEL_PER_CALL: u64 = 1_000_000;

// ─── Domain types ─────────────────────────────────────────────────────────────

/// State snapshot of a single NPC at evaluation time.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NpcState {
    pub id: i64,
    pub name: String,
    pub role: String,
    pub gold: f64,
    pub happiness: f64,
    pub hunger: f64,
    pub energy: f64,
    pub neighborhood: String,
}

/// Global world state snapshot at evaluation time.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorldState {
    pub tick: u64,
    pub day_number: u32,
    pub time_of_day: f64,
    pub is_night: bool,
    pub population: u32,
    pub total_gold: f64,
    pub average_happiness: f64,
}

/// Full context passed to a WASM policy's `evaluate` function as JSON.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyInput {
    pub event: TownEvent,
    pub npc_state: Option<NpcState>,
    pub world_state: Option<WorldState>,
}

/// The result returned by a WASM policy's `evaluate` function.
///
/// Policies can approve, reject, or modify events. Modifications from multiple
/// chained policies accumulate: the last modifier wins per field.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyResult {
    /// Whether the event is allowed to proceed.
    pub allowed: bool,

    /// Human-readable reason (shown in audit logs).
    pub reason: String,

    /// Optional modified version of the event. If `Some`, downstream
    /// processing uses this instead of the original event.
    pub modified_event: Option<TownEvent>,
}

impl PolicyResult {
    /// Construct an allowing result with no modification.
    pub fn allow(reason: impl Into<String>) -> Self {
        Self {
            allowed: true,
            reason: reason.into(),
            modified_event: None,
        }
    }

    /// Construct a rejecting result.
    pub fn reject(reason: impl Into<String>) -> Self {
        Self {
            allowed: false,
            reason: reason.into(),
            modified_event: None,
        }
    }
}

/// Result of executing a chain of policies against a single event.
#[derive(Debug, Clone)]
pub struct ChainResult {
    /// Final verdict after running all policies.
    pub allowed: bool,

    /// Reason from the first rejecting policy, or from the last policy if all
    /// allowed.
    pub reason: String,

    /// Accumulated event modifications. If multiple policies modify the event,
    /// the last modification wins.
    pub final_event: TownEvent,

    /// Per-policy verdicts for audit/debugging.
    pub policy_results: Vec<(String, PolicyResult)>,
}

// ─── Error type ───────────────────────────────────────────────────────────────

/// Errors that can occur during sandbox execution.
#[derive(Debug)]
pub enum SandboxError {
    /// Wasmtime engine or module initialisation failed.
    Setup(wasmtime::Error),

    /// The module rejected the event or the policy returned an error code.
    PolicyRejected(String),

    /// The module consumed all available fuel (infinite-loop guard).
    FuelExhausted,

    /// The module trapped (OOM, unreachable instruction, etc.).
    Trap(wasmtime::Error),

    /// Serialisation of the event to JSON failed before the call.
    Serialisation(serde_json::Error),

    /// The output written by the policy could not be decoded.
    OutputDecode(String),
}

impl fmt::Display for SandboxError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            SandboxError::Setup(e) => write!(f, "sandbox setup error: {e}"),
            SandboxError::PolicyRejected(msg) => write!(f, "policy rejected event: {msg}"),
            SandboxError::FuelExhausted => {
                write!(f, "policy exhausted its fuel budget (infinite loop guard)")
            }
            SandboxError::Trap(e) => write!(f, "WASM trap: {e}"),
            SandboxError::Serialisation(e) => write!(f, "event serialisation error: {e}"),
            SandboxError::OutputDecode(s) => write!(f, "policy output decode error: {s}"),
        }
    }
}

impl std::error::Error for SandboxError {}

// ─── Execution statistics ─────────────────────────────────────────────────────

/// Per-policy execution statistics updated atomically on each call.
#[derive(Debug, Default)]
pub struct PolicyStats {
    /// Total number of times this policy was invoked.
    pub invocation_count: AtomicU64,

    /// Total fuel consumed across all invocations.
    pub total_fuel_consumed: AtomicU64,

    /// Total execution duration in microseconds (for avg calculation).
    pub total_duration_us: AtomicU64,

    /// Number of failed invocations (traps, fuel exhaustion, decode errors).
    pub error_count: AtomicU64,
}

impl PolicyStats {
    /// Record one successful invocation.
    pub fn record_success(&self, fuel_consumed: u64, duration_us: u64) {
        self.invocation_count.fetch_add(1, Ordering::Relaxed);
        self.total_fuel_consumed
            .fetch_add(fuel_consumed, Ordering::Relaxed);
        self.total_duration_us
            .fetch_add(duration_us, Ordering::Relaxed);
    }

    /// Record one failed invocation.
    pub fn record_error(&self) {
        self.invocation_count.fetch_add(1, Ordering::Relaxed);
        self.error_count.fetch_add(1, Ordering::Relaxed);
    }

    /// Average duration in milliseconds.
    pub fn avg_duration_ms(&self) -> f64 {
        let count = self.invocation_count.load(Ordering::Relaxed);
        if count == 0 {
            return 0.0;
        }
        let total_us = self.total_duration_us.load(Ordering::Relaxed);
        (total_us as f64 / count as f64) / 1000.0
    }

    /// Snapshot of statistics for serialisation.
    pub fn snapshot(&self) -> PolicyStatsSnapshot {
        PolicyStatsSnapshot {
            invocation_count: self.invocation_count.load(Ordering::Relaxed),
            total_fuel_consumed: self.total_fuel_consumed.load(Ordering::Relaxed),
            avg_duration_ms: self.avg_duration_ms(),
            error_count: self.error_count.load(Ordering::Relaxed),
        }
    }
}

/// Serialisable snapshot of `PolicyStats`.
#[derive(Debug, Clone, Serialize)]
pub struct PolicyStatsSnapshot {
    pub invocation_count: u64,
    pub total_fuel_consumed: u64,
    pub avg_duration_ms: f64,
    pub error_count: u64,
}

// ─── Host-side data threaded through the Store ────────────────────────────────

/// Data stored in the Wasmtime `Store` for the duration of one policy call.
struct HostState {
    /// JSON-serialised `PolicyInput` written to WASM memory before the call.
    input_json: Vec<u8>,
    /// Output bytes read back from WASM memory after the call.
    output_json: Vec<u8>,
}

// ─── WasmSandbox ─────────────────────────────────────────────────────────────

/// Executes user-submitted policy modules in an isolated WASM sandbox.
///
/// A single `WasmSandbox` instance can be reused across many policy calls; it
/// owns the `Engine` (and its JIT cache) but creates a fresh `Store` per call
/// to guarantee hermetic isolation.
pub struct WasmSandbox {
    /// Shared Wasmtime engine — holds the JIT compiler and module cache.
    pub(crate) engine: Engine,

    /// Maximum linear-memory bytes each module is allowed to allocate.
    memory_limit_bytes: usize,
}

impl WasmSandbox {
    /// Creates a new sandbox with the given memory cap.
    pub fn new(memory_limit_bytes: usize) -> Self {
        let mut config = wasmtime::Config::new();

        // Enable fuel metering so we can cap CPU work per call.
        config.consume_fuel(true);

        // Limit stack per call.
        config.max_wasm_stack(512 * 1024); // 512 KiB stack per call

        let engine = Engine::new(&config).expect("failed to create Wasmtime engine");

        Self {
            engine,
            memory_limit_bytes,
        }
    }

    /// Creates a sandbox with the default 64 MiB memory limit.
    pub fn with_defaults() -> Self {
        Self::new(DEFAULT_MEMORY_LIMIT_BYTES)
    }

    // ── Core execution ────────────────────────────────────────────────────────

    /// Execute a pre-compiled `Module` with a full `PolicyInput` context.
    ///
    /// Tries the new `evaluate` export first (returns `PolicyResult` JSON),
    /// then falls back to the legacy `validate` export (returns i32 1/0).
    pub fn execute_module(
        &self,
        module: &Module,
        input: &PolicyInput,
        stats: Option<&PolicyStats>,
    ) -> Result<PolicyResult, SandboxError> {
        let input_json = serde_json::to_vec(input).map_err(SandboxError::Serialisation)?;

        let host_state = HostState {
            input_json,
            output_json: Vec::new(),
        };

        let mut store: Store<HostState> = Store::new(&self.engine, host_state);
        store
            .set_fuel(MAX_FUEL_PER_CALL)
            .map_err(SandboxError::Setup)?;

        store.limiter(|_state| &mut MemoryLimiter {
            limit: self.memory_limit_bytes,
        });

        let linker: Linker<HostState> = Linker::new(&self.engine);
        let instance = linker
            .instantiate(&mut store, module)
            .map_err(SandboxError::Trap)?;

        let memory = instance
            .get_memory(&mut store, "memory")
            .ok_or_else(|| SandboxError::Setup(wasmtime::Error::msg("module has no 'memory' export")))?;

        // Write input JSON at offset 0.
        let input_bytes = store.data().input_json.clone();
        let input_ptr: i32 = 0;
        let input_len: i32 = input_bytes.len() as i32;

        memory
            .write(&mut store, input_ptr as usize, &input_bytes)
            .map_err(|e| SandboxError::Trap(e.into()))?;

        let start = Instant::now();
        let fuel_before = store.fuel_consumed().unwrap_or(0);

        // Try the new `evaluate` export first.
        let result = if let Ok(evaluate_fn) =
            instance.get_typed_func::<(i32, i32), i32>(&mut store, "evaluate")
        {
            let out_ptr = evaluate_fn
                .call(&mut store, (input_ptr, input_len))
                .map_err(|e| {
                    if store.fuel_consumed().unwrap_or(0) >= MAX_FUEL_PER_CALL {
                        SandboxError::FuelExhausted
                    } else {
                        SandboxError::Trap(e)
                    }
                })?;

            // Read output JSON from WASM memory.
            // Convention: the module writes [4-byte-len][json-bytes] at out_ptr.
            if out_ptr <= 0 {
                // Negative/zero pointer = rejection with no message.
                Ok(PolicyResult::reject("policy returned null output pointer"))
            } else {
                let mem_data = memory.data(&store);
                let base = out_ptr as usize;
                if base + 4 > mem_data.len() {
                    Err(SandboxError::OutputDecode(
                        "output pointer out of bounds".into(),
                    ))
                } else {
                    let len = u32::from_le_bytes([
                        mem_data[base],
                        mem_data[base + 1],
                        mem_data[base + 2],
                        mem_data[base + 3],
                    ]) as usize;
                    let end = base + 4 + len;
                    if end > mem_data.len() {
                        Err(SandboxError::OutputDecode("output JSON truncated".into()))
                    } else {
                        let json_slice = &mem_data[base + 4..end];
                        serde_json::from_slice::<PolicyResult>(json_slice).map_err(|e| {
                            SandboxError::OutputDecode(format!("JSON decode: {e}"))
                        })
                    }
                }
            }
        } else if let Ok(validate_fn) =
            instance.get_typed_func::<(i32, i32), i32>(&mut store, "validate")
        {
            // Legacy protocol: 1 = allow, 0 = reject.
            let code = validate_fn
                .call(&mut store, (input_ptr, input_len))
                .map_err(|e| {
                    if store.fuel_consumed().unwrap_or(0) >= MAX_FUEL_PER_CALL {
                        SandboxError::FuelExhausted
                    } else {
                        SandboxError::Trap(e)
                    }
                })?;
            match code {
                1 => Ok(PolicyResult::allow("policy accepted (legacy validate=1)")),
                0 => Ok(PolicyResult::reject("policy rejected (legacy validate=0)")),
                c => Err(SandboxError::PolicyRejected(format!(
                    "legacy validate returned unknown code {c}"
                ))),
            }
        } else {
            Err(SandboxError::Setup(wasmtime::Error::msg(
                "module exports neither 'evaluate' nor 'validate'",
            )))
        };

        let elapsed_us = start.elapsed().as_micros() as u64;
        let fuel_consumed = store.fuel_consumed().unwrap_or(0).saturating_sub(fuel_before);

        if let Some(s) = stats {
            match &result {
                Ok(_) => s.record_success(fuel_consumed, elapsed_us),
                Err(_) => s.record_error(),
            }
        }

        result
    }

    /// Compile raw WASM bytes into a cached `Module` using the shared engine.
    pub fn compile(&self, wasm_bytes: &[u8]) -> Result<Module, SandboxError> {
        Module::new(&self.engine, wasm_bytes).map_err(SandboxError::Setup)
    }

    // ── Legacy execute_policy (backwards-compat) ──────────────────────────────

    /// Execute a user-submitted policy WASM module against a single event.
    ///
    /// Returns `Ok(true)` if the policy accepted the event, `Ok(false)` if
    /// rejected. Deprecated in favour of `execute_module`.
    pub fn execute_policy(
        &self,
        wasm_bytes: &[u8],
        event: &TownEvent,
    ) -> Result<bool, SandboxError> {
        let module = self.compile(wasm_bytes)?;
        let input = PolicyInput {
            event: event.clone(),
            npc_state: None,
            world_state: None,
        };
        let result = self.execute_module(&module, &input, None)?;
        Ok(result.allowed)
    }

    // ── Chain execution ───────────────────────────────────────────────────────

    /// Execute a sequence of compiled modules against one event.
    ///
    /// Chain semantics:
    /// - If any policy rejects, the chain stops immediately and returns the
    ///   rejection.
    /// - Modifications from `modified_event` accumulate: each policy receives
    ///   the event as modified by all prior policies.
    /// - All policy verdicts are recorded for audit regardless of short-circuit.
    pub fn execute_chain(
        &self,
        modules: &[(String, Arc<Module>, Arc<PolicyStats>)],
        input: &PolicyInput,
    ) -> ChainResult {
        let mut current_event = input.event.clone();
        let mut policy_results: Vec<(String, PolicyResult)> = Vec::new();

        for (name, module, stats) in modules {
            let step_input = PolicyInput {
                event: current_event.clone(),
                npc_state: input.npc_state.clone(),
                world_state: input.world_state.clone(),
            };

            let verdict = match self.execute_module(module, &step_input, Some(stats)) {
                Ok(r) => r,
                Err(e) => PolicyResult::reject(format!("sandbox error: {e}")),
            };

            if let Some(ref modified) = verdict.modified_event {
                current_event = modified.clone();
            }

            let rejected = !verdict.allowed;
            let reason_clone = verdict.reason.clone();
            policy_results.push((name.clone(), verdict));

            if rejected {
                return ChainResult {
                    allowed: false,
                    reason: reason_clone,
                    final_event: current_event,
                    policy_results,
                };
            }
        }

        let reason = policy_results
            .last()
            .map(|(_, r)| r.reason.clone())
            .unwrap_or_else(|| "no policies registered".into());

        ChainResult {
            allowed: true,
            reason,
            final_event: current_event,
            policy_results,
        }
    }
}

// ─── MemoryLimiter ───────────────────────────────────────────────────────────

/// Wasmtime resource limiter that caps linear-memory growth.
struct MemoryLimiter {
    limit: usize,
}

impl wasmtime::ResourceLimiter for MemoryLimiter {
    fn memory_growing(
        &mut self,
        _current: usize,
        desired: usize,
        _maximum: Option<usize>,
    ) -> Result<bool, wasmtime::Error> {
        Ok(desired <= self.limit)
    }

    fn table_growing(
        &mut self,
        _current: u32,
        _desired: u32,
        _maximum: Option<u32>,
    ) -> Result<bool, wasmtime::Error> {
        Ok(true)
    }
}

// ─────────────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_event() -> TownEvent {
        TownEvent {
            event_type: "trade".to_string(),
            npc_id: 7,
            amount: 42.0,
            resource: Some("gold".to_string()),
            metadata: None,
        }
    }

    #[test]
    fn sandbox_constructs_with_defaults() {
        let sandbox = WasmSandbox::with_defaults();
        assert_eq!(sandbox.memory_limit_bytes, DEFAULT_MEMORY_LIMIT_BYTES);
    }

    #[test]
    fn invalid_wasm_bytes_return_setup_error() {
        let sandbox = WasmSandbox::with_defaults();
        let event = sample_event();
        let result = sandbox.execute_policy(b"not valid wasm", &event);
        assert!(matches!(result, Err(SandboxError::Setup(_))));
    }

    #[test]
    fn policy_result_constructors() {
        let allow = PolicyResult::allow("all good");
        assert!(allow.allowed);
        assert_eq!(allow.reason, "all good");
        assert!(allow.modified_event.is_none());

        let reject = PolicyResult::reject("too much gold");
        assert!(!reject.allowed);
        assert_eq!(reject.reason, "too much gold");
    }

    #[test]
    fn policy_stats_avg_duration() {
        let stats = PolicyStats::default();
        assert_eq!(stats.avg_duration_ms(), 0.0);
        stats.record_success(100, 2_000); // 2ms
        stats.record_success(200, 4_000); // 4ms
        let avg = stats.avg_duration_ms();
        assert!((avg - 3.0).abs() < 0.001, "expected ~3ms, got {avg}");
    }

    #[test]
    fn chain_result_with_empty_modules() {
        let sandbox = WasmSandbox::with_defaults();
        let input = PolicyInput {
            event: sample_event(),
            npc_state: None,
            world_state: None,
        };
        let result = sandbox.execute_chain(&[], &input);
        assert!(result.allowed);
        assert!(result.policy_results.is_empty());
    }
}
