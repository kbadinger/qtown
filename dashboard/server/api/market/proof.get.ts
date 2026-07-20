// BFF: GET /api/market/proof?resource=gold&depth=8
//
// Reads market-district's own HTTP read-model (:6060 → /api/orderbook, /api/trades),
// aggregates the raw per-order book into price levels, and returns a compact,
// browser-friendly snapshot for the Market proof panel.
//
// If market is reachable but idle, `live` is true with an empty book (honest
// "no activity"). If market is UNREACHABLE, we return a dormant shape
// (live:false, nulls/empties) — never a fabricated number
// (docs/plans/03-PROOF-OF-WORK.md §4 rule 1: "No fabricated values, ever").

interface RawLevel {
  price: number
  quantity: number
}
interface RawBook {
  resource: string
  bids: RawLevel[]
  asks: RawLevel[]
  midPrice: number
  spread: number
}
interface RawTrade {
  id: string
  resource: string
  price: number
  quantity: number
  ts: number
}

interface ProofLevel {
  price: number
  quantity: number
}
interface ProofBook {
  bids: ProofLevel[]
  asks: ProofLevel[]
  mid: number | null
  spread: number | null
}
interface ProofTrade {
  id: string
  resource: string
  price: number
  quantity: number
  ts: number
}
interface MarketProof {
  live: boolean
  resource: string
  book: ProofBook
  trades: ProofTrade[]
}

// Collapse per-order levels into per-price levels, summing quantity, then take
// the top `depth` (bids descending, asks ascending by price).
function aggregate(levels: RawLevel[], descending: boolean, depth: number): ProofLevel[] {
  const byPrice = new Map<number, number>()
  for (const level of levels) {
    byPrice.set(level.price, (byPrice.get(level.price) ?? 0) + level.quantity)
  }
  const out: ProofLevel[] = [...byPrice.entries()].map(([price, quantity]) => ({ price, quantity }))
  out.sort((a, b) => (descending ? b.price - a.price : a.price - b.price))
  return out.slice(0, depth)
}

function dormant(resource: string): MarketProof {
  return {
    live: false,
    resource,
    book: { bids: [], asks: [], mid: null, spread: null },
    trades: [],
  }
}

export default defineEventHandler(async (event): Promise<MarketProof> => {
  const config = useRuntimeConfig(event)
  const marketHttpUrl = config.marketHttpUrl as string

  const query = getQuery(event)
  const resource = (query.resource as string | undefined) ?? 'gold'
  const depth = Math.min(Math.max(Number(query.depth ?? 8), 1), 20)

  try {
    const [rawBook, rawTrades] = await Promise.all([
      $fetch<RawBook>(`${marketHttpUrl}/api/orderbook`, { query: { resource } }),
      $fetch<RawTrade[]>(`${marketHttpUrl}/api/trades`, { query: { resource, limit: 12 } }),
    ])

    const bids = aggregate(rawBook.bids ?? [], true, depth)
    const asks = aggregate(rawBook.asks ?? [], false, depth)
    const twoSided = bids.length > 0 && asks.length > 0

    return {
      live: true,
      resource,
      book: {
        bids,
        asks,
        mid: twoSided && rawBook.midPrice > 0 ? rawBook.midPrice : null,
        spread: twoSided ? rawBook.spread : null,
      },
      trades: rawTrades ?? [],
    }
  } catch {
    // Market unreachable — dormant, honest, no fabricated data.
    console.warn('[market/proof] read-model unavailable — returning dormant state')
    return dormant(resource)
  }
})
