import { describe, it, expect, vi, beforeEach } from "vitest";
import type { ResolverContext } from "../resolvers.js";
import type { NPC, WorldState, OrderBook, LeaderboardEntry } from "../types.js";

// ============================================================================
// Mock gRPC client factory
// ============================================================================

type GrpcMethod = (req: unknown, meta: unknown, opts: unknown, cb: (err: null, res: unknown) => void) => void;

function mockGrpcClient(methods: Record<string, unknown>): { [key: string]: GrpcMethod } {
  return Object.fromEntries(
    Object.entries(methods).map(([name, returnValue]) => [
      name,
      (_req: unknown, _meta: unknown, _opts: unknown, cb: (err: null, res: unknown) => void) => {
        cb(null, returnValue);
      },
    ])
  ) as { [key: string]: GrpcMethod };
}

// ============================================================================
// Mock Redis cache
// ============================================================================

class MockRedisCache {
  private store = new Map<string, string>();

  async get(key: string): Promise<string | null> {
    return this.store.get(key) ?? null;
  }

  async set(key: string, value: string, _ex: string, _ttl: number): Promise<string | null> {
    this.store.set(key, value);
    return "OK";
  }

  async zrevrange(_key: string, _start: number, _stop: number, _ws: string): Promise<string[]> {
    return ["npc-001", "500", "npc-002", "300"];
  }

  duplicate(): MockRedisCache {
    return this;
  }

  disconnect(): void {}
}

// ============================================================================
// Mock DataLoaders
// ============================================================================

function mockNpcLoader(npcs: Record<string, NPC>) {
  return {
    load: async (id: string): Promise<NPC | null> => npcs[id] ?? null,
  };
}

// ============================================================================
// Context builder
// ============================================================================

function buildCtx(overrides: Partial<{
  townCoreMethods: Record<string, unknown>;
  marketMethods: Record<string, unknown>;
  academyMethods: Record<string, unknown>;
  npcs: Record<string, NPC>;
}>): ResolverContext {
  const redis = new MockRedisCache();
  const townCoreClient = mockGrpcClient(overrides.townCoreMethods ?? {});
  const marketDistrictClient = mockGrpcClient(overrides.marketMethods ?? {});
  const academyClient = mockGrpcClient(overrides.academyMethods ?? {});
  const fortressClient = mockGrpcClient({});

  const npc001: NPC = {
    id: "npc-001",
    name: "Alice",
    role: "merchant",
    gold: 500,
    hunger: 30,
    energy: 70,
    happiness: 80,
    neighborhood: "market",
    status: "ACTIVE",
  };

  return {
    townCoreClient: townCoreClient as unknown as import("@grpc/grpc-js").Client,
    marketDistrictClient: marketDistrictClient as unknown as import("@grpc/grpc-js").Client,
    academyClient: academyClient as unknown as import("@grpc/grpc-js").Client,
    fortressClient: fortressClient as unknown as import("@grpc/grpc-js").Client,
    redisCache: redis as unknown as import("ioredis").default,
    dataLoaders: {
      npcLoader: mockNpcLoader(overrides.npcs ?? { "npc-001": npc001 }) as unknown as import("dataloader")<string, NPC | null>,
      orderLoader: { load: async () => [] } as unknown as import("dataloader")<string, import("../types.js").Order[]>,
      dialogueLoader: { load: async () => [] } as unknown as import("dataloader")<string, import("../types.js").Dialogue[]>,
    },
  };
}

// ============================================================================
// Tests
// ============================================================================

describe("Query.npc", () => {
  it("loads NPC via DataLoader", async () => {
    const { Query } = await import("../resolvers.js").then((m) => ({
      Query: (m.resolvers as { Query: { npc: (p: unknown, a: { id: string }, c: ResolverContext) => Promise<NPC | null> } }).Query,
    }));

    const ctx = buildCtx({});
    const result = await Query.npc(undefined, { id: "npc-001" }, ctx);
    expect(result).not.toBeNull();
    expect(result?.id).toBe("npc-001");
    expect(result?.name).toBe("Alice");
  });

  it("returns null for unknown NPC", async () => {
    const { Query } = await import("../resolvers.js").then((m) => ({
      Query: (m.resolvers as { Query: { npc: (p: unknown, a: { id: string }, c: ResolverContext) => Promise<NPC | null> } }).Query,
    }));

    const ctx = buildCtx({});
    const result = await Query.npc(undefined, { id: "npc-unknown" }, ctx);
    expect(result).toBeNull();
  });
});

