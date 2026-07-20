<script setup lang="ts">
useHead({ title: 'Tavern — Qtown' })
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-qtown-text-primary">Tavern</h1>
        <p class="text-qtown-text-secondary text-sm mt-0.5">
          Real-time social gateway · Kafka → Redis pub/sub → WebSocket
        </p>
      </div>
    </div>

    <!-- Flagship: gateway proof (W1-T) -->
    <div class="grid grid-cols-1 xl:grid-cols-2 gap-6">
      <TavernProofPanel />
      <TavernTeaching />
    </div>
  </div>
</template>
