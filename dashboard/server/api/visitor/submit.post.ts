// POST /api/visitor/submit
// Accepts a feature request, forwards to Academy GenerateQuest RPC, returns quest details

import { z } from 'zod'

const FeatureRequestSchema = z.object({
  title: z.string().min(3).max(100),
  description: z.string().min(10).max(500),
  category: z.enum(['economy', 'social', 'infrastructure', 'combat', 'exploration']),
  priority: z.enum(['low', 'medium', 'high']),
})

interface QuestResponse {
  questId: string
  assignedNpc: string
  requestId: string
}

interface AcademyQuestResult {
  quest_id: string
  npc_id: string
  npc_name: string
  steps: string[]
}

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const academyUrl = config.academyUrl as string

  // Parse and validate body
  let body: unknown
  try {
    body = await readBody(event)
  } catch {
    throw createError({ statusCode: 400, statusMessage: 'Bad Request', message: 'Invalid JSON body' })
  }

  const parseResult = FeatureRequestSchema.safeParse(body)
  if (!parseResult.success) {
    throw createError({
      statusCode: 422,
      statusMessage: 'Unprocessable Entity',
      message: parseResult.error.issues.map(i => i.message).join('; '),
    })
  }

  const request = parseResult.data

  try {
    // Forward to Academy service — GenerateQuest endpoint
    const academyResult = await $fetch<AcademyQuestResult>(`${academyUrl}/api/quests/generate`, {
      method: 'POST',
      body: {
        title: request.title,
        description: request.description,
        category: request.category,
        priority: request.priority,
        source: 'visitor',
      },
      headers: { 'Content-Type': 'application/json' },
    })

    const response: QuestResponse = {
      questId: academyResult.quest_id,
      assignedNpc: academyResult.npc_name ?? 'Pending assignment',
      requestId: `vr-${Date.now().toString(36)}`,
    }

    return response
  } catch (err) {
    // Academy unavailable — surface an honest error instead of a fabricated quest.
    // A fake "success" (invented questId / assigned NPC) would violate the project's
    // honesty rule (docs/plans/03-PROOF-OF-WORK.md §4 rule 1: "No fabricated values,
    // ever"). The UI renders this as a submit failure, not a phantom quest.
    const message = err instanceof Error ? err.message : 'Academy upstream unavailable'
    console.warn('[visitor/submit] Academy upstream unavailable:', message)

    throw createError({
      statusCode: 502,
      statusMessage: 'Bad Gateway',
      message: `Failed to create quest — Academy service unavailable: ${message}`,
    })
  }
})
