<script setup lang="ts">
import { useFortress } from '~/composables/useFortress'
import type { PolicySummary, CompileResult, PolicyResult } from '~/composables/useFortress'

useHead({ title: 'Policy Editor — Qtown' })

// ─── Composable ─────────────────────────────────────────────────────────────

const fortress = useFortress()

// ─── State ──────────────────────────────────────────────────────────────────

// Left panel: policy list
const policies = ref<PolicySummary[]>([])
const selectedPolicyName = ref<string | null>(null)

// Center panel: editor
const DEFAULT_POLICY_TEMPLATE = `// ─── Qtown Policy Module ─────────────────────────────────────────────────────
//
// This module is compiled to WebAssembly and executed by the Fortress sandbox
// for every town event that matches the policy's registration.
//
// Input  (event_ptr, event_len): JSON-encoded PolicyInput
//   { "event": { "event_type", "npc_id", "amount", ... },
//     "npc_state": { ... }, "world_state": { ... } }
//
// Output: pointer to [4-byte-LE-len][JSON-bytes] in WASM linear memory
//   { "allowed": true|false, "reason": "...", "modified_event": null }
//
// Security rules enforced by the compiler:
//   ✗  No unsafe blocks
//   ✗  No std::fs / std::net / std::process imports
//   ✓  Pure computation only
// ─────────────────────────────────────────────────────────────────────────────

static mut OUT_BUF: [u8; 65536] = [0u8; 65536];

fn write_result(allowed: bool, reason: &str) -> i32 {
    let json = if allowed {
        format!(r#"{{"allowed":true,"reason":"{}","modified_event":null}}"#, reason)
    } else {
        format!(r#"{{"allowed":false,"reason":"{}","modified_event":null}}"#, reason)
    };
    let bytes = json.as_bytes();
    let len = bytes.len().min(65532);
    unsafe {
        let buf = OUT_BUF.as_mut_ptr();
        buf.write((len as u32).to_le_bytes()[0]);
        buf.offset(1).write((len as u32).to_le_bytes()[1]);
        buf.offset(2).write((len as u32).to_le_bytes()[2]);
        buf.offset(3).write((len as u32).to_le_bytes()[3]);
        core::ptr::copy_nonoverlapping(bytes.as_ptr(), buf.offset(4), len);
        buf as i32
    }
}

#[no_mangle]
pub extern "C" fn evaluate(event_ptr: i32, event_len: i32) -> i32 {
    let input_slice = unsafe {
        core::slice::from_raw_parts(event_ptr as *const u8, event_len as usize)
    };
    let input_str = match core::str::from_utf8(input_slice) {
        Ok(s) => s,
        Err(_) => return write_result(false, "invalid UTF-8 input"),
    };

    // Example: reject trade events over 1000 gold.
    if input_str.contains(r#""event_type":"trade""#) {
        if let Some(amount) = extract_f64(input_str, "\\"amount\\":") {
            if amount > 1000.0 {
                return write_result(false, "Trade amount exceeds 1000 gold limit");
            }
        }
    }

    write_result(true, "event permitted by policy")
}

fn extract_f64(json: &str, key: &str) -> Option<f64> {
    let start = json.find(key)? + key.len();
    let slice = json[start..].trim_start_matches([' ', '\\t', '\\n', '\\r']);
    let end = slice
        .find(|c: char| !c.is_ascii_digit() && c != '.' && c != '-')
        .unwrap_or(slice.len());
    slice[..end].parse().ok()
}
`

const editorSource = ref<string>(DEFAULT_POLICY_TEMPLATE)
const newPolicyName = ref<string>('my-policy')

// Right panel: compile/deploy state
type CompileStatus = 'idle' | 'compiling' | 'success' | 'error'
const compileStatus = ref<CompileStatus>('idle')
const compileMessage = ref<string>('')
const compiledWasm = ref<Uint8Array | null>(null)
const compileMs = ref<number>(0)

// Test execution
type TestStatus = 'idle' | 'running' | 'done' | 'error'
const testStatus = ref<TestStatus>('idle')
const testResult = ref<PolicyResult | null>(null)
const testEvent = ref<string>(JSON.stringify(fortress.sampleTownEvent(), null, 2))

// Deployment
const isDeploying = ref<boolean>(false)
const deployMessage = ref<string>('')

// Bottom console log
const consoleLogs = ref<Array<{ time: string; level: 'info' | 'success' | 'error' | 'warn'; message: string }>>([])

// ─── Helpers ─────────────────────────────────────────────────────────────────

