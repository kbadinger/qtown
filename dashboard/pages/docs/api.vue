<script setup lang="ts">
definePageMeta({ layout: 'docs' })
useHead({ title: 'API Reference' })

type Tab = 'graphql' | 'rest' | 'grpc' | 'websocket'
const activeTab = ref<Tab>('graphql')

const tabs: { id: Tab; label: string }[] = [
  { id: 'graphql', label: 'GraphQL' },
  { id: 'rest', label: 'REST' },
  { id: 'grpc', label: 'gRPC' },
  { id: 'websocket', label: 'WebSocket' },
]

const graphqlSchema = `# Qtown GraphQL Schema (cartographer gateway — port 4000)

type Query {
  world: WorldState!
  npc(id: ID!): Npc
  npcs(
    page: Int = 1
    pageSize: Int = 20
    role: String
    status: NpcStatus
    neighborhood: String
    search: String
  ): NpcList!
  orderBook(resource: Resource!, depth: Int = 20): OrderBook!
  priceHistory(resource: Resource!, ticks: Int = 100): [PriceCandle!]!
  newspaper(day: Int): NewspaperEdition
  newspapers(limit: Int = 30): [NewspaperEdition!]!
  fortressStats: FortressStats!
  academyStats: AcademyStats!
  tournamentActive: Tournament
  tournaments(limit: Int = 10): [Tournament!]!
}

type WorldState {
  tick: Int!
  dayNumber: Int!
  timeOfDay: Float!
  isNight: Boolean!
  population: Int!
  totalGold: Float!
  averageHappiness: Float!
  activeNpcs: Int!
  weather: Weather!
}

type Npc {
  id: ID!
  name: String!
  role: String!
  gold: Float!
  happiness: Float!
  hunger: Float!
  energy: Float!
  neighborhood: String!
  status: NpcStatus!
  x: Float!
  y: Float!
  inventory: [InventoryItem!]!
  recentActions: [NpcAction!]!
}

type OrderBook {
  resource: Resource!
  bids: [OrderLevel!]!
  asks: [OrderLevel!]!
  lastPrice: Float
  spread: Float
  timestamp: String!
}

type Tournament {
  id: ID!
  name: String!
  status: TournamentStatus!
  startTick: Int!
  endTick: Int
  standings: [Standing!]!
  totalTrades: Int!
  winner: Npc
}

type Standing {
  rank: Int!
  npc: Npc!
  gold: Float!
  inventoryValue: Float!
  totalValue: Float!
  tradesExecuted: Int!
  profitLoss: Float!
}

enum NpcStatus { active traveling sleeping idle }
enum Resource { wood stone food gold iron herb }
enum TournamentStatus { pending active ended }`

interface RestEndpoint {
  method: string
  path: string
  service: string
  description: string
  response: string
}

const restEndpoints: RestEndpoint[] = [
  { method: 'GET', path: '/api/world', service: 'town-core:8000', description: 'World state snapshot', response: 'WorldStateResponse' },
  { method: 'GET', path: '/api/npcs', service: 'town-core:8000', description: 'Paginated NPC list (page, pageSize, role, status, search)', response: 'NpcListResponse' },
  { method: 'GET', path: '/api/npcs/:id', service: 'town-core:8000', description: 'Single NPC profile', response: 'NpcResponse' },
  { method: 'GET', path: '/api/newspaper/latest', service: 'town-core:8000', description: 'Latest newspaper edition', response: 'NewspaperEdition' },
  { method: 'GET', path: '/api/newspaper/:day', service: 'town-core:8000', description: 'Newspaper by day number', response: 'NewspaperEdition' },
  { method: 'GET', path: '/api/newspaper/archive', service: 'town-core:8000', description: 'Past editions (limit param)', response: 'NewspaperEdition[]' },
  { method: 'GET', path: '/api/fortress/stats', service: 'town-core:8000', description: 'Validation statistics', response: 'FortressStats' },
  { method: 'GET', path: '/api/sla/compliance', service: 'town-core:8000', description: 'SLA compliance report', response: 'ComplianceReport' },
  { method: 'GET', path: '/api/sla/violations', service: 'town-core:8000', description: 'Recent SLA violations (hours param)', response: 'SLAViolation[]' },
  { method: 'GET', path: '/api/stats', service: 'academy:8001', description: 'LLM usage and cost stats', response: 'AcademyStats' },
  { method: 'GET', path: '/api/generations', service: 'academy:8001', description: 'Recent LLM generations (limit param)', response: 'GenerationRecord[]' },
  { method: 'GET', path: '/search', service: 'library:8004', description: 'Full-text search (q, type, limit)', response: 'SearchResponse' },
  { method: 'POST', path: '/api/visitor/submit', service: 'dashboard BFF', description: 'Submit visitor feature request', response: 'FeatureRequestResult' },
  { method: 'GET', path: '/api/visitor/requests', service: 'dashboard BFF', description: 'Recent visitor requests', response: 'FeatureRequest[]' },
  { method: 'GET', path: '/api/sla/compliance', service: 'dashboard BFF', description: 'SLA compliance proxy', response: 'ComplianceReport' },
]

