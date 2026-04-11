import { gql } from "graphql-tag";

export const typeDefs = gql`
  # -------------------------------------------------------------------------
  # Scalars
  # -------------------------------------------------------------------------

  scalar JSON
  scalar DateTime

  # -------------------------------------------------------------------------
  # Core domain types
  # -------------------------------------------------------------------------

  type NPC {
    id: ID!
    name: String!
    district: String!
    gold: Float!
    occupation: String
    mood: String
    """ Live orders this NPC has open in the Market District. """
    orders: [Order!]!
    """ Recent dialogue lines from Academy. """
    dialogues: [Dialogue!]!
    """ Leaderboard rank for a given metric (e.g. "wealth", "reputation"). """
    leaderboardRank(metric: String!): LeaderboardEntry
  }

  type Building {
    id: ID!
    name: String!
    district: String!
    type: String!
    owner: NPC
    coordinates: Coordinates!
  }

  type Coordinates {
    x: Float!
    y: Float!
  }

  type WorldState {
    tick: Int!
    timestamp: DateTime!
    totalNpcs: Int!
    totalBuildings: Int!
    economyIndex: Float!
    activeDistricts: [String!]!
  }

  type Order {
    id: ID!
    npcId: ID!
    resource: String!
    side: OrderSide!
    price: Float!
    quantity: Float!
    timestamp: DateTime!
  }

  enum OrderSide {
    BID
    ASK
  }

  type Dialogue {
    id: ID!
    npcId: ID!
    speaker: String!
    text: String!
    timestamp: DateTime!
    context: JSON
  }

  type LeaderboardEntry {
    metric: String!
    npcId: ID!
    npcName: String!
    score: Float!
    rank: Int!
  }

  type OrderBook {
    resource: String!
    bids: [Order!]!
    asks: [Order!]!
    lastTradePrice: Float
    spread: Float
  }

  type SearchResult {
    id: ID!
    type: String!
    title: String!
    snippet: String!
    similarity: Float!
  }

  type SearchResults {
    query: String!
    results: [SearchResult!]!
    totalCount: Int!
  }

  # -------------------------------------------------------------------------
  # Queries
  # -------------------------------------------------------------------------

  type Query {
    """ Fetch a single NPC by ID. """
    npc(id: ID!): NPC

    """ Fetch multiple NPCs with optional filters. """
    npcs(
      district: String
      occupation: String
      limit: Int = 20
      offset: Int = 0
    ): [NPC!]!

    """ Current global world state snapshot. """
    worldState: WorldState!

    """ Semantic search through town history (events, dialogues, newspapers). """
    searchHistory(query: String!, k: Int = 10): SearchResults!

    """ Order book for a specific resource. """
    orderBook(resource: String!): OrderBook!

    """ Top-N leaderboard for a given metric. """
    leaderboard(metric: String!, limit: Int = 10): [LeaderboardEntry!]!
  }

  # -------------------------------------------------------------------------
  # Subscriptions
  # -------------------------------------------------------------------------

  type Subscription {
    """ Stream of all town events (filtered by optional type list). """
    eventStream(types: [String!]): JSON!

    """ Real-time price updates for a resource's order book. """
    priceUpdates(resource: String!): OrderBook!
  }
`;
