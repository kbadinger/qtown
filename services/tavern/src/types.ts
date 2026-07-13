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

export interface TradeSettled extends KafkaEvent {
  type: "economy.trade.settled";
  trade_id: string;
  buyer_id: string;
  seller_id: string;
  resource: string;
  quantity: number;
  price: number;
  buyer_gold_after: number;
  seller_gold_after: number;
}

export interface PriceUpdate extends KafkaEvent {
  type: "economy.price.update";
  resource: string;
  price: number;
  volume: number;
  tick: number;
}

export interface ContentGenerated extends KafkaEvent {
  type: "ai.content.generated";
  content_type: "newspaper" | "dialogue" | "description";
  content_id: string;
  npc_id?: string;
  day?: number;
  text: string;
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

export interface NPCTravelDepart extends KafkaEvent {
  type: "npc.travel.depart";
  npc_id: string;
  from_neighborhood: string;
  from_building: string;
  to_neighborhood: string;
  to_building: string;
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
