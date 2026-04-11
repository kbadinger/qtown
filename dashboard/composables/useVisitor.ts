// Visitor mode composable — public read-only + feature requests

export interface FeatureRequest {
  id?: string
  title: string
  description: string
  category: 'economy' | 'social' | 'infrastructure' | 'combat' | 'exploration'
  priority: 'low' | 'medium' | 'high'
  questId?: string
  assignedNpc?: string
  status?: 'pending' | 'in_progress' | 'completed'
  progress?: number
  createdAt?: string
}

export interface SubmitResult {
  questId: string
  assignedNpc: string
  requestId: string
}

export interface RequestStatus {
  status: 'pending' | 'in_progress' | 'completed'
  progress: number
  assignedNpc: string
}

export function useVisitor() {
  const isSubmitting = ref(false)
  const isLoading = ref(false)
  const lastError = ref<string | null>(null)

  async function submitFeatureRequest(request: FeatureRequest): Promise<SubmitResult | null> {
    isSubmitting.value = true
    lastError.value = null
    try {
      const result = await $fetch<SubmitResult>('/api/visitor/submit', {
        method: 'POST',
        body: request,
      })
      return result
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to submit feature request'
      lastError.value = message
      console.error('[useVisitor] submit error:', message)
      return null
    } finally {
      isSubmitting.value = false
    }
  }

  async function getRecentRequests(limit = 10): Promise<FeatureRequest[]> {
    isLoading.value = true
    lastError.value = null
    try {
      const result = await $fetch<{ requests: FeatureRequest[] }>(`/api/visitor/requests?limit=${limit}`)
      return result.requests ?? []
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch requests'
      lastError.value = message
      console.error('[useVisitor] fetch error:', message)
      return []
    } finally {
      isLoading.value = false
    }
  }

  async function getRequestStatus(questId: string): Promise<RequestStatus | null> {
    try {
      const result = await $fetch<RequestStatus>(`/api/visitor/requests/${questId}/status`)
      return result
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch status'
      lastError.value = message
      return null
    }
  }

  return {
    isSubmitting: readonly(isSubmitting),
    isLoading: readonly(isLoading),
    lastError: readonly(lastError),
    submitFeatureRequest,
    getRecentRequests,
    getRequestStatus,
  }
}
