import { defineStore } from 'pinia'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface Building {
  id: string
  type: string
  name: string
  x: number
  y: number
  level: number
  ownerId: string | null
}

export interface NpcSummary {
  id: string
  name: string
  role: string
  gold: number
  happiness: number
  hunger: number
  energy: number
  neighborhood: string
  status: 'active' | 'traveling' | 'sleeping' | 'idle'
  x: number
  y: number
}

export interface WeatherState {
  condition: 'clear' | 'cloudy' | 'rain' | 'storm' | 'snow' | 'fog'
  temperature: number
  windSpeed: number
}

export interface EconomySnapshot {
  tick: number
  goldSupply: number
  totalTransactions: number
  timestamp: string
}

export interface PopulationSnapshot {
  tick: number
  count: number
  births: number
  deaths: number
  timestamp: string
}

export interface WorldState {
  tick: number
  dayNumber: number
  timeOfDay: number // 0-1 representing position in day cycle
  isNight: boolean
  population: number
  totalGold: number
  averageHappiness: number
  activeNpcs: number
  weather: WeatherState
  buildings: Building[]
  npcs: NpcSummary[]
  economyHistory: EconomySnapshot[]
  populationHistory: PopulationSnapshot[]
}

export interface TownEvent {
  id: string
  tick: number
  type: string
  description: string
  entityId: string | null
  entityType: string | null
  metadata: Record<string, unknown>
  timestamp: string
}

// ─── Initial State ────────────────────────────────────────────────────────────

function createInitialState(): WorldState {
  return {
    tick: 0,
    dayNumber: 1,
    timeOfDay: 0.5,
    isNight: false,
    population: 0,
    totalGold: 0,
    averageHappiness: 50,
    activeNpcs: 0,
    weather: {
      condition: 'clear',
      temperature: 20,
      windSpeed: 5,
    },
    buildings: [],
    npcs: [],
    economyHistory: [],
    populationHistory: [],
  }
}

// ─── Store ────────────────────────────────────────────────────────────────────

export const useTownState = defineStore('townState', () => {
  const worldState = ref<WorldState>(createInitialState())
  const recentEvents = ref<TownEvent[]>([])
  const isLoading = ref(false)
  const lastFetchError = ref<string | null>(null)
  const lastUpdated = ref<Date | null>(null)

  // ─── Getters ───────────────────────────────────────────────────────────────

  const npcById = computed(() => {
    return (id: string): NpcSummary | undefined =>
      worldState.value.npcs.find((npc) => npc.id === id)
  })

  const activeNpcList = computed(() =>
    worldState.value.npcs.filter((npc) => npc.status === 'active')
  )

  const buildingsByType = computed(() => {
    const map = new Map<string, Building[]>()
    for (const building of worldState.value.buildings) {
      const list = map.get(building.type) ?? []
      list.push(building)
      map.set(building.type, list)
    }
    return map
  })

  const dayNightLabel = computed(() => {
    const t = worldState.value.timeOfDay
    if (t < 0.25) return 'Dawn'
    if (t < 0.5) return 'Morning'
    if (t < 0.75) return 'Afternoon'
    if (t < 0.9) return 'Dusk'
    return 'Night'
  })

  // ─── Actions ───────────────────────────────────────────────────────────────

  async function fetchState(): Promise<void> {
    isLoading.value = true
    lastFetchError.value = null

    try {
      const data = await $fetch<WorldState>('/api/town-state')
      worldState.value = data
      lastUpdated.value = new Date()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch town state'
      lastFetchError.value = message
      console.error('[useTownState] fetchState error:', message)
    } finally {
      isLoading.value = false
    }
  }

  function updateFromEvent(event: TownEvent): void {
    // Add to recent events (keep last 200)
    recentEvents.value.unshift(event)
    if (recentEvents.value.length > 200) {
      recentEvents.value = recentEvents.value.slice(0, 200)
    }

    // Update tick
    if (event.tick > worldState.value.tick) {
      worldState.value.tick = event.tick
    }

    // Handle specific event types
    switch (event.type) {
      case 'npc.moved': {
        const npc = worldState.value.npcs.find((n) => n.id === event.entityId)
        if (npc && event.metadata.x !== undefined && event.metadata.y !== undefined) {
          npc.x = event.metadata.x as number
          npc.y = event.metadata.y as number
        }
        break
      }
      case 'npc.status_changed': {
        const npc = worldState.value.npcs.find((n) => n.id === event.entityId)
        if (npc && event.metadata.status) {
          npc.status = event.metadata.status as NpcSummary['status']
        }
        break
      }
      case 'economy.tick': {
        if (event.metadata.goldSupply !== undefined) {
          worldState.value.totalGold = event.metadata.goldSupply as number
          worldState.value.economyHistory.push({
            tick: event.tick,
            goldSupply: event.metadata.goldSupply as number,
            totalTransactions: (event.metadata.totalTransactions as number) ?? 0,
            timestamp: event.timestamp,
          })
          // Keep last 100 snapshots
          if (worldState.value.economyHistory.length > 100) {
            worldState.value.economyHistory = worldState.value.economyHistory.slice(-100)
          }
        }
        break
      }
      case 'world.tick': {
        if (event.metadata.timeOfDay !== undefined) {
          worldState.value.timeOfDay = event.metadata.timeOfDay as number
          worldState.value.isNight = (event.metadata.isNight as boolean) ?? false
          worldState.value.dayNumber = (event.metadata.dayNumber as number) ?? worldState.value.dayNumber
        }
        if (event.metadata.weather !== undefined) {
          worldState.value.weather = event.metadata.weather as WeatherState
        }
        break
      }
      default:
        break
    }
  }

  function setNpcs(npcs: NpcSummary[]): void {
    worldState.value.npcs = npcs
    worldState.value.activeNpcs = npcs.filter((n) => n.status === 'active').length
  }

  function reset(): void {
    worldState.value = createInitialState()
    recentEvents.value = []
    lastFetchError.value = null
    lastUpdated.value = null
  }

  return {
    // State
    worldState,
    recentEvents,
    isLoading,
    lastFetchError,
    lastUpdated,

    // Getters
    npcById,
    activeNpcList,
    buildingsByType,
    dayNightLabel,

    // Actions
    fetchState,
    updateFromEvent,
    setNpcs,
    reset,
  }
})
