<script setup lang="ts">
import type { SubmitResult } from '~/composables/useVisitor'

definePageMeta({ layout: false })
useHead({ title: 'Visitor — Qtown' })

const { getRecentRequests, isLoading } = useVisitor()
const { fetchWorldState } = useApi()

interface VisitorWorldState {
  tick: number
  population: number
  totalGold: number
  averageHappiness: number
  weather: { condition: string; temperature: number }
}

const worldState = ref<VisitorWorldState | null>(null)
const recentRequests = ref<Awaited<ReturnType<typeof getRecentRequests>>>([])
const lastSubmitted = ref<SubmitResult | null>(null)

onMounted(async () => {
  const [state, requests] = await Promise.all([
    fetchWorldState(),
    getRecentRequests(8),
  ])
  if (state) worldState.value = state
  recentRequests.value = requests
})

function onSubmitted(result: SubmitResult) {
  lastSubmitted.value = result
  getRecentRequests(8).then(r => { recentRequests.value = r })
}

const happinessColor = computed(() => {
  const h = worldState.value?.averageHappiness ?? 0
  if (h >= 70) return 'text-green-400'
  if (h >= 40) return 'text-yellow-400'
  return 'text-red-400'
})

const steps = [
  { n: 1, label: 'Submit', detail: 'Fill out the feature request form below.' },
  { n: 2, label: 'Quest Created', detail: 'The Academy AI converts your request into an NPC quest.' },
  { n: 3, label: 'Assigned', detail: 'An available NPC is assigned as the quest champion.' },
  { n: 4, label: 'Executed', detail: 'The NPC works on your quest over the next several ticks.' },
]

const categoryColors: Record<string, string> = {
  economy: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
  social: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  infrastructure: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  combat: 'bg-red-500/10 text-red-400 border-red-500/20',
  exploration: 'bg-green-500/10 text-green-400 border-green-500/20',
}

const priorityColors: Record<string, string> = {
  low: 'text-green-400',
  medium: 'text-yellow-400',
  high: 'text-red-400',
}

const statusColors: Record<string, string> = {
  pending: 'bg-qtown-border text-qtown-text-dim',
  in_progress: 'bg-blue-500/10 text-blue-400',
  completed: 'bg-green-500/10 text-green-400',
}
</script>

