// SSR-safe WebSocket composable
// On the server side, all operations are no-ops.

export type WsStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

export interface WsMessage {
  channel: string
  type: string
  payload: unknown
  timestamp: string
}

type MessageHandler = (message: WsMessage) => void

interface UseWebSocketOptions {
  url?: string
  autoConnect?: boolean
  reconnectDelay?: number
  maxReconnectDelay?: number
  maxReconnectAttempts?: number
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const config = useRuntimeConfig()

  const wsUrl = options.url ?? (config.public.tavernWsUrl as string)
  const maxReconnectDelay = options.maxReconnectDelay ?? 30_000
  const maxReconnectAttempts = options.maxReconnectAttempts ?? 10

  // ─── State ──────────────────────────────────────────────────────────────────
  const status = ref<WsStatus>('disconnected')
  const lastError = ref<string | null>(null)
  const reconnectAttempts = ref(0)

  // Internal refs (not reactive, just internal tracking)
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let currentReconnectDelay = options.reconnectDelay ?? 1000
  const subscribers = new Map<string, Set<MessageHandler>>()
  const globalHandlers = new Set<MessageHandler>()

  // ─── Helpers ────────────────────────────────────────────────────────────────

  function getExponentialDelay(attempt: number): number {
    const base = options.reconnectDelay ?? 1000
    return Math.min(base * Math.pow(2, attempt), maxReconnectDelay)
  }

  function clearReconnectTimer(): void {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  // ─── Core ────────────────────────────────────────────────────────────────────

  function connect(): void {
    if (import.meta.server) return
    if (ws?.readyState === WebSocket.OPEN) return
    if (ws?.readyState === WebSocket.CONNECTING) return

    status.value = 'connecting'
    lastError.value = null

    try {
      ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        status.value = 'connected'
        reconnectAttempts.value = 0
        currentReconnectDelay = options.reconnectDelay ?? 1000
        clearReconnectTimer()
      }

      ws.onmessage = (event: MessageEvent) => {
        let message: WsMessage
        try {
          message = JSON.parse(event.data as string) as WsMessage
        } catch {
          return
        }

        // Dispatch to channel subscribers
        const channelHandlers = subscribers.get(message.channel)
        if (channelHandlers) {
          for (const handler of channelHandlers) {
            handler(message)
          }
        }

        // Dispatch to global handlers
        for (const handler of globalHandlers) {
          handler(message)
        }
      }

      ws.onerror = () => {
        status.value = 'error'
        lastError.value = 'WebSocket connection error'
      }

      ws.onclose = (event: CloseEvent) => {
        ws = null
        if (event.wasClean) {
          status.value = 'disconnected'
          return
        }

        status.value = 'disconnected'

        if (reconnectAttempts.value < maxReconnectAttempts) {
          reconnectAttempts.value++
          currentReconnectDelay = getExponentialDelay(reconnectAttempts.value)
          reconnectTimer = setTimeout(() => {
            connect()
          }, currentReconnectDelay)
        } else {
          status.value = 'error'
          lastError.value = `Max reconnect attempts (${maxReconnectAttempts}) reached`
        }
      }
    } catch (err) {
      status.value = 'error'
      lastError.value = err instanceof Error ? err.message : 'Failed to create WebSocket'
    }
  }

  function disconnect(): void {
    if (import.meta.server) return
    clearReconnectTimer()
    reconnectAttempts.value = 0
    if (ws) {
      ws.close(1000, 'Client disconnecting')
      ws = null
    }
    status.value = 'disconnected'
  }

  function send(data: unknown): boolean {
    if (import.meta.server) return false
    if (!ws || ws.readyState !== WebSocket.OPEN) return false
    try {
      ws.send(JSON.stringify(data))
      return true
    } catch {
      return false
    }
  }

  function subscribe(channel: string, handler: MessageHandler): () => void {
    if (!subscribers.has(channel)) {
      subscribers.set(channel, new Set())
    }
    subscribers.get(channel)!.add(handler)

    // Send subscription message to server
    send({ type: 'subscribe', channel })

    // Return unsubscribe function
    return () => unsubscribe(channel, handler)
  }

  function unsubscribe(channel: string, handler?: MessageHandler): void {
    if (handler) {
      subscribers.get(channel)?.delete(handler)
      if (subscribers.get(channel)?.size === 0) {
        subscribers.delete(channel)
        send({ type: 'unsubscribe', channel })
      }
    } else {
      subscribers.delete(channel)
      send({ type: 'unsubscribe', channel })
    }
  }

  function onMessage(handler: MessageHandler): () => void {
    globalHandlers.add(handler)
    return () => globalHandlers.delete(handler)
  }

  // ─── Lifecycle ───────────────────────────────────────────────────────────────

  onMounted(() => {
    if (options.autoConnect !== false) {
      connect()
    }
  })

  onUnmounted(() => {
    disconnect()
    subscribers.clear()
    globalHandlers.clear()
  })

  return {
    status: readonly(status),
    lastError: readonly(lastError),
    reconnectAttempts: readonly(reconnectAttempts),
    connect,
    disconnect,
    send,
    subscribe,
    unsubscribe,
    onMessage,
    isConnected: computed(() => status.value === 'connected'),
    isConnecting: computed(() => status.value === 'connecting'),
  }
}
