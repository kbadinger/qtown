<script setup lang="ts">
useHead({ titleTemplate: '%s — Qtown Docs' })
</script>

<template>
  <div class="min-h-screen bg-qtown-bg text-qtown-text-primary flex flex-col">
    <!-- Top bar -->
    <header class="fixed top-0 left-0 right-0 z-50 h-14 bg-qtown-card border-b border-qtown-border flex items-center px-6 gap-4">
      <NuxtLink to="/" class="flex items-center gap-2 text-qtown-gold hover:text-qtown-gold/80 transition-colors">
        <svg viewBox="0 0 24 24" fill="none" class="w-6 h-6" aria-label="Qtown">
          <path d="M12 2L3 8v12h5v-6h8v6h5V8L12 2z" fill="currentColor" opacity="0.9" />
          <path d="M9 14h6v6H9z" fill="currentColor" opacity="0.6" />
          <path d="M11 6h2v4h-2z" fill="currentColor" opacity="0.4" />
        </svg>
        <span class="font-mono text-sm font-semibold tracking-wider">QTOWN</span>
      </NuxtLink>
      <span class="text-qtown-border">|</span>
      <span class="text-qtown-text-secondary text-sm font-medium">Documentation</span>
      <div class="flex-1" />
      <a
        href="https://github.com/qtown/qtown"
        target="_blank"
        rel="noopener noreferrer"
        class="flex items-center gap-2 text-qtown-text-dim hover:text-qtown-text-secondary text-sm transition-colors"
      >
        <svg viewBox="0 0 24 24" fill="currentColor" class="w-4 h-4">
          <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
        </svg>
        Edit on GitHub
      </a>
    </header>

    <div class="flex pt-14 flex-1">
      <!-- Docs sidebar -->
      <DocsSidebar />

      <!-- Main content -->
      <main class="flex-1 pl-72 min-h-[calc(100vh-3.5rem)]">
        <div class="max-w-4xl mx-auto px-8 py-10">
          <slot />
        </div>
      </main>
    </div>
  </div>
</template>
