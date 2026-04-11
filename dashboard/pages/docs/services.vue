<script setup lang="ts">
definePageMeta({ layout: 'docs' })
useHead({ title: 'Services' })

interface RPC {
  name: string
  request: string
  response: string
  description: string
}

interface ServiceDoc {
  id: string
  name: string
  purpose: string
  technology: string
  language: string
  keyFiles: string[]
  rpcs: RPC[]
  kafkaProduces: string[]
  kafkaConsumes: string[]
  proofCommand: string
  color: string
}

const services: ServiceDoc[] = [
  {
    id: 'town-core',
    name: 'town-core',
    purpose: 'The simulation engine. Runs the tick loop, orchestrates NPC decisions, manages world state (population, gold, weather, time). The authoritative source of truth for all game state.',
    technology: 'FastAPI, asyncio, SQLAlchemy, asyncpg',
    language: 'Python 3.12',
    keyFiles: [
      'engine/tick_engine.py — main simulation loop',
      'engine/npc_engine.py — NPC decision orchestration',
      'engine/world_state.py — world state management',
      'engine/sla.py — SLA monitoring',
      'api/routers/ — FastAPI route handlers',
      'models/ — SQLAlchemy ORM models',
    ],
    rpcs: [
      { name: 'GetWorldState', request: 'WorldStateRequest', response: 'WorldStateResponse', description: 'Returns current tick, population, economy snapshot' },
      { name: 'GetNpc', request: 'NpcRequest { npc_id }', response: 'NpcResponse', description: 'Full NPC profile including memory, inventory, stats' },
      { name: 'ListNpcs', request: 'NpcListRequest { filters }', response: 'NpcListResponse', description: 'Paginated NPC list with optional filters' },
      { name: 'ForceAction', request: 'ForceActionRequest { npc_id, action }', response: 'ActionResult', description: 'Debug: manually trigger an NPC action' },
    ],
    kafkaProduces: ['tick.completed', 'npc.action', 'npc.travel', 'newspaper.published'],
    kafkaConsumes: ['validation.rejected', 'market.trade', 'academy.generation'],
    proofCommand: 'curl http://localhost:8000/api/world | jq .tick',
    color: 'border-green-500/40 text-green-400',
  },
  {
    id: 'market-district',
    name: 'market-district',
    purpose: 'High-throughput order book and trading engine. Matches buy/sell orders for resources (wood, stone, food, gold). Hosts the NPC trading tournament system. Tracks price history and market statistics.',
    technology: 'Go 1.22, gRPC, Kafka producer',
    language: 'Go',
    keyFiles: [
      'internal/orderbook/book.go — core matching engine',
      'internal/orderbook/order.go — order types',
      'internal/price/tracker.go — OHLCV price history',
      'internal/tournaments/tournament.go — tournament system',
      'internal/tournaments/scheduler.go — recurring tournament scheduling',
      'proto/market.proto — gRPC service definition',
    ],
    rpcs: [
      { name: 'PlaceOrder', request: 'PlaceOrderRequest { npc_id, side, resource, qty, price }', response: 'OrderResult', description: 'Submit a limit order to the book' },
      { name: 'CancelOrder', request: 'CancelOrderRequest { order_id }', response: 'CancelResult', description: 'Cancel an open order' },
      { name: 'GetOrderBook', request: 'OrderBookRequest { resource, depth }', response: 'OrderBookResponse', description: 'Current bid/ask ladder' },
      { name: 'GetPriceHistory', request: 'PriceHistoryRequest { resource, ticks }', response: 'PriceHistoryResponse', description: 'OHLCV candles for charting' },
      { name: 'GetStandings', request: 'StandingsRequest { tournament_id }', response: 'StandingsResponse', description: 'Live tournament leaderboard' },
    ],
    kafkaProduces: ['market.trade', 'market.order', 'tournament.started', 'tournament.tick', 'tournament.ended'],
    kafkaConsumes: ['tick.completed', 'npc.action'],
    proofCommand: 'grpcurl -plaintext localhost:50052 market.MarketService/GetOrderBook',
    color: 'border-qtown-stone-light/40 text-qtown-stone-light',
  },
  {
    id: 'fortress',
    name: 'fortress',
    purpose: 'Rule enforcement and validation. Every NPC action is validated before execution — checks sufficient gold, valid target, game rule compliance, anti-cheat. Maintains an immutable audit log.',
    technology: 'Go 1.22, gRPC, append-only log',
    language: 'Go',
    keyFiles: [
      'internal/validator/action_validator.go — rule set',
      'internal/validator/gold_check.go — economic validation',
      'internal/validator/position_check.go — spatial validation',
      'internal/auditlog/writer.go — immutable append-only log',
      'proto/fortress.proto — gRPC service definition',
    ],
    rpcs: [
      { name: 'ValidateAction', request: 'ValidateRequest { npc_id, action, params }', response: 'ValidationResult { valid, reason }', description: 'Synchronous action gate — called before every NPC action' },
      { name: 'GetAuditLog', request: 'AuditLogRequest { npc_id?, from_tick, to_tick }', response: 'AuditLogResponse', description: 'Query the validation audit log' },
      { name: 'GetStats', request: 'StatsRequest', response: 'StatsResponse', description: 'Rejection rates, top reasons, throughput metrics' },
    ],
    kafkaProduces: ['validation.rejected'],
    kafkaConsumes: ['npc.action'],
    proofCommand: 'grpcurl -plaintext localhost:50053 fortress.FortressService/GetStats',
    color: 'border-red-500/40 text-red-400',
  },
  {
    id: 'academy',
    name: 'academy',
    purpose: 'LLM gateway and AI model router. Serves as the single integration point for all OpenAI API calls. Routes tasks to appropriate models (GPT-4o for complex decisions, GPT-4o-mini for simple choices), tracks token spend and quality scores.',
    technology: 'Python 3.12, gRPC, OpenAI SDK, SQLAlchemy',
    language: 'Python',
    keyFiles: [
      'academy/router.py — model routing logic',
      'academy/prompts/ — prompt templates per task type',
      'academy/quality.py — response quality scoring',
      'academy/budget.py — token budget enforcement',
      'proto/academy.proto — gRPC service definition',
    ],
    rpcs: [
      { name: 'DecideAction', request: 'DecisionRequest { npc_id, context, options[] }', response: 'DecisionResponse { action, reasoning }', description: 'NPC decision-making — core AI loop' },
      { name: 'GenerateInsight', request: 'InsightRequest { topic, npc_id }', response: 'InsightResponse { content, tokens }', description: 'Generate NPC study insight or memory' },
      { name: 'GenerateNewspaper', request: 'NewspaperRequest { events[], day }', response: 'NewspaperResponse { headline, body, editorial }', description: 'Daily newspaper generation' },
      { name: 'GenerateQuest', request: 'QuestRequest { title, description, category }', response: 'QuestResponse { quest_id, npc_id, steps[] }', description: 'Convert feature request into NPC quest' },
      { name: 'GetStats', request: 'StatsRequest { from, to }', response: 'StatsResponse', description: 'Token usage, cost, latency breakdown' },
    ],
    kafkaProduces: ['academy.generation'],
    kafkaConsumes: ['tick.completed'],
    proofCommand: 'grpcurl -plaintext localhost:50054 academy.AcademyService/GetStats',
    color: 'border-purple-400/40 text-purple-400',
  },
  {
    id: 'tavern',
    name: 'tavern',
    purpose: 'Real-time event hub. Consumes Kafka events and fans them out to connected WebSocket clients (the dashboard) via Redis Pub/Sub. Handles connection management, message filtering per client subscription.',
    technology: 'Node.js 22, ws, ioredis, kafkajs',
    language: 'TypeScript',
    keyFiles: [
      'src/server.ts — WebSocket server setup',
      'src/kafka/consumer.ts — Kafka topic consumers',
      'src/redis/publisher.ts — Redis pub/sub bridge',
      'src/channels.ts — channel subscription logic',
    ],
    rpcs: [],
    kafkaProduces: [],
    kafkaConsumes: ['tick.completed', 'npc.action', 'npc.travel', 'market.trade', 'tournament.tick', 'newspaper.published'],
    proofCommand: 'wscat -c ws://localhost:3001 -x \'{"type":"subscribe","channel":"metrics"}\'',
    color: 'border-yellow-400/40 text-yellow-400',
  },
  {
    id: 'cartographer',
    name: 'cartographer',
    purpose: 'GraphQL API gateway. Federates queries across town-core, market-district, fortress, and academy via gRPC calls. Provides DataLoader batching, subscriptions, and the unified schema used by the dashboard.',
    technology: 'Node.js 22, Apollo Server 4, GraphQL',
    language: 'TypeScript',
    keyFiles: [
      'src/schema/ — GraphQL type definitions',
      'src/resolvers/ — query/mutation resolvers',
      'src/loaders/ — DataLoader batching',
      'src/clients/ — gRPC client wrappers',
    ],
    rpcs: [],
    kafkaProduces: [],
    kafkaConsumes: ['tick.completed'],
    proofCommand: 'curl -X POST http://localhost:4000/graphql -d \'{"query":"{world{tick population}}"}\'',
    color: 'border-blue-400/40 text-blue-400',
  },
  {
    id: 'library',
    name: 'library',
    purpose: 'Historical archive and full-text search. Persists all Kafka events to PostgreSQL. Provides search over NPC history, newspaper editions, and trade records. Powers the time-travel view in the dashboard.',
    technology: 'Python 3.12, FastAPI, SQLAlchemy, PostgreSQL FTS',
    language: 'Python',
    keyFiles: [
      'library/consumers.py — Kafka consumer group',
      'library/storage.py — Postgres write path',
      'library/search.py — full-text search logic',
      'library/api.py — REST search endpoints',
    ],
    rpcs: [],
    kafkaProduces: [],
    kafkaConsumes: ['tick.completed', 'npc.action', 'market.trade', 'newspaper.published', 'tournament.ended'],
    proofCommand: 'curl "http://localhost:8004/search?q=wheat&type=trade&limit=10"',
    color: 'border-qtown-stone-light/40 text-qtown-stone-light',
  },
  {
    id: 'asset-pipeline',
    name: 'asset-pipeline',
    purpose: 'Media generation pipeline. Consumes newspaper events and generates AI illustrations (OpenAI DALL-E 3) for each edition. Also handles NPC portrait generation on first spawn.',
    technology: 'Python 3.12, OpenAI Images API, S3/MinIO',
    language: 'Python',
    keyFiles: [
      'pipeline/newspaper_art.py — newspaper illustration generation',
      'pipeline/npc_portrait.py — NPC portrait generation',
      'pipeline/storage.py — S3/MinIO upload',
    ],
    rpcs: [],
    kafkaProduces: [],
    kafkaConsumes: ['newspaper.published', 'npc.action{spawn}'],
    proofCommand: 'curl http://localhost:8005/health',
    color: 'border-qtown-stone-light/40 text-qtown-stone-light',
  },
]

