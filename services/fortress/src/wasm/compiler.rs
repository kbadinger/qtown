//! Rust → WASM compilation pipeline with security validation.
//!
//! Accepts Rust source code as a string, writes it to a temporary file,
//! invokes `rustc --target wasm32-unknown-unknown --crate-type cdylib`,
//! then validates the output module exports the required `evaluate` symbol.
//!
//! # Security controls
//!
//! 1. `unsafe` blocks — rejected at source level.
//! 2. Forbidden imports — `std::fs`, `std::net`, `std::process` cause
//!    `CompileError::ForbiddenImport`.
//! 3. Module export validation — the compiled `.wasm` must export `evaluate`
//!    (or the legacy `validate`) or `CompileError::MissingExport` is returned.
//! 4. Source size cap — inputs over 1 MiB are rejected.
//!
//! Note: actual `rustc` invocation requires a Rust toolchain with the
//! `wasm32-unknown-unknown` target installed on the host. In CI / Docker the
//! target is pre-installed; in unit tests, `compile_policy` is mocked via a
//! feature flag or the test supplies pre-built `.wasm` bytes directly.

use std::fmt;
use std::io::Write;
use std::path::PathBuf;
use std::process::Command;

// ─── Error type ───────────────────────────────────────────────────────────────

/// Errors produced by the compilation pipeline.
#[derive(Debug, Clone)]
pub enum CompileError {
    /// The Rust source code contains a syntax or semantic error reported by
    /// `rustc`. The payload is the compiler's stderr output.
    SyntaxError(String),

    /// The source contains `unsafe { … }` — rejected by policy.
    UnsafeCode,

    /// The source imports a forbidden module (`std::fs`, `std::net`,
    /// `std::process`). The payload names the offending import.
    ForbiddenImport(String),

    /// The compiled WASM module does not export `evaluate` or `validate`.
    MissingExport,

    /// A system-level error occurred (I/O, process spawn failure, etc.).
    CompilationFailed(String),
}

impl fmt::Display for CompileError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            CompileError::SyntaxError(msg) => write!(f, "syntax error: {msg}"),
            CompileError::UnsafeCode => {
                write!(f, "unsafe code is not permitted in policy modules")
            }
            CompileError::ForbiddenImport(imp) => {
                write!(f, "forbidden import '{imp}' — policies may not use std::fs, std::net, or std::process")
            }
            CompileError::MissingExport => {
                write!(f, "compiled module must export 'evaluate' or 'validate'")
            }
            CompileError::CompilationFailed(msg) => write!(f, "compilation failed: {msg}"),
        }
    }
}

impl std::error::Error for CompileError {}

/// Successful compilation output.
#[derive(Debug, Clone)]
pub struct CompileResult {
    /// Raw compiled `.wasm` bytes ready for the policy registry.
    pub wasm_bytes: Vec<u8>,

    /// Total compilation time in milliseconds.
    pub compile_duration_ms: u64,

    /// `rustc` version string captured from stderr (e.g. "rustc 1.78.0").
    pub compiler_version: String,
}

// ─── Forbidden patterns ───────────────────────────────────────────────────────

const MAX_SOURCE_BYTES: usize = 1024 * 1024; // 1 MiB

/// Patterns that trigger `CompileError::UnsafeCode`.
const UNSAFE_PATTERNS: &[&str] = &["unsafe {", "unsafe{", "unsafe fn ", "unsafe impl "];

/// (pattern, canonical_name) pairs that trigger `CompileError::ForbiddenImport`.
const FORBIDDEN_IMPORTS: &[(&str, &str)] = &[
    ("use std::fs", "std::fs"),
    ("use std::net", "std::net"),
    ("use std::process", "std::process"),
    ("std::fs::", "std::fs"),
    ("std::net::", "std::net"),
    ("std::process::", "std::process"),
    ("::std::fs", "std::fs"),
    ("::std::net", "std::net"),
    ("::std::process", "std::process"),
];

// ─── Source sanitisation ──────────────────────────────────────────────────────

/// Validate the Rust source before passing it to `rustc`.
///
/// Returns `Err(CompileError)` on the first security violation found.
fn sanitise_source(source: &str) -> Result<(), CompileError> {
    if source.len() > MAX_SOURCE_BYTES {
        return Err(CompileError::CompilationFailed(format!(
            "source too large: {} bytes (max {MAX_SOURCE_BYTES})",
            source.len()
        )));
    }

    // Check for unsafe blocks (simple textual scan — not a full AST parse, but
    // sufficient as a defence-in-depth layer before rustc runs).
    for pattern in UNSAFE_PATTERNS {
        if source.contains(pattern) {
            return Err(CompileError::UnsafeCode);
        }
    }

    // Check forbidden imports.
    for (pattern, canonical) in FORBIDDEN_IMPORTS {
        if source.contains(pattern) {
            return Err(CompileError::ForbiddenImport(canonical.to_string()));
        }
    }

    Ok(())
}

