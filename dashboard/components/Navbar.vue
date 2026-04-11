<script setup lang="ts">
import { useWebSocket } from '~/composables/useWebSocket'
import { useTownState } from '~/composables/useTownState'

const townState = useTownState()
const { status: wsStatus } = useWebSocket({ autoConnect: false })

const wsStatusColor = computed(() => {
  switch (wsStatus.value) {
    case 'connected': return 'bg-green-500'
    case 'connecting': return 'bg-yellow-500 animate-pulse'
    case 'error': return 'bg-red-600'
    default: return 'bg-gray-500'
  }
})

const wsStatusLabel = computed(() => {
  switch (wsStatus.value) {
    case 'connected': return 'Live'
    case 'connecting': return 'Connecting...'
    case 'error': return 'Error'
    default: return 'Offline'
  }
})

const navLinks = [
  { label: 'Town', href: '/' },
  { label: 'Dashboard', href: '/dashboard' },
  { label: 'NPCs', href: '/npcs' },
  { label: 'Market', href: '/market' },
  { label: 'Newspaper', href: '/newspaper' },
  { label: 'Academy', href: '/academy' },
  { label: 'Fortress', href: '/fortress' },
]

const route = useRoute()
const isActive = (href: string) => route.path === href
</script>

<template>
  <header class="fixed top-0 left-0 right-0 z-50 h-14 bg-qtown-card border-b border-qtown-border flex items-center px-4 gap-4">
    <!-- Logo -->
    <NuxtLink to="/" class="flex items-center gap-2 shrink-0">
      <svg
        viewBox="0 0 32 32"
        class="w-8 h-8"
        aria-label="Qtown Logo"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <!-- Castle tower silhouette -->
        <rect x="4" y="12" width="24" height="16" rx="1" fill="#e94560" />
        <rect x="4" y="8" width="6" height="8" rx="1" fill="#f5a623" />
        <rect x="13" y="6" width="6" height="10" rx="1" fill="#f5a623" />
        <rect x="22" y="8" width="6" height="8" rx="1" fill="#f5a623" />
        <!-- Battlements -->
        <rect x="4" y="6" width="3" height="4" rx="0.5" fill="#f5a623" />
        <rect x="8" y="6" width="2" height="4" rx="0.5" fill="#f5a623" />
        <rect x="13" y="4" width="3" height="4" rx="0.5" fill="#e94560" />
        <rect x="17" y="4" width="2" height="4" rx="0.5" fill="#e94560" />
        <rect x="22" y="6" width="3" height="4" rx="0.5" fill="#f5a623" />
        <rect x="26" y="6" width="2" height="4" rx="0.5" fill="#f5a623" />
        <!-- Gate -->
        <rect x="13" y="20" width="6" height="8" rx="3" fill="#0d0d1a" />
        <!-- Windows -->
        <rect x="6" y="15" width="3" height="4" rx="1" fill="#0d0d1a" opacity="0.7" />
        <rect x="23" y="15" width="3" height="4" rx="1" fill="#0d0d1a" opacity="0.7" />
      </svg>
      <span class="text-qtown-gold font-bold text-lg tracking-wide font-mono">QTOWN</span>
    </NuxtLink>

    <!-- Nav links (desktop) -->
    <nav class="hidden md:flex items-center gap-1 ml-4">
      <NuxtLink
        v-for="link in navLinks"
        :key="link.href"
        :to="link.href"
        class="px-3 py-1.5 rounded text-sm transition-colors duration-150"
        :class="isActive(link.href)
          ? 'bg-qtown-accent text-white'
          : 'text-qtown-text-secondary hover:text-qtown-text-primary hover:bg-qtown-border'"
      >
        {{ link.label }}
      </NuxtLink>
    </nav>

    <div class="flex-1" />

    <!-- Tick counter -->
    <div class="hidden sm:flex items-center gap-1.5 text-xs font-mono text-qtown-text-secondary">
      <span class="text-qtown-text-dim">TICK</span>
      <span class="text-qtown-gold font-bold tabular-nums">{{ townState.worldState.tick.toLocaleString() }}</span>
    </div>

    <!-- Day indicator -->
    <div class="hidden sm:flex items-center gap-1.5 text-xs font-mono text-qtown-text-secondary">
      <span class="text-qtown-text-dim">DAY</span>
      <span class="text-qtown-text-primary font-bold">{{ townState.worldState.dayNumber }}</span>
    </div>

    <!-- WS Status -->
    <div class="flex items-center gap-1.5 text-xs">
      <span :class="['w-2 h-2 rounded-full', wsStatusColor]" />
      <span class="text-qtown-text-dim hidden sm:block">{{ wsStatusLabel }}</span>
    </div>
  </header>
</template>
