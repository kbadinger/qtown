<script setup lang="ts">
// First-class LIVE / DORMANT status pill for proof panels. `live` reflects
// whether the backing data source is reachable — dormant is an honest state
// (the area is real but its source isn't answering), never a failure to hide.
defineProps<{ live: boolean }>()
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wider"
    :class="live ? 'bg-green-500/10 text-green-400' : 'bg-gray-500/10 text-qtown-text-dim'"
  >
    <span
      class="w-1.5 h-1.5 rounded-full"
      :class="live ? 'bg-green-400 animate-pulse' : 'bg-gray-500'"
    />
    {{ live ? 'Live' : 'Dormant' }}
  </span>
</template>