// ─── WASM export validation ───────────────────────────────────────────────────

/// Validate that the compiled WASM exports `evaluate` or `validate`.
///
/// Uses a lightweight hand-rolled binary parser for the export section rather
/// than pulling in a full `wasmparser` dependency (wasmtime is already linked,
/// but we keep this fast and allocation-light).
fn validate_exports(wasm_bytes: &[u8]) -> Result<(), CompileError> {
    // WASM magic + version (8 bytes)
    if wasm_bytes.len() < 8 {
        return Err(CompileError::MissingExport);
    }
    if &wasm_bytes[0..4] != b"\0asm" {
        return Err(CompileError::MissingExport);
    }

    let mut pos = 8;
    while pos < wasm_bytes.len() {
        if pos + 1 >= wasm_bytes.len() {
            break;
        }
        let section_id = wasm_bytes[pos];
        pos += 1;

        // Decode LEB128 section length.
        let (section_len, leb_bytes) = decode_leb128(&wasm_bytes[pos..]);
        pos += leb_bytes;

        if section_id == 7 {
            // Export section
            let end = pos + section_len as usize;
            if end > wasm_bytes.len() {
                return Err(CompileError::MissingExport);
            }
            let export_data = &wasm_bytes[pos..end];
            if find_export_name(export_data, "evaluate") || find_export_name(export_data, "validate") {
                return Ok(());
            }
            return Err(CompileError::MissingExport);
        }

        pos += section_len as usize;
    }

    Err(CompileError::MissingExport)
}

/// Decode an unsigned LEB128 integer. Returns (value, bytes_consumed).
fn decode_leb128(data: &[u8]) -> (u64, usize) {
    let mut result: u64 = 0;
    let mut shift = 0;
    let mut i = 0;
    loop {
        if i >= data.len() {
            break;
        }
        let byte = data[i];
        i += 1;
        result |= ((byte & 0x7F) as u64) << shift;
        shift += 7;
        if byte & 0x80 == 0 {
            break;
        }
    }
    (result, i)
}

/// Scan the raw export section bytes for an export with the given name.
fn find_export_name(data: &[u8], name: &str) -> bool {
    let target = name.as_bytes();
    let (count, mut pos) = decode_leb128(data);
    for _ in 0..count {
        if pos >= data.len() {
            return false;
        }
        let (name_len, leb) = decode_leb128(&data[pos..]);
        pos += leb;
        let end = pos + name_len as usize;
        if end > data.len() {
            return false;
        }
        let entry_name = &data[pos..end];
        if entry_name == target {
            return true;
        }
        pos = end;
        // Skip kind byte + index LEB128
        if pos >= data.len() {
            return false;
        }
        pos += 1; // kind
        let (_, idx_leb) = decode_leb128(&data[pos..]);
        pos += idx_leb;
    }
    false
}

// ─── Main compilation function ────────────────────────────────────────────────

