// GET /api/visitor/requests?limit=N
// Returns recent visitor-submitted feature requests with status

interface FeatureRequestRecord {
  id: string
  title: string
  description: string
  category: string
  priority: string
  questId: string | null
  assignedNpc: string | null
  status: 'pending' | 'in_progress' | 'completed'
  progress: number
  createdAt: string
}

interface RequestsResponse {
  requests: FeatureRequestRecord[]
  total: number
  sourceAvailable?: boolean
}

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const townCoreUrl = config.townCoreUrl as string

  const query = getQuery(event)
  const limit = Math.min(Number(query.limit ?? 10), 50)

  try {
    const data = await $fetch<RequestsResponse>(
      `${townCoreUrl}/api/visitor/requests?limit=${limit}`,
      { headers: { 'Content-Type': 'application/json' } }
    )
    return data
  } catch {
    // Upstream unavailable — return an honest empty state, never fabricated requests
    // (docs/plans/03-PROOF-OF-WORK.md §4 rule 1: "No fabricated values, ever").
    // The empty list renders as the page's "No visitor quests yet" dormant state.
    console.warn('[visitor/requests] upstream unavailable, returning empty (source unavailable)')

    return {
      requests: [],
      total: 0,
      sourceAvailable: false,
    } as RequestsResponse
  }
})