interface GrpcService {
  name: string
  port: number
  protoPackage: string
  methods: string[]
}

const grpcServices: GrpcService[] = [
  {
    name: 'TownCoreService',
    port: 50051,
    protoPackage: 'towncore.v1',
    methods: ['GetWorldState(WorldStateRequest) → WorldStateResponse', 'GetNpc(NpcRequest) → NpcResponse', 'ListNpcs(NpcListRequest) → NpcListResponse', 'ForceAction(ForceActionRequest) → ActionResult'],
  },
  {
    name: 'MarketService',
    port: 50052,
    protoPackage: 'market.v1',
    methods: ['PlaceOrder(PlaceOrderRequest) → OrderResult', 'CancelOrder(CancelOrderRequest) → CancelResult', 'GetOrderBook(OrderBookRequest) → OrderBookResponse', 'GetPriceHistory(PriceHistoryRequest) → PriceHistoryResponse', 'GetStandings(StandingsRequest) → StandingsResponse'],
  },
  {
    name: 'FortressService',
    port: 50053,
    protoPackage: 'fortress.v1',
    methods: ['ValidateAction(ValidateRequest) → ValidationResult', 'GetAuditLog(AuditLogRequest) → AuditLogResponse', 'GetStats(StatsRequest) → StatsResponse'],
  },
  {
    name: 'AcademyService',
    port: 50054,
    protoPackage: 'academy.v1',
    methods: ['DecideAction(DecisionRequest) → DecisionResponse', 'GenerateInsight(InsightRequest) → InsightResponse', 'GenerateNewspaper(NewspaperRequest) → NewspaperResponse', 'GenerateQuest(QuestRequest) → QuestResponse', 'GetStats(StatsRequest) → StatsResponse'],
  },
]

interface WsChannel {
  channel: string
  direction: string
  schema: string
  description: string
}

const wsChannels: WsChannel[] = [
  { channel: 'metrics', direction: '← server', schema: '{ type: "tick", payload: WorldState }', description: 'World state on every tick (~500ms)' },
  { channel: 'npc:positions', direction: '← server', schema: '{ type: "positions", payload: NpcPosition[] }', description: 'Bulk NPC position update each tick' },
  { channel: 'npc:event', direction: '← server', schema: '{ type: "npc_event", payload: NpcAction }', description: 'Individual NPC action events' },
  { channel: 'market', direction: '← server', schema: '{ type: "trade", payload: Trade }', description: 'Real-time trade feed' },
  { channel: 'tournament', direction: '← server', schema: '{ type: "standings", payload: Standing[] }', description: 'Live tournament leaderboard updates' },
  { channel: 'subscribe', direction: '→ client sends', schema: '{ type: "subscribe", channel: string }', description: 'Subscribe to a channel' },
  { channel: 'unsubscribe', direction: '→ client sends', schema: '{ type: "unsubscribe", channel: string }', description: 'Unsubscribe from a channel' },
]
</script>

