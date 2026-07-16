<script setup lang="ts">
// Market teaching layer (DoD "Explained"): answers "how does this work" in-app,
// tied to the real code. Copy is deliberately accurate to the implementation —
// no aspirational claims. Native <details> for accessible, JS-free disclosure.

interface Explainer {
  q: string
  body: string
  ref: string
}

const flow = [
  { label: 'town-core', sub: 'originates' },
  { label: 'PlaceOrder', sub: 'gRPC' },
  { label: 'order book', sub: 'match' },
  { label: 'trade.settled ×2', sub: 'Kafka' },
  { label: 'consumer', sub: 'gold + ledger' },
]

const explainers: Explainer[] = [
  {
    q: 'Matching engine — price-time priority',
    body:
      'Orders rest in a per-resource book sorted by price, then arrival time. An incoming order ' +
      'crosses when a bid’s price meets or exceeds the best ask; the trade fills at the resting ' +
      'order’s price, and any unfilled remainder stays on the book (partial fills). Matching runs ' +
      'in-process on every PlaceOrder.',
    ref: 'services/market-district/internal/orderbook/orderbook.go',
  },
  {
    q: 'Typed gRPC contract & single-sided settlement',
    body:
      'The wire contract is generated from market.proto (buf → committed gen/, drift-gated in CI), ' +
      'so client and server can’t silently disagree. A match emits two independent ' +
      'qtown.economy.trade.settled events — one per counterparty (buyer gold_delta < 0, seller > 0) ' +
      'sharing one trade_id — so each consumer only needs its own side.',
    ref: 'proto/qtown/market.proto · docs/adr/0001',
  },
  {
    q: 'At-least-once delivery + idempotent consumers',
    body:
      'Emitting to Kafka is best-effort — a broker hiccup is logged, never fails the trade. That ' +
      'makes delivery at-least-once, so town-core dedupes on the compound key (trade_id, npc_id), ' +
      'applies the gold delta and ledger row atomically, and routes poison messages to a ' +
      '<topic>.dlq with a replay path.',
    ref: 'services/town-core/engine/kafka_consumer.py · docs/adr/0001',
  },
  {
    q: 'Reading the latency numbers',
    body:
      'Two numbers, because a PlaceOrder’s cost depends on whether it matches. Placement p99 ' +
      '(2.16 ms) is the gRPC + book-insert path. Full-spine p99 (24.7 ms) adds the synchronous 2× ' +
      'settlement emit — the producer’s 10 ms batch-timeout dominates the matched tail, not the ' +
      '2.2 µs engine. Measured locally (i9-12900K, loopback) as a reference run, not a CI-enforced ' +
      'SLO. Moving emit off the hot path (W1-M5) would collapse the tail.',
    ref: 'docs/perf/market-loadtest.md',
  },
]
</script>

<template>
  <div class="qtown-card">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-base font-bold text-qtown-text-primary">How this works</h2>
      <span class="section-title">Teaching</span>
    </div>

    <!-- Flow strip: the distributed path a trade actually takes -->
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
      Each claim above is behind a green CI gate (<span class="font-mono">test-market</span>,
      <span class="font-mono">e2e-market</span>) or a committed measurement — see the service README and ADR-0001.
    </p>
  </div>
</template>
