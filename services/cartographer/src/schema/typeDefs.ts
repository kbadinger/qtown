import { gql } from "graphql-tag";

export const typeDefs = gql`
  # ============================================================================
  # Enums
  # ============================================================================

  enum NPCStatus {
    ACTIVE
    TRAVELING
    SLEEPING
    WORKING
  }

  enum OrderSide {
    BUY
    SELL
  }

  enum OrderStatus {
    OPEN
    FILLED
    PARTIAL
    CANCELLED
  }

  enum LeaderboardType {
    GOLD
    HAPPINESS
    CRIMES
  }

  enum DocType {
    EVENT
    DIALOGUE
    NEWSPAPER
    TRANSACTION
  }

  # ============================================================================
  # Core types
  # ============================================================================

  type NPC {
    id: ID!
    name: String!
    role: String!
    gold: Float!
    hunger: Float!
    energy: Float!
    happiness: Float!
    neighborhood: String
    status: NPCStatus!
    recentEvents(limit: Int): [Event!]!
    orders(limit: Int): [Order!]!
    dialogues(limit: Int): [Dialogue!]!
    leaderboardRanks: LeaderboardRanks!
    decisionTrace(tick: Int): DecisionTrace
  }

  type LeaderboardRanks {
    gold: Int
    happiness: Int
    crimes: Int
  }

  type WorldState {
    tick: Int!
    day: Int!
    population: Int!
    totalGold: Float!
    activeEvents: Int!
    timestamp: String!
  }

  type Order {
    id: ID!
    npcId: ID!
    side: OrderSide!
    resource: String!
    price: Float!
    quantity: Int!
    status: OrderStatus!
    createdAt: String!
  }

  type OrderBook {
    bids: [Order!]!
    asks: [Order!]!
    spread: Float
    lastPrice: Float
  }

  type Newspaper {
    day: Int!
    headline: String!
    lead: String!
    body: String!
    editorial: String!
    generatedAt: String!
  }

  type LeaderboardEntry {
    npcId: ID!
    npcName: String!
    score: Float!
    rank: Int!
  }

  type SearchResults {
    total: Int!
    results: [SearchResult!]!
  }

  type SearchResult {
    docType: DocType!
    docId: ID!
    content: String!
    score: Float!
    highlight: String
  }

  type DecisionTrace {
    npcId: ID!
    tick: Int!
    nodes: [TraceNode!]!
    finalDecision: String!
    totalDurationMs: Float!
  }

  type TraceNode {
    name: String!
    durationMs: Float!
    inputSummary: String!
    outputSummary: String!
  }

  type Dialogue {
    id: ID!
    npcId: ID!
    text: String!
    context: String
    generatedAt: String!
  }

  type Event {
    id: ID!
    type: String!
    description: String!
    tick: Int!
    timestamp: String!
  }

  type PriceUpdate {
    resource: String!
    price: Float!
    volume: Int!
    timestamp: String!
  }

  # ============================================================================
  # Query
  # ============================================================================

  type Query {
    npc(id: ID!): NPC
    npcs(limit: Int, offset: Int, neighborhood: String): [NPC!]!
    worldState: WorldState!
    orderBook(resource: String!): OrderBook!
    orders(npcId: ID): [Order!]!
    newspaper(day: Int): Newspaper
    newspapers(limit: Int): [Newspaper!]!
    leaderboard(type: LeaderboardType!, limit: Int): [LeaderboardEntry!]!
    searchHistory(query: String!, types: [DocType]): SearchResults!
    npcDecisionTrace(npcId: ID!, tick: Int): DecisionTrace
  }

  # ============================================================================
  # Subscription
  # ============================================================================

  type Subscription {
    eventStream(channels: [String!]): Event!
    priceUpdates(resource: String): PriceUpdate!
  }
`;
