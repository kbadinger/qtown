<script setup lang="ts">
import { useApi } from '~/composables/useApi'
import type { NpcListItem } from '~/composables/useApi'

useHead({ title: 'NPCs — Qtown' })

const api = useApi()

// ─── State ────────────────────────────────────────────────────────────────────

const npcs = ref<NpcListItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 25

const searchQuery = ref('')
const filterRole = ref('')
const filterStatus = ref('')
const filterNeighborhood = ref('')
const sortKey = ref<keyof NpcListItem>('name')
const sortDir = ref<'asc' | 'desc'>('asc')

const roles = ['Farmer', 'Merchant', 'Scholar', 'Guard', 'Artisan', 'Innkeeper', 'Miner', 'Fisher']
const statuses = ['active', 'traveling', 'sleeping', 'idle']
const neighborhoods = ['Market District', 'Residential Quarter', 'Scholars Row', 'Harbor', 'Fortress Quarter', 'Farmlands']

// ─── Fetch ─────────────────────────────────────────────────────────────────────

async function loadNpcs() {
  const result = await api.fetchNpcs({
    page: page.value,
    pageSize,
    search: searchQuery.value || undefined,
    role: filterRole.value || undefined,
    status: filterStatus.value || undefined,
    neighborhood: filterNeighborhood.value || undefined,
  })
  if (result) {
    npcs.value = result.npcs
    total.value = result.total
  }
}

onMounted(loadNpcs)

watch([searchQuery, filterRole, filterStatus, filterNeighborhood], () => {
  page.value = 1
  loadNpcs()
})

watch(page, loadNpcs)

// ─── Sorting ──────────────────────────────────────────────────────────────────

function toggleSort(key: keyof NpcListItem) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
}

const sortedNpcs = computed(() => {
  return [...npcs.value].sort((a, b) => {
    const aVal = a[sortKey.value]
    const bVal = b[sortKey.value]
    let cmp = 0
    if (typeof aVal === 'string' && typeof bVal === 'string') {
      cmp = aVal.localeCompare(bVal)
    } else if (typeof aVal === 'number' && typeof bVal === 'number') {
      cmp = aVal - bVal
    }
    return sortDir.value === 'asc' ? cmp : -cmp
  })
})

// ─── Status styles ───────────────────────────────────────────────────────────

const statusStyle: Record<string, string> = {
  active: 'bg-green-400/10 text-green-400 border-green-400/30',
  traveling: 'bg-blue-400/10 text-blue-400 border-blue-400/30',
  sleeping: 'bg-indigo-400/10 text-indigo-400 border-indigo-400/30',
  idle: 'bg-qtown-border/50 text-qtown-text-dim border-qtown-border',
}

// ─── Pagination ───────────────────────────────────────────────────────────────

const totalPages = computed(() => Math.ceil(total.value / pageSize))

// ─── Sort indicator ───────────────────────────────────────────────────────────

