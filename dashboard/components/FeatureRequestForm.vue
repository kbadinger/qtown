<script setup lang="ts">
import type { FeatureRequest, SubmitResult } from '~/composables/useVisitor'

const emit = defineEmits<{
  submitted: [result: SubmitResult]
}>()

const { submitFeatureRequest, isSubmitting, lastError } = useVisitor()

const form = ref<FeatureRequest>({
  title: '',
  description: '',
  category: 'economy',
  priority: 'medium',
})

interface ValidationErrors {
  title?: string
  description?: string
}

const errors = ref<ValidationErrors>({})
const submitted = ref<SubmitResult | null>(null)

const categories: Array<{ value: FeatureRequest['category']; label: string }> = [
  { value: 'economy', label: 'Economy' },
  { value: 'social', label: 'Social' },
  { value: 'infrastructure', label: 'Infrastructure' },
  { value: 'combat', label: 'Combat' },
  { value: 'exploration', label: 'Exploration' },
]

const priorities: Array<{ value: FeatureRequest['priority']; label: string; color: string }> = [
  { value: 'low', label: 'Low', color: 'text-green-400' },
  { value: 'medium', label: 'Medium', color: 'text-yellow-400' },
  { value: 'high', label: 'High', color: 'text-red-400' },
]

function validate(): boolean {
  const newErrors: ValidationErrors = {}

  const title = form.value.title.trim()
  if (!title) {
    newErrors.title = 'Title is required'
  } else if (title.length < 3) {
    newErrors.title = 'Title must be at least 3 characters'
  } else if (title.length > 100) {
    newErrors.title = 'Title must be 100 characters or fewer'
  }

  const description = form.value.description.trim()
  if (!description) {
    newErrors.description = 'Description is required'
  } else if (description.length < 10) {
    newErrors.description = 'Description must be at least 10 characters'
  } else if (description.length > 500) {
    newErrors.description = 'Description must be 500 characters or fewer'
  }

  errors.value = newErrors
  return Object.keys(newErrors).length === 0
}

async function handleSubmit() {
  if (!validate()) return

  const result = await submitFeatureRequest({
    ...form.value,
    title: form.value.title.trim(),
    description: form.value.description.trim(),
  })

  if (result) {
    submitted.value = result
    emit('submitted', result)
    form.value = { title: '', description: '', category: 'economy', priority: 'medium' }
    errors.value = {}
  }
}

function resetForm() {
  submitted.value = null
}
</script>

