<script setup lang="ts">
definePageMeta({ layout: 'docs' })
useHead({ title: 'Architecture' })

interface PatternRow {
  pattern: string
  protocol: string
  usedBy: string
  characteristics: string
}

const patterns: PatternRow[] = [
  {
    pattern: 'Synchronous RPC',
    protocol: 'gRPC / HTTP/2',
    usedBy: 'town-core → market-district, town-core → fortress, cartographer → all',
    characteristics: 'Typed Protobuf contracts, bidirectional streaming, request/response',
  },
  {
    pattern: 'Async event streaming',
    protocol: 'Apache Kafka',
    usedBy: 'All services produce/consume domain events',
    characteristics: 'At-least-once delivery, topic partitioning, consumer groups, replay',
  },
  {
    pattern: 'Presence & cache',
    protocol: 'Redis Pub/Sub + GET/SET',
    usedBy: 'tavern ↔ dashboard, NPC position caching',
    characteristics: 'Sub-millisecond read, ephemeral, fan-out to WebSocket connections',
  },
  {
    pattern: 'Client-facing API',
    protocol: 'GraphQL over HTTP',
    usedBy: 'dashboard → cartographer',
    characteristics: 'Schema-typed queries, subscriptions, N+1 batching via DataLoader',
  },
  {
    pattern: 'Long-polling / streaming',
    protocol: 'WebSocket',
    usedBy: 'dashboard → tavern',
    characteristics: 'Real-time NPC events, tick heartbeats, market feed',
  },
]

interface KafkaTopic {
  topic: string
  producer: string
  consumers: string
  schema: string
}

const kafkaTopics: KafkaTopic[] = [
  { topic: 'tick.completed', producer: 'town-core', consumers: 'market-district, fortress, academy, tavern, library', schema: '{ tick, timestamp, population, totalGold }' },
  { topic: 'npc.action', producer: 'town-core', consumers: 'fortress, academy, library, asset-pipeline', schema: '{ npcId, action, params, tick }' },
  { topic: 'npc.travel', producer: 'town-core', consumers: 'tavern, library, cartographer', schema: '{ npcId, from, to, path[], eta_ticks }' },
  { topic: 'market.trade', producer: 'market-district', consumers: 'town-core, library, tavern', schema: '{ buyerId, sellerId, resource, qty, price, tick }' },
  { topic: 'market.order', producer: 'market-district', consumers: 'tavern, library', schema: '{ orderId, npcId, side, resource, qty, price }' },
  { topic: 'validation.rejected', producer: 'fortress', consumers: 'town-core, library', schema: '{ eventId, reason, entityId, tick }' },
  { topic: 'newspaper.published', producer: 'town-core', consumers: 'tavern, library, asset-pipeline', schema: '{ dayNumber, headline, body, model }' },
  { topic: 'academy.generation', producer: 'academy', consumers: 'library, town-core', schema: '{ generationId, model, purpose, tokens, costUsd, latencyMs }' },
  { topic: 'tournament.started', producer: 'market-district', consumers: 'tavern, dashboard', schema: '{ tournamentId, name, participants[], rules }' },
  { topic: 'tournament.tick', producer: 'market-district', consumers: 'tavern, dashboard', schema: '{ tournamentId, tick, standings[] }' },
  { topic: 'tournament.ended', producer: 'market-district', consumers: 'tavern, library, dashboard', schema: '{ tournamentId, winnerId, result }' },
]
</script>

