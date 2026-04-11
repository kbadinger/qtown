<script setup lang="ts">
import { useGraphQL } from '~/composables/useGraphQL'
import type { NpcFullProfile, LangGraphNode } from '~/composables/useGraphQL'

const route = useRoute()
const npcId = computed(() => route.params.id as string)

useHead(() => ({ title: `NPC — Qtown` }))

const graphql = useGraphQL()
const profile = ref<NpcFullProfile | null>(null)
const activeTab = ref<'events' | 'orders' | 'dialogue' | 'langgraph'>('events')

onMounted(async () => {
  profile.value = await graphql.fetchNpcProfile(npcId.value)
  if (profile.value) {
    useHead({ title: `${profile.value.name} — Qtown` })
  }
})

// ─── Stat bars ────────────────────────────────────────────────────────────────

interface StatBar {
  label: string
  value: number
  color: string
}

const statBars = computed<StatBar[]>(() => {
  if (!profile.value) return []
  return [
    { label: 'Happiness', value: profile.value.happiness, color: 'bg-purple-400' },
    { label: 'Hunger', value: profile.value.hunger, color: 'bg-orange-400' },
    { label: 'Energy', value: profile.value.energy, color: 'bg-blue-400' },
  ]
})

// ─── Status ───────────────────────────────────────────────────────────────────

const statusStyle: Record<string, string> = {
  active: 'bg-green-400/10 text-green-400 border-green-400/30',
  traveling: 'bg-blue-400/10 text-blue-400 border-blue-400/30',
  sleeping: 'bg-indigo-400/10 text-indigo-400 border-indigo-400/30',
  idle: 'bg-qtown-border/50 text-qtown-text-dim border-qtown-border',
}

// ─── Portrait color ───────────────────────────────────────────────────────────

const portraitColor = computed(() => {
  if (!profile.value) return '#4a4e69'
  let hash = 0
  for (const char of profile.value.id) {
    hash = (hash << 5) - hash + char.charCodeAt(0)
    hash |= 0
  }
  const hue = Math.abs(hash) % 360
  return `hsl(${hue}, 55%, 30%)`
})

const initials = computed(() => {
  if (!profile.value) return '??'
  const parts = profile.value.name.split(' ')
  return parts.length >= 2 ? `${parts[0][0]}${parts[1][0]}` : profile.value.name.slice(0, 2)
})

// ─── LangGraph trace display ──────────────────────────────────────────────────

const selectedTrace = ref(0)

const currentTrace = computed(() => profile.value?.langGraphTraces[selectedTrace.value] ?? null)

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

function truncateText(text: string, max = 120): string {
  return text.length > max ? `${text.slice(0, max)}…` : text
}
</script>

