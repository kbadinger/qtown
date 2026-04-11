// BFF proxy: GET /api/npcs/:id → Cartographer GraphQL

interface NpcProfileQueryResult {
  npc: {
    id: string
    name: string
    role: string
    gold: number
    happiness: number
    hunger: number
    energy: number
    neighborhood: string
    status: string
    x: number
    y: number
    currentActivity: {
      type: string
      description: string
      startedAt: string
      location: string
    } | null
    recentEvents: Array<{
      id: string
      type: string
      description: string
      tick: number
      timestamp: string
    }>
    orderHistory: Array<{
      id: string
      resourceType: string
      quantity: number
      price: number
      side: string
      status: string
      createdAt: string
      filledAt: string | null
    }>
    dialogueHistory: Array<{
      id: string
      prompt: string
      response: string
      model: string
      tokensUsed: number
      createdAt: string
    }>
    langGraphTraces: Array<{
      runId: string
      tick: number
      totalDurationMs: number
      timestamp: string
      nodes: Array<{
        nodeId: string
        decision: string
        reasoning: string
        durationMs: number
        inputs: Record<string, unknown>
        outputs: Record<string, unknown>
      }>
    }>
  } | null
}

const NPC_PROFILE_QUERY = `
  query GetNpcProfile($id: ID!) {
    npc(id: $id) {
      id name role gold happiness hunger energy
      neighborhood status x y
      currentActivity {
        type description startedAt location
      }
      recentEvents(limit: 10) {
        id type description tick timestamp
      }
      orderHistory(limit: 20) {
        id resourceType quantity price side status createdAt filledAt
      }
      dialogueHistory(limit: 10) {
        id prompt response model tokensUsed createdAt
      }
      langGraphTraces(limit: 5) {
        runId tick totalDurationMs timestamp
        nodes {
          nodeId decision reasoning durationMs
          inputs outputs
        }
      }
    }
  }
`

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const cartographerUrl = config.cartographerUrl as string

  const npcId = getRouterParam(event, 'id')
  if (!npcId) {
    throw createError({
      statusCode: 400,
      statusMessage: 'Bad Request',
      message: 'NPC id is required',
    })
  }

  try {
    const response = await $fetch<{ data: NpcProfileQueryResult; errors?: Array<{ message: string }> }>(
      `${cartographerUrl}/graphql`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: {
          query: NPC_PROFILE_QUERY,
          variables: { id: npcId },
        },
      }
    )

    if (response.errors?.length) {
      const errorMsg = response.errors.map((e) => e.message).join('; ')
      throw createError({
        statusCode: 422,
        statusMessage: 'Upstream GraphQL Error',
        message: errorMsg,
      })
    }

    if (!response.data.npc) {
      throw createError({
        statusCode: 404,
        statusMessage: 'Not Found',
        message: `NPC with id "${npcId}" not found`,
      })
    }

    return response.data.npc
  } catch (err) {
    if ((err as { statusCode?: number }).statusCode) throw err
    const message = err instanceof Error ? err.message : 'Upstream error'
    console.error('[server/api/npcs/[id]] proxy error:', message)
    throw createError({
      statusCode: 502,
      statusMessage: 'Bad Gateway',
      message: `Failed to fetch NPC profile: ${message}`,
    })
  }
})
