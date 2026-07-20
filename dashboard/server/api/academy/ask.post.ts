// BFF: POST /api/academy/ask  { question: string, k?: number }
//
// Proxies academy's grounded RAG endpoint (/rag/ask) and normalises the response
// to a browser-friendly camelCase shape. The answerer only speaks from retrieved
// passages and cites them; on any backend failure this returns grounded:false +
// unavailable:true with an EMPTY answer — it never invents a reply (REQUIREMENTS
// §2 principle 1). An empty question is a 400.

interface RawCitation {
  n: number
  doc_id: string
  source: string
  heading: string
  snippet: string
  score: number
}
interface RawAnswer {
  question: string
  answer: string
  grounded: boolean
  model: string
  retrieved: number
  latency_ms: number
  citations: RawCitation[]
}

interface Citation {
  n: number
  source: string
  heading: string
  snippet: string
  score: number
}
interface AskResult {
  question: string
  answer: string
  grounded: boolean
  model: string
  retrieved: number
  latencyMs: number
  citations: Citation[]
  unavailable: boolean
}

function dormant(question: string): AskResult {
  return {
    question,
    answer: '',
    grounded: false,
    model: '',
    retrieved: 0,
    latencyMs: 0,
    citations: [],
    unavailable: true,
  }
}

export default defineEventHandler(async (event): Promise<AskResult> => {
  const config = useRuntimeConfig(event)
  const academyUrl = config.academyUrl as string

  const body = await readBody<{ question?: string; k?: number }>(event)
  const question = (body?.question ?? '').trim()
  if (!question) {
    setResponseStatus(event, 400)
    return dormant('')
  }
  const k = Math.min(Math.max(Number(body?.k ?? 5), 1), 10)

  try {
    // Generation is model-backed and can take several seconds (longer on a cold
    // model) — allow a generous ceiling; the panel shows a spinner meanwhile.
    const raw = await $fetch<RawAnswer>(`${academyUrl}/rag/ask`, {
      method: 'POST',
      body: { question, k },
      timeout: 60000,
    })
    return {
      question: raw.question,
      answer: raw.answer,
      grounded: raw.grounded,
      model: raw.model,
      retrieved: raw.retrieved,
      latencyMs: raw.latency_ms,
      citations: (raw.citations ?? []).map((c) => ({
        n: c.n,
        source: c.source,
        heading: c.heading,
        snippet: c.snippet,
        score: c.score,
      })),
      unavailable: false,
    }
  } catch {
    console.warn('[academy/ask] rag backend unavailable — returning dormant (no fabricated answer)')
    return dormant(question)
  }
})
