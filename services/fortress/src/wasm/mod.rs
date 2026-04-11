//! WASM policy subsystem — module re-exports.
//!
//! This module aggregates the compilation pipeline, in-memory policy registry,
//! default template, and integration tests for the Fortress WASM runtime.
//!
//! # Module map
//!
//! ```
//! wasm/
//!   mod.rs            — re-exports (this file)
//!   compiler.rs       — Rust → WASM compilation pipeline with security checks
//!   policy_registry.rs— in-memory policy registry with hot-reload support
//!   policy_template.rs— default Rust policy template for the editor
//!   tests.rs          — integration tests for the full WASM pipeline
//! ```

pub mod compiler;
pub mod policy_registry;
pub mod policy_template;

#[cfg(test)]
pub mod tests;

// ─── Re-exports ───────────────────────────────────────────────────────────────

pub use compiler::{compile_policy, CompileError, CompileResult};
pub use policy_registry::{
    ChainResult, PolicyEntry, PolicyRegistry, PolicySummary,
};
pub use crate::wasm_sandbox::PolicyStatsSnapshot;
pub use policy_template::DEFAULT_POLICY_TEMPLATE;
