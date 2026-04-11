<script setup lang="ts">
import { useApi } from '~/composables/useApi'
import type { NewspaperEdition } from '~/composables/useApi'

useHead({ title: 'Newspaper — Qtown' })

const api = useApi()
const currentEdition = ref<NewspaperEdition | null>(null)
const archive = ref<NewspaperEdition[]>([])
const selectedDayNumber = ref<number | null>(null)

onMounted(async () => {
  const [latest, arch] = await Promise.all([
    api.fetchNewspaper(),
    api.fetchNewspaperArchive(30),
  ])
  currentEdition.value = latest
  archive.value = arch
  if (latest) {
    selectedDayNumber.value = latest.dayNumber
  }
})

async function loadEdition(dayNumber: number) {
  selectedDayNumber.value = dayNumber
  currentEdition.value = await api.fetchNewspaper(dayNumber)
}

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString(undefined, {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  } catch {
    return dateStr
  }
}

const bodyParagraphs = computed<string[]>(() => {
  if (!currentEdition.value?.body) return []
  return currentEdition.value.body.split(/\n\n+/).filter(Boolean)
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div>
      <h1 class="text-2xl font-bold text-qtown-text-primary">Qtown Gazette</h1>
      <p class="text-qtown-text-secondary text-sm mt-0.5">
        AI-generated town newspaper · Updated daily
      </p>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-4 gap-6">
      <!-- Archive sidebar -->
      <div class="xl:col-span-1">
        <div class="qtown-card p-0 overflow-hidden">
          <div class="px-4 py-3 border-b border-qtown-border">
            <h2 class="section-title">Archive</h2>
          </div>
          <div class="overflow-y-auto" style="max-height: 600px">
            <div
              v-for="edition in archive"
              :key="edition.id"
              :class="[
                'px-4 py-3 border-b border-qtown-border/50 cursor-pointer transition-colors',
                selectedDayNumber === edition.dayNumber
                  ? 'bg-qtown-accent/10 border-l-2 border-l-qtown-accent'
                  : 'hover:bg-qtown-border/30',
              ]"
              @click="loadEdition(edition.dayNumber)"
            >
              <div class="text-xs font-mono text-qtown-text-dim">Day {{ edition.dayNumber }}</div>
              <div class="text-sm text-qtown-text-primary mt-0.5 line-clamp-2 leading-snug">
                {{ edition.headline }}
              </div>
              <div class="text-xs text-qtown-text-dim mt-1">
                {{ formatDate(edition.generatedAt) }}
              </div>
            </div>

            <div
              v-if="archive.length === 0"
              class="px-4 py-8 text-center text-qtown-text-dim text-sm"
            >
              No archive yet
            </div>
          </div>
        </div>
      </div>

      <!-- Newspaper display -->
      <div class="xl:col-span-3">
        <!-- Loading -->
        <div
          v-if="api.isLoading.value"
          class="qtown-card flex items-center justify-center"
          style="min-height: 400px"
        >
          <div class="text-center text-qtown-text-dim">
            <div class="flex gap-1.5 justify-center mb-3">
              <div class="w-2 h-2 rounded-full bg-qtown-gold animate-bounce" style="animation-delay: 0ms" />
              <div class="w-2 h-2 rounded-full bg-qtown-gold animate-bounce" style="animation-delay: 150ms" />
              <div class="w-2 h-2 rounded-full bg-qtown-gold animate-bounce" style="animation-delay: 300ms" />
            </div>
            <p class="text-sm">Loading edition...</p>
          </div>
        </div>

        <!-- No edition -->
        <div
          v-else-if="!currentEdition"
          class="qtown-card flex items-center justify-center"
          style="min-height: 400px"
        >
          <div class="text-center text-qtown-text-dim">
            <div class="text-4xl mb-3">📰</div>
            <p class="text-sm">No newspaper available yet</p>
            <p class="text-xs mt-1">The Gazette publishes each game day</p>
          </div>
        </div>

        <!-- Newspaper content -->
        <article v-else class="qtown-card space-y-6">
          <!-- Masthead -->
          <div class="text-center border-b-2 border-qtown-gold pb-6">
            <div class="section-title mb-1">Est. Day 1 · Qtown</div>
            <h1 class="text-3xl font-bold font-serif text-qtown-parchment tracking-wide">
              THE QTOWN GAZETTE
            </h1>
            <div class="flex items-center justify-between mt-2 text-xs text-qtown-text-dim">
              <span>Day {{ currentEdition.dayNumber }}</span>
              <span class="border-x border-qtown-border px-4">
                {{ formatDate(currentEdition.generatedAt) }}
              </span>
              <span class="font-mono text-qtown-text-dim">Model: {{ currentEdition.model }}</span>
            </div>
          </div>

          <!-- Headline -->
          <div class="border-b border-qtown-border pb-4">
            <div class="section-title mb-2">HEADLINE</div>
            <h2 class="text-xl font-bold text-qtown-text-primary leading-tight">
              {{ currentEdition.headline }}
            </h2>
          </div>

          <!-- Lead -->
          <div class="border-b border-qtown-border pb-4">
            <div class="section-title mb-2">LEAD</div>
            <p class="text-qtown-text-primary text-base leading-relaxed italic font-serif">
              {{ currentEdition.lead }}
            </p>
          </div>

          <!-- Body -->
          <div class="border-b border-qtown-border pb-4">
            <div class="section-title mb-3">TODAY'S REPORT</div>
            <div class="space-y-4">
              <p
                v-for="(para, idx) in bodyParagraphs"
                :key="idx"
                class="text-qtown-text-secondary leading-relaxed text-sm"
              >
                {{ para }}
              </p>
            </div>
          </div>

          <!-- Editorial -->
          <div class="bg-qtown-surface rounded-lg p-4 border-l-4 border-qtown-gold">
            <div class="section-title mb-2">EDITOR'S NOTE</div>
            <p class="text-qtown-text-secondary leading-relaxed text-sm italic">
              {{ currentEdition.editorial }}
            </p>
          </div>

          <!-- Footer -->
          <div class="text-center text-xs text-qtown-text-dim border-t border-qtown-border pt-4">
            <p>The Qtown Gazette is generated by artificial intelligence.</p>
            <p>All events and characters are simulated. Printed on digital parchment.</p>
          </div>
        </article>
      </div>
    </div>
  </div>
</template>
