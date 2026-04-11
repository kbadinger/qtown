//! In-memory policy registry with hot-reload support.
//!
//! The `PolicyRegistry` stores compiled WASM modules alongside their metadata
//! and per-policy execution statistics. Modules are keyed by name. Replacing a
//! module (hot-reload) is an atomic write behind an `RwLock` — ongoing calls
//! complete with the old module while the new one takes effect immediately for
//! subsequent invocations.
//!
//! # Thread safety
//!
//! `PolicyRegistry` wraps its state in `Arc<RwLock<_>>` so it can be shared
//! across Tokio tasks and Rayon worker threads without additional wrapping.

use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use serde::Serialize;
use wasmtime::Module;

use crate::wasm_sandbox::{
    PolicyInput, PolicyResult, PolicyStats, PolicyStatsSnapshot, WasmSandbox,
};

/// Result of running a named policy chain against one event.
/// Re-exported from `wasm_sandbox` for consumers that import from `wasm/`.
pub use crate::wasm_sandbox::ChainResult;

// ─── Registry entry ───────────────────────────────────────────────────────────

/// Full record for a registered policy, including the compiled module.
pub struct PolicyEntry {
    /// Unique string identifier (e.g. "gold-cap-policy").
    pub id: String,

    /// Human-readable name (same as id for the prototype).
    pub name: String,

    /// Monotonically increasing version counter. Bumped on hot-reload.
    pub version: u32,

    /// Original `.wasm` bytes (kept for download / re-compile).
    pub wasm_bytes: Vec<u8>,

    /// Pre-compiled Wasmtime module (shared across calls via `Arc`).
    pub compiled_module: Arc<Module>,

    /// Policy author (free-text, from registration request).
    pub author: String,

    /// Unix timestamp (seconds) of when this entry was first registered.
    pub created_at: u64,

    /// Unix timestamp (seconds) of the most recent hot-reload.
    pub updated_at: u64,

    /// Execution statistics updated atomically on every invocation.
    pub stats: Arc<PolicyStats>,

    /// Last error message observed during execution (if any).
    pub last_error: RwLock<Option<String>>,
}

impl std::fmt::Debug for PolicyEntry {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("PolicyEntry")
            .field("id", &self.id)
            .field("version", &self.version)
            .field("author", &self.author)
            .finish()
    }
}

// ─── Serialisable summary ─────────────────────────────────────────────────────

/// Lightweight snapshot of a `PolicyEntry` — safe to serialise and send over
/// the wire (does not include raw WASM bytes or the compiled module).
#[derive(Debug, Clone, Serialize)]
pub struct PolicySummary {
    pub id: String,
    pub name: String,
    pub version: u32,
    pub author: String,
    pub created_at: u64,
    pub updated_at: u64,
    pub wasm_size_bytes: usize,
    pub stats: PolicyStatsSnapshot,
    pub last_error: Option<String>,
}

// ─── Registry ─────────────────────────────────────────────────────────────────

/// In-memory store of compiled WASM policies.
///
/// Clone is cheap — the inner `Arc<RwLock<_>>` is shared.
#[derive(Clone)]
pub struct PolicyRegistry {
    sandbox: Arc<WasmSandbox>,
    entries: Arc<RwLock<HashMap<String, PolicyEntry>>>,
}

