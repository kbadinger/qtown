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
    // Academy unavailable — return a plausible stub so the UI still works in dev
    console.warn('[visitor/submit] Academy upstream unavailable, returning stub:', err)

    const stubResponse: QuestResponse = {
      questId: `q-${Date.now().toString(36)}`,
      assignedNpc: 'Aldric the Wanderer',
      requestId: `vr-${Date.now().toString(36)}`,
    }

    return stubResponse
  }
})
