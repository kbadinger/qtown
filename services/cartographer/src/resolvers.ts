import pino from "pino";
import { grpcUnary } from "./grpc-clients.js";
import { NpcFieldResolvers } from "./resolvers/npc.js";
import { cacheGet, cacheSet, makeCacheKey, CACHE_TTL } from "./cache.js";
import type { ResolverContext } from "./context.js";
import type {
  NPC,
  WorldState,
  OrderBook,
  Order,
  Newspaper,
  LeaderboardEntry,
  SearchResults,
  DecisionTrace,
  Event,
  PriceUpdate,
} from "./types.js";

const logger = pino({ name: "resolvers" });

export type { ResolverContext } from "./context.js";

// ============================================================================
// Query resolvers
// ============================================================================

const Query = {
  /**
   * Single NPC lookup — DataLoader batches concurrent requests.
   */
  async npc(
    _parent: unknown,
    args: { id: string },
    ctx: ResolverContext
  ): Promise<NPC | null> {
    logger.debug({ id: args.id }, "Query.npc");
    return ctx.dataLoaders.npcLoader.load(args.id);
  },

  /**
   * Paginated NPC list — direct gRPC call with optional neighborhood filter.
   * Complexity: 5 × limit items.
   */
  async npcs(
    _parent: unknown,
    args: { limit?: number | null; offset?: number | null; neighborhood?: string | null },
    ctx: ResolverContext
  ): Promise<NPC[]> {
    const limit = args.limit ?? 20;
    const offset = args.offset ?? 0;
    logger.debug({ limit, offset, neighborhood: args.neighborhood }, "Query.npcs");

    try {
      const response = await grpcUnary<
        { limit: number; offset: number; neighborhood?: string },
        { npcs: NPC[] }
      >(ctx.townCoreClient, "ListNPCs", {
        limit,
        offset,
        ...(args.neighborhood ? { neighborhood: args.neighborhood } : {}),
      });
      return response.npcs ?? [];
    } catch (err) {
      logger.error({ err }, "Query.npcs gRPC failed");
      return [];
    }
  },

  /**
   * World state — gRPC call to town-core, cached 5 s.
   */
  async worldState(
    _parent: unknown,
    _args: Record<string, never>,
    ctx: ResolverContext
  ): Promise<WorldState> {
    const cacheKey = "cartographer:worldState";
    const cached = await cacheGet<WorldState>(ctx.redisCache, cacheKey);
    if (cached !== null) {
      logger.debug("Query.worldState — cache hit");
      return cached;
    }

    try {
      const response = await grpcUnary<Record<string, never>, { worldState: WorldState }>(
        ctx.townCoreClient,
        "GetWorldState",
        {}
      );
      const ws = response.worldState;
      await cacheSet(ctx.redisCache, cacheKey, ws, CACHE_TTL.worldState);
      return ws;
    } catch (err) {
      logger.error({ err }, "Query.worldState gRPC failed");
      return {
        tick: 0,
        day: 1,
        population: 0,
        totalGold: 0,
        activeEvents: 0,
        timestamp: new Date().toISOString(),
      };
    }
  },

  /**
   * Order book for a resource — gRPC call to market-district, cached 3 s.
   */
  async orderBook(
    _parent: unknown,
    args: { resource: string },
    ctx: ResolverContext
  ): Promise<OrderBook> {
    const cacheKey = `cartographer:orderBook:${args.resource}`;
    const cached = await cacheGet<OrderBook>(ctx.redisCache, cacheKey);
    if (cached !== null) return cached;

    try {
      const response = await grpcUnary<
        { resource: string },
        { bids: Order[]; asks: Order[]; lastPrice: number | null }
      >(ctx.marketDistrictClient, "GetOrderBook", { resource: args.resource });

      const bids = response.bids ?? [];
      const asks = response.asks ?? [];
      const spread =
        asks.length > 0 && bids.length > 0
          ? (asks[0]?.price ?? 0) - (bids[0]?.price ?? 0)
          : null;

      const book: OrderBook = {
        bids,
        asks,
        spread,
        lastPrice: response.lastPrice ?? null,
      };

      await cacheSet(ctx.redisCache, cacheKey, book, CACHE_TTL.orderBook);
      return book;
    } catch (err) {
      logger.error({ err, resource: args.resource }, "Query.orderBook gRPC failed");
      return { bids: [], asks: [], spread: null, lastPrice: null };
    }
  },

  /**
   * Orders — gRPC call to market-district, optionally filtered by npcId.
   */
  async orders(
    _parent: unknown,
    args: { npcId?: string | null },
    ctx: ResolverContext
  ): Promise<Order[]> {
    logger.debug({ npcId: args.npcId }, "Query.orders");

    try {
      const response = await grpcUnary<
        { npc_id?: string },
        { orders: Order[] }
      >(ctx.marketDistrictClient, "GetOrders", {
        ...(args.npcId ? { npc_id: args.npcId } : {}),
      });
      return response.orders ?? [];
    } catch (err) {
      logger.error({ err }, "Query.orders gRPC failed");
      return [];
    }
  },

  /**
   * Single newspaper — gRPC call to academy, cached 60 s.
   */
  async newspaper(
    _parent: unknown,
    args: { day?: number | null },
    ctx: ResolverContext
  ): Promise<Newspaper | null> {
    const dayStr = args.day !== null && args.day !== undefined ? String(args.day) : "latest";
    const cacheKey = `cartographer:newspaper:${dayStr}`;
    const cached = await cacheGet<Newspaper>(ctx.redisCache, cacheKey);
    if (cached !== null) return cached;

    try {
      const response = await grpcUnary<
        { day?: number },
        { newspaper: Newspaper | null }
      >(ctx.academyClient, "GetNewspaper", {
        ...(args.day !== null && args.day !== undefined ? { day: args.day } : {}),
      });
      const paper = response.newspaper ?? null;
      if (paper) {
        await cacheSet(ctx.redisCache, cacheKey, paper, CACHE_TTL.newspaper);
      }
      return paper;
    } catch (err) {
      logger.error({ err }, "Query.newspaper gRPC failed");
      return null;
    }
  },

  /**
   * Multiple newspapers — gRPC call to academy.
   */
  async newspapers(
    _parent: unknown,
    args: { limit?: number | null },
    ctx: ResolverContext
  ): Promise<Newspaper[]> {
    const limit = args.limit ?? 7;
    logger.debug({ limit }, "Query.newspapers");

    try {
      const response = await grpcUnary<
        { limit: number },
        { newspapers: Newspaper[] }
      >(ctx.academyClient, "ListNewspapers", { limit });
      return response.newspapers ?? [];
    } catch (err) {
      logger.error({ err }, "Query.newspapers gRPC failed");
      return [];
    }
  },

  /**
   * Leaderboard — reads from Redis directly (Tavern writes to these keys).
   * Cached 10 s.
   */
  async leaderboard(
    _parent: unknown,
    args: { type: string; limit?: number | null },
    ctx: ResolverContext
  ): Promise<LeaderboardEntry[]> {
    const limit = args.limit ?? 10;
    const type = args.type.toLowerCase();
    const cacheKey = `cartographer:leaderboard:${type}:${limit}`;

    const cached = await cacheGet<LeaderboardEntry[]>(ctx.redisCache, cacheKey);
    if (cached !== null) {
      logger.debug({ type, limit }, "Query.leaderboard — cache hit");
      return cached;
    }

    // Read directly from Redis sorted sets (written by Tavern's Leaderboard class)
    const redisKey = `qtown:leaderboard:${type}`;
    try {
      const raw = await ctx.redisCache.zrevrange(redisKey, 0, limit - 1, "WITHSCORES");
      const entries: LeaderboardEntry[] = [];
      for (let i = 0; i < raw.length; i += 2) {
        const npcId = raw[i] ?? "";
        const score = parseFloat(raw[i + 1] ?? "0");
        const rank = Math.floor(i / 2) + 1;
        entries.push({ npcId, npcName: npcId, score, rank });
      }
      await cacheSet(ctx.redisCache, cacheKey, entries, CACHE_TTL.leaderboard);
      return entries;
    } catch (err) {
      logger.error({ err, type }, "Query.leaderboard Redis failed");
      return [];
    }
  },

  /**
   * Full-text search — HTTP call to library service (or gRPC to academy).
   */
  async searchHistory(
    _parent: unknown,
    args: { query: string; types?: string[] | null },
    ctx: ResolverContext
  ): Promise<SearchResults> {
    const cacheKey = makeCacheKey(
      "search",
      `${args.query}:${(args.types ?? []).join(",")}`
    );
    const cached = await cacheGet<SearchResults>(ctx.redisCache, cacheKey);
    if (cached !== null) return cached;

    logger.debug({ query: args.query, types: args.types }, "Query.searchHistory");

    try {
      const response = await grpcUnary<
        { query: string; doc_types?: string[] },
        SearchResults
      >(ctx.academyClient, "SearchHistory", {
        query: args.query,
        ...(args.types && args.types.length > 0 ? { doc_types: args.types } : {}),
      });
      await cacheSet(ctx.redisCache, cacheKey, response, CACHE_TTL.searchResults);
      return response;
    } catch (err) {
      logger.error({ err }, "Query.searchHistory gRPC failed");
      return { total: 0, results: [] };
    }
  },

  /**
   * Decision trace — gRPC call to academy.
   */
  async npcDecisionTrace(
    _parent: unknown,
    args: { npcId: string; tick?: number | null },
    ctx: ResolverContext
  ): Promise<DecisionTrace | null> {
    logger.debug({ npcId: args.npcId, tick: args.tick }, "Query.npcDecisionTrace");

    try {
      const response = await grpcUnary<
        { npc_id: string; tick?: number },
        { trace: DecisionTrace | null }
      >(ctx.academyClient, "GetDecisionTrace", {
        npc_id: args.npcId,
        ...(args.tick !== null && args.tick !== undefined ? { tick: args.tick } : {}),
      });
      return response.trace ?? null;
    } catch (err) {
      logger.error({ err, npcId: args.npcId }, "Query.npcDecisionTrace gRPC failed");
      return null;
    }
  },
};

