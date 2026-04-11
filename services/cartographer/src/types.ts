/**
 * Placeholder for generated GraphQL types.
 *
 * Run `npm run codegen` to regenerate this file from schema.ts using
 * @graphql-codegen/typescript and @graphql-codegen/typescript-resolvers.
 * The generated output will be written here by the codegen config (codegen.yml).
 *
 * Manual types below are used until codegen is run for the first time.
 */

export type Maybe<T> = T | null;

export interface NPC {
  id: string;
  name: string;
  gold: number;
  happiness: number;
  neighborhood: string;
  location?: Location | null;
}

export interface Location {
  x: number;
  y: number;
}

export interface Order {
  id: string;
  npcId: string;
  resource: string;
  side: "BID" | "ASK";
  price: number;
  quantity: number;
}

export interface Trade {
  id: string;
  buyOrderId: string;
  sellOrderId: string;
  resource: string;
  price: number;
  quantity: number;
  timestamp: string;
}

export interface ValidationResult {
  valid: boolean;
  ruleName: string;
  message?: string | null;
}

export interface LeaderboardEntry {
  npcId: string;
  score: number;
  rank: number;
}

export interface TownEvent {
  id: string;
  type: string;
  description: string;
  timestamp: string;
  npcId?: string | null;
}

// ---------------------------------------------------------------------------
// gRPC stub response shapes (used before proto codegen)
// ---------------------------------------------------------------------------

export interface GrpcNPCResponse {
  npcs: NPC[];
}

export interface GrpcOrderResponse {
  orders: Order[];
}

export interface GrpcLeaderboardResponse {
  entries: LeaderboardEntry[];
}