describe("Query.worldState", () => {
  it("returns world state from gRPC", async () => {
    const mockWorldState: WorldState = {
      tick: 42,
      day: 3,
      population: 100,
      totalGold: 50000,
      activeEvents: 5,
      timestamp: "2024-01-01T00:00:00Z",
    };

    const { Query } = await import("../resolvers.js").then((m) => ({
      Query: (m.resolvers as { Query: { worldState: (p: unknown, a: Record<never, never>, c: ResolverContext) => Promise<WorldState> } }).Query,
    }));

    const ctx = buildCtx({
      townCoreMethods: {
        GetWorldState: { worldState: mockWorldState },
      },
    });

    const result = await Query.worldState(undefined, {}, ctx);
    expect(result.tick).toBe(42);
    expect(result.day).toBe(3);
    expect(result.population).toBe(100);
  });

  it("returns fallback when gRPC fails", async () => {
    const { Query } = await import("../resolvers.js").then((m) => ({
      Query: (m.resolvers as { Query: { worldState: (p: unknown, a: Record<never, never>, c: ResolverContext) => Promise<WorldState> } }).Query,
    }));

    // gRPC client with no methods → will throw "method not found"
    const ctx = buildCtx({});
    const result = await Query.worldState(undefined, {}, ctx);
    expect(result.tick).toBe(0);
    expect(result.population).toBe(0);
  });
});

describe("Query.orderBook", () => {
  it("calculates spread from bids and asks", async () => {
    const { Query } = await import("../resolvers.js").then((m) => ({
      Query: (m.resolvers as { Query: { orderBook: (p: unknown, a: { resource: string }, c: ResolverContext) => Promise<OrderBook> } }).Query,
    }));

    const ctx = buildCtx({
      marketMethods: {
        GetOrderBook: {
          bids: [{ id: "b1", npcId: "npc-001", side: "BUY", resource: "wood", price: 95, quantity: 10, status: "OPEN", createdAt: "" }],
          asks: [{ id: "a1", npcId: "npc-002", side: "SELL", resource: "wood", price: 100, quantity: 5, status: "OPEN", createdAt: "" }],
          lastPrice: 98,
        },
      },
    });

    const result = await Query.orderBook(undefined, { resource: "wood" }, ctx);
    expect(result.bids).toHaveLength(1);
    expect(result.asks).toHaveLength(1);
    expect(result.spread).toBe(5); // 100 - 95
    expect(result.lastPrice).toBe(98);
  });

  it("returns empty order book on gRPC error", async () => {
    const { Query } = await import("../resolvers.js").then((m) => ({
      Query: (m.resolvers as { Query: { orderBook: (p: unknown, a: { resource: string }, c: ResolverContext) => Promise<OrderBook> } }).Query,
    }));

    const ctx = buildCtx({});
    const result = await Query.orderBook(undefined, { resource: "wood" }, ctx);
    expect(result.bids).toHaveLength(0);
    expect(result.asks).toHaveLength(0);
    expect(result.spread).toBeNull();
  });
});

describe("Query.leaderboard", () => {
  it("parses Redis ZREVRANGE with scores", async () => {
    const { Query } = await import("../resolvers.js").then((m) => ({
      Query: (m.resolvers as { Query: { leaderboard: (p: unknown, a: { type: string; limit?: number }, c: ResolverContext) => Promise<LeaderboardEntry[]> } }).Query,
    }));

    const ctx = buildCtx({});
    const result = await Query.leaderboard(undefined, { type: "GOLD", limit: 10 }, ctx);
    // MockRedisCache returns ["npc-001", "500", "npc-002", "300"]
    expect(result).toHaveLength(2);
    expect(result[0]?.npcId).toBe("npc-001");
    expect(result[0]?.score).toBe(500);
    expect(result[0]?.rank).toBe(1);
    expect(result[1]?.npcId).toBe("npc-002");
    expect(result[1]?.rank).toBe(2);
  });
});

describe("Query.npcs", () => {
  it("applies default limit and offset", async () => {
    const { Query } = await import("../resolvers.js").then((m) => ({
      Query: (m.resolvers as { Query: { npcs: (p: unknown, a: { limit?: number; offset?: number; neighborhood?: string }, c: ResolverContext) => Promise<NPC[]> } }).Query,
    }));

    const npcs: NPC[] = [
      { id: "npc-001", name: "Alice", role: "merchant", gold: 100, hunger: 0, energy: 100, happiness: 80, neighborhood: "market", status: "ACTIVE" },
    ];

    const ctx = buildCtx({
      townCoreMethods: { ListNPCs: { npcs } },
    });

    const result = await Query.npcs(undefined, {}, ctx);
    expect(result).toHaveLength(1);
    expect(result[0]?.name).toBe("Alice");
  });
});

describe("Query.searchHistory", () => {
  it("returns empty results on gRPC error", async () => {
    const { Query } = await import("../resolvers.js").then((m) => ({
      Query: (m.resolvers as { Query: { searchHistory: (p: unknown, a: { query: string; types?: string[] }, c: ResolverContext) => Promise<{ total: number; results: unknown[] }> } }).Query,
    }));

    const ctx = buildCtx({});
    const result = await Query.searchHistory(undefined, { query: "test" }, ctx);
    expect(result.total).toBe(0);
    expect(result.results).toHaveLength(0);
  });
});