<template>
  <div class="animate-fade-in">
    <h1 class="text-3xl font-bold text-qtown-text-primary mb-3">API Reference</h1>
    <p class="text-qtown-text-secondary text-base mb-8 leading-relaxed">
      GraphQL schema, REST endpoints, gRPC services, and WebSocket protocol.
    </p>

    <!-- Tab nav -->
    <div class="flex gap-1 mb-8 border-b border-qtown-border">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px"
        :class="activeTab === tab.id
          ? 'text-qtown-accent border-qtown-accent'
          : 'text-qtown-text-dim border-transparent hover:text-qtown-text-secondary'"
        @click="activeTab = tab.id"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- GraphQL -->
    <div v-if="activeTab === 'graphql'" class="space-y-6 animate-fade-in">
      <div class="bg-qtown-surface border border-qtown-border rounded p-3 flex items-center gap-3">
        <span class="text-xs font-mono text-qtown-text-dim">Endpoint:</span>
        <code class="text-xs font-mono text-qtown-gold">POST http://localhost:4000/graphql</code>
        <span class="text-xs font-mono text-qtown-text-dim ml-4">Subscriptions:</span>
        <code class="text-xs font-mono text-qtown-gold">ws://localhost:4000/graphql</code>
      </div>

      <div class="bg-qtown-bg border border-qtown-border rounded-lg overflow-hidden">
        <div class="bg-qtown-surface border-b border-qtown-border px-4 py-2 flex items-center gap-2">
          <div class="w-2.5 h-2.5 rounded-full bg-red-500" />
          <div class="w-2.5 h-2.5 rounded-full bg-yellow-500" />
          <div class="w-2.5 h-2.5 rounded-full bg-green-500" />
          <span class="text-xs font-mono text-qtown-text-dim ml-2">schema.graphql</span>
        </div>
        <pre class="text-xs font-mono text-qtown-text-secondary p-5 overflow-x-auto leading-relaxed">{{ graphqlSchema }}</pre>
      </div>
    </div>

    <!-- REST -->
    <div v-if="activeTab === 'rest'" class="animate-fade-in">
      <div class="overflow-x-auto rounded-lg border border-qtown-border">
        <table class="w-full text-xs">
          <thead>
            <tr class="bg-qtown-surface border-b border-qtown-border">
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono uppercase">Method</th>
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono uppercase">Path</th>
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono uppercase">Service</th>
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono uppercase">Description</th>
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono uppercase">Response</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="ep in restEndpoints"
              :key="`${ep.method}-${ep.path}`"
              class="border-b border-qtown-border last:border-b-0 bg-qtown-card hover:bg-qtown-border/30 transition-colors"
            >
              <td class="px-4 py-2.5">
                <span
                  class="font-mono font-bold px-1.5 py-0.5 rounded text-xs"
                  :class="ep.method === 'GET' ? 'bg-green-500/10 text-green-400' : 'bg-blue-500/10 text-blue-400'"
                >{{ ep.method }}</span>
              </td>
              <td class="px-4 py-2.5 font-mono text-qtown-gold">{{ ep.path }}</td>
              <td class="px-4 py-2.5 font-mono text-qtown-text-dim">{{ ep.service }}</td>
              <td class="px-4 py-2.5 text-qtown-text-secondary">{{ ep.description }}</td>
              <td class="px-4 py-2.5 font-mono text-qtown-text-dim">{{ ep.response }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- gRPC -->
    <div v-if="activeTab === 'grpc'" class="space-y-6 animate-fade-in">
      <div
        v-for="svc in grpcServices"
        :key="svc.name"
        class="bg-qtown-card border border-qtown-border rounded-lg overflow-hidden"
      >
        <div class="bg-qtown-surface border-b border-qtown-border px-5 py-3 flex items-center gap-3">
          <span class="font-mono font-bold text-qtown-gold text-sm">{{ svc.name }}</span>
          <span class="text-xs font-mono text-qtown-text-dim bg-qtown-bg px-2 py-0.5 rounded">:{{ svc.port }}</span>
          <span class="text-xs font-mono text-qtown-text-dim">{{ svc.protoPackage }}</span>
        </div>
        <ul class="divide-y divide-qtown-border">
          <li
            v-for="method in svc.methods"
            :key="method"
            class="px-5 py-3 font-mono text-xs text-qtown-text-secondary hover:text-qtown-text-primary hover:bg-qtown-border/20 transition-colors"
          >
            <span class="text-qtown-accent">rpc</span> {{ method }}
          </li>
        </ul>
      </div>
    </div>

    <!-- WebSocket -->
    <div v-if="activeTab === 'websocket'" class="space-y-6 animate-fade-in">
      <div class="bg-qtown-surface border border-qtown-border rounded p-3">
        <code class="text-xs font-mono text-qtown-gold">ws://localhost:3001</code>
        <span class="text-xs text-qtown-text-dim ml-3">— Tavern WebSocket hub (Redis-backed fan-out)</span>
      </div>

      <div>
        <h3 class="text-sm font-semibold text-qtown-text-primary mb-3">Connection Handshake</h3>
        <div class="bg-qtown-bg border border-qtown-border rounded-lg px-4 py-3">
          <pre class="text-xs font-mono text-qtown-text-secondary">// 1. Connect
ws = new WebSocket('ws://localhost:3001')

// 2. Subscribe to channels
ws.send(JSON.stringify({ type: 'subscribe', channel: 'metrics' }))
ws.send(JSON.stringify({ type: 'subscribe', channel: 'market' }))

// 3. Receive messages
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data) // { type, channel, payload }
  if (msg.type === 'tick') updateWorldState(msg.payload)
  if (msg.type === 'trade') updateOrderBook(msg.payload)
}</pre>
        </div>
      </div>

      <div class="overflow-x-auto rounded-lg border border-qtown-border">
        <table class="w-full text-xs">
          <thead>
            <tr class="bg-qtown-surface border-b border-qtown-border">
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono uppercase">Channel</th>
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono uppercase">Direction</th>
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono uppercase">Schema</th>
              <th class="text-left px-4 py-3 text-qtown-text-dim font-mono uppercase">Description</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="ch in wsChannels"
              :key="ch.channel"
              class="border-b border-qtown-border last:border-b-0 bg-qtown-card hover:bg-qtown-border/30 transition-colors"
            >
              <td class="px-4 py-2.5 font-mono text-qtown-gold">{{ ch.channel }}</td>
              <td class="px-4 py-2.5 font-mono text-qtown-text-dim">{{ ch.direction }}</td>
              <td class="px-4 py-2.5 font-mono text-qtown-text-dim">{{ ch.schema }}</td>
              <td class="px-4 py-2.5 text-qtown-text-secondary">{{ ch.description }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
