<script setup lang="ts">
// NPC dialogue feed (Flow 2 render, W1-A7): the conversations Academy generated
// for co-located NPC pairs, persisted by town-core and polled via the
// /api/town/dialogues BFF. Dormant-safe — shows an honest empty / — state when
// town-core is unreachable, never fabricated dialogue.
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

const data = ref<DialogueFeed | null>(null)
const pending = ref(true)
let timer: ReturnType<typeof setInterval> | null = null

async function refresh(): Promise<void> {
  try {
    data.value = await $fetch<DialogueFeed>('/api/town/dialogues', { query: { limit: 15 } })
  } catch {
    data.value = { available: false, dialogues: [] }
  } finally {
    pending.value = false
  }
}

onMounted(() => {
  void refresh()
  if (import.meta.client) {
    timer = setInterval(() => void refresh(), 6000)
  }
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})

const live = computed(() => data.value?.available ?? false)
const dialogues = computed(() => data.value?.dialogues ?? [])
</script>

<template>
  <div class="qtown-card">
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-2">
        <h2 class="text-base font-bold text-qtown-text-primary">NPC Dialogue</h2>
        <ProofBadge :live="live" />
      </div>
      <span class="section-title">Academy → town</span>
    </div>

    <div v-if="!live && !pending" class="py-8 text-center text-qtown-text-dim text-sm">
      town-core unavailable — <span class="font-mono">—</span>
    </div>
    <div v-else-if="dialogues.length === 0" class="py-8 text-center text-qtown-text-dim text-sm">
      No conversations yet
    </div>
    <div v-else class="space-y-2 max-h-[420px] overflow-y-auto pr-1">
      <div
        v-for="d in dialogues"
        :key="d.id"
        class="rounded border border-qtown-border bg-qtown-surface/40 px-3 py-2"
      >
        <div class="flex items-center justify-between text-xs mb-1">
          <span class="font-semibold text-qtown-gold">
            {{ d.speaker }}<span v-if="d.listener" class="text-qtown-text-dim"> → {{ d.listener }}</span>
          </span>
          <span class="text-qtown-text-dim font-mono">tick {{ d.tick }}</span>
        </div>
        <p class="text-sm text-qtown-text-secondary leading-snug">{{ d.message }}</p>
      </div>
    </div>

    <p class="mt-3 text-xs text-qtown-text-dim">
      town-core pairs co-located NPCs → Academy
      <span class="font-mono">GenerateDialogue</span> (gRPC) → emitted on
      <span class="font-mono">qtown.ai.content.generated</span>.
    </p>
  </div>
</template>