function sortIndicator(key: keyof NpcListItem): string {
  if (sortKey.value !== key) return '⇅'
  return sortDir.value === 'asc' ? '↑' : '↓'
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-qtown-text-primary">NPCs</h1>
        <p class="text-qtown-text-secondary text-sm mt-0.5">
          {{ total.toLocaleString() }} citizens
        </p>
      </div>
      <button
        class="qtown-btn-ghost text-sm flex items-center gap-2"
        @click="loadNpcs"
      >
        <svg viewBox="0 0 16 16" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M14 8A6 6 0 102 8" stroke-linecap="round" />
          <path d="M14 5v3h-3" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        Refresh
      </button>
    </div>

    <!-- Filters row -->
    <div class="qtown-card flex flex-wrap gap-3">
      <!-- Search -->
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Search by name..."
        class="qtown-input text-sm flex-1 min-w-48"
      />

      <!-- Role filter -->
      <select v-model="filterRole" class="qtown-input text-sm min-w-36">
        <option value="">All Roles</option>
        <option v-for="role in roles" :key="role" :value="role">{{ role }}</option>
      </select>

      <!-- Status filter -->
      <select v-model="filterStatus" class="qtown-input text-sm min-w-36">
        <option value="">All Statuses</option>
        <option v-for="s in statuses" :key="s" :value="s" class="capitalize">{{ s }}</option>
      </select>

      <!-- Neighborhood filter -->
      <select v-model="filterNeighborhood" class="qtown-input text-sm min-w-44">
        <option value="">All Neighborhoods</option>
        <option v-for="n in neighborhoods" :key="n" :value="n">{{ n }}</option>
      </select>
    </div>

    <!-- Table -->
    <div class="qtown-card p-0 overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-qtown-border">
              <th
                v-for="col in [
                  { key: 'name', label: 'Name' },
                  { key: 'role', label: 'Role' },
                  { key: 'gold', label: 'Gold' },
                  { key: 'happiness', label: 'Happiness' },
                  { key: 'neighborhood', label: 'Neighborhood' },
                  { key: 'status', label: 'Status' },
                ]"
                :key="col.key"
                class="px-4 py-3 text-left text-qtown-text-dim font-medium section-title cursor-pointer hover:text-qtown-text-secondary select-none"
                @click="toggleSort(col.key as keyof NpcListItem)"
              >
                <span class="flex items-center gap-1">
                  {{ col.label }}
                  <span class="font-mono text-xs opacity-60">
                    {{ sortIndicator(col.key as keyof NpcListItem) }}
                  </span>
                </span>
              </th>
            </tr>
          </thead>

          <tbody>
            <tr
              v-for="npc in sortedNpcs"
              :key="npc.id"
              class="border-b border-qtown-border/50 hover:bg-qtown-border/20 cursor-pointer transition-colors"
              @click="navigateTo(`/npcs/${npc.id}`)"
            >
              <!-- Name -->
              <td class="px-4 py-3 font-medium text-qtown-text-primary">
                {{ npc.name }}
              </td>

              <!-- Role -->
              <td class="px-4 py-3 text-qtown-text-secondary">
                {{ npc.role }}
              </td>

              <!-- Gold -->
              <td class="px-4 py-3 font-mono text-qtown-gold font-semibold">
                {{ npc.gold.toLocaleString() }}
              </td>

              <!-- Happiness -->
              <td class="px-4 py-3">
                <div class="flex items-center gap-2">
                  <div class="w-16 h-1.5 bg-qtown-border rounded-full overflow-hidden">
                    <div
                      class="h-full rounded-full"
                      :class="npc.happiness >= 70 ? 'bg-green-500' : npc.happiness >= 40 ? 'bg-yellow-500' : 'bg-red-500'"
                      :style="{ width: `${npc.happiness}%` }"
                    />
                  </div>
                  <span class="font-mono text-xs text-qtown-text-secondary">{{ npc.happiness }}%</span>
                </div>
              </td>

              <!-- Neighborhood -->
              <td class="px-4 py-3 text-qtown-text-secondary text-xs">
                {{ npc.neighborhood }}
              </td>

              <!-- Status -->
              <td class="px-4 py-3">
                <span :class="['qtown-badge border capitalize', statusStyle[npc.status] ?? statusStyle['idle']]">
                  {{ npc.status }}
                </span>
              </td>
            </tr>

            <!-- Empty state -->
            <tr v-if="sortedNpcs.length === 0">
              <td colspan="6" class="px-4 py-12 text-center text-qtown-text-dim">
                <div class="text-3xl mb-2">🧑‍🤝‍🧑</div>
                <div>No NPCs found</div>
                <div class="text-xs mt-1">Try adjusting your filters</div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div
        v-if="totalPages > 1"
        class="flex items-center justify-between px-4 py-3 border-t border-qtown-border"
      >
        <span class="text-xs text-qtown-text-dim">
          Page {{ page }} of {{ totalPages }} · {{ total }} total
        </span>
        <div class="flex items-center gap-2">
          <button
            class="qtown-btn-ghost text-xs px-2 py-1 disabled:opacity-40"
            :disabled="page <= 1"
            @click="page--"
          >
            ← Prev
          </button>
          <button
            class="qtown-btn-ghost text-xs px-2 py-1 disabled:opacity-40"
            :disabled="page >= totalPages"
            @click="page++"
          >
            Next →
          </button>
        </div>
      </div>
    </div>

    <!-- Loading indicator -->
    <div v-if="api.isLoading.value" class="flex items-center gap-2 text-xs text-qtown-text-dim">
      <div class="w-1.5 h-1.5 rounded-full bg-qtown-gold animate-bounce" />
      Loading NPCs...
    </div>
  </div>
</template>
