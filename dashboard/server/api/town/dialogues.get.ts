// BFF: GET /api/town/dialogues?limit=20
//
// Proxies town-core's dialogue history — the NPC conversations Academy generated
// and town-core persisted (Flow 2). Dormant-safe: if town-core is unreachable,
// returns available:false with an empty list, never fabricated dialogue
// (REQUIREMENTS §2 principle 1).

interface RawDialogue {
  id: number
  speaker_npc_id: number
  listener_npc_id: number | null
  speaker_name: string | null
  listener_name: string | null
  message: string
  tick: number
}
interface DialogueEntry {
  id: number
  speaker: string
  listener: string | null
  message: string
  tick: number
}
interface DialogueFeed {
  available: boolean
  dialogues: DialogueEntry[]
}

export default defineEventHandler(async (event): Promise<DialogueFeed> => {
  const config = useRuntimeConfig(event)
  const townCoreUrl = config.townCoreUrl as string

  const q = getQuery(event)
  const limit = Math.min(Math.max(Number(q.limit ?? 20), 1), 100)

  try {
    const raw = await $fetch<RawDialogue[]>(`${townCoreUrl}/api/dialogues/`, {
      query: { limit },
      timeout: 4000,
    })
    return {
      available: true,
      dialogues: (raw ?? []).map((d) => ({
        id: d.id,
        speaker: d.speaker_name ?? `NPC ${d.speaker_npc_id}`,
        listener:
          d.listener_name ??
          (d.listener_npc_id != null ? `NPC ${d.listener_npc_id}` : null),
        message: d.message,
        tick: d.tick,
      })),
    }
  } catch {
    console.warn('[town/dialogues] town-core unavailable — returning dormant state')
    return { available: false, dialogues: [] }
  }
})
