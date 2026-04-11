<script setup lang="ts">
// Sidebar collapse state (shared with sidebar component via provide/inject or just local)
const sidebarCollapsed = ref(false)
</script>

<template>
  <div class="min-h-screen bg-qtown-bg text-qtown-text-primary">
    <!-- Top navigation bar -->
    <Navbar />

    <!-- Sidebar -->
    <Sidebar />

    <!-- Main content area -->
    <main
      class="pt-14 transition-all duration-300"
      :class="sidebarCollapsed ? 'pl-14' : 'pl-56'"
    >
      <!-- Inner scroll area -->
      <div class="min-h-[calc(100vh-3.5rem)] p-6">
        <slot />
      </div>
    </main>
  </div>
</template>