<template>
  <div class="bg-qtown-card border border-qtown-border rounded-xl p-6">
    <!-- Success state -->
    <div v-if="submitted" class="text-center py-4">
      <div class="w-12 h-12 rounded-full bg-green-500/10 border border-green-500/30 flex items-center justify-center mx-auto mb-4">
        <svg viewBox="0 0 20 20" fill="currentColor" class="w-6 h-6 text-green-400">
          <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
        </svg>
      </div>
      <h3 class="font-semibold text-qtown-text-primary text-lg mb-2">Request Submitted!</h3>
      <p class="text-qtown-text-secondary text-sm mb-4">Your feature request has been converted into an NPC quest.</p>
      <div class="bg-qtown-surface rounded-lg p-4 text-left mb-4 space-y-2">
        <div class="flex justify-between text-sm">
          <span class="text-qtown-text-dim">Quest ID</span>
          <code class="font-mono text-qtown-gold text-xs">{{ submitted.questId }}</code>
        </div>
        <div class="flex justify-between text-sm">
          <span class="text-qtown-text-dim">Assigned NPC</span>
          <span class="text-qtown-text-secondary font-medium">{{ submitted.assignedNpc }}</span>
        </div>
      </div>
      <button
        class="text-sm text-qtown-accent hover:underline"
        @click="resetForm"
      >
        Submit another request
      </button>
    </div>

    <!-- Form -->
    <form v-else @submit.prevent="handleSubmit" novalidate>
      <h3 class="font-semibold text-qtown-text-primary text-lg mb-5 flex items-center gap-2">
        <svg viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5 text-qtown-accent">
          <path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd" />
        </svg>
        Submit a Feature Request
      </h3>

      <!-- Title -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-qtown-text-secondary mb-1.5">
          Title <span class="text-qtown-accent">*</span>
        </label>
        <input
          v-model="form.title"
          type="text"
          maxlength="100"
          placeholder="e.g. Add a blacksmith NPC who can forge weapons"
          class="w-full bg-qtown-surface border rounded-lg px-4 py-2.5 text-sm text-qtown-text-primary placeholder-qtown-text-dim focus:outline-none focus:ring-1 transition-colors"
          :class="errors.title ? 'border-red-500/50 focus:ring-red-500/30' : 'border-qtown-border focus:border-qtown-accent/50 focus:ring-qtown-accent/20'"
        />
        <div v-if="errors.title" class="mt-1.5 text-xs text-red-400">{{ errors.title }}</div>
        <div class="mt-1 text-xs text-qtown-text-dim text-right">{{ form.title.length }}/100</div>
      </div>

      <!-- Description -->
      <div class="mb-4">
        <label class="block text-sm font-medium text-qtown-text-secondary mb-1.5">
          Description <span class="text-qtown-accent">*</span>
        </label>
        <textarea
          v-model="form.description"
          rows="4"
          maxlength="500"
          placeholder="Describe what you'd like to see in the town. The more specific, the better the NPC quest will be."
          class="w-full bg-qtown-surface border rounded-lg px-4 py-2.5 text-sm text-qtown-text-primary placeholder-qtown-text-dim focus:outline-none focus:ring-1 transition-colors resize-none"
          :class="errors.description ? 'border-red-500/50 focus:ring-red-500/30' : 'border-qtown-border focus:border-qtown-accent/50 focus:ring-qtown-accent/20'"
        />
        <div v-if="errors.description" class="mt-1.5 text-xs text-red-400">{{ errors.description }}</div>
        <div class="mt-1 text-xs text-qtown-text-dim text-right">{{ form.description.length }}/500</div>
      </div>

      <!-- Category + Priority row -->
      <div class="grid grid-cols-2 gap-4 mb-6">
        <div>
          <label class="block text-sm font-medium text-qtown-text-secondary mb-1.5">Category</label>
          <select
            v-model="form.category"
            class="w-full bg-qtown-surface border border-qtown-border rounded-lg px-4 py-2.5 text-sm text-qtown-text-primary focus:outline-none focus:ring-1 focus:border-qtown-accent/50 focus:ring-qtown-accent/20 transition-colors"
          >
            <option v-for="cat in categories" :key="cat.value" :value="cat.value">{{ cat.label }}</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-qtown-text-secondary mb-1.5">Priority</label>
          <select
            v-model="form.priority"
            class="w-full bg-qtown-surface border border-qtown-border rounded-lg px-4 py-2.5 text-sm text-qtown-text-primary focus:outline-none focus:ring-1 focus:border-qtown-accent/50 focus:ring-qtown-accent/20 transition-colors"
          >
            <option v-for="p in priorities" :key="p.value" :value="p.value">{{ p.label }}</option>
          </select>
        </div>
      </div>

      <!-- Error banner -->
      <div v-if="lastError" class="mb-4 bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-sm text-red-400">
        {{ lastError }}
      </div>

      <!-- Submit -->
      <button
        type="submit"
        :disabled="isSubmitting"
        class="w-full bg-qtown-accent hover:bg-qtown-accent/90 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-2.5 px-6 rounded-lg transition-colors text-sm flex items-center justify-center gap-2"
      >
        <svg v-if="isSubmitting" class="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        {{ isSubmitting ? 'Submitting...' : 'Submit Request → Create Quest' }}
      </button>
    </form>
  </div>
</template>