impl PolicyRegistry {
    /// Create a new, empty registry backed by the given sandbox.
    pub fn new(sandbox: Arc<WasmSandbox>) -> Self {
        Self {
            sandbox,
            entries: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    // ── Registration ─────────────────────────────────────────────────────────

    /// Register or hot-reload a named policy from raw WASM bytes.
    ///
    /// If `name` already exists in the registry, the module is replaced
    /// in-place (hot-reload) and the version counter is incremented.
    ///
    /// Returns a `PolicySummary` of the new entry.
    pub fn register(
        &self,
        name: impl Into<String>,
        wasm_bytes: Vec<u8>,
        author: impl Into<String>,
    ) -> Result<PolicySummary, String> {
        let name = name.into();
        let author = author.into();

        // Compile the module using the shared engine.
        let compiled_module = self
            .sandbox
            .compile(&wasm_bytes)
            .map_err(|e| e.to_string())?;

        let now = now_secs();

        let mut entries = self.entries.write().expect("registry write lock poisoned");

        let entry = entries.entry(name.clone()).or_insert_with(|| PolicyEntry {
            id: name.clone(),
            name: name.clone(),
            version: 0,
            wasm_bytes: Vec::new(),
            compiled_module: Arc::new(compiled_module.clone()),
            author: author.clone(),
            created_at: now,
            updated_at: now,
            stats: Arc::new(PolicyStats::default()),
            last_error: RwLock::new(None),
        });

        // Update fields (hot-reload path for existing entries).
        entry.wasm_bytes = wasm_bytes.clone();
        entry.compiled_module = Arc::new(compiled_module);
        entry.author = author;
        entry.updated_at = now;
        entry.version += 1;

        Ok(PolicySummary {
            id: entry.id.clone(),
            name: entry.name.clone(),
            version: entry.version,
            author: entry.author.clone(),
            created_at: entry.created_at,
            updated_at: entry.updated_at,
            wasm_size_bytes: wasm_bytes.len(),
            stats: entry.stats.snapshot(),
            last_error: entry
                .last_error
                .read()
                .ok()
                .and_then(|g| g.clone()),
        })
    }

    // ── Removal ───────────────────────────────────────────────────────────────

    /// Remove a named policy from the registry.
    ///
    /// Returns `true` if the policy was found and removed, `false` if it did
    /// not exist.
    pub fn unregister(&self, name: &str) -> bool {
        let mut entries = self.entries.write().expect("registry write lock poisoned");
        entries.remove(name).is_some()
    }

    // ── Lookup ────────────────────────────────────────────────────────────────

    /// Check if a policy with the given name is registered.
    pub fn contains(&self, name: &str) -> bool {
        let entries = self.entries.read().expect("registry read lock poisoned");
        entries.contains_key(name)
    }

    // ── Enumeration ───────────────────────────────────────────────────────────

    /// List all registered policies as lightweight summaries.
    ///
    /// Results are sorted by `name` for stable ordering.
    pub fn list(&self) -> Vec<PolicySummary> {
        let entries = self.entries.read().expect("registry read lock poisoned");
        let mut summaries: Vec<PolicySummary> = entries
            .values()
            .map(|e| PolicySummary {
                id: e.id.clone(),
                name: e.name.clone(),
                version: e.version,
                author: e.author.clone(),
                created_at: e.created_at,
                updated_at: e.updated_at,
                wasm_size_bytes: e.wasm_bytes.len(),
                stats: e.stats.snapshot(),
                last_error: e.last_error.read().ok().and_then(|g| g.clone()),
            })
            .collect();
        summaries.sort_by(|a, b| a.name.cmp(&b.name));
        summaries
    }

    // ── Execution ─────────────────────────────────────────────────────────────

    /// Execute a single named policy against the given input.
    ///
    /// Returns `Err(String)` if the policy is not registered or the sandbox
    /// traps.
    pub fn execute(
        &self,
        policy_name: &str,
        input: &PolicyInput,
    ) -> Result<PolicyResult, String> {
        let entries = self.entries.read().expect("registry read lock poisoned");
        let entry = entries
            .get(policy_name)
            .ok_or_else(|| format!("policy '{policy_name}' not registered"))?;

        let module = Arc::clone(&entry.compiled_module);
        let stats = Arc::clone(&entry.stats);
        drop(entries); // release read lock before sandbox execution

        let result = self
            .sandbox
            .execute_module(&module, input, Some(&stats));

        match result {
            Ok(r) => Ok(r),
            Err(e) => {
                let msg = e.to_string();
                // Record last error (best-effort — ignore lock poison).
                if let Ok(entries_r) = self.entries.read() {
                    if let Some(entry_r) = entries_r.get(policy_name) {
                        if let Ok(mut last_err) = entry_r.last_error.write() {
                            *last_err = Some(msg.clone());
                        }
                    }
                }
                Err(msg)
            }
        }
    }

    /// Execute a chain of named policies against one event.
    ///
    /// Chain semantics (same as `WasmSandbox::execute_chain`):
    /// - First rejection short-circuits the chain.
    /// - Event modifications accumulate across policies.
    ///
    /// Policies that are not registered are skipped with a warning included in
    /// the chain result's policy_results list.
    pub fn execute_chain(
        &self,
        policy_names: &[String],
        input: &PolicyInput,
    ) -> ChainResult {
        let entries = self.entries.read().expect("registry read lock poisoned");

        // Collect (name, module, stats) for policies that exist.
        // Missing policies are flagged as immediate rejections in the result.
        let modules: Vec<(String, Arc<Module>, Arc<PolicyStats>)> = policy_names
            .iter()
            .filter_map(|name| {
                entries.get(name.as_str()).map(|e| {
                    (
                        name.clone(),
                        Arc::clone(&e.compiled_module),
                        Arc::clone(&e.stats),
                    )
                })
            })
            .collect();

        // Check for missing policies.
        let missing: Vec<&String> = policy_names
            .iter()
            .filter(|n| !entries.contains_key(n.as_str()))
            .collect();

        drop(entries); // release read lock before sandbox calls

        if !missing.is_empty() {
            let names = missing
                .iter()
                .map(|s| s.as_str())
                .collect::<Vec<_>>()
                .join(", ");
            return ChainResult {
                allowed: false,
                reason: format!("unknown policies: {names}"),
                final_event: input.event.clone(),
                policy_results: missing
                    .iter()
                    .map(|n| {
                        (
                            n.to_string(),
                            PolicyResult::reject(format!("policy '{n}' not registered")),
                        )
                    })
                    .collect(),
            };
        }

        self.sandbox.execute_chain(&modules, input)
    }
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or(Duration::ZERO)
        .as_secs()
}

// PolicyStatsSnapshot is imported from wasm_sandbox above and re-exported
// via `wasm/mod.rs` — no additional re-export needed here.

// ─── Unit tests ───────────────────────────────────────────────────────────────

#[cfg(test)]
mod unit_tests {
    use super::*;

    fn make_registry() -> PolicyRegistry {
        let sandbox = Arc::new(WasmSandbox::with_defaults());
        PolicyRegistry::new(sandbox)
    }

    fn sample_input() -> PolicyInput {
        PolicyInput {
            event: crate::types::TownEvent {
                event_type: "trade".to_string(),
                npc_id: 1,
                amount: 50.0,
                resource: Some("gold".to_string()),
                metadata: None,
            },
            npc_state: None,
            world_state: None,
        }
    }

    #[test]
    fn empty_registry_list_is_empty() {
        let reg = make_registry();
        assert!(reg.list().is_empty());
    }

    #[test]
    fn unregister_nonexistent_returns_false() {
        let reg = make_registry();
        assert!(!reg.unregister("ghost"));
    }

    #[test]
    fn execute_unknown_policy_returns_err() {
        let reg = make_registry();
        let input = sample_input();
        let result = reg.execute("nonexistent", &input);
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("not registered"));
    }

    #[test]
    fn execute_chain_with_missing_policy() {
        let reg = make_registry();
        let input = sample_input();
        let chain = reg.execute_chain(&["missing".to_string()], &input);
        assert!(!chain.allowed);
        assert!(chain.reason.contains("unknown policies"));
    }

    #[test]
    fn execute_chain_empty_is_allowed() {
        let reg = make_registry();
        let input = sample_input();
        let chain = reg.execute_chain(&[], &input);
        // Empty chain — sandbox returns allowed with "no policies registered".
        assert!(chain.allowed);
    }
}
