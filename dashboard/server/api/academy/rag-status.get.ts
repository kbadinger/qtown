// BFF: GET /api/academy/rag-status
//
// Reads academy's /rag/status — the corpus size + vector-store availability that
// backs the Academy RAG proof panel. Dormant-safe: if academy (or its pgvector
// store) is unreachable, returns available:false with zero counts — an honest
// dormant state, never a fabricated number (REQUIREMENTS §2 principle 1).

interface RagStatus {
  available: boolean
  chunks: number
  sources: number
}

export default defineEventHandler(async (event): Promise<RagStatus> => {
  const config = useRuntimeConfig(event)
  const academyUrl = config.academyUrl as string

  try {
    return await $fetch<RagStatus>(`${academyUrl}/rag/status`, { timeout: 4000 })
  } catch {
    console.warn('[academy/rag-status] academy unavailable — returning dormant state')
    return { available: false, chunks: 0, sources: 0 }
  }
})
