<script setup lang="ts">
interface NavItem {
  label: string
  href: string
}
interface NavSection {
  title: string
  items: NavItem[]
  collapsible?: boolean
}

const sections: NavSection[] = [
  {
    title: 'Overview',
    items: [
      { label: 'Introduction', href: '/docs' },
      { label: 'Architecture', href: '/docs/architecture' },
    ],
  },
  {
    title: 'Reference',
    items: [
      { label: 'Services', href: '/docs/services' },
      { label: 'API', href: '/docs/api' },
    ],
  },
  {
    title: 'Development',
    items: [
      { label: 'Ralph — AI Author', href: '/docs/ralph' },
    ],
  },
]

const collapsed = ref<Record<string, boolean>>({})
const route = useRoute()

function toggle(title: string) {
  collapsed.value[title] = !collapsed.value[title]
}

function isActive(href: string) {
  return route.path === href
}
</script>

<template>
  <aside class="fixed left-0 top-14 bottom-0 w-72 bg-qtown-card border-r border-qtown-border overflow-y-auto z-40 flex flex-col">
    <!-- Logo / title area -->
    <div class="px-5 py-4 border-b border-qtown-border">
      <p class="text-qtown-text-dim text-xs font-mono uppercase tracking-widest">Qtown v2</p>
      <p class="text-qtown-text-secondary text-xs mt-0.5">Phase 5 Docs</p>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 py-4 px-3">
      <div
        v-for="section in sections"
        :key="section.title"
        class="mb-6"
      >
        <button
          class="w-full flex items-center justify-between px-2 mb-1.5 text-qtown-text-dim text-xs font-mono uppercase tracking-widest hover:text-qtown-text-secondary transition-colors"
          @click="toggle(section.title)"
        >
          {{ section.title }}
          <svg
            viewBox="0 0 16 16"
            class="w-3 h-3 transition-transform duration-200"
            :class="collapsed[section.title] ? '-rotate-90' : ''"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
          >
            <path d="M4 6l4 4 4-4" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>

        <ul v-if="!collapsed[section.title]" class="space-y-0.5">
          <li v-for="item in section.items" :key="item.href">
            <NuxtLink
              :to="item.href"
              class="flex items-center gap-2 px-3 py-2 rounded text-sm transition-colors duration-150"
              :class="isActive(item.href)
                ? 'bg-qtown-accent/15 text-qtown-accent border-l-2 border-qtown-accent pl-2.5'
                : 'text-qtown-text-secondary hover:text-qtown-text-primary hover:bg-qtown-border'"
            >
              {{ item.label }}
            </NuxtLink>
          </li>
        </ul>
      </div>
    </nav>

    <!-- Footer -->
    <div class="border-t border-qtown-border px-5 py-3">
      <p class="text-qtown-text-dim text-xs">
        Built with <span class="text-qtown-gold">♠</span> by Ralph
      </p>
    </div>
  </aside>
</template>