// ============================================================================
// Subscription resolvers
// ============================================================================

const Subscription = {
  eventStream: {
    // eslint-disable-next-line @typescript-eslint/require-await
    subscribe: async function* (
      _parent: unknown,
      args: { channels?: string[] | null },
      ctx: ResolverContext
    ): AsyncGenerator<{ eventStream: Event }> {
      // Filter channels or default to all
      const channels = args.channels ?? ["events"];
      logger.info({ channels }, "Subscription.eventStream subscribed");

      // Use Redis SUBSCRIBE via pub/sub
      const Redis = (await import("ioredis")).default;
      const subscriber = ctx.redisCache.duplicate() as InstanceType<typeof Redis>;

      try {
        await subscriber.subscribe(...channels);

        const queue: Event[] = [];
        let resolve: (() => void) | null = null;

        subscriber.on("message", (_channel: string, message: string) => {
          try {
            const event = JSON.parse(message) as Event;
            queue.push(event);
            resolve?.();
            resolve = null;
          } catch {
            // ignore parse errors
          }
        });

        while (true) {
          if (queue.length > 0) {
            yield { eventStream: queue.shift()! };
          } else {
            await new Promise<void>((res) => {
              resolve = res;
            });
          }
        }
      } finally {
        await subscriber.unsubscribe(...channels);
        subscriber.disconnect();
      }
    },
  },

  priceUpdates: {
    // eslint-disable-next-line @typescript-eslint/require-await
    subscribe: async function* (
      _parent: unknown,
      args: { resource?: string | null },
      ctx: ResolverContext
    ): AsyncGenerator<{ priceUpdates: PriceUpdate }> {
      logger.info({ resource: args.resource }, "Subscription.priceUpdates subscribed");

      const Redis = (await import("ioredis")).default;
      const subscriber = ctx.redisCache.duplicate() as InstanceType<typeof Redis>;

      try {
        await subscriber.subscribe("market");

        const queue: PriceUpdate[] = [];
        let resolve: (() => void) | null = null;

        subscriber.on("message", (_channel: string, message: string) => {
          try {
            const event = JSON.parse(message) as {
              type?: string;
              resource?: string;
              price?: number;
              volume?: number;
              timestamp?: string;
            };
            if (event.type !== "economy.price.update") return;
            if (args.resource && event.resource !== args.resource) return;

            queue.push({
              resource: event.resource ?? "",
              price: event.price ?? 0,
              volume: event.volume ?? 0,
              timestamp: event.timestamp ?? new Date().toISOString(),
            });
            resolve?.();
            resolve = null;
          } catch {
            // ignore
          }
        });

        while (true) {
          if (queue.length > 0) {
            yield { priceUpdates: queue.shift()! };
          } else {
            await new Promise<void>((res) => {
              resolve = res;
            });
          }
        }
      } finally {
        await subscriber.unsubscribe("market");
        subscriber.disconnect();
      }
    },
  },
};

// ============================================================================
// Resolver map
// ============================================================================

export const resolvers = {
  Query,
  Subscription,
  NPC: NpcFieldResolvers,
};
