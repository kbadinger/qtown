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
    // Return placeholder data when upstream is unavailable
    console.warn('[visitor/requests] upstream unavailable, returning placeholder data')

    const placeholders: FeatureRequestRecord[] = [
      {
        id: 'vr-m8x2',
        title: 'Add a blacksmith who can forge enchanted weapons',
        description: 'It would be interesting to have an NPC blacksmith who can craft special weapons using rare ores from the mine. NPCs could commission custom gear.',
        category: 'economy',
        priority: 'high',
        questId: 'q-9f3a',
        assignedNpc: 'Gareth the Smith',
        status: 'in_progress',
        progress: 45,
        createdAt: new Date(Date.now() - 3_600_000).toISOString(),
      },
      {
        id: 'vr-k7p1',
        title: 'NPC marriages and family trees',
        description: 'NPCs should be able to form romantic relationships and eventually start families. Children NPCs could inherit traits from parents.',
        category: 'social',
        priority: 'medium',
        questId: 'q-4b2c',
        assignedNpc: 'Elara the Matchmaker',
        status: 'pending',
        progress: 0,
        createdAt: new Date(Date.now() - 7_200_000).toISOString(),
      },
      {
        id: 'vr-j2n9',
        title: 'Build a harbor and add fishing as a profession',
        description: 'Add a waterfront district with a harbor. NPCs could become fishers, trading their catch at the market.',
        category: 'infrastructure',
        priority: 'medium',
        questId: 'q-8d5e',
        assignedNpc: 'Nora the Planner',
        status: 'in_progress',
        progress: 20,
        createdAt: new Date(Date.now() - 86_400_000).toISOString(),
      },
      {
        id: 'vr-h5q4',
        title: 'Seasonal festivals with special events',
        description: 'The town should celebrate seasonal festivals — harvest feast in autumn, ice market in winter — with unique NPC behaviors and market anomalies.',
        category: 'social',
        priority: 'low',
        questId: 'q-1c9f',
        assignedNpc: 'Finn the Bard',
        status: 'completed',
        progress: 100,
        createdAt: new Date(Date.now() - 172_800_000).toISOString(),
      },
    ]

    return {
      requests: placeholders.slice(0, limit),
      total: placeholders.length,
    } as RequestsResponse
  }
})
