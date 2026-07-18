<script setup lang="ts">
// Tavern teaching layer (DoD "Explained"): how the real-time gateway works, tied
// to the real code — and an honest cross-link for WHERE the grounding lives.
// Tavern is the delivery gateway; the "why this NPC said this" (memory, context,
// cited sources) lives upstream in Academy + town-core, not in tavern. Native
// <details> for accessible, JS-free disclosure.

interface Explainer {
  q: string
  body: string
  ref: string
}

const flow = [
  { label: 'Kafka', sub: 'town events' },
  { label: 'consumer', sub: 'route' },
  { label: 'Redis', sub: 'pub/sub' },
  { label: 'WS channel', sub: 'fan-out' },
  { label: 'browser', sub: 'subscribe' },
]

const explainers: Explainer[] = [
  {
    q: 'Kafka topics → WebSocket channels',
    body:
      'The gateway consumes six town topics (events, trade.settled, price.update, ' +
      'ai.content.generated, and the two travel topics) and routes each to a WebSocket ' +
      'channel — events, market, content, or a per-NPC npc:{id}. Consuming is done off ' +
      'the tick’s critical path; a slow browser never slows the town.',
    ref: 'services/tavern/src/kafka-consumer.ts',
  },
  {
    q: 'Redis pub/sub — the single, multi-instance fan-out path',
    body:
      'A handler publishes the event to Redis; a dedicated Redis subscriber forwards it ' +
      'to the WebSocket layer. That one path is what lets many tavern instances share ' +
      'clients — any instance’s event reaches every instance’s subscribers. It is the ' +
      'ONLY fan-out path: broadcasting directly as well would double-deliver, since the ' +
      'subscriber echoes this process’s own publishes back.',
    ref: 'services/tavern/src/redis-pubsub.ts · server.ts',
  },
  {
    q: 'Channel-scoped WebSocket delivery',
    body:
      'Clients connect once and subscribe to the channels they want; an event is sent ' +
      'only to that channel’s subscribers, in a { channel, type, payload } envelope. A ' +
      '30-second ping/pong heartbeat reaps dead connections. Disallowed channels and ' +
      'unknown verbs are rejected.',
    ref: 'services/tavern/src/websocket.ts',
  },
  {
    q: 'Where the grounding lives (why this NPC said this)',
    body:
      'Tavern is the delivery gateway — it does not generate or ground dialogue. The ' +
      '“why”: town-core builds each conversation’s context from its own state (the pair’s ' +
      'mood, recent events), and Academy answers only from retrieved, cited sources. The ' +
      'content event carries that lineage (participants, tone, model) so the panel can ' +
      'attribute it honestly, rather than tavern claiming a memory it doesn’t own.',
    ref: 'services/academy/academy/rag/answer.py · services/town-core/engine/simulation/dialogue.py',
  },
]
</script>

<template>
  <div class="qtown-card">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-base font-bold text-qtown-text-primary">How this works</h2>
      <span class="section-title">Teaching</span>
    </div>

    <!-- Flow strip: the path a town event takes to the browser -->
    <div class="flex items-stretch gap-1.5 overflow-x-auto pb-1 mb-5">
      <template v-for="(step, i) in flow" :key="step.label">
        <div class="flex-shrink-0 rounded border border-qtown-border bg-qtown-surface px-2.5 py-1.5 text-center min-w-[92px]">
          <div class="text-xs font-mono font-semibold text-qtown-text-primary">{{ step.label }}</div>
          <div class="text-[10px] text-qtown-text-dim uppercase tracking-wide mt-0.5">{{ step.sub }}</div>
        </div>
        <div v-if="i < flow.length - 1" class="flex items-center text-qtown-gold text-sm font-mono" aria-hidden="true">→</div>
      </template>
    </div>

    <!-- Explainers -->
    <div class="space-y-2">
      <details
        v-for="ex in explainers"
        :key="ex.q"
        class="group rounded border border-qtown-border bg-qtown-surface/40 open:bg-qtown-surface/70"
      >
        <summary
          class="flex items-center justify-between gap-2 cursor-pointer list-none px-3 py-2.5 text-sm font-medium text-qtown-text-primary hover:text-qtown-gold"
        >
          <span>{{ ex.q }}</span>
          <span class="text-qtown-text-dim text-xs transition-transform group-open:rotate-90" aria-hidden="true">▸</span>
        </summary>
        <div class="px-3 pb-3 -mt-0.5">
          <p class="text-sm text-qtown-text-secondary leading-relaxed">{{ ex.body }}</p>
          <p class="mt-2 text-xs font-mono text-qtown-text-dim">{{ ex.ref }}</p>
        </div>
      </details>
    </div>

    <p class="mt-4 text-xs text-qtown-text-dim">
      The WebSocket contract + the Kafka→content path are behind a green CI gate
      (<span class="font-mono">test-tavern</span>); live multi-client delivery needs
      Redis + Kafka — see the service README and docs/adr/0003-tavern-realtime-gateway.md.
    </p>
  </div>
</template>