<template>
  <div class="space-y-6">
    <!-- Back button -->
    <NuxtLink
      to="/npcs"
      class="inline-flex items-center gap-2 text-qtown-text-secondary hover:text-qtown-text-primary text-sm transition-colors"
    >
      <svg viewBox="0 0 16 16" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M10 12L6 8l4-4" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      Back to NPCs
    </NuxtLink>

    <!-- Loading -->
    <div
      v-if="graphql.isLoading.value"
      class="flex flex-col items-center justify-center py-20 text-qtown-text-dim"
    >
      <div class="flex gap-1.5 mb-3">
        <div class="w-2 h-2 rounded-full bg-qtown-gold animate-bounce" style="animation-delay: 0ms" />
        <div class="w-2 h-2 rounded-full bg-qtown-gold animate-bounce" style="animation-delay: 150ms" />
        <div class="w-2 h-2 rounded-full bg-qtown-gold animate-bounce" style="animation-delay: 300ms" />
      </div>
      <p class="text-sm">Loading NPC profile...</p>
    </div>

    <!-- Error -->
    <div
      v-else-if="graphql.lastError.value && !profile"
      class="qtown-card border border-qtown-accent/30 bg-qtown-accent/5"
    >
      <p class="text-qtown-accent font-medium">Failed to load NPC</p>
      <p class="text-qtown-text-dim text-sm mt-1">{{ graphql.lastError.value }}</p>
    </div>

    <!-- Profile -->
    <template v-else-if="profile">
      <!-- Header card -->
      <div class="qtown-card">
        <div class="flex items-start gap-6">
          <!-- Portrait -->
          <div
            class="w-20 h-20 rounded-xl flex items-center justify-center text-2xl font-bold font-mono text-white shrink-0 shadow-card"
            :style="{ backgroundColor: portraitColor }"
          >
            {{ initials.toUpperCase() }}
          </div>

          <!-- Main info -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-3 flex-wrap">
              <h1 class="text-2xl font-bold text-qtown-text-primary">{{ profile.name }}</h1>
              <span :class="['qtown-badge border capitalize', statusStyle[profile.status] ?? statusStyle['idle']]">
                {{ profile.status }}
              </span>
            </div>
            <div class="flex items-center gap-4 mt-1 text-sm text-qtown-text-secondary">
              <span>{{ profile.role }}</span>
              <span>·</span>
              <span>{{ profile.neighborhood }}</span>
              <span>·</span>
              <span class="font-mono text-xs text-qtown-text-dim">ID: {{ profile.id }}</span>
            </div>

            <!-- Stat bars -->
            <div class="mt-4 space-y-2 max-w-xs">
              <div
                v-for="stat in statBars"
                :key="stat.label"
                class="flex items-center gap-3"
              >
                <span class="section-title w-20 text-right">{{ stat.label }}</span>
                <div class="flex-1 h-1.5 bg-qtown-border rounded-full overflow-hidden">
                  <div
                    :class="['h-full rounded-full transition-all duration-500', stat.color]"
                    :style="{ width: `${Math.max(0, Math.min(100, stat.value))}%` }"
                  />
                </div>
                <span class="font-mono text-xs text-qtown-text-secondary w-8">{{ stat.value }}%</span>
              </div>
            </div>
          </div>

          <!-- Gold -->
          <div class="text-right shrink-0">
            <div class="text-3xl font-bold font-mono text-qtown-gold">
              {{ profile.gold.toLocaleString() }}
            </div>
            <div class="text-qtown-text-dim text-xs mt-0.5">gold coins</div>
          </div>
        </div>
      </div>

      <!-- Current activity + position -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="qtown-card">
          <h2 class="section-title mb-3">Current Activity</h2>
          <div v-if="profile.currentActivity">
            <div class="flex items-center gap-2 mb-2">
              <span class="qtown-badge bg-qtown-gold/10 text-qtown-gold border-qtown-gold/30">
                {{ profile.currentActivity.type }}
              </span>
            </div>
            <p class="text-qtown-text-primary text-sm">{{ profile.currentActivity.description }}</p>
            <div class="flex items-center gap-4 mt-2 text-xs text-qtown-text-dim">
              <span>📍 {{ profile.currentActivity.location }}</span>
              <span>⏱ {{ profile.currentActivity.startedAt }}</span>
            </div>
          </div>
          <div v-else class="text-qtown-text-dim text-sm">
            No current activity
          </div>
        </div>

        <div class="qtown-card">
          <h2 class="section-title mb-3">Position</h2>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <span class="section-title">Grid X</span>
              <div class="font-mono font-bold text-qtown-text-primary text-xl">{{ profile.x }}</div>
            </div>
            <div>
              <span class="section-title">Grid Y</span>
              <div class="font-mono font-bold text-qtown-text-primary text-xl">{{ profile.y }}</div>
            </div>
          </div>
          <p class="text-qtown-text-dim text-xs mt-2">Neighborhood: {{ profile.neighborhood }}</p>
        </div>
      </div>

      <!-- Tabbed detail panel -->
      <div class="qtown-card p-0 overflow-hidden">
        <!-- Tab header -->
        <div class="flex border-b border-qtown-border">
          <button
            v-for="tab in [
              { key: 'events', label: 'Recent Events', count: profile.recentEvents.length },
              { key: 'orders', label: 'Order History', count: profile.orderHistory.length },
              { key: 'dialogue', label: 'Dialogue', count: profile.dialogueHistory.length },
              { key: 'langgraph', label: 'LangGraph', count: profile.langGraphTraces.length },
            ]"
            :key="tab.key"
            :class="[
              'px-4 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2',
              activeTab === tab.key
                ? 'border-qtown-accent text-qtown-accent'
                : 'border-transparent text-qtown-text-secondary hover:text-qtown-text-primary',
            ]"
            @click="activeTab = tab.key as typeof activeTab"
          >
            {{ tab.label }}
            <span class="text-xs font-mono opacity-60">({{ tab.count }})</span>
          </button>
        </div>

        <!-- Tab content -->
        <div class="p-4">
          <!-- Recent Events -->
          <div v-if="activeTab === 'events'" class="space-y-2">
            <div
              v-for="event in profile.recentEvents"
              :key="event.id"
              class="flex items-start gap-3 p-2 rounded bg-qtown-border/20 hover:bg-qtown-border/30 transition-colors"
            >
              <span class="font-mono text-xs text-qtown-text-dim shrink-0 pt-0.5">T{{ event.tick }}</span>
              <span class="qtown-badge bg-qtown-border text-qtown-text-secondary text-xs shrink-0">{{ event.type }}</span>
              <span class="text-sm text-qtown-text-primary flex-1">{{ event.description }}</span>
              <span class="text-xs text-qtown-text-dim shrink-0">{{ new Date(event.timestamp).toLocaleTimeString() }}</span>
            </div>
            <p v-if="profile.recentEvents.length === 0" class="text-qtown-text-dim text-sm text-center py-8">
              No recent events
            </p>
          </div>

          <!-- Order History -->
          <div v-else-if="activeTab === 'orders'" class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-qtown-text-dim border-b border-qtown-border">
                  <th class="text-left py-2 px-3 section-title">Resource</th>
                  <th class="text-left py-2 px-3 section-title">Side</th>
                  <th class="text-right py-2 px-3 section-title">Qty</th>
                  <th class="text-right py-2 px-3 section-title">Price</th>
                  <th class="text-left py-2 px-3 section-title">Status</th>
                  <th class="text-left py-2 px-3 section-title">Date</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="order in profile.orderHistory"
                  :key="order.id"
                  class="border-b border-qtown-border/40 hover:bg-qtown-border/20"
                >
                  <td class="py-2 px-3 text-qtown-text-primary">{{ order.resourceType }}</td>
                  <td class="py-2 px-3">
                    <span :class="order.side === 'buy' ? 'text-green-400' : 'text-red-400'" class="font-mono uppercase text-xs">
                      {{ order.side }}
                    </span>
                  </td>
                  <td class="py-2 px-3 text-right font-mono text-qtown-text-secondary">{{ order.quantity }}</td>
                  <td class="py-2 px-3 text-right font-mono text-qtown-gold">{{ order.price.toFixed(4) }}</td>
                  <td class="py-2 px-3">
                    <span
                      :class="[
                        'qtown-badge text-xs',
                        order.status === 'filled' ? 'bg-green-400/10 text-green-400' :
                        order.status === 'cancelled' ? 'bg-red-400/10 text-red-400' :
                        order.status === 'partial' ? 'bg-yellow-400/10 text-yellow-400' :
                        'bg-qtown-border text-qtown-text-dim',
                      ]"
                    >{{ order.status }}</span>
                  </td>
                  <td class="py-2 px-3 text-xs text-qtown-text-dim">
                    {{ new Date(order.createdAt).toLocaleDateString() }}
                  </td>
                </tr>
                <tr v-if="profile.orderHistory.length === 0">
                  <td colspan="6" class="py-8 text-center text-qtown-text-dim">No orders</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Dialogue History -->
          <div v-else-if="activeTab === 'dialogue'" class="space-y-4">
            <div
              v-for="dialogue in profile.dialogueHistory"
              :key="dialogue.id"
              class="border border-qtown-border rounded-lg overflow-hidden"
            >
              <div class="px-3 py-2 bg-qtown-border/20 flex items-center gap-3 text-xs text-qtown-text-dim">
                <span class="qtown-badge bg-purple-400/10 text-purple-400">{{ dialogue.model }}</span>
                <span>{{ dialogue.tokensUsed }} tokens</span>
                <span>{{ new Date(dialogue.createdAt).toLocaleString() }}</span>
              </div>
              <div class="p-3 space-y-2">
                <div>
                  <div class="section-title mb-1">Prompt</div>
                  <p class="text-sm text-qtown-text-secondary">{{ truncateText(dialogue.prompt, 200) }}</p>
                </div>
                <div class="border-t border-qtown-border pt-2">
                  <div class="section-title mb-1">Response</div>
                  <p class="text-sm text-qtown-text-primary">{{ truncateText(dialogue.response, 300) }}</p>
                </div>
              </div>
            </div>
            <p v-if="profile.dialogueHistory.length === 0" class="text-qtown-text-dim text-sm text-center py-8">
              No dialogue history
            </p>
          </div>

          <!-- LangGraph Trace -->
          <div v-else-if="activeTab === 'langgraph'" class="space-y-4">
            <!-- Trace selector -->
            <div v-if="profile.langGraphTraces.length > 1" class="flex gap-2 flex-wrap">
              <button
                v-for="(trace, idx) in profile.langGraphTraces"
                :key="trace.runId"
                :class="[
                  'px-3 py-1.5 rounded text-xs font-mono border transition-colors',
                  selectedTrace === idx
                    ? 'bg-qtown-accent/20 border-qtown-accent text-qtown-accent'
                    : 'border-qtown-border text-qtown-text-dim hover:border-qtown-text-dim',
                ]"
                @click="selectedTrace = idx"
              >
                T{{ trace.tick }} · {{ formatDuration(trace.totalDurationMs) }}
              </button>
            </div>

            <div v-if="currentTrace">
              <div class="flex items-center gap-4 text-xs text-qtown-text-dim mb-4">
                <span class="font-mono">Run: {{ currentTrace.runId }}</span>
                <span>Total: <span class="text-qtown-gold">{{ formatDuration(currentTrace.totalDurationMs) }}</span></span>
                <span>Tick: {{ currentTrace.tick }}</span>
                <span>{{ new Date(currentTrace.timestamp).toLocaleString() }}</span>
              </div>

              <!-- Node trace -->
              <div class="space-y-2">
                <div
                  v-for="(node, nIdx) in currentTrace.nodes"
                  :key="node.nodeId"
                  class="border border-qtown-border rounded-lg overflow-hidden"
                >
                  <div class="px-3 py-2 bg-qtown-border/20 flex items-center gap-3">
                    <span class="w-5 h-5 rounded-full bg-qtown-gold/10 text-qtown-gold text-xs font-mono flex items-center justify-center shrink-0">
                      {{ nIdx + 1 }}
                    </span>
                    <span class="text-sm font-mono font-medium text-qtown-text-primary">{{ node.nodeId }}</span>
                    <span class="ml-auto text-xs font-mono text-qtown-text-dim">{{ formatDuration(node.durationMs) }}</span>
                  </div>
                  <div class="p-3 space-y-2">
                    <div>
                      <span class="section-title">Decision</span>
                      <p class="text-sm text-qtown-gold mt-0.5">{{ node.decision }}</p>
                    </div>
                    <div>
                      <span class="section-title">Reasoning</span>
                      <p class="text-sm text-qtown-text-secondary mt-0.5">{{ truncateText(node.reasoning, 250) }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <p v-if="profile.langGraphTraces.length === 0" class="text-qtown-text-dim text-sm text-center py-8">
              No LangGraph traces available
            </p>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
