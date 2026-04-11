// ============================================================================
// Scalar helpers
// ============================================================================

export type Maybe<T> = T | null | undefined;

// ============================================================================
// Enums
// ============================================================================

export type NPCStatus = "ACTIVE" | "TRAVELING" | "SLEEPING" | "WORKING";
export type OrderSide = "BUY" | "SELL";
export type OrderStatus = "OPEN" | "FILLED" | "PARTIAL" | "CANCELLED";
export type LeaderboardType = "GOLD" | "HAPPINESS" | "CRIMES";
export type DocType = "EVENT" | "DIALOGUE" | "NEWSPAPER" | "TRANSACTION";

// ============================================================================
// NPC types
// ============================================================================

export interface NPC {
  id: string;
  name: string;
  role: string;
  gold: number;
  hunger: number;
  energy: number;
  happiness: number;
  neighborhood: Maybe<string>;
  status: NPCStatus;
}

export interface LeaderboardRanks {
  gold: Maybe<number>;
  happiness: Maybe<number>;
  crimes: Maybe<number>;
}

// ============================================================================
// World State
// ============================================================================

export interface WorldState {
  tick: number;
  day: number;
  population: number;
  totalGold: number;
  activeEvents: number;
  timestamp: string;
}

// ============================================================================
// Orders & Order Book
// ============================================================================

export interface Order {
  id: string;
  npcId: string;
  side: OrderSide;
  resource: string;
  price: number;
  quantity: number;
  status: OrderStatus;
  createdAt: string;
}

export interface OrderBook {
  bids: Order[];
  asks: Order[];
  spread: Maybe<number>;
  lastPrice: Maybe<number>;
}

// ============================================================================
// Newspaper
// ============================================================================

export interface Newspaper {
  day: number;
  headline: string;
  lead: string;
  body: string;
  editorial: string;
  generatedAt: string;
}

// ============================================================================
// Leaderboard
// ============================================================================

export interface LeaderboardEntry {
  npcId: string;
  npcName: string;
  score: number;
  rank: number;
}

// ============================================================================
// Search
// ============================================================================

export interface SearchResult {
  docType: DocType;
  docId: string;
  content: string;
  score: number;
  highlight: Maybe<string>;
}

export interface SearchResults {
  total: number;
  results: SearchResult[];
}

// ============================================================================
// Decision Trace
// ============================================================================

export interface TraceNode {
  name: string;
  durationMs: number;
  inputSummary: string;
  outputSummary: string;
}

export interface DecisionTrace {
  npcId: string;
  tick: number;
  nodes: TraceNode[];
  finalDecision: string;
  totalDurationMs: number;
}

// ============================================================================
// Events & Subscriptions
// ============================================================================

export interface Event {
  id: string;
  type: string;
  description: string;
  tick: number;
  timestamp: string;
}

export interface PriceUpdate {
  resource: string;
  price: number;
  volume: number;
  timestamp: string;
}

// ============================================================================
// Dialogue
// ============================================================================

export interface Dialogue {
  id: string;
  npcId: string;
  text: string;
  context: Maybe<string>;
  generatedAt: string;
}

// ============================================================================
// gRPC response envelope types
// ============================================================================

export interface GrpcNPCResponse {
  npc: NPC;
}

export interface GrpcNPCsResponse {
  npcs: NPC[];
  total: number;
}

export interface GrpcWorldStateResponse {
  worldState: WorldState;
}

export interface GrpcOrderBookResponse {
  bids: Order[];
  asks: Order[];
  lastPrice: number | null;
}

export interface GrpcOrdersResponse {
  orders: Order[];
}

export interface GrpcNewspaperResponse {
  newspaper: Newspaper;
}

export interface GrpcDialoguesResponse {
  dialogues: Dialogue[];
}

export interface GrpcDecisionTraceResponse {
  trace: DecisionTrace;
}

// ============================================================================
// DataLoaders context
// ============================================================================

export interface DataLoaders {
  npcLoader: import("dataloader")<string, NPC | null>;
  orderLoader: import("dataloader")<string, Order[]>;
  dialogueLoader: import("dataloader")<string, Dialogue[]>;
}
