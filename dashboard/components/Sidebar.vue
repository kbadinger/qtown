<script setup lang="ts">
const isCollapsed = ref(false)

const navItems = [
  {
    label: 'Town View',
    href: '/',
    icon: 'town',
    description: 'Isometric town renderer',
  },
  {
    label: 'Dashboard',
    href: '/dashboard',
    icon: 'chart',
    description: 'Metrics & analytics',
  },
  {
    label: 'NPCs',
    href: '/npcs',
    icon: 'people',
    description: 'Citizens & residents',
  },
  {
    label: 'Tournaments',
    href: '/tournaments',
    icon: 'trophy',
    description: 'NPC trading competitions',
  },
  {
    label: 'SLA',
    href: '/sla',
    icon: 'sla',
    description: 'Performance budget compliance',
  },
  {
    label: 'Market',
    href: '/market',
    icon: 'market',
    description: 'Order book & trades',
  },
  {
    label: 'Newspaper',
    href: '/newspaper',
    icon: 'newspaper',
    description: 'AI-generated news',
  },
  {
    label: 'Academy',
    href: '/academy',
    icon: 'academy',
    description: 'AI model analytics',
  },
  {
    label: 'Fortress',
    href: '/fortress',
    icon: 'fortress',
    description: 'Validation & audit',
  },
  {
    label: 'Policies',
    href: '/policies',
    icon: 'policies',
    description: 'WASM policy editor',
  },
  {
    label: 'Docs',
    href: '/docs',
    icon: 'docs',
    description: 'Architecture & API reference',
  },
  {
    label: 'Visitor',
    href: '/visitor',
    icon: 'visitor',
    description: 'Public visitor mode',
  },
]

const route = useRoute()
const isActive = (href: string) => route.path === href || (href !== '/' && route.path.startsWith(href))
</script>

