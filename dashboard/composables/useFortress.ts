// Fortress API composable — wraps Fortress gRPC-web / REST endpoints.
//
// All methods are typed strictly; no `any` is used. The Fortress service
// is expected to expose a JSON-over-HTTP gateway at the `fortressUrl`
// runtime config key (e.g. http://localhost:8080). In development the
// Nuxt server proxy routes /api/fortress/* to that address.

// ─── Domain types ─────────────────────────────────────────────────────────────

export interface TownEvent {
  event_type: string
  npc_id: number
  amount: number
  resource: string | null
  metadata: Record<string, unknown> | null
}

export interface NpcState {
  id: number
  name: string
  role: string
  gold: number
  happiness: number
  hunger: number
  energy: number
  neighborhood: string
}

export interface WorldState {
  tick: number
  day_number: number
  time_of_day: number
  is_night: boolean
  population: number
  total_gold: number
  average_happiness: number
}

export interface PolicyResult {
  allowed: boolean
  reason: string
  modified_event: TownEvent | null
}

export interface PolicyStatsSnapshot {
  invocation_count: number
  total_fuel_consumed: number
  avg_duration_ms: number
  error_count: number
}

export interface PolicySummary {
  id: string
  name: string
  version: number
  author: string
  created_at: number
  updated_at: number
  wasm_size_bytes: number
  stats: PolicyStatsSnapshot
  last_error: string | null
}

export interface CompileSuccess {
  success: true
  wasm: Uint8Array
  compile_duration_ms: number
  compiler_version: string
}

export interface CompileFailure {
  success: false
  error: string
  error_kind: 'SyntaxError' | 'UnsafeCode' | 'ForbiddenImport' | 'MissingExport' | 'CompilationFailed'
}

export type CompileResult = CompileSuccess | CompileFailure

export interface RegisterResult {
  id: string
  name: string
  version: number
  author: string
}

export interface ChainPolicyResult {
  policy_name: string
  result: PolicyResult
}

export interface ChainResult {
  allowed: boolean
  reason: string
  final_event: TownEvent
  policy_results: ChainPolicyResult[]
}

// ─── Mock data helpers ────────────────────────────────────────────────────────

/** Produces a sample TownEvent for test executions. */
export function sampleTownEvent(overrides: Partial<TownEvent> = {}): TownEvent {
  return {
    event_type: 'trade',
    npc_id: 1,
    amount: 500.0,
    resource: 'gold',
    metadata: null,
    ...overrides,
  }
}

// ─── Composable ───────────────────────────────────────────────────────────────