<template>
  <div class="min-h-screen bg-qtown-bg text-qtown-text-primary">
    <!-- Header bar -->
    <header class="border-b border-qtown-border bg-qtown-card px-6 py-4 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <svg viewBox="0 0 24 24" fill="none" class="w-7 h-7 text-qtown-gold" aria-label="Qtown">
          <path d="M12 2L3 8v12h5v-6h8v6h5V8L12 2z" fill="currentColor" opacity="0.9" />
        </svg>
        <div>
          <h1 class="font-bold text-qtown-text-primary text-lg leading-none">Qtown</h1>
          <p class="text-xs text-qtown-text-dim mt-0.5">Visitor View — Read Only</p>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <NuxtLink to="/docs" class="text-xs text-qtown-text-dim hover:text-qtown-text-secondary transition-colors">Docs</NuxtLink>
        <NuxtLink to="/" class="text-xs bg-qtown-accent/10 text-qtown-accent border border-qtown-accent/30 px-3 py-1.5 rounded hover:bg-qtown-accent/20 transition-colors">
          Dashboard →
        </NuxtLink>
      </div>
    </header>

    <div class="max-w-6xl mx-auto px-6 py-10">
      <!-- Hero section -->
      <div class="text-center mb-12">
        <h2 class="text-4xl font-bold text-qtown-text-primary mb-4">Welcome to Qtown</h2>
        <p class="text-qtown-text-secondary text-lg max-w-2xl mx-auto leading-relaxed">
          A living medieval town powered by AI. Hundreds of NPCs make decisions, trade resources,
          study at the academy, and defend the fortress — all autonomously, all right now.
        </p>
      </div>

      <!-- Town state cards -->
      <div class="grid grid-cols-4 gap-4 mb-12">
        <div v-if="worldState" class="col-span-4 grid grid-cols-4 gap-4">
          <div class="bg-qtown-card border border-qtown-border rounded-xl px-5 py-4">
            <div class="text-qtown-text-dim text-xs font-mono uppercase tracking-wider mb-2">Population</div>
            <div class="text-3xl font-bold text-qtown-text-primary font-mono">{{ worldState.population.toLocaleString() }}</div>
            <div class="text-xs text-qtown-text-dim mt-1">NPC citizens</div>
          </div>
          <div class="bg-qtown-card border border-qtown-border rounded-xl px-5 py-4">
            <div class="text-qtown-text-dim text-xs font-mono uppercase tracking-wider mb-2">Economy</div>
            <div class="text-3xl font-bold text-qtown-gold font-mono">{{ Math.round(worldState.totalGold).toLocaleString() }}</div>
            <div class="text-xs text-qtown-text-dim mt-1">gold in circulation</div>
          </div>
          <div class="bg-qtown-card border border-qtown-border rounded-xl px-5 py-4">
            <div class="text-qtown-text-dim text-xs font-mono uppercase tracking-wider mb-2">Happiness</div>
            <div class="text-3xl font-bold font-mono" :class="happinessColor">{{ Math.round(worldState.averageHappiness) }}%</div>
            <div class="text-xs text-qtown-text-dim mt-1">average NPC mood</div>
          </div>
          <div class="bg-qtown-card border border-qtown-border rounded-xl px-5 py-4">
            <div class="text-qtown-text-dim text-xs font-mono uppercase tracking-wider mb-2">Simulation</div>
            <div class="text-3xl font-bold text-blue-400 font-mono">{{ worldState.tick.toLocaleString() }}</div>
            <div class="text-xs text-qtown-text-dim mt-1">ticks elapsed</div>
          </div>
        </div>
        <div v-else class="col-span-4 grid grid-cols-4 gap-4">
          <div v-for="i in 4" :key="i" class="bg-qtown-card border border-qtown-border rounded-xl px-5 py-4 animate-pulse">
            <div class="h-3 w-20 bg-qtown-border rounded mb-3" />
            <div class="h-8 w-24 bg-qtown-border rounded" />
          </div>
        </div>
      </div>

      <!-- Main grid: form + recent requests -->
      <div class="grid grid-cols-5 gap-8 mb-14">
        <!-- Feature request form (left 3/5) -->
        <div class="col-span-3">
          <FeatureRequestForm @submitted="onSubmitted" />
        </div>

        <!-- How it works (right 2/5) -->
        <div class="col-span-2">
          <h3 class="font-semibold text-qtown-text-primary mb-4 flex items-center gap-2">
            <svg viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4 text-qtown-gold">
              <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
            </svg>
            How It Works
          </h3>
          <div class="space-y-3">
            <div
              v-for="step in steps"
              :key="step.n"
              class="flex items-start gap-3 bg-qtown-card border border-qtown-border rounded-lg px-4 py-3"
            >
              <span class="w-6 h-6 rounded-full bg-qtown-accent/15 text-qtown-accent border border-qtown-accent/30 flex items-center justify-center flex-shrink-0 text-xs font-bold font-mono mt-0.5">
                {{ step.n }}
              </span>
              <div>
                <div class="font-medium text-sm text-qtown-text-primary">{{ step.label }}</div>
                <div class="text-xs text-qtown-text-dim mt-0.5">{{ step.detail }}</div>
              </div>
            </div>
          </div>

          <div class="mt-5 bg-qtown-surface border border-qtown-border rounded-lg px-4 py-3">
            <p class="text-xs text-qtown-text-dim leading-relaxed">
              Your feature request becomes a real NPC objective. The academy service uses
              GPT-4o to generate a structured quest with steps, rewards, and a narrative.
              An NPC champion is selected based on their skills and current assignments.
            </p>
          </div>
        </div>
      </div>

      <!-- Recent visitor-submitted quests -->
      <section>
        <h3 class="font-semibold text-qtown-text-primary text-xl mb-5 flex items-center gap-2">
          Recent Visitor Quests
          <span v-if="isLoading" class="w-3 h-3 rounded-full border-2 border-qtown-accent border-t-transparent animate-spin" />
        </h3>

        <div v-if="recentRequests.length === 0 && !isLoading" class="text-center py-12 text-qtown-text-dim">
          <p>No visitor quests yet. Be the first to submit!</p>
        </div>

        <div v-else class="grid grid-cols-2 gap-4">
          <div
            v-for="req in recentRequests"
            :key="req.id ?? req.title"
            class="bg-qtown-card border border-qtown-border rounded-xl p-5 hover:border-qtown-accent/20 transition-colors"
          >
            <div class="flex items-start justify-between gap-3 mb-3">
              <h4 class="font-medium text-qtown-text-primary text-sm leading-snug flex-1">{{ req.title }}</h4>
              <span
                v-if="req.status"
                class="text-xs px-2 py-0.5 rounded font-mono flex-shrink-0"
                :class="statusColors[req.status] ?? 'bg-qtown-border text-qtown-text-dim'"
              >{{ req.status.replace('_', ' ') }}</span>
            </div>
            <p class="text-xs text-qtown-text-dim leading-relaxed mb-3 line-clamp-2">{{ req.description }}</p>
            <div class="flex items-center gap-2 flex-wrap">
              <span
                class="text-xs px-2 py-0.5 rounded border font-mono capitalize"
                :class="categoryColors[req.category] ?? 'bg-qtown-border/50 text-qtown-text-dim'"
              >{{ req.category }}</span>
              <span class="text-xs font-mono" :class="priorityColors[req.priority] ?? 'text-qtown-text-dim'">
                {{ req.priority }} priority
              </span>
              <span v-if="req.assignedNpc" class="text-xs text-qtown-text-dim">
                → {{ req.assignedNpc }}
              </span>
            </div>
            <div v-if="req.status === 'in_progress' && req.progress !== undefined" class="mt-3">
              <div class="h-1.5 bg-qtown-surface rounded-full overflow-hidden">
                <div
                  class="h-full bg-blue-500 rounded-full transition-all duration-500"
                  :style="{ width: `${req.progress}%` }"
                />
              </div>
              <div class="text-xs text-qtown-text-dim mt-1 text-right">{{ req.progress }}% complete</div>
            </div>
            <div v-if="req.questId" class="mt-3 text-xs font-mono text-qtown-text-dim">
              Quest: <code class="text-qtown-gold">{{ req.questId }}</code>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