<template>
  <div class="animate-fade-in">
    <h1 class="text-3xl font-bold text-qtown-text-primary mb-3">Architecture</h1>
    <p class="text-qtown-text-secondary text-base mb-10 leading-relaxed">
      Deep dive into Qtown's service topology, communication protocols, and data flow.
    </p>

    <!-- Service Topology -->
    <section class="mb-12">
      <h2 class="text-xl font-semibold text-qtown-text-primary mb-5">Service Topology — All 9 Services</h2>
      <div class="bg-qtown-card border border-qtown-border rounded-lg p-6 overflow-x-auto">
        <svg viewBox="0 0 800 480" class="w-full" style="min-width:640px" aria-label="Full Qtown service topology">
          <defs>
            <marker id="arrow-green" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" fill="#40916c" />
            </marker>
            <marker id="arrow-gold" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" fill="#f5a623" />
            </marker>
            <marker id="arrow-red" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" fill="#e94560" />
            </marker>
            <marker id="arrow-blue" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" fill="#60a5fa" />
            </marker>
          </defs>

          <rect width="800" height="480" fill="#0d0d1a" rx="8" />

          <!-- Layer labels -->
          <text x="16" y="90" fill="#475569" font-size="9" font-family="monospace" transform="rotate(-90,16,90)">EXTERNAL</text>
          <text x="16" y="210" fill="#475569" font-size="9" font-family="monospace" transform="rotate(-90,16,210)">GATEWAY</text>
          <text x="16" y="330" fill="#475569" font-size="9" font-family="monospace" transform="rotate(-90,16,330)">CORE</text>
          <text x="16" y="450" fill="#475569" font-size="9" font-family="monospace" transform="rotate(-90,16,450)">INFRA</text>

          <!-- Layer bands -->
          <rect x="30" y="20" width="750" height="100" fill="#1a1a2e" rx="4" opacity="0.4" />
          <rect x="30" y="135" width="750" height="90" fill="#16213e" rx="4" opacity="0.4" />
          <rect x="30" y="240" width="750" height="130" fill="#1a1a2e" rx="4" opacity="0.4" />
          <rect x="30" y="385" width="750" height="80" fill="#16213e" rx="4" opacity="0.4" />

          <!-- Dashboard (external) -->
          <rect x="300" y="30" width="110" height="50" fill="#1e3a2f" rx="6" stroke="#40916c" stroke-width="1.5" />
          <text x="355" y="52" text-anchor="middle" fill="#40916c" font-size="10" font-family="monospace" font-weight="bold">dashboard</text>
          <text x="355" y="66" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">Nuxt 3 / Vue</text>

          <!-- Visitor (external) -->
          <rect x="450" y="30" width="100" height="50" fill="#1e3a2f" rx="6" stroke="#40916c" stroke-width="1.5" />
          <text x="500" y="52" text-anchor="middle" fill="#40916c" font-size="10" font-family="monospace" font-weight="bold">visitor</text>
          <text x="500" y="66" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">public UI</text>

          <!-- cartographer (gateway) -->
          <rect x="130" y="145" width="120" height="60" fill="#16213e" rx="6" stroke="#60a5fa" stroke-width="1.5" />
          <text x="190" y="170" text-anchor="middle" fill="#60a5fa" font-size="10" font-family="monospace" font-weight="bold">cartographer</text>
          <text x="190" y="183" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">GraphQL gateway</text>
          <text x="190" y="196" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">Node.js / Apollo</text>

          <!-- tavern (gateway) -->
          <rect x="290" y="145" width="110" height="60" fill="#16213e" rx="6" stroke="#f5a623" stroke-width="1.5" />
          <text x="345" y="170" text-anchor="middle" fill="#f5a623" font-size="10" font-family="monospace" font-weight="bold">tavern</text>
          <text x="345" y="183" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">WebSocket hub</text>
          <text x="345" y="196" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">Node.js / Redis</text>

          <!-- town-core -->
          <rect x="60" y="252" width="120" height="65" fill="#16213e" rx="6" stroke="#2d6a4f" stroke-width="1.5" />
          <text x="120" y="278" text-anchor="middle" fill="#40916c" font-size="10" font-family="monospace" font-weight="bold">town-core</text>
          <text x="120" y="291" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">Simulation engine</text>
          <text x="120" y="304" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">Python / asyncio</text>

          <!-- market-district -->
          <rect x="210" y="252" width="130" height="65" fill="#16213e" rx="6" stroke="#2a2a4a" stroke-width="1.5" />
          <text x="275" y="278" text-anchor="middle" fill="#a8b2c1" font-size="10" font-family="monospace" font-weight="bold">market-district</text>
          <text x="275" y="291" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">Order book</text>
          <text x="275" y="304" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">Go / gRPC</text>

          <!-- fortress -->
          <rect x="365" y="252" width="100" height="65" fill="#16213e" rx="6" stroke="#c1121f" stroke-width="1.5" />
          <text x="415" y="278" text-anchor="middle" fill="#e94560" font-size="10" font-family="monospace" font-weight="bold">fortress</text>
          <text x="415" y="291" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">Validation</text>
          <text x="415" y="304" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">Go / gRPC</text>

          <!-- academy -->
          <rect x="490" y="252" width="100" height="65" fill="#16213e" rx="6" stroke="#4a4e69" stroke-width="1.5" />
          <text x="540" y="278" text-anchor="middle" fill="#9a8c98" font-size="10" font-family="monospace" font-weight="bold">academy</text>
          <text x="540" y="291" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">LLM gateway</text>
          <text x="540" y="304" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">Python / gRPC</text>

          <!-- library -->
          <rect x="615" y="252" width="100" height="65" fill="#16213e" rx="6" stroke="#2a2a4a" stroke-width="1.5" />
          <text x="665" y="278" text-anchor="middle" fill="#a8b2c1" font-size="10" font-family="monospace" font-weight="bold">library</text>
          <text x="665" y="291" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">Search + archive</text>
          <text x="665" y="304" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">Python / PG</text>

          <!-- Kafka -->
          <rect x="60" y="393" width="480" height="55" fill="#1e2a1e" rx="6" stroke="#f5a623" stroke-width="1.5" />
          <text x="300" y="418" text-anchor="middle" fill="#f5a623" font-size="11" font-family="monospace" font-weight="bold">Apache Kafka — Event Bus</text>
          <text x="300" y="436" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">11 topics · at-least-once · consumer groups</text>

          <!-- Redis -->
          <rect x="570" y="393" width="110" height="55" fill="#2a1e1e" rx="6" stroke="#e94560" stroke-width="1.5" />
          <text x="625" y="418" text-anchor="middle" fill="#e94560" font-size="11" font-family="monospace" font-weight="bold">Redis 7</text>
          <text x="625" y="436" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">cache + pub/sub</text>

          <!-- Connections: dashboard → cartographer -->
          <line x1="340" y1="80" x2="230" y2="145" stroke="#60a5fa" stroke-width="1.5" marker-end="url(#arrow-blue)" />
          <!-- dashboard → tavern -->
          <line x1="360" y1="80" x2="350" y2="145" stroke="#f5a623" stroke-width="1" stroke-dasharray="4,2" marker-end="url(#arrow-gold)" />
          <!-- visitor → tavern -->
          <line x1="490" y1="80" x2="400" y2="145" stroke="#f5a623" stroke-width="1" stroke-dasharray="4,2" marker-end="url(#arrow-gold)" />

          <!-- cartographer → town-core -->
          <line x1="160" y1="205" x2="130" y2="252" stroke="#60a5fa" stroke-width="1" marker-end="url(#arrow-blue)" />
          <!-- tavern → Redis -->
          <line x1="380" y1="205" x2="590" y2="393" stroke="#e94560" stroke-width="1" stroke-dasharray="3,2" marker-end="url(#arrow-red)" />

          <!-- Services → Kafka -->
          <line x1="120" y1="317" x2="150" y2="393" stroke="#f5a623" stroke-width="1" stroke-dasharray="3,2" marker-end="url(#arrow-gold)" />
          <line x1="275" y1="317" x2="260" y2="393" stroke="#f5a623" stroke-width="1" stroke-dasharray="3,2" marker-end="url(#arrow-gold)" />
          <line x1="415" y1="317" x2="350" y2="393" stroke="#f5a623" stroke-width="1" stroke-dasharray="3,2" marker-end="url(#arrow-gold)" />
          <line x1="540" y1="317" x2="430" y2="393" stroke="#f5a623" stroke-width="1" stroke-dasharray="3,2" marker-end="url(#arrow-gold)" />

          <!-- gRPC: town-core → market -->
          <line x1="180" y1="285" x2="210" y2="285" stroke="#40916c" stroke-width="1.5" marker-end="url(#arrow-green)" />
          <!-- gRPC: town-core → fortress -->
          <line x1="180" y1="295" x2="365" y2="275" stroke="#40916c" stroke-width="1.5" marker-end="url(#arrow-green)" />

          <!-- Legend -->
          <line x1="50" y1="464" x2="76" y2="464" stroke="#60a5fa" stroke-width="1.5" />
          <text x="80" y="467" fill="#475569" font-size="9" font-family="monospace">GraphQL</text>
          <line x1="130" y1="464" x2="156" y2="464" stroke="#40916c" stroke-width="1.5" />
          <text x="160" y="467" fill="#475569" font-size="9" font-family="monospace">gRPC</text>
          <line x1="200" y1="464" x2="226" y2="464" stroke="#f5a623" stroke-width="1" stroke-dasharray="3,2" />
          <text x="230" y="467" fill="#475569" font-size="9" font-family="monospace">Kafka</text>
          <line x1="270" y1="464" x2="296" y2="464" stroke="#e94560" stroke-width="1" stroke-dasharray="3,2" />
          <text x="300" y="467" fill="#475569" font-size="9" font-family="monospace">Redis pub/sub</text>
        </svg>
      </div>
    </section>

    <!-- Communication patterns -->
    <section class="mb-12">
      <h2 class="text-xl font-semibold text-qtown-text-primary mb-4">Communication Patterns</h2>
      <div class="overflow-x-auto rounded-lg border border-qtown-border">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-qtown-surface border-b border-qtown-border">
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase">Pattern</th>
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase">Protocol</th>
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase">Used By</th>
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono text-xs uppercase">Characteristics</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in patterns"
              :key="row.pattern"
              class="border-b border-qtown-border last:border-b-0 bg-qtown-card hover:bg-qtown-border/30 transition-colors"
            >
              <td class="px-4 py-3 text-qtown-text-secondary font-medium">{{ row.pattern }}</td>
              <td class="px-4 py-3 font-mono text-qtown-gold text-xs">{{ row.protocol }}</td>
              <td class="px-4 py-3 text-qtown-text-dim text-xs">{{ row.usedBy }}</td>
              <td class="px-4 py-3 text-qtown-text-dim text-xs">{{ row.characteristics }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Data Flow: Tick Processing -->
    <section class="mb-12">
      <h2 class="text-xl font-semibold text-qtown-text-primary mb-4">Data Flow: Tick Processing</h2>
      <div class="bg-qtown-card border border-qtown-border rounded-lg p-6">
        <pre class="text-xs font-mono text-qtown-text-secondary leading-relaxed overflow-x-auto">
┌─────────────────────────────────────────────────────────────────────┐
│  town-core TickEngine (every ~500ms)                                 │
│                                                                      │
│  1. INCREMENT tick counter                                           │
│  2. For each active NPC (async parallel):                            │
│     a. Load NPC state from Redis                                     │
│     b. Evaluate needs (hunger, gold, happiness, energy)              │
│     c. SELECT action via Academy (GPT-4o-mini decision)              │
│     d. VALIDATE action via Fortress gRPC call                        │
│     e. If valid → EXECUTE action:                                    │
│        - Trade: send order to market-district gRPC                   │
│        - Travel: update position, publish npc.travel → Kafka         │
│        - Study: call academy GenerateInsight gRPC                    │
│        - Rest: update energy, no external call                       │
│     f. Publish npc.action → Kafka                                    │
│  3. Aggregate world state (population, totalGold, avgHappiness)      │
│  4. Publish tick.completed → Kafka                                   │
│  5. Push world state to Redis (for dashboard WebSocket)              │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼ Kafka consumers (parallel, independent)
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│  tavern        │  │  library       │  │  asset-pipeline│
│  ─────────     │  │  ──────        │  │  ─────────     │
│  Broadcast to  │  │  Archive events│  │  Generate      │
│  WebSocket     │  │  in Postgres   │  │  newspaper     │
│  clients via   │  │  Build search  │  │  images every  │
│  Redis pub/sub │  │  index         │  │  N days        │
└────────────────┘  └────────────────┘  └────────────────┘</pre>
      </div>
    </section>

    <!-- NPC Travel Protocol -->
    <section class="mb-12">
      <h2 class="text-xl font-semibold text-qtown-text-primary mb-4">NPC Travel Protocol</h2>
      <div class="bg-qtown-card border border-qtown-border rounded-lg p-6">
        <pre class="text-xs font-mono text-qtown-text-secondary leading-relaxed overflow-x-auto">
Sequence: NPC travels from Marketplace → Academy

NPC       town-core     Fortress(gRPC)  market-dist   Kafka         tavern        Dashboard
 │            │               │              │           │              │              │
 │──decide──►│               │              │           │              │              │
 │            │──ValidateAct─►│              │           │              │              │
 │            │◄──{valid}─────│              │           │              │              │
 │            │──PlaceOrder──────────────────►|           │              │              │
 │            │◄──{orderId}──────────────────|           │              │              │
 │            │                              │           │              │              │
 │            │──publish npc.travel──────────────────────►│              │              │
 │            │                              │           │──consume─────►│              │
 │            │                              │           │              │──broadcast──►│
 │            │                              │           │              │  (WebSocket)  │
 │            │  [every tick: update x,y]    │           │              │              │
 │            │──publish npc.action──────────────────────►│              │              │
 │            │                              │           │──consume─────►│              │
 │            │                              │           │              │──position   ─►│
 │            │  [on arrival at Academy]     │           │              │  update       │
 │            │──publish npc.action{study}───────────────►│              │              │
 │            │──GenerateInsight(gRPC)───────────────────────────────────────────────   │
 │            │  (academy service)                                                       │</pre>
      </div>
    </section>

    <!-- Kafka Topics Table -->
    <section class="mb-12">
      <h2 class="text-xl font-semibold text-qtown-text-primary mb-4">Kafka Topics</h2>
      <div class="overflow-x-auto rounded-lg border border-qtown-border">
        <table class="w-full text-xs">
          <thead>
            <tr class="bg-qtown-surface border-b border-qtown-border">
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono uppercase tracking-wider">Topic</th>
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono uppercase tracking-wider">Producer</th>
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono uppercase tracking-wider">Consumers</th>
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono uppercase tracking-wider">Schema</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="topic in kafkaTopics"
              :key="topic.topic"
              class="border-b border-qtown-border last:border-b-0 bg-qtown-card hover:bg-qtown-border/30 transition-colors"
            >
              <td class="px-4 py-2.5 font-mono text-qtown-gold">{{ topic.topic }}</td>
              <td class="px-4 py-2.5 text-qtown-text-secondary">{{ topic.producer }}</td>
              <td class="px-4 py-2.5 text-qtown-text-dim">{{ topic.consumers }}</td>
              <td class="px-4 py-2.5 font-mono text-qtown-text-dim text-xs">{{ topic.schema }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