export function useFortress() {
  const config = useRuntimeConfig()
  // Fortress URL — falls back to /api/fortress proxy when not configured.
  const fortressBase = (config.public.fortressUrl as string | undefined) ?? '/api/fortress'

  const isLoading = ref(false)
  const lastError = ref<string | null>(null)

  // ── Internal fetch helper ─────────────────────────────────────────────────

  async function apiFetch<T>(
    path: string,
    opts: RequestInit = {},
  ): Promise<T | null> {
    isLoading.value = true
    lastError.value = null

    try {
      const url = `${fortressBase}${path}`
      const res = await $fetch<T>(url, {
        ...opts,
        headers: {
          'Content-Type': 'application/json',
          ...(opts.headers as Record<string, string> | undefined),
        },
      })
      return res
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : `Fortress request to ${path} failed`
      lastError.value = msg
      console.error('[useFortress]', path, msg)
      return null
    } finally {
      isLoading.value = false
    }
  }

  // ── CompilePolicy ─────────────────────────────────────────────────────────

  /**
   * Submit Rust source code for compilation to WASM.
   *
   * The server runs `rustc --target wasm32-unknown-unknown` with security
   * checks (no unsafe, no std::fs/net/process). Returns compiled WASM bytes
   * on success or a structured error on failure.
   */
  async function compilePolicy(source: string): Promise<CompileResult> {
    interface ApiResponse {
      success: boolean
      wasm_base64?: string
      compile_duration_ms?: number
      compiler_version?: string
      error?: string
      error_kind?: CompileFailure['error_kind']
    }

    const result = await apiFetch<ApiResponse>('/compile', {
      method: 'POST',
      body: JSON.stringify({ source }),
    })

    if (!result) {
      return {
        success: false,
        error: lastError.value ?? 'Network error',
        error_kind: 'CompilationFailed',
      }
    }

    if (!result.success || !result.wasm_base64) {
      return {
        success: false,
        error: result.error ?? 'Unknown compilation error',
        error_kind: result.error_kind ?? 'CompilationFailed',
      }
    }

    // Decode base64 → Uint8Array
    const binaryStr = atob(result.wasm_base64)
    const bytes = new Uint8Array(binaryStr.length)
    for (let i = 0; i < binaryStr.length; i++) {
      bytes[i] = binaryStr.charCodeAt(i)
    }

    return {
      success: true,
      wasm: bytes,
      compile_duration_ms: result.compile_duration_ms ?? 0,
      compiler_version: result.compiler_version ?? 'unknown',
    }
  }

  // ── RegisterPolicy ────────────────────────────────────────────────────────

  /**
   * Register a compiled WASM policy with a name and author.
   *
   * If a policy with the same name already exists, it is hot-reloaded.
   * The version counter is incremented on each reload.
   */
  async function registerPolicy(
    name: string,
    wasm: Uint8Array,
    author: string = 'dashboard',
  ): Promise<RegisterResult | null> {
    // Encode WASM bytes as base64 for JSON transport.
    let binary = ''
    for (let i = 0; i < wasm.length; i++) {
      binary += String.fromCharCode(wasm[i])
    }
    const wasm_base64 = btoa(binary)

    return apiFetch<RegisterResult>('/policies/register', {
      method: 'POST',
      body: JSON.stringify({ name, wasm_base64, author }),
    })
  }

  // ── ListPolicies ──────────────────────────────────────────────────────────

  /** Fetch the list of all registered policies with their execution stats. */
  async function listPolicies(): Promise<PolicySummary[]> {
    const result = await apiFetch<{ policies: PolicySummary[] }>('/policies')
    return result?.policies ?? []
  }

  // ── UnregisterPolicy ──────────────────────────────────────────────────────

  /** Remove a registered policy by name. Returns true if it existed. */
  async function unregisterPolicy(name: string): Promise<boolean> {
    const result = await apiFetch<{ removed: boolean }>(`/policies/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    })
    return result?.removed ?? false
  }

  // ── ExecuteTest ───────────────────────────────────────────────────────────

  /**
   * Run a registered policy against a sample event and return the result.
   *
   * Use this for the "Test" button in the policy editor. The event defaults
   * to a 500-gold trade if not supplied.
   */
  async function executeTest(
    policyName: string,
    event: TownEvent = sampleTownEvent(),
    npcState: NpcState | null = null,
    worldState: WorldState | null = null,
  ): Promise<PolicyResult | null> {
    return apiFetch<PolicyResult>(`/policies/${encodeURIComponent(policyName)}/execute`, {
      method: 'POST',
      body: JSON.stringify({ event, npc_state: npcState, world_state: worldState }),
    })
  }

  // ── ExecuteWASM ───────────────────────────────────────────────────────────

  /**
   * Execute raw WASM bytes against an event without registering the policy.
   *
   * Useful for quick ad-hoc testing before registration.
   */
  async function executeWasm(
    wasm: Uint8Array,
    event: TownEvent = sampleTownEvent(),
    npcState: NpcState | null = null,
    worldState: WorldState | null = null,
  ): Promise<PolicyResult | null> {
    let binary = ''
    for (let i = 0; i < wasm.length; i++) {
      binary += String.fromCharCode(wasm[i])
    }
    const wasm_base64 = btoa(binary)

    return apiFetch<PolicyResult>('/execute', {
      method: 'POST',
      body: JSON.stringify({ wasm_base64, event, npc_state: npcState, world_state: worldState }),
    })
  }

  // ── ExecuteChain ──────────────────────────────────────────────────────────

  /**
   * Execute a chain of named policies against one event.
   *
   * The first rejection short-circuits the chain.
   */
  async function executeChain(
    policyNames: string[],
    event: TownEvent = sampleTownEvent(),
    npcState: NpcState | null = null,
    worldState: WorldState | null = null,
  ): Promise<ChainResult | null> {
    return apiFetch<ChainResult>('/policies/chain', {
      method: 'POST',
      body: JSON.stringify({
        policy_names: policyNames,
        event,
        npc_state: npcState,
        world_state: worldState,
      }),
    })
  }

  // ── Return ────────────────────────────────────────────────────────────────

  return {
    isLoading: readonly(isLoading),
    lastError: readonly(lastError),

    compilePolicy,
    registerPolicy,
    listPolicies,
    unregisterPolicy,
    executeTest,
    executeWasm,
    executeChain,

    // Helper
    sampleTownEvent,
  }
}