const openService = ref<string | null>(null)

function toggle(id: string) {
  openService.value = openService.value === id ? null : id
}
</script>

<template>
  <div class="animate-fade-in">
    <h1 class="text-3xl font-bold text-qtown-text-primary mb-3">Services</h1>
    <p class="text-qtown-text-secondary text-base mb-8 leading-relaxed">
      Per-service reference documentation. Click a service to expand its full details.
    </p>

    <div class="space-y-2">
      <div
        v-for="svc in services"
        :key="svc.id"
        class="border rounded-lg overflow-hidden transition-all duration-200"
        :class="[svc.color, openService === svc.id ? 'bg-qtown-card' : 'bg-qtown-surface hover:bg-qtown-card']"
      >
        <!-- Header -->
        <button
          class="w-full flex items-center justify-between px-5 py-4 text-left"
          @click="toggle(svc.id)"
        >
          <div class="flex items-center gap-4">
            <span class="font-mono font-bold text-base">{{ svc.name }}</span>
            <span class="text-xs bg-qtown-bg px-2 py-0.5 rounded font-mono text-qtown-text-dim">{{ svc.language }}</span>
            <span class="text-sm text-qtown-text-dim hidden sm:block">{{ svc.purpose.slice(0, 70) }}...</span>
          </div>
          <svg
            viewBox="0 0 16 16"
            class="w-4 h-4 text-qtown-text-dim flex-shrink-0 transition-transform duration-200"
            :class="openService === svc.id ? 'rotate-180' : ''"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
          >
            <path d="M4 6l4 4 4-4" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>

        <!-- Expanded content -->
        <div v-if="openService === svc.id" class="border-t border-qtown-border px-5 py-5 space-y-6">
          <!-- Purpose -->
          <div>
            <h3 class="text-xs font-mono uppercase tracking-wider text-qtown-text-dim mb-2">Purpose</h3>
            <p class="text-qtown-text-secondary text-sm leading-relaxed">{{ svc.purpose }}</p>
          </div>

          <!-- Technology -->
          <div>
            <h3 class="text-xs font-mono uppercase tracking-wider text-qtown-text-dim mb-2">Technology</h3>
            <code class="text-sm text-qtown-gold font-mono">{{ svc.technology }}</code>
          </div>

          <!-- Key files -->
          <div>
            <h3 class="text-xs font-mono uppercase tracking-wider text-qtown-text-dim mb-2">Key Files</h3>
            <ul class="space-y-1">
              <li v-for="f in svc.keyFiles" :key="f" class="flex items-start gap-2 text-sm">
                <span class="text-qtown-accent mt-0.5 flex-shrink-0">›</span>
                <code class="text-qtown-text-secondary font-mono text-xs">{{ f }}</code>
              </li>
            </ul>
          </div>

          <!-- RPCs -->
          <div v-if="svc.rpcs.length > 0">
            <h3 class="text-xs font-mono uppercase tracking-wider text-qtown-text-dim mb-3">gRPC RPCs</h3>
            <div class="overflow-x-auto rounded border border-qtown-border">
              <table class="w-full text-xs">
                <thead>
                  <tr class="bg-qtown-surface border-b border-qtown-border">
                    <th class="text-left px-3 py-2 text-qtown-text-dim font-mono">RPC</th>
                    <th class="text-left px-3 py-2 text-qtown-text-dim font-mono">Request</th>
                    <th class="text-left px-3 py-2 text-qtown-text-dim font-mono">Response</th>
                    <th class="text-left px-3 py-2 text-qtown-text-dim font-mono">Description</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="rpc in svc.rpcs"
                    :key="rpc.name"
                    class="border-b border-qtown-border last:border-b-0 hover:bg-qtown-bg/50"
                  >
                    <td class="px-3 py-2 font-mono text-qtown-gold font-bold">{{ rpc.name }}</td>
                    <td class="px-3 py-2 font-mono text-qtown-text-dim">{{ rpc.request }}</td>
                    <td class="px-3 py-2 font-mono text-qtown-text-dim">{{ rpc.response }}</td>
                    <td class="px-3 py-2 text-qtown-text-secondary">{{ rpc.description }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Kafka -->
          <div class="grid grid-cols-2 gap-4">
            <div v-if="svc.kafkaProduces.length > 0">
              <h3 class="text-xs font-mono uppercase tracking-wider text-qtown-text-dim mb-2">Produces → Kafka</h3>
              <div class="flex flex-wrap gap-1.5">
                <span
                  v-for="t in svc.kafkaProduces"
                  :key="t"
                  class="text-xs font-mono bg-qtown-gold/10 text-qtown-gold border border-qtown-gold/20 px-2 py-0.5 rounded"
                >{{ t }}</span>
              </div>
            </div>
            <div v-if="svc.kafkaConsumes.length > 0">
              <h3 class="text-xs font-mono uppercase tracking-wider text-qtown-text-dim mb-2">Consumes ← Kafka</h3>
              <div class="flex flex-wrap gap-1.5">
                <span
                  v-for="t in svc.kafkaConsumes"
                  :key="t"
                  class="text-xs font-mono bg-qtown-border/50 text-qtown-text-secondary border border-qtown-border px-2 py-0.5 rounded"
                >{{ t }}</span>
              </div>
            </div>
          </div>

          <!-- Proof command -->
          <div>
            <h3 class="text-xs font-mono uppercase tracking-wider text-qtown-text-dim mb-2">Proof Command</h3>
            <div class="bg-qtown-bg rounded border border-qtown-border px-4 py-3">
              <code class="text-xs font-mono text-green-400">$ {{ svc.proofCommand }}</code>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
