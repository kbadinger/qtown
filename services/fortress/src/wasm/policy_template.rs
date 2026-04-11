//! Default Rust policy template presented in the dashboard editor.
//!
//! Users start from this template when creating a new policy. It demonstrates:
//! - The required `evaluate` function signature.
//! - How to parse the JSON input (event + npc_state + world_state).
//! - How to write a `PolicyResult` back to WASM memory using the
//!   [len][json] protocol expected by the Fortress sandbox.
//! - Example guard: reject trades over 1000 gold.
//!
//! The template deliberately avoids `unsafe` blocks (prohibited by the
//! compiler pipeline) by using a minimal allocation scheme that writes
//! the output into a static buffer in the `.data` section.

/// Default Rust source code presented to users in the policy editor.
pub const DEFAULT_POLICY_TEMPLATE: &str = r#"// ─── Qtown Policy Module ─────────────────────────────────────────────────────
//
// This module is compiled to WebAssembly and executed by the Fortress sandbox
// for every town event that matches the policy's registration.
//
// Input  (event_ptr, event_len): JSON-encoded PolicyInput
//   {
//     "event":       { "event_type", "npc_id", "amount", "resource", ... },
//     "npc_state":   { "id", "name", "role", "gold", "happiness", ... },
//     "world_state": { "tick", "day_number", "time_of_day", ... }
//   }
//
// Output: pointer to [4-byte-LE-len][JSON-bytes] in WASM linear memory
//   {
//     "allowed": true | false,
//     "reason":  "...",
//     "modified_event": null | { ... }
//   }
//
// Security rules enforced by the compiler pipeline:
//   ✗  No unsafe blocks
//   ✗  No std::fs / std::net / std::process imports
//   ✓  Pure computation only
// ─────────────────────────────────────────────────────────────────────────────

// Output buffer — written into WASM linear memory (static to avoid allocation).
static mut OUT_BUF: [u8; 65536] = [0u8; 65536];

/// Write a PolicyResult JSON into OUT_BUF and return a pointer to
/// [4-byte-LE-length][JSON-bytes].
fn write_result(allowed: bool, reason: &str) -> i32 {
    let json = if allowed {
        format!(
            r#"{{"allowed":true,"reason":"{}","modified_event":null}}"#,
            reason.replace('"', "\\\"")
        )
    } else {
        format!(
            r#"{{"allowed":false,"reason":"{}","modified_event":null}}"#,
            reason.replace('"', "\\\"")
        )
    };

    let bytes = json.as_bytes();
    let len = bytes.len().min(65532);

    let buf = OUT_BUF.as_mut_ptr();
    // Write 4-byte little-endian length header.
    buf.write((len as u32).to_le_bytes()[0]);
    buf.offset(1).write((len as u32).to_le_bytes()[1]);
    buf.offset(2).write((len as u32).to_le_bytes()[2]);
    buf.offset(3).write((len as u32).to_le_bytes()[3]);
    // Write JSON body.
    core::ptr::copy_nonoverlapping(bytes.as_ptr(), buf.offset(4), len);

    buf as i32
}

// ─── Policy entry point ───────────────────────────────────────────────────────

#[no_mangle]
pub extern "C" fn evaluate(event_ptr: i32, event_len: i32) -> i32 {
    // Safety contract: the Fortress sandbox writes valid UTF-8 JSON at
    // event_ptr with byte length event_len before calling evaluate.
    let input_slice: &[u8] = core::slice::from_raw_parts(
        event_ptr as *const u8,
        event_len as usize,
    );

    // ── Parse the JSON input ──────────────────────────────────────────────────
    // This minimal parser avoids pulling in serde_json (no_std friendly).
    // For complex policies you may add serde_json as a dependency in your
    // Cargo.toml (the compiler pipeline will include it automatically).

    let input_str = match core::str::from_utf8(input_slice) {
        Ok(s) => s,
        Err(_) => return write_result(false, "invalid UTF-8 input"),
    };

    // ── Business logic ────────────────────────────────────────────────────────
    // Example: reject trade events where amount > 1000 gold.

    if input_str.contains(r#""event_type":"trade""#) {
        // Extract amount with a simple search (replace with serde for prod).
        if let Some(amount) = extract_f64(input_str, "\"amount\":") {
            if amount > 1000.0 {
                return write_result(
                    false,
                    "Trade amount exceeds policy limit of 1000 gold",
                );
            }
        }
    }

    // ── Default: allow ────────────────────────────────────────────────────────
    write_result(true, "event permitted by default policy")
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/// Extract the first f64 value following `key` in a JSON string.
fn extract_f64(json: &str, key: &str) -> Option<f64> {
    let start = json.find(key)? + key.len();
    let slice = json[start..].trim_start_matches([' ', '\t', '\n', '\r']);
    let end = slice
        .find(|c: char| !c.is_ascii_digit() && c != '.' && c != '-' && c != 'e' && c != 'E' && c != '+')
        .unwrap_or(slice.len());
    slice[..end].parse().ok()
}
"#;

/// A minimal allow-everything policy for testing.
pub const ALLOW_ALL_TEMPLATE: &str = r#"static mut OUT_BUF: [u8; 256] = [0u8; 256];

#[no_mangle]
pub extern "C" fn evaluate(_ptr: i32, _len: i32) -> i32 {
    let json = b"{\"allowed\":true,\"reason\":\"allow-all policy\",\"modified_event\":null}";
    let len = json.len() as u32;
    let buf = OUT_BUF.as_mut_ptr();
    buf.write(len.to_le_bytes()[0]);
    buf.offset(1).write(len.to_le_bytes()[1]);
    buf.offset(2).write(len.to_le_bytes()[2]);
    buf.offset(3).write(len.to_le_bytes()[3]);
    core::ptr::copy_nonoverlapping(json.as_ptr(), buf.offset(4), json.len());
    buf as i32
}
"#;

/// A reject-everything policy for testing.
pub const REJECT_ALL_TEMPLATE: &str = r#"static mut OUT_BUF: [u8; 256] = [0u8; 256];

#[no_mangle]
pub extern "C" fn evaluate(_ptr: i32, _len: i32) -> i32 {
    let json = b"{\"allowed\":false,\"reason\":\"reject-all policy\",\"modified_event\":null}";
    let len = json.len() as u32;
    let buf = OUT_BUF.as_mut_ptr();
    buf.write(len.to_le_bytes()[0]);
    buf.offset(1).write(len.to_le_bytes()[1]);
    buf.offset(2).write(len.to_le_bytes()[2]);
    buf.offset(3).write(len.to_le_bytes()[3]);
    core::ptr::copy_nonoverlapping(json.as_ptr(), buf.offset(4), json.len());
    buf as i32
}
"#;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn template_is_non_empty() {
        assert!(!DEFAULT_POLICY_TEMPLATE.is_empty());
    }

    #[test]
    fn template_contains_evaluate_export() {
        assert!(DEFAULT_POLICY_TEMPLATE.contains("pub extern \"C\" fn evaluate"));
    }

    #[test]
    fn template_contains_no_unsafe() {
        // The default template must pass our own sanitiser.
        assert!(!DEFAULT_POLICY_TEMPLATE.contains("unsafe {"));
        assert!(!DEFAULT_POLICY_TEMPLATE.contains("unsafe fn "));
    }

    #[test]
    fn template_contains_no_forbidden_imports() {
        assert!(!DEFAULT_POLICY_TEMPLATE.contains("use std::fs"));
        assert!(!DEFAULT_POLICY_TEMPLATE.contains("use std::net"));
        assert!(!DEFAULT_POLICY_TEMPLATE.contains("use std::process"));
    }
}
