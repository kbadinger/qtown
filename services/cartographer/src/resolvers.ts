import type * as grpc from "@grpc/grpc-js";
import pino from "pino";
import type {
  NPC,
  Order,
  Trade,
  LeaderboardEntry,
  TownEvent,
} from "./types.js";
import type { Dataloaders } from "./dataloaders.js";

const logger = pino({ name: "resolvers" });

// ---------------------------------------------------------------------------
// Context type
// ---------------------------------------------------------------------------

export interface ResolverContext {
  townCoreClient: grpc.Client;
  marketClient: grpc.Client;
  fortressClient: grpc.Client;
  dataloaders: Dataloaders;
}

// ---------------------------------------------------------------------------
// Query resolvers
// ---------------------------------------------------------------------------

const Query = {
  /**
   * Single NPC lookup — uses DataLoader for batching.
   */
  async npc(
    _parent: unknown,
    args: { id: string },
    ctx: ResolverContext
  ): Promise<NPC | null> {
    logger.debug({ id: args.id }, "Query.npc");
    return ctx.dataloaders.npcLoader.load(args.id);
  },

  /**
   * Paginated NPC list — gRPC call to town-core.
   */
  async npcs(
    _parent: unknown,
    args: { limit?: number; offset?: number },
    ctx: ResolverContext
  ): Promise<NPC[]> {
    const limit = args.limit ?? 20;
    const offset = args.offset ?? 0;
    logger.debug({ limit, offset }, "Query.npcs");

    try {
      return await grpcUnary<NPC[]>(ctx.townCoreClient, "ListNpcs", { limit, offset }).then(
        (r) => (r as { npcs: NPC[] }).npcs ?? []
      );
    } catch (err) {
      logger.error({ err }, "Query.npcs gRPC call failed — returning mock data");
      return Array.from({ length: Math.min(limit, 5) }, (_, i) => createMockNpc(`mock-${offset + i}`));
    }
  },

  /**
   * Order book for a resource — gRPC call to market-district.
   */
  async orderBook(
    _parent: unknown,
    args: { resource: string },
    ctx: ResolverContext
  ): Promise<Order[]> {
    logger.debug({ resource: args.resource }, "Query.orderBook");

    try {
      return await grpcUnary<Order[]>(ctx.marketClient, "GetOrderBook", {
        resource: args.resource,
      }).then((r) => (r as { orders: Order[] }).orders ?? []);
    } catch (err) {
      logger.error({ err }, "Query.orderBook gRPC call failed — returning mock data");
      return [createMockOrder(args.resource, "BID"), createMockOrder(args.resource, "ASK")];
    }
  },

  /**
   * Trade history for a resource — gRPC call to market-district.
   */
  async trades(
    _parent: unknown,
    args: { resource: string; limit?: number },
    ctx: ResolverContext
  ): Promise<Trade[]> {
    const limit = args.limit ?? 20;
    logger.debug({ resource: args.resource, limit }, "Query.trades");

    try {
      return await grpcUnary<Trade[]>(ctx.marketClient, "GetTrades", {
        resource: args.resource,
        limit,
      }).then((r) => (r as { trades: Trade[] }).trades ?? []);
    } catch (err) {
      logger.error({ err }, "Query.trades gRPC call failed — returning mock data");
      return [createMockTrade(args.resource)];
    }
  },

  /**
   * Leaderboard — gRPC call to Tavern.
   */
  async leaderboard(
    _parent: unknown,
    args: { limit?: number },
    ctx: ResolverContext
  ): Promise<LeaderboardEntry[]> {
    const limit = args.limit ?? 10;
    logger.debug({ limit }, "Query.leaderboard");

    try {
      return await grpcUnary<LeaderboardEntry[]>(ctx.townCoreClient, "GetLeaderboard", {
        limit,
      }).then((r) => (r as { entries: LeaderboardEntry[] }).entries ?? []);
    } catch (err) {
      logger.error({ err }, "Query.leaderboard gRPC call failed — returning mock data");
      return Array.from({ length: Math.min(limit, 3) }, (_, i) => ({
        npcId: `mock-npc-${i + 1}`,
        score: 1000 - i * 100,
        rank: i + 1,
      }));
    }
  },

  /**
   * Full-text event search — gRPC call to town-core.
   */
  async searchEvents(
    _parent: unknown,
    args: { query: string; limit?: number },
    ctx: ResolverContext
  ): Promise<TownEvent[]> {
    const limit = args.limit ?? 10;
    logger.debug({ query: args.query, limit }, "Query.searchEvents");

    try {
      return await grpcUnary<TownEvent[]>(ctx.townCoreClient, "SearchEvents", {
        query: args.query,
        limit,
      }).then((r) => (r as { events: TownEvent[] }).events ?? []);
    } catch (err) {
      logger.error({ err }, "Query.searchEvents gRPC call failed — returning mock data");
      return [createMockEvent(args.query)];
    }
  },
};

