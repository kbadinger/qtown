import { gql } from "graphql-tag";

export const typeDefs = gql`
  type NPC {
    id: ID!
    name: String!
    gold: Float!
    happiness: Float!
    neighborhood: String!
    location: Location
  }

  type Location {
    x: Float!
    y: Float!
  }

  type Order {
    id: ID!
    npcId: ID!
    resource: String!
    side: OrderSide!
    price: Float!
    quantity: Float!
  }

  enum OrderSide {
    BID
    ASK
  }

  type Trade {
    id: ID!
    buyOrderId: ID!
    sellOrderId: ID!
    resource: String!
    price: Float!
    quantity: Float!
    timestamp: String!
  }

  type ValidationResult {
    valid: Boolean!
    ruleName: String!
    message: String
  }

  type LeaderboardEntry {
    npcId: ID!
    score: Float!
    rank: Int!
  }

  type TownEvent {
    id: ID!
    type: String!
    description: String!
    timestamp: String!
    npcId: ID
  }

  type Query {
    npc(id: ID!): NPC
    npcs(limit: Int, offset: Int): [NPC!]!
    orderBook(resource: String!): [Order!]!
    trades(resource: String!, limit: Int): [Trade!]!
    leaderboard(limit: Int): [LeaderboardEntry!]!
    searchEvents(query: String!, limit: Int): [TownEvent!]!
  }

  type Subscription {
    eventStream(types: [String!]): TownEvent!
    leaderboardUpdate: LeaderboardEntry!
  }
`;
