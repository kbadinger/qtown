// ============================================================================
// WebSocket protocol types
// ============================================================================

export interface SubscribeMessage {
  action: "subscribe";
  channel: string;
}

export interface UnsubscribeMessage {
  action: "unsubscribe";
  channel: string;
}

export type WebSocketClientMessage = SubscribeMessage | UnsubscribeMessage;

export interface BroadcastMessage {
  channel: string;
  data: unknown;
  timestamp: string;
}

export interface WebSocketMessage {
  channel: string;
  event: KafkaEvent;
}

// ============================================================================
// Leaderboard types
// ============================================================================

export type LeaderboardType = "gold" | "happiness" | "crimes";

export interface LeaderboardEntry {
  npc_id: string;
  name: string;
  score: number;
  rank: number;
}

// ============================================================================
// Kafka event types
// ============================================================================

export interface KafkaEvent {
  event_id: string;
  type: string;
  timestamp: string;
  [key: string]: unknown;
}

// Single-sided settlement: market-district emits ONE message per counterparty
// (town-core reads the same shape). `gold_delta` is the change to apply to the
// NPC's running gold total — not an absolute balance.
export interface TradeSettled extends KafkaEvent {
  type: "economy.trade.settled";
  npc_id: number;
  gold_delta: number;
  resource: string;
  price: number;
  quantity: number;
  trade_id: string;
}

export interface PriceUpdate extends KafkaEvent {
  type: "economy.price.update";
  resource: string;
  price: number;
  volume: number;
  tick: number;
}

// academy emits { content_type, content_id, content, metadata, timestamp }.
// `text` is a convenience rendering some producers include; treat it as
// optional so the handler consumes messages without it.
export interface ContentGenerated extends KafkaEvent {
  type: "ai.content.generated";
  content_type: "newspaper" | "dialogue" | "description";
  content_id: string;
  npc_id?: string;
  day?: number;
  content?: unknown;
  text?: string;
  metadata?: Record<string, unknown>;
}

export interface EventBroadcast extends KafkaEvent {
  type: "events.broadcast";
  event_type: string;
  description: string;
  tick: number;
  npc_id?: string;
  crime?: boolean;
  crime_count?: number;
}

// town-core emits the canonical `qtown.npc.travel` (spec: Wanderers' Path,
// origin → destination) with { tick, npc_id, from, to, npc_state }. `from`/`to`
// are neighborhood names; there is no building granularity in the travel payload.
export interface NPCTravelDepart extends KafkaEvent {
  type: "npc.travel";
  npc_id: number;
  from: string;
  to: string;
  tick?: number;
  npc_state?: Record<string, unknown>;
}

export interface NPCTravelComplete extends KafkaEvent {
  type: "npc.travel.complete";
  npc_id: string;
  neighborhood: string;
  building: string;
}

// ============================================================================
// NPC Presence types
// ============================================================================

export type NPCStatus = "active" | "traveling" | "sleeping" | "working";

export interface NPCPresence {
  npc_id: string;
  neighborhood: string;
  building: string;
  status: NPCStatus;
  updated_at: string;
}

// ============================================================================
// Connection metrics
// ============================================================================

export interface ConnectionMetrics {
  totalConnections: number;
  messagesPerSecond: number;
  activeChannels: string[];
}