function log(level: 'info' | 'success' | 'error' | 'warn', message: string) {
  consoleLogs.value.push({
    time: new Date().toLocaleTimeString(),
    level,
    message,
  })
  // Keep last 200 entries
  if (consoleLogs.value.length > 200) {
    consoleLogs.value.splice(0, consoleLogs.value.length - 200)
  }
  nextTick(() => {
    const el = document.getElementById('console-scroll')
    if (el) el.scrollTop = el.scrollHeight
  })
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

function formatTimestamp(unix: number): string {
  return new Date(unix * 1000).toLocaleString()
}

// ─── Policy list actions ──────────────────────────────────────────────────────

async function refreshPolicies() {
  policies.value = await fortress.listPolicies()
  log('info', `Policy list refreshed — ${policies.value.length} registered`)
}

function selectPolicy(name: string) {
  selectedPolicyName.value = name
  log('info', `Selected policy: ${name}`)
}

function newPolicy() {
  selectedPolicyName.value = null
  editorSource.value = DEFAULT_POLICY_TEMPLATE
  newPolicyName.value = 'my-policy'
  compiledWasm.value = null
  compileStatus.value = 'idle'
  testResult.value = null
  log('info', 'Started new policy — loaded default template')
}

async function deletePolicy(name: string) {
  const removed = await fortress.unregisterPolicy(name)
  if (removed) {
    log('success', `Policy "${name}" removed`)
    if (selectedPolicyName.value === name) {
      selectedPolicyName.value = null
    }
    await refreshPolicies()
  } else {
    log('error', `Failed to remove policy "${name}"`)
  }
}

// ─── Compile ─────────────────────────────────────────────────────────────────

async function compileSource() {
  compileStatus.value = 'compiling'
  compileMessage.value = ''
  compiledWasm.value = null
  log('info', 'Compiling Rust source → WASM…')

  const result: CompileResult = await fortress.compilePolicy(editorSource.value)

  if (result.success) {
    compiledWasm.value = result.wasm
    compileMs.value = result.compile_duration_ms
    compileStatus.value = 'success'
    compileMessage.value = `Compiled in ${result.compile_duration_ms}ms — ${formatBytes(result.wasm.length)} (${result.compiler_version})`
    log('success', compileMessage.value)
  } else {
    compileStatus.value = 'error'
    compileMessage.value = `[${result.error_kind}] ${result.error}`
    log('error', compileMessage.value)
  }
}

// ─── Deploy ───────────────────────────────────────────────────────────────────

async function deployPolicy() {
  if (!compiledWasm.value) return
  isDeploying.value = true
  deployMessage.value = ''
  log('info', `Deploying policy "${newPolicyName.value}"…`)

  const result = await fortress.registerPolicy(newPolicyName.value, compiledWasm.value)
  isDeploying.value = false

  if (result) {
    deployMessage.value = `Deployed as "${result.name}" v${result.version}`
    log('success', deployMessage.value)
    selectedPolicyName.value = result.name
    await refreshPolicies()
  } else {
    deployMessage.value = fortress.lastError.value ?? 'Deploy failed'
    log('error', deployMessage.value)
  }
}

// ─── Test ─────────────────────────────────────────────────────────────────────

async function runTest() {
  const name = selectedPolicyName.value
  if (!name) {
    log('warn', 'No policy selected — deploy first, then test')
    return
  }

  testStatus.value = 'running'
  testResult.value = null
  log('info', `Testing policy "${name}" with sample event…`)

  let parsedEvent = fortress.sampleTownEvent()
  try {
    parsedEvent = JSON.parse(testEvent.value)
  } catch {
    log('warn', 'Could not parse test event JSON — using default trade event')
  }

  const result = await fortress.executeTest(name, parsedEvent)
  if (result) {
    testResult.value = result
    testStatus.value = 'done'
    log(
      result.allowed ? 'success' : 'warn',
      `Policy result: ${result.allowed ? 'ALLOW' : 'REJECT'} — ${result.reason}`,
    )
    if (result.modified_event) {
      log('info', `Modified event: ${JSON.stringify(result.modified_event)}`)
    }
  } else {
    testStatus.value = 'error'
    log('error', `Test failed: ${fortress.lastError.value ?? 'unknown error'}`)
  }
}

// ─── Computed ─────────────────────────────────────────────────────────────────

const selectedPolicySummary = computed<PolicySummary | null>(() => {
  if (!selectedPolicyName.value) return null
  return policies.value.find((p) => p.name === selectedPolicyName.value) ?? null
})

const canDeploy = computed(() => compileStatus.value === 'success' && compiledWasm.value !== null)
const canTest = computed(() => selectedPolicyName.value !== null)

// ─── Lifecycle ────────────────────────────────────────────────────────────────

onMounted(() => {
  log('info', 'Policy editor loaded — connect to Fortress to manage WASM policies')
  refreshPolicies()
})
</script>

<template>
  <div class="policies-page">
    <!-- Page header -->
    <div class="policies-header">
      <div>
        <h1 class="text-2xl font-bold text-qtown-text-primary">Policy Editor</h1>
        <p class="text-qtown-text-secondary text-sm mt-0.5">
          Compile, deploy and test Rust → WASM governance policies
        </p>
      </div>
      <div class="flex gap-2">
        <button class="qtown-btn-ghost text-sm flex items-center gap-1.5" @click="newPolicy">
          <svg viewBox="0 0 16 16" class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M8 3v10M3 8h10" stroke-linecap="round" />
          </svg>
          New Policy
        </button>
        <button class="qtown-btn-ghost text-sm flex items-center gap-1.5" @click="refreshPolicies">
          <svg viewBox="0 0 16 16" class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M14 8A6 6 0 102 8" stroke-linecap="round" />
            <path d="M14 5v3h-3" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          Refresh
        </button>
      </div>
    </div>

    <!-- Main 3-column layout -->
    <div class="policies-body">

      <!-- Left panel: policy list -->
      <aside class="policies-left">
        <div class="panel-title">Registered Policies</div>

        <div v-if="policies.length === 0" class="panel-empty">
          <div class="text-2xl mb-2 opacity-40">📜</div>
          <p class="text-xs text-qtown-text-dim">No policies registered.</p>
          <p class="text-xs text-qtown-text-dim mt-0.5">Write and deploy one to begin.</p>
        </div>

        <div
          v-for="p in policies"
          :key="p.id"
          class="policy-item"
          :class="{ 'policy-item--active': selectedPolicyName === p.name }"
          @click="selectPolicy(p.name)"
        >
          <div class="policy-item__top">
            <!-- Status dot: green = ok, red = has last_error -->
            <span
              class="policy-item__dot"
              :class="p.last_error ? 'bg-red-400' : 'bg-green-400'"
              :title="p.last_error ?? 'OK'"
            />
            <span class="policy-item__name" :title="p.name">{{ p.name }}</span>
            <span class="policy-item__version">v{{ p.version }}</span>
          </div>
          <div class="policy-item__meta">
            {{ p.stats.invocation_count.toLocaleString() }} calls ·
            {{ p.stats.avg_duration_ms.toFixed(1) }}ms avg ·
            {{ formatBytes(p.wasm_size_bytes) }}
          </div>
          <div class="policy-item__actions">
            <button
              class="policy-action-btn text-red-400 hover:text-red-300"
              title="Remove policy"
              @click.stop="deletePolicy(p.name)"
            >
              <svg viewBox="0 0 16 16" class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M2 4h12M5 4V3a1 1 0 011-1h4a1 1 0 011 1v1m2 0l-.5 9a1 1 0 01-1 1h-7a1 1 0 01-1-1L3 4" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
          </div>
        </div>
      </aside>

      <!-- Center panel: code editor -->
      <main class="policies-center">
        <div class="panel-title flex items-center justify-between">
          <span>Source Editor</span>
          <div class="flex items-center gap-2">
            <input
              v-model="newPolicyName"
              class="qtown-input text-xs py-1 px-2 w-36"
              placeholder="policy-name"
              title="Policy name for deployment"
            />
            <span class="text-qtown-text-dim text-xs">{{ editorSource.split('\n').length }} lines</span>
          </div>
        </div>
        <div class="editor-wrapper">
          <PolicyEditor
            v-model="editorSource"
            language="rust"
            :read-only="false"
          />
        </div>
      </main>

      <!-- Right panel: actions + stats -->
      <aside class="policies-right">

        <!-- Compile section -->
        <div class="action-section">
          <div class="panel-title">Compile</div>
          <button
            class="w-full qtown-btn text-sm py-2 flex items-center justify-center gap-2"
            :disabled="fortress.isLoading.value"
            @click="compileSource"
          >
            <svg
              v-if="compileStatus === 'compiling'"
              class="w-3.5 h-3.5 animate-spin"
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
            >
              <path d="M14 8A6 6 0 102 8" stroke-linecap="round" />
            </svg>
            <svg v-else viewBox="0 0 16 16" class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M4 3l8 5-8 5V3z" stroke-linejoin="round"/>
            </svg>
            {{ compileStatus === 'compiling' ? 'Compiling…' : 'Compile' }}
          </button>

          <div
            v-if="compileStatus !== 'idle'"
            class="compile-status"
            :class="{
              'compile-status--success': compileStatus === 'success',
              'compile-status--error': compileStatus === 'error',
              'compile-status--pending': compileStatus === 'compiling',
            }"
          >
            <div class="compile-status__icon">
              <span v-if="compileStatus === 'success'">✓</span>
              <span v-else-if="compileStatus === 'error'">✗</span>
              <span v-else>…</span>
            </div>
            <div class="compile-status__msg">{{ compileMessage }}</div>
          </div>
        </div>

        <!-- Deploy section -->
        <div class="action-section">
          <div class="panel-title">Deploy</div>
          <button
            class="w-full text-sm py-2 flex items-center justify-center gap-2 rounded"
            :class="canDeploy
              ? 'bg-qtown-accent/20 border border-qtown-accent/40 text-qtown-accent hover:bg-qtown-accent/30 cursor-pointer'
              : 'bg-qtown-border/30 border border-qtown-border text-qtown-text-dim cursor-not-allowed opacity-50'"
            :disabled="!canDeploy || isDeploying"
            @click="deployPolicy"
          >
            <svg v-if="isDeploying" class="w-3.5 h-3.5 animate-spin" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M14 8A6 6 0 102 8" stroke-linecap="round" />
            </svg>
            <svg v-else viewBox="0 0 16 16" class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M8 2v8M4 7l4 4 4-4M3 13h10" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            {{ isDeploying ? 'Deploying…' : 'Deploy' }}
          </button>
          <p v-if="deployMessage" class="text-xs mt-2" :class="deployMessage.includes('fail') || deployMessage.includes('Failed') ? 'text-red-400' : 'text-green-400'">
            {{ deployMessage }}
          </p>
          <p v-if="!canDeploy" class="text-xs text-qtown-text-dim mt-1">
            Compile successfully first.
          </p>
        </div>

        <!-- Test section -->
        <div class="action-section">
          <div class="panel-title flex items-center justify-between">
            <span>Test Execution</span>
            <span v-if="!canTest" class="text-qtown-text-dim text-xs">deploy first</span>
          </div>

          <div class="mb-2">
            <label class="text-xs text-qtown-text-dim block mb-1">Test event (JSON)</label>
            <textarea
              v-model="testEvent"
              class="w-full qtown-input text-xs font-mono resize-none"
              rows="6"
              spellcheck="false"
            />
          </div>

          <button
            class="w-full text-sm py-2 flex items-center justify-center gap-2 rounded"
            :class="canTest
              ? 'bg-purple-500/20 border border-purple-500/40 text-purple-300 hover:bg-purple-500/30 cursor-pointer'
              : 'bg-qtown-border/30 border border-qtown-border text-qtown-text-dim cursor-not-allowed opacity-50'"
            :disabled="!canTest || testStatus === 'running'"
            @click="runTest"
          >
            <svg v-if="testStatus === 'running'" class="w-3.5 h-3.5 animate-spin" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M14 8A6 6 0 102 8" stroke-linecap="round" />
            </svg>
            <svg v-else viewBox="0 0 16 16" class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M3 8h10M8 3l5 5-5 5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            {{ testStatus === 'running' ? 'Testing…' : 'Run Test' }}
          </button>

          <!-- Test result -->
          <div
            v-if="testResult"
            class="test-result mt-3"
            :class="testResult.allowed ? 'test-result--allow' : 'test-result--reject'"
          >
            <div class="test-result__verdict">
              {{ testResult.allowed ? '✓ ALLOW' : '✗ REJECT' }}
            </div>
            <div class="test-result__reason">{{ testResult.reason }}</div>
            <div v-if="testResult.modified_event" class="test-result__modified">
              <div class="text-xs text-yellow-400 mb-0.5">Modified event:</div>
              <pre class="text-xs font-mono overflow-x-auto">{{ JSON.stringify(testResult.modified_event, null, 2) }}</pre>
            </div>
          </div>
        </div>

        <!-- Execution stats for selected policy -->
        <div v-if="selectedPolicySummary" class="action-section">
          <div class="panel-title">Policy Stats — {{ selectedPolicySummary.name }}</div>
          <div class="stats-grid">
            <div class="stat-cell">
              <div class="stat-cell__label">Invocations</div>
              <div class="stat-cell__value">
                {{ selectedPolicySummary.stats.invocation_count.toLocaleString() }}
              </div>
            </div>
            <div class="stat-cell">
              <div class="stat-cell__label">Avg Duration</div>
              <div class="stat-cell__value">
                {{ selectedPolicySummary.stats.avg_duration_ms.toFixed(2) }}ms
              </div>
            </div>
            <div class="stat-cell">
              <div class="stat-cell__label">Fuel Used</div>
              <div class="stat-cell__value">
                {{ selectedPolicySummary.stats.total_fuel_consumed.toLocaleString() }}
              </div>
            </div>
            <div class="stat-cell">
              <div class="stat-cell__label">Errors</div>
              <div class="stat-cell__value" :class="selectedPolicySummary.stats.error_count > 0 ? 'text-red-400' : ''">
                {{ selectedPolicySummary.stats.error_count }}
              </div>
            </div>
          </div>
          <div class="text-xs text-qtown-text-dim mt-2">
            v{{ selectedPolicySummary.version }} by {{ selectedPolicySummary.author }} ·
            {{ formatBytes(selectedPolicySummary.wasm_size_bytes) }} ·
            Updated {{ formatTimestamp(selectedPolicySummary.updated_at) }}
          </div>
          <div v-if="selectedPolicySummary.last_error" class="mt-2 text-xs text-red-400 bg-red-400/5 border border-red-400/20 rounded p-2">
            <div class="font-semibold mb-0.5">Last error:</div>
            {{ selectedPolicySummary.last_error }}
          </div>
        </div>

      </aside>
    </div>

    <!-- Bottom console panel -->
    <div class="policies-console">
      <div class="console-header">
        <span class="panel-title">Console</span>
        <button
          class="text-xs text-qtown-text-dim hover:text-qtown-text-secondary"
          @click="consoleLogs = []"
        >
          Clear
        </button>
      </div>
      <div id="console-scroll" class="console-body">
        <div
          v-for="(entry, idx) in consoleLogs"
          :key="idx"
          class="console-line"
          :class="`console-line--${entry.level}`"
        >
          <span class="console-time">{{ entry.time }}</span>
          <span class="console-level">{{ entry.level.toUpperCase().padEnd(7) }}</span>
          <span class="console-msg">{{ entry.message }}</span>
        </div>
        <div v-if="consoleLogs.length === 0" class="console-empty">
          Console output will appear here after actions.
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ─── Layout ──────────────────────────────────────────────────────────────── */