/// Compile Rust source code to a `.wasm` cdylib.
///
/// Requires `rustc` on `$PATH` with the `wasm32-unknown-unknown` target.
///
/// # Steps
///
/// 1. Sanitise source (unsafe check, forbidden imports, size cap).
/// 2. Write source to a temp file.
/// 3. Invoke `rustc --target wasm32-unknown-unknown --crate-type cdylib`.
/// 4. Read the output `.wasm` bytes.
/// 5. Validate exports.
/// 6. Return `CompileResult`.
pub fn compile_policy(source: &str) -> Result<CompileResult, CompileError> {
    // Step 1: sanitise.
    sanitise_source(source)?;

    // Step 2: write to temp file.
    let tmp_dir = std::env::temp_dir().join(format!("qtown_policy_{}", std::process::id()));
    std::fs::create_dir_all(&tmp_dir).map_err(|e| {
        CompileError::CompilationFailed(format!("failed to create temp dir: {e}"))
    })?;

    let src_path: PathBuf = tmp_dir.join("policy.rs");
    let out_path: PathBuf = tmp_dir.join("policy.wasm");

    {
        let mut f = std::fs::File::create(&src_path).map_err(|e| {
            CompileError::CompilationFailed(format!("failed to write source: {e}"))
        })?;
        f.write_all(source.as_bytes()).map_err(|e| {
            CompileError::CompilationFailed(format!("failed to write source bytes: {e}"))
        })?;
    }

    // Step 3: compile.
    let start = std::time::Instant::now();

    let output = Command::new("rustc")
        .args([
            "--target",
            "wasm32-unknown-unknown",
            "--crate-type",
            "cdylib",
            "--edition",
            "2021",
            "-C",
            "opt-level=2",
            "-o",
            out_path.to_str().unwrap_or("policy.wasm"),
            src_path.to_str().unwrap_or("policy.rs"),
        ])
        .output()
        .map_err(|e| CompileError::CompilationFailed(format!("failed to spawn rustc: {e}")))?;

    let compile_duration_ms = start.elapsed().as_millis() as u64;

    // Capture rustc version from a quick version query (best-effort).
    let compiler_version = Command::new("rustc")
        .arg("--version")
        .output()
        .ok()
        .and_then(|o| String::from_utf8(o.stdout).ok())
        .unwrap_or_else(|| "unknown".to_string())
        .trim()
        .to_string();

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).into_owned();
        // Clean up temp files.
        let _ = std::fs::remove_dir_all(&tmp_dir);
        return Err(CompileError::SyntaxError(stderr));
    }

    // Step 4: read .wasm bytes.
    let wasm_bytes = std::fs::read(&out_path).map_err(|e| {
        CompileError::CompilationFailed(format!("failed to read compiled wasm: {e}"))
    })?;

    // Clean up temp files.
    let _ = std::fs::remove_dir_all(&tmp_dir);

    // Step 5: validate exports.
    validate_exports(&wasm_bytes)?;

    Ok(CompileResult {
        wasm_bytes,
        compile_duration_ms,
        compiler_version,
    })
}

// ─── Unit tests ───────────────────────────────────────────────────────────────

#[cfg(test)]
mod unit_tests {
    use super::*;

    #[test]
    fn sanitise_rejects_unsafe_block() {
        let src = r#"pub extern "C" fn f() { unsafe { let _x = 1; } }"#;
        assert!(matches!(sanitise_source(src), Err(CompileError::UnsafeCode)));
    }

    #[test]
    fn sanitise_rejects_unsafe_fn() {
        let src = "unsafe fn dangerous() {}";
        assert!(matches!(sanitise_source(src), Err(CompileError::UnsafeCode)));
    }

    #[test]
    fn sanitise_rejects_fs_import() {
        let src = "use std::fs::File;";
        assert!(matches!(
            sanitise_source(src),
            Err(CompileError::ForbiddenImport(ref s)) if s == "std::fs"
        ));
    }

    #[test]
    fn sanitise_rejects_net_import() {
        let src = "use std::net::TcpStream;";
        assert!(matches!(
            sanitise_source(src),
            Err(CompileError::ForbiddenImport(ref s)) if s == "std::net"
        ));
    }

    #[test]
    fn sanitise_rejects_process_import() {
        let src = "use std::process::exit;";
        assert!(matches!(
            sanitise_source(src),
            Err(CompileError::ForbiddenImport(ref s)) if s == "std::process"
        ));
    }

    #[test]
    fn sanitise_accepts_clean_source() {
        let src = r#"
#[no_mangle]
pub extern "C" fn evaluate(ptr: *const u8, len: usize) -> i32 { 1 }
"#;
        assert!(sanitise_source(src).is_ok());
    }

    #[test]
    fn leb128_decode_single_byte() {
        assert_eq!(decode_leb128(&[0x00]), (0, 1));
        assert_eq!(decode_leb128(&[0x7F]), (127, 1));
    }

    #[test]
    fn leb128_decode_two_bytes() {
        // 128 = 0x80 0x01
        assert_eq!(decode_leb128(&[0x80, 0x01]), (128, 2));
    }

    #[test]
    fn validate_exports_rejects_too_short() {
        assert!(matches!(validate_exports(b""), Err(CompileError::MissingExport)));
        assert!(matches!(validate_exports(b"\0asm"), Err(CompileError::MissingExport)));
    }

    #[test]
    fn validate_exports_rejects_non_wasm() {
        assert!(matches!(
            validate_exports(b"NOTAWASM\x01\x00\x00\x00"),
            Err(CompileError::MissingExport)
        ));
    }
}