// ---------------------------------------------------------------------------
// Field resolvers
// ---------------------------------------------------------------------------

const NPC = {
  /**
   * Resolve the `location` field via DataLoader — avoids extra round trips
   * when NPC location data is stored separately.
   */
  location(parent: NPC): NPC["location"] {
    return parent.location ?? null;
  },
};

// ---------------------------------------------------------------------------
// Subscription resolvers (stubs)
// ---------------------------------------------------------------------------

const Subscription = {
  eventStream: {
    subscribe: () => {
      // TODO: wire up AsyncIterator from Redis pub/sub or Kafka consumer
      logger.warn("Subscription.eventStream — not yet implemented");
      return (async function* () {
        // Placeholder: yields nothing
      })();
    },
    resolve: (payload: TownEvent) => payload,
  },
  leaderboardUpdate: {
    subscribe: () => {
      logger.warn("Subscription.leaderboardUpdate — not yet implemented");
      return (async function* () {})();
    },
    resolve: (payload: LeaderboardEntry) => payload,
  },
};

// ---------------------------------------------------------------------------
// Resolver map (exported for Apollo Server)
// ---------------------------------------------------------------------------

export const resolvers = {
  Query,
  NPC,
  Subscription,
};

// ---------------------------------------------------------------------------
// gRPC helper
// ---------------------------------------------------------------------------

function grpcUnary<T>(client: grpc.Client, method: string, request: unknown): Promise<T> {
  return new Promise((resolve, reject) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const fn = (client as any)[method];
    if (typeof fn !== "function") {
      return reject(new Error(`gRPC method "${method}" not found on client`));
    }
    fn.call(client, request, (err: grpc.ServiceError | null, response: T) => {
      if (err) return reject(err);
      resolve(response);
    });
  });
}

// ---------------------------------------------------------------------------
// Mock factories
// ---------------------------------------------------------------------------

function createMockNpc(id: string): NPC {
  return {
    id,
    name: `NPC ${id}`,
    gold: Math.random() * 1000,
    happiness: 50 + Math.random() * 50,
    neighborhood: "tavern-district",
    location: { x: Math.random() * 100, y: Math.random() * 100 },
  };
}

function createMockOrder(resource: string, side: "BID" | "ASK"): Order {
  return {
    id: `order-${Math.random().toString(36).slice(2)}`,
    npcId: "mock-npc-1",
    resource,
    side,
    price: 10 + Math.random() * 90,
    quantity: 1 + Math.random() * 10,
  };
}

function createMockTrade(resource: string): Trade {
  return {
    id: `trade-${Math.random().toString(36).slice(2)}`,
    buyOrderId: "order-buy-1",
    sellOrderId: "order-sell-1",
    resource,
    price: 50,
    quantity: 5,
    timestamp: new Date().toISOString(),
  };
}

function createMockEvent(query: string): TownEvent {
  return {
    id: `event-${Math.random().toString(36).slice(2)}`,
    type: "search-result",
    description: `Mock event matching: "${query}"`,
    timestamp: new Date().toISOString(),
    npcId: null,
  };
}
