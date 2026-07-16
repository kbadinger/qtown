// useMarketProof — reactive client for the Market proof panel.
//
// Polls /api/market/proof (the BFF over market-district's read-model) and
// exposes live order-book + recent-trade state plus the committed, measured
// performance numbers. On any fetch error it falls back to a dormant shape —
// never fabricated values.

export interface ProofLevel {
  price: number
  quantity: number
}
export interface ProofBook {
  bids: ProofLevel[]
  asks: ProofLevel[]
  mid: number | null
  spread: number | null
}
export interface ProofTrade {
  id: string
  resource: string
  price: number
  quantity: number
  ts: number
}
export interface MarketProof {
  live: boolean
  resource: string
  book: ProofBook
  trades: ProofTrade[]
}

// Measured, committed numbers from docs/perf/market-loadtest.md (W1-M7).
// A dated LOCAL-REFERENCE measurement — not a live gauge, and not a
// CI-enforced SLO. Displayed with its provenance so it can never read as a
// fabricated or guaranteed figure.
export const MARKET_PERF = {
  measuredOn: '2026-07-15',
  hardware: 'i9-12900K · loopback',
  provenance: 'local reference — not a CI-enforced SLO',
  placementP99Ms: 2.16,
  placementRps: 41758,
  fullSpineP99Ms: 24.71,
  engineNsPerOp: 2186,
} as const

function dormant(resource: string): MarketProof {
  return {
    live: false,
    resource,
    book: { bids: [], asks: [], mid: null, spread: null },
    trades: [],
  }
}

export function useMarketProof(initialResource = 'gold') {
  const resource = ref(initialResource)
  const data = ref<MarketProof | null>(null)
  const pending = ref(true)
  let timer: ReturnType<typeof setInterval> | null = null

  async function refresh(): Promise<void> {
    try {
      data.value = await $fetch<MarketProof>('/api/market/proof', {
        query: { resource: resource.value },
      })
    } catch {
      data.value = dormant(resource.value)
    } finally {
      pending.value = false
    }
  }

  function start(intervalMs = 4000): void {
    void refresh()
    if (import.meta.client) {
      timer = setInterval(() => void refresh(), intervalMs)
    }
  }

  function stop(): void {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  watch(resource, () => {
    void refresh()
  })

  return { resource, data, pending, refresh, start, stop }
}
