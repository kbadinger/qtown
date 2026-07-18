// BFF: GET /api/tavern/content?limit=15
//
// Reads tavern's HTTP read-model — recent content events that passed through the
// gateway (/content/recent) plus live WebSocket gateway metrics (/metrics) — and
// returns a compact snapshot for the Tavern proof panel. Dormant-safe: if tavern
// is unreachable, returns live:false with empty/null values, never fabricated
// numbers (REQUIREMENTS §2 principle 1).

interface RawItem {
  content_type: string
  content_id: string
  text?: string
  content?: unknown
  metadata?: Record<string, unknown>
  received_at: string
}
interface RawRecent {
  available: boolean
  items: RawItem[]
}
interface RawMetrics {
  totalConnections: number
  messagesPerSecond: number
  activeChannels: string[]
}

interface ContentEntry {
  id: string
  contentType: string
  text: string
  receivedAt: string
  participants: string | null
  tone: string | null
  model: string | null
}
interface TavernProof {
  live: boolean
  connections: number | null
  messagesPerSecond: number | null
  activeChannels: string[]
  items: ContentEntry[]
}

function str(v: unknown): string | null {
  return v === undefined || v === null ? null : String(v)
}

function mapItem(it: RawItem): ContentEntry {
  const meta = it.metadata ?? {}
  const a = str(meta.npc_a)
  const b = str(meta.npc_b)
  const participants = a && b ? `${a} ↔ ${b}` : null
  const text = it.text ?? (it.content !== undefined ? JSON.stringify(it.content) : '')
  return {
    id: it.content_id,
    contentType: it.content_type,
    text,
    receivedAt: it.received_at,
    participants,
    tone: str(meta.tone),
    model: str(meta.model_used),
  }
}

function dormant(): TavernProof {
  return {
    live: false,
    connections: null,
    messagesPerSecond: null,
    activeChannels: [],
    items: [],
  }
}

export default defineEventHandler(async (event): Promise<TavernProof> => {
  const config = useRuntimeConfig(event)
  const base = config.tavernHttpUrl as string

  const q = getQuery(event)
  const limit = Math.min(Math.max(Number(q.limit ?? 15), 1), 100)

  try {
    const [recent, metrics] = await Promise.all([
      $fetch<RawRecent>(`${base}/content/recent`, { query: { limit }, timeout: 4000 }),
      $fetch<RawMetrics>(`${base}/metrics`, { timeout: 4000 }),
    ])
    return {
      live: true,
      connections: metrics.totalConnections,
      messagesPerSecond: metrics.messagesPerSecond,
      activeChannels: metrics.activeChannels ?? [],
      items: (recent.items ?? []).map(mapItem),
    }
  } catch {
    console.warn('[tavern/content] tavern unavailable — returning dormant state')
    return dormant()
  }
})