.policies-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  min-height: 0;
}

.policies-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-shrink: 0;
}

.policies-body {
  display: grid;
  grid-template-columns: 220px 1fr 280px;
  gap: 12px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.policies-console {
  flex-shrink: 0;
  height: 180px;
  display: flex;
  flex-direction: column;
  background: #0a0a15;
  border: 1px solid #2a2a4a;
  border-radius: 6px;
  overflow: hidden;
}

/* ─── Panels ──────────────────────────────────────────────────────────────── */

.policies-left,
.policies-right {
  display: flex;
  flex-direction: column;
  gap: 0;
  background: var(--qtown-card, #12122a);
  border: 1px solid #2a2a4a;
  border-radius: 6px;
  overflow-y: auto;
  padding: 12px;
}

.policies-center {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  overflow: hidden;
}

.editor-wrapper {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.editor-wrapper > :deep(.policy-editor) {
  height: 100%;
  min-height: 400px;
}

.panel-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #475569;
  margin-bottom: 10px;
}

/* ─── Policy list ─────────────────────────────────────────────────────────── */

.panel-empty {
  text-align: center;
  padding: 24px 8px;
  color: #475569;
}

.policy-item {
  padding: 8px 6px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s;
  border: 1px solid transparent;
  margin-bottom: 2px;
  position: relative;
}

.policy-item:hover {
  background: rgba(255,255,255,0.04);
}

.policy-item--active {
  background: rgba(233, 69, 96, 0.1);
  border-color: rgba(233, 69, 96, 0.3);
}

.policy-item__top {
  display: flex;
  align-items: center;
  gap: 6px;
}

.policy-item__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.policy-item__name {
  font-size: 13px;
  font-weight: 500;
  color: #c8d3f5;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.policy-item__version {
  font-size: 10px;
  font-family: ui-monospace, monospace;
  color: #475569;
  flex-shrink: 0;
}

.policy-item__meta {
  font-size: 10px;
  color: #475569;
  margin-top: 3px;
  padding-left: 12px;
}

.policy-item__actions {
  position: absolute;
  right: 6px;
  top: 8px;
  display: none;
}

.policy-item:hover .policy-item__actions {
  display: flex;
}

.policy-action-btn {
  padding: 2px;
  border-radius: 3px;
  transition: color 0.15s;
}

/* ─── Action sections (right panel) ────────────────────────────────────────── */

.action-section {
  border-bottom: 1px solid #2a2a4a;
  padding-bottom: 16px;
  margin-bottom: 16px;
}

.action-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

/* Compile button (inherits qtown-btn if defined in global CSS) */
.qtown-btn {
  background: rgba(233, 69, 96, 0.2);
  border: 1px solid rgba(233, 69, 96, 0.4);
  color: #e94560;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s;
}

.qtown-btn:hover:not(:disabled) {
  background: rgba(233, 69, 96, 0.3);
}

.qtown-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ─── Compile status ──────────────────────────────────────────────────────── */

.compile-status {
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: 4px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 11px;
}

.compile-status--success {
  background: rgba(64, 145, 108, 0.1);
  border: 1px solid rgba(64, 145, 108, 0.3);
  color: #4ade80;
}

.compile-status--error {
  background: rgba(233, 69, 96, 0.1);
  border: 1px solid rgba(233, 69, 96, 0.3);
  color: #e94560;
}

.compile-status--pending {
  background: rgba(250, 204, 21, 0.08);
  border: 1px solid rgba(250, 204, 21, 0.2);
  color: #fbbf24;
}

.compile-status__icon {
  font-weight: 700;
  flex-shrink: 0;
  width: 14px;
  text-align: center;
}

.compile-status__msg {
  flex: 1;
  font-family: ui-monospace, monospace;
  word-break: break-word;
  line-height: 1.4;
}

/* ─── Test result ─────────────────────────────────────────────────────────── */

.test-result {
  padding: 10px;
  border-radius: 4px;
  font-size: 12px;
}

.test-result--allow {
  background: rgba(64, 145, 108, 0.1);
  border: 1px solid rgba(64, 145, 108, 0.3);
}

.test-result--reject {
  background: rgba(233, 69, 96, 0.1);
  border: 1px solid rgba(233, 69, 96, 0.3);
}

.test-result__verdict {
  font-weight: 700;
  font-size: 13px;
  margin-bottom: 4px;
}

.test-result--allow .test-result__verdict { color: #4ade80; }
.test-result--reject .test-result__verdict { color: #e94560; }

.test-result__reason {
  color: #94a3b8;
  line-height: 1.4;
}

.test-result__modified {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(255,255,255,0.06);
}

/* ─── Stats grid ──────────────────────────────────────────────────────────── */

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.stat-cell {
  background: rgba(255,255,255,0.03);
  border: 1px solid #2a2a4a;
  border-radius: 4px;
  padding: 8px;
}

.stat-cell__label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #475569;
  margin-bottom: 2px;
}

.stat-cell__value {
  font-size: 16px;
  font-weight: 700;
  font-family: ui-monospace, monospace;
  color: #c8d3f5;
}

/* ─── Console ─────────────────────────────────────────────────────────────── */

.console-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  border-bottom: 1px solid #2a2a4a;
  flex-shrink: 0;
}

.console-body {
  flex: 1;
  overflow-y: auto;
  padding: 6px 0;
  font-family: ui-monospace, 'JetBrains Mono', monospace;
  font-size: 11px;
}

.console-line {
  display: flex;
  gap: 8px;
  padding: 1px 12px;
  line-height: 1.5;
}

.console-line:hover {
  background: rgba(255,255,255,0.02);
}

.console-time {
  color: #3d3d6b;
  flex-shrink: 0;
}

.console-level {
  flex-shrink: 0;
  width: 52px;
}

.console-line--info .console-level   { color: #475569; }
.console-line--success .console-level { color: #4ade80; }
.console-line--error .console-level  { color: #e94560; }
.console-line--warn .console-level   { color: #fbbf24; }

.console-msg {
  color: #94a3b8;
  word-break: break-word;
}

.console-line--success .console-msg { color: #86efac; }
.console-line--error .console-msg   { color: #fca5a5; }
.console-line--warn .console-msg    { color: #fde68a; }

.console-empty {
  color: #3d3d6b;
  font-style: italic;
  padding: 8px 12px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.animate-spin {
  animation: spin 1s linear infinite;
}
</style>
