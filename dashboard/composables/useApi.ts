// REST API client composable
// Queries town-core (port 8000) and academy (port 8001)

// ─── Town Core Types ──────────────────────────────────────────────────────────

export interface NpcListItem {
  id: string
  name: string
  role: string
  gold: number
  happiness: number
  hunger: number
  energy: number
  neighborhood: string
  status: 'active' | 'traveling' | 'sleeping' | 'idle'
  x: number
  y: number
}

export interface NpcListResponse {
  npcs: NpcListItem[]
  total: number
  page: number
  pageSize: number
}

export interface WorldStateResponse {
  tick: number
  dayNumber: number
  timeOfDay: number
  isNight: boolean
  population: number
  totalGold: number
  averageHappiness: number
  activeNpcs: number
  weather: {
    condition: string
    temperature: number
    windSpeed: number
  }
}

// ─── Academy Types ────────────────────────────────────────────────────────────

export interface ModelRoutingEntry {
  model: string
  count: number
  totalTokens: number
  totalCostUsd: number
  avgLatencyMs: number
}

export interface GenerationRecord {
  id: string
  model: string
  purpose: string
  promptTokens: number
  completionTokens: number
  totalTokens: number
  costUsd: number
  latencyMs: number
  qualityScore: number | null
  createdAt: string
}

export interface AcademyStats {
  totalGenerations: number
  totalCostUsd: number
  avgLatencyMs: number
  modelBreakdown: ModelRoutingEntry[]
  generationsOverTime: Array<{
    hour: string
    count: number
    costUsd: number
    avgLatencyMs: number
  }>
  recentGenerations: GenerationRecord[]
}

// ─── Fortress / Validation Types ──────────────────────────────────────────────

export interface ValidationEntry {
  id: string
  tick: number
  eventType: string
  entityId: string
  entityType: string
  passed: boolean
  rejectionReason: string | null
  validationMs: number
  timestamp: string
}

export interface FortressStats {
  totalValidated: number
  totalRejected: number
  rejectionRate: number
  topRejectionReasons: Array<{
    reason: string
    count: number
    percentage: number
  }>
  recentAuditLog: ValidationEntry[]
}

// ─── Newspaper Types ──────────────────────────────────────────────────────────

export interface NewspaperEdition {
  id: string
  dayNumber: number
  headline: string
  lead: string
  body: string
  editorial: string
  generatedAt: string
  model: string
}

// ─── Composable ───────────────────────────────────────────────────────────────

export function useApi() {
  const config = useRuntimeConfig()

  const townCoreUrl = config.public.townCoreUrl as string
  const academyUrl = config.public.academyUrl as string

  const isLoading = ref(false)
  const lastError = ref<string | null>(null)

  // Generic typed fetch helper
  async function apiFetch<T>(url: string, opts?: RequestInit): Promise<T | null> {
    isLoading.value = true
    lastError.value = null

    try {
      const response = await $fetch<T>(url, {
        ...opts,
        headers: {
          'Content-Type': 'application/json',
          ...(opts?.headers as Record<string, string> | undefined),
        },
      })
      return response
    } catch (err) {
      const message = err instanceof Error ? err.message : `Request to ${url} failed`
      lastError.value = message
      console.error('[useApi] error:', message)
      return null
    } finally {
      isLoading.value = false
    }
  }

  // ─── Town Core ─────────────────────────────────────────────────────────────

  async function fetchWorldState(): Promise<WorldStateResponse | null> {
    return apiFetch<WorldStateResponse>(`${townCoreUrl}/api/world`)
  }

  async function fetchNpcs(params?: {
    page?: number
    pageSize?: number
    search?: string
    role?: string
    status?: string
    neighborhood?: string
  }): Promise<NpcListResponse | null> {
    const queryParams = new URLSearchParams()
    if (params?.page !== undefined) queryParams.set('page', String(params.page))
    if (params?.pageSize !== undefined) queryParams.set('pageSize', String(params.pageSize))
    if (params?.search) queryParams.set('search', params.search)
    if (params?.role) queryParams.set('role', params.role)
    if (params?.status) queryParams.set('status', params.status)
    if (params?.neighborhood) queryParams.set('neighborhood', params.neighborhood)

    const qs = queryParams.toString()
    return apiFetch<NpcListResponse>(`${townCoreUrl}/api/npcs${qs ? `?${qs}` : ''}`)
  }

  async function fetchNpcById(id: string): Promise<NpcListItem | null> {
    return apiFetch<NpcListItem>(`${townCoreUrl}/api/npcs/${id}`)
  }

  async function fetchNewspaper(dayNumber?: number): Promise<NewspaperEdition | null> {
    const url = dayNumber !== undefined
      ? `${townCoreUrl}/api/newspaper/${dayNumber}`
      : `${townCoreUrl}/api/newspaper/latest`
    return apiFetch<NewspaperEdition>(url)
  }

  async function fetchNewspaperArchive(limit = 30): Promise<NewspaperEdition[]> {
    const result = await apiFetch<{ editions: NewspaperEdition[] }>(
      `${townCoreUrl}/api/newspaper/archive?limit=${limit}`
    )
    return result?.editions ?? []
  }

  async function fetchFortressStats(): Promise<FortressStats | null> {
    return apiFetch<FortressStats>(`${townCoreUrl}/api/fortress/stats`)
  }

  // ─── Academy ───────────────────────────────────────────────────────────────

  async function fetchAcademyStats(): Promise<AcademyStats | null> {
    return apiFetch<AcademyStats>(`${academyUrl}/api/stats`)
  }

  async function fetchRecentGenerations(limit = 50): Promise<GenerationRecord[]> {
    const result = await apiFetch<{ generations: GenerationRecord[] }>(
      `${academyUrl}/api/generations?limit=${limit}`
    )
    return result?.generations ?? []
  }

  return {
    isLoading: readonly(isLoading),
    lastError: readonly(lastError),

    // Town Core
    fetchWorldState,
    fetchNpcs,
    fetchNpcById,
    fetchNewspaper,
    fetchNewspaperArchive,
    fetchFortressStats,

    // Academy
    fetchAcademyStats,
    fetchRecentGenerations,
  }
}