<template>
  <aside
    :class="[
      'fixed left-0 top-14 bottom-0 z-40 flex flex-col bg-qtown-card border-r border-qtown-border transition-all duration-300',
      isCollapsed ? 'w-14' : 'w-56',
    ]"
  >
    <!-- Toggle button -->
    <button
      class="flex items-center justify-center w-full h-10 border-b border-qtown-border text-qtown-text-dim hover:text-qtown-text-secondary hover:bg-qtown-border transition-colors"
      :aria-label="isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
      @click="isCollapsed = !isCollapsed"
    >
      <svg
        viewBox="0 0 16 16"
        class="w-4 h-4 transition-transform duration-300"
        :class="isCollapsed ? 'rotate-180' : ''"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
      >
        <path d="M10 4L6 8l4 4" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </button>

    <!-- Nav items -->
    <nav class="flex-1 overflow-y-auto py-2">
      <NuxtLink
        v-for="item in navItems"
        :key="item.href"
        :to="item.href"
        :title="isCollapsed ? item.label : undefined"
        class="flex items-center gap-3 px-3 py-2.5 mx-1 rounded transition-colors duration-150 group"
        :class="isActive(item.href)
          ? 'bg-qtown-accent/20 text-qtown-accent border border-qtown-accent/30'
          : 'text-qtown-text-secondary hover:text-qtown-text-primary hover:bg-qtown-border'"
      >
        <!-- Icon -->
        <span class="shrink-0 w-5 h-5 flex items-center justify-center">
          <!-- Town icon -->
          <svg v-if="item.icon === 'town'" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path d="M10 2L2 8v10h5v-6h6v6h5V8L10 2z" />
          </svg>
          <!-- Chart icon -->
          <svg v-else-if="item.icon === 'chart'" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path d="M2 2h2v16H2V2zm4 6h2v10H6V8zm4-3h2v13h-2V5zm4 5h2v8h-2v-8z" />
          </svg>
          <!-- People icon -->
          <svg v-else-if="item.icon === 'people'" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path d="M9 6a3 3 0 1 1-6 0 3 3 0 0 1 6 0zm8 0a3 3 0 1 1-6 0 3 3 0 0 1 6 0zM5 14c0-2.761 1.79-5 4-5s4 2.239 4 5v1H5v-1zm9.273-1C13.48 11.52 12.31 10 11 10c.24 0 .474.03.7.083C12.704 10.564 13.5 12.17 13.5 14v1H17v-1c0-.346-.025-.685-.073-1.013z" />
          </svg>
          <!-- Market icon -->
          <svg v-else-if="item.icon === 'market'" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path d="M3 3a1 1 0 000 2h1.22l.305 1.222a.997.997 0 00.01.042l1.358 5.43-.893.892C3.74 13.846 4.632 16 6.414 16H15a1 1 0 000-2H6.414l1-1H14a1 1 0 00.894-.553l3-6A1 1 0 0017 5H6.28l-.31-1.243A1 1 0 005 3H3z" />
          </svg>
          <!-- Newspaper icon -->
          <svg v-else-if="item.icon === 'newspaper'" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path fill-rule="evenodd" d="M2 5a2 2 0 012-2h8a2 2 0 012 2v10a2 2 0 002 2H4a2 2 0 01-2-2V5zm3 1h6v4H5V6zm6 6H5v2h6v-2z" clip-rule="evenodd" />
            <path d="M15 7h1a2 2 0 012 2v5.5a1.5 1.5 0 01-3 0V7z" />
          </svg>
          <!-- Academy icon -->
          <svg v-else-if="item.icon === 'academy'" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path d="M10.394 2.08a1 1 0 00-.788 0l-7 3a1 1 0 000 1.84L5.25 8.051a.999.999 0 01.356-.257l4-1.714a1 1 0 11.788 1.838L7.667 9.088l1.94.831a1 1 0 00.787 0l7-3a1 1 0 000-1.838l-7-3z" />
            <path d="M3.31 9.397L5 10.12v4.102a8.969 8.969 0 00-1.05-.174 1 1 0 01-.89-.89 11.115 11.115 0 01.25-3.762zM9.3 16.573A9.026 9.026 0 007 14.935v-3.957l1.818.78a3 3 0 002.364 0l5.508-2.361a11.026 11.026 0 01.25 3.762 1 1 0 01-.89.89 8.968 8.968 0 00-5.35 2.524 1 1 0 01-1.4 0zM6 18a1 1 0 001-1v-2.065a8.935 8.935 0 00-2-.712V17a1 1 0 001 1z" />
          </svg>
          <!-- Fortress icon -->
          <svg v-else-if="item.icon === 'fortress'" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path fill-rule="evenodd" d="M3 6a3 3 0 013-3h10a1 1 0 01.8 1.6L14.25 7l2.55 2.4A1 1 0 0116 11H6a1 1 0 00-1 1v3a1 1 0 11-2 0V6z" clip-rule="evenodd" />
          </svg>
          <!-- Trophy icon -->
          <svg v-else-if="item.icon === 'trophy'" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path fill-rule="evenodd" d="M10 2a1 1 0 011 1v1h2a1 1 0 011 1v2c0 2.21-1.79 4-4 4S6 9.21 6 7V5a1 1 0 011-1h2V3a1 1 0 011-1zm-3 3v2a3 3 0 006 0V5H7zm3 6a1 1 0 011 1v1h1a1 1 0 110 2H8a1 1 0 110-2h1v-1a1 1 0 011-1zM4 5a1 1 0 00-1 1v1a3 3 0 002 2.83V11H4a1 1 0 000 2h1a1 1 0 001-1V9.83A3 3 0 008 7V6H5V5H4zm12 0h-1v1h-3v1a3 3 0 002 2.83V11h1a1 1 0 010 2h-1a1 1 0 01-1-1V9.83A3 3 0 0015 7V6h-3V5a1 1 0 00-1-1h1a1 1 0 001 1z" clip-rule="evenodd" />
          </svg>
          <!-- SLA icon -->
          <svg v-else-if="item.icon === 'sla'" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path fill-rule="evenodd" d="M3 3a1 1 0 000 2v8a2 2 0 002 2h2.586l-1.293 1.293a1 1 0 101.414 1.414L10 15.414l2.293 2.293a1 1 0 001.414-1.414L12.414 15H15a2 2 0 002-2V5a1 1 0 100-2H3zm11 4a1 1 0 10-2 0v4a1 1 0 102 0V7zm-3 1a1 1 0 10-2 0v3a1 1 0 102 0V8zM8 9a1 1 0 00-2 0v2a1 1 0 102 0V9z" clip-rule="evenodd" />
          </svg>
          <!-- Policies icon -->
          <svg v-else-if="item.icon === 'policies'" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z" />
            <path fill-rule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z" clip-rule="evenodd" />
          </svg>
          <!-- Docs icon -->
          <svg v-else-if="item.icon === 'docs'" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z" clip-rule="evenodd" />
          </svg>
          <!-- Visitor icon -->
          <svg v-else-if="item.icon === 'visitor'" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path fill-rule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clip-rule="evenodd" />
          </svg>
        </span>

        <!-- Label -->
        <span
          v-if="!isCollapsed"
          class="text-sm font-medium truncate transition-opacity duration-200"
        >
          {{ item.label }}
        </span>
      </NuxtLink>
    </nav>

    <!-- Bottom info (only when expanded) -->
    <div
      v-if="!isCollapsed"
      class="border-t border-qtown-border px-3 py-3"
    >
      <p class="text-qtown-text-dim text-xs font-mono">Qtown v2</p>
      <p class="text-qtown-text-dim text-xs">Phase 5 Dashboard</p>
    </div>
  </aside>
</template>
