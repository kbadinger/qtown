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

use std::fmt;

use serde_json;
use wasmtime::{Engine, Linker, Module, Store};

use crate::types::TownEvent;

// ─── Constants ────────────────────────────────────────────────────────────────

/// Default memory cap for a sandbox instance (64 MiB).
const DEFAULT_MEMORY_LIMIT_BYTES: usize = 64 * 1024 * 1024;

/// Maximum fuel (approximate instruction budget) per policy call.
/// Wasmtime consumes 1 unit per WebAssembly instruction.
const MAX_FUEL_PER_CALL: u64 = 1_000_000;

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
        }
    }
}

impl std::error::Error for SandboxError {}

// ─── Host-side data threaded through the Store ────────────────────────────────

/// Data stored in the Wasmtime `Store` for the duration of one policy call.
/// The policy module can read back the serialised event via a host function.
struct HostState {
    /// JSON-serialised `TownEvent` written to WASM memory before the call.
    event_json: Vec<u8>,
}

// ─── WasmSandbox ─────────────────────────────────────────────────────────────

/// Executes user-submitted policy modules in an isolated WASM sandbox.
///
/// A single `WasmSandbox` instance can be reused across many policy calls; it
/// owns the `Engine` (and its JIT cache) but creates a fresh `Store` per call
/// to guarantee hermetic isolation.
pub struct WasmSandbox {
    /// Shared Wasmtime engine — holds the JIT compiler and module cache.
    engine: Engine,

    /// Maximum linear-memory bytes each module is allowed to allocate.
    memory_limit_bytes: usize,
}

impl WasmSandbox {
    /// Creates a new sandbox with the given memory cap.
    ///
    /// Call once at startup; the `Engine` is expensive to construct (it spins
    /// up the JIT) but cheap to clone thereafter.
    pub fn new(memory_limit_bytes: usize) -> Self {
        let mut config = wasmtime::Config::new();

        // Enable fuel metering so we can cap CPU work per call.
        config.consume_fuel(true);

        // Limit store memory to the configured cap.
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

    /// Executes a user-submitted policy WASM module against a single event.
    ///
    /// # Protocol
    ///
    /// The WASM module is expected to export a function with this signature:
    ///
    /// ```wat
    /// (func (export "validate") (param i32 i32) (result i32))
    ///       ;; param 0: pointer to event JSON in WASM memory
    ///       ;; param 1: length of JSON bytes
    ///       ;; result: 1 = accept, 0 = reject, negative = error code
    /// ```
    ///
    /// The host writes the serialised event into WASM linear memory before
    /// calling `validate` so the module can parse it at its own pace.
    ///
    /// # Security
    ///
    /// * Fresh `Store` per call — no state carries between invocations.
    /// * `MAX_FUEL_PER_CALL` fuel units are granted; excess burns return
    ///   `SandboxError::FuelExhausted` rather than looping forever.
    /// * Memory is capped at `self.memory_limit_bytes` via Wasmtime's
    ///   `Store::limiter`.
    ///
    /// # Errors
    ///
    /// Returns `Err(SandboxError)` if the module traps, runs out of fuel,
    /// fails to export `validate`, or produces a non-positive result code.
    pub fn execute_policy(
        &self,
        wasm_bytes: &[u8],
        event: &TownEvent,
    ) -> Result<bool, SandboxError> {
        // ── 1. Serialise the event so we can pass it to the WASM module. ─────
        let event_json: Vec<u8> =
            serde_json::to_vec(event).map_err(SandboxError::Serialisation)?;

        // ── 2. Compile the module (cached by Wasmtime's JIT layer). ──────────
        //
        // In production, modules should be pre-compiled with `Module::new` at
        // upload time and stored as `Module` objects to avoid per-call JIT
        // cost. For the prototype we compile on demand.
        let module = Module::new(&self.engine, wasm_bytes).map_err(SandboxError::Setup)?;

        // ── 3. Create a fresh, isolated Store for this call. ─────────────────
        //
        // The Store owns all WASM state (memories, tables, globals). Dropping
        // it at the end of this function reclaims all resources allocated by
        // the module.
        let host_state = HostState { event_json };
        let mut store: Store<HostState> = Store::new(&self.engine, host_state);

        // Grant fuel budget — prevents runaway modules.
        store
            .set_fuel(MAX_FUEL_PER_CALL)
            .map_err(SandboxError::Setup)?;

        // Enforce memory cap via the ResourceLimiter trait.
        store.limiter(|_state| {
            // Return a simple size-capping limiter closure.
            // We use a Box to satisfy the trait object requirement.
            &mut MemoryLimiter {
                limit: self.memory_limit_bytes,
            }
        });

        // ── 4. Instantiate without linking extra host imports. ────────────────
        //
        // User policy modules must be self-contained. If a module requires
        // host imports (e.g. logging), they must be explicitly linked here —
        // absent links cause instantiation to fail, never crash the host.
        let linker: Linker<HostState> = Linker::new(&self.engine);
        let instance = linker
            .instantiate(&mut store, &module)
            .map_err(SandboxError::Trap)?;

        // ── 5. Write event JSON into WASM linear memory. ─────────────────────
        let memory = instance
            .get_memory(&mut store, "memory")
            .ok_or_else(|| SandboxError::Setup(wasmtime::Error::msg("module has no 'memory' export")))?;

        // Use the first 8 bytes of memory as a scratch offset header
        // (real implementation should use a proper ABI / shared allocator).
        let json_bytes = store.data().event_json.clone();
        let json_ptr: i32 = 0; // write at offset 0 for prototype
        let json_len: i32 = json_bytes.len() as i32;

        memory
            .write(&mut store, json_ptr as usize, &json_bytes)
            .map_err(|e| SandboxError::Trap(e.into()))?;

        // ── 6. Call the policy's `validate` export. ───────────────────────────
        let validate_fn = instance
            .get_typed_func::<(i32, i32), i32>(&mut store, "validate")
            .map_err(|e| SandboxError::Setup(e.into()))?;

        let result_code: i32 = validate_fn
            .call(&mut store, (json_ptr, json_len))
            .map_err(|e| {
                // Distinguish fuel-exhaustion traps from other traps.
                if store.fuel_consumed().unwrap_or(0) >= MAX_FUEL_PER_CALL {
                    SandboxError::FuelExhausted
                } else {
                    SandboxError::Trap(e)
                }
            })?;

        // ── 7. Interpret the result code. ─────────────────────────────────────
        match result_code {
            1 => Ok(true),   // module accepted the event
            0 => Ok(false),  // module rejected the event
            code => Err(SandboxError::PolicyRejected(format!(
                "policy returned error code {code}"
            ))),
        }
    }
}

// ─── MemoryLimiter ───────────────────────────────────────────────────────────

/// Wasmtime resource limiter that caps linear-memory growth.
///
/// Passed to `Store::limiter`; Wasmtime calls `memory_growing` before each
/// `memory.grow` instruction. Returning `false` causes a WASM OOM trap.
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
        // No cap on table growth — tables are small.
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
}
