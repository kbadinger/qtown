// GraphQL client composable — queries the Cartographer service

export interface GraphQLError {
  message: string
  locations?: Array<{ line: number; column: number }>
  path?: string[]
  extensions?: Record<string, unknown>
}

export interface GraphQLResponse<T> {
  data: T | null
  errors?: GraphQLError[]
}

export interface GraphQLRequestOptions {
  headers?: Record<string, string>
}

// ─── NPC Types ────────────────────────────────────────────────────────────────

export interface NpcActivity {
  type: string
  description: string
  startedAt: string
  location: string
}

export interface NpcEvent {
  id: string
  type: string
  description: string
  tick: number
  timestamp: string
}

export interface OrderRecord {
  id: string
  resourceType: string
  quantity: number
  price: number
  side: 'buy' | 'sell'
  status: 'open' | 'filled' | 'cancelled' | 'partial'
  createdAt: string
  filledAt: string | null
}

export interface DialogueRecord {
  id: string
  prompt: string
  response: string
  model: string
  tokensUsed: number
  createdAt: string
}

export interface LangGraphNode {
  nodeId: string
  decision: string
  reasoning: string
  inputs: Record<string, unknown>
  outputs: Record<string, unknown>
  durationMs: number
}

export interface LangGraphTrace {
  runId: string
  tick: number
  nodes: LangGraphNode[]
  totalDurationMs: number
  timestamp: string
}

export interface NpcFullProfile {
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
  currentActivity: NpcActivity | null
  recentEvents: NpcEvent[]
  orderHistory: OrderRecord[]
  dialogueHistory: DialogueRecord[]
  langGraphTraces: LangGraphTrace[]
}

// ─── Market Types ─────────────────────────────────────────────────────────────

export interface Trade {
  id: string
  resourceType: string
  quantity: number
  price: number
  buyerName: string
  sellerName: string
  executedAt: string
}

export interface OrderBookEntry {
  price: number
  quantity: number
  totalQuantity: number
}

export interface OrderBook {
  resourceType: string
  bids: OrderBookEntry[]
  asks: OrderBookEntry[]
  lastPrice: number
  volume24h: number
  priceHistory: Array<{ tick: number; price: number; timestamp: string }>
}

// ─── Composable ───────────────────────────────────────────────────────────────

export function useGraphQL() {
  const config = useRuntimeConfig()
  const graphqlUrl = config.public.graphqlUrl as string

  const isLoading = ref(false)
  const lastError = ref<string | null>(null)

  async function query<T>(
    queryString: string,
    variables?: Record<string, unknown>,
    options?: GraphQLRequestOptions
  ): Promise<T | null> {
    isLoading.value = true
    lastError.value = null

    try {
      const response = await $fetch<GraphQLResponse<T>>(graphqlUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
        body: {
          query: queryString,
          variables: variables ?? {},
        },
      })

      if (response.errors && response.errors.length > 0) {
        const errorMessages = response.errors.map((e) => e.message).join('; ')
        lastError.value = errorMessages
        console.error('[useGraphQL] GraphQL errors:', errorMessages)
        return null
      }

      return response.data
    } catch (err) {
      const message = err instanceof Error ? err.message : 'GraphQL request failed'
      lastError.value = message
      console.error('[useGraphQL] fetch error:', message)
      return null
    } finally {
      isLoading.value = false
    }
  }

  async function mutation<T>(
    mutationString: string,
    variables?: Record<string, unknown>,
    options?: GraphQLRequestOptions
  ): Promise<T | null> {
    return query<T>(mutationString, variables, options)
  }

  // ─── Typed Query Functions ─────────────────────────────────────────────────

  async function fetchNpcProfile(npcId: string): Promise<NpcFullProfile | null> {
    const result = await query<{ npc: NpcFullProfile }>(
      `
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
      `,
      { id: npcId }
    )
    return result?.npc ?? null
  }

  async function fetchOrderBook(resourceType: string): Promise<OrderBook | null> {
    const result = await query<{ orderBook: OrderBook }>(
      `
      query GetOrderBook($resourceType: String!) {
        orderBook(resourceType: $resourceType) {
          resourceType lastPrice volume24h
          bids { price quantity totalQuantity }
          asks { price quantity totalQuantity }
          priceHistory(limit: 100) {
            tick price timestamp
          }
        }
      }
      `,
      { resourceType }
    )
    return result?.orderBook ?? null
  }

  async function fetchRecentTrades(resourceType?: string, limit = 50): Promise<Trade[]> {
    const result = await query<{ recentTrades: Trade[] }>(
      `
      query GetRecentTrades($resourceType: String, $limit: Int) {
        recentTrades(resourceType: $resourceType, limit: $limit) {
          id resourceType quantity price buyerName sellerName executedAt
        }
      }
      `,
      { resourceType, limit }
    )
    return result?.recentTrades ?? []
  }

  return {
    isLoading: readonly(isLoading),
    lastError: readonly(lastError),
    query,
    mutation,
    fetchNpcProfile,
    fetchOrderBook,
    fetchRecentTrades,
  }
}
