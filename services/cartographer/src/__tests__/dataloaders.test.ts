import { describe, it, expect, vi, beforeEach } from "vitest";
import DataLoader from "dataloader";
import type { NPC, Order, Dialogue } from "../types.js";

// ============================================================================
// Mock gRPC client
// ============================================================================

type GrpcCallback<T> = (err: null | Error, res: T) => void;
type MockFn<TReq, TRes> = (req: TReq, meta: unknown, opts: unknown, cb: GrpcCallback<TRes>) => void;

function makeMockGrpcClient<TReq, TRes>(
  methodName: string,
  handler: (req: TReq) => TRes
): { [key: string]: MockFn<TReq, TRes> } {
  return {
    [methodName]: (req: TReq, _meta: unknown, _opts: unknown, cb: GrpcCallback<TRes>) => {
      try {
        cb(null, handler(req));
      } catch (err) {
        cb(err as Error, {} as TRes);
      }
    },
  };
}

// ============================================================================
// NPC DataLoader tests
// ============================================================================

describe("NPC DataLoader", () => {
  it("batches multiple IDs into a single gRPC call", async () => {
    const batchFn = vi.fn((req: { ids: string[] }) => ({
      npcs: req.ids.map((id) => ({
        id,
        name: `NPC-${id}`,
        role: "citizen",
        gold: 100,
        hunger: 50,
        energy: 80,
        happiness: 60,
        neighborhood: "market",
        status: "ACTIVE" as const,
      })),
    }));

    const client = makeMockGrpcClient<{ ids: string[] }, { npcs: NPC[] }>(
      "BatchGetNPCs",
      batchFn
    );

    const { createNpcLoader } = await import("../dataloaders.js");
    const loader = createNpcLoader(client as unknown as import("@grpc/grpc-js").Client);

    // Load 3 NPCs concurrently — should batch into 1 gRPC call
    const [npc1, npc2, npc3] = await Promise.all([
      loader.load("npc-001"),
      loader.load("npc-002"),
      loader.load("npc-003"),
    ]);

    // Verify all NPCs loaded correctly
    expect(npc1?.id).toBe("npc-001");
    expect(npc2?.id).toBe("npc-002");
    expect(npc3?.id).toBe("npc-003");

    // The batch function should have been called exactly once
    expect(batchFn).toHaveBeenCalledTimes(1);
    const callArg = batchFn.mock.calls[0]?.[0];
    expect(callArg?.ids).toHaveLength(3);
    expect(callArg?.ids).toContain("npc-001");
    expect(callArg?.ids).toContain("npc-002");
    expect(callArg?.ids).toContain("npc-003");
  });

  it("returns null for missing NPCs", async () => {
    const client = makeMockGrpcClient<{ ids: string[] }, { npcs: NPC[] }>(
      "BatchGetNPCs",
      (req) => ({
        // Only return npc-001, not npc-unknown
        npcs: req.ids
          .filter((id) => id === "npc-001")
          .map((id) => ({
            id,
            name: "Alice",
            role: "merchant",
            gold: 500,
            hunger: 20,
            energy: 90,
            happiness: 85,
            neighborhood: "market",
            status: "ACTIVE" as const,
          })),
      })
    );

    const { createNpcLoader } = await import("../dataloaders.js");
    const loader = createNpcLoader(client as unknown as import("@grpc/grpc-js").Client);

    const [npc1, npcUnknown] = await Promise.all([
      loader.load("npc-001"),
      loader.load("npc-unknown"),
    ]);

    expect(npc1?.id).toBe("npc-001");
    expect(npcUnknown).toBeNull();
  });

  it("caches within a single request", async () => {
    const batchFn = vi.fn((req: { ids: string[] }) => ({
      npcs: req.ids.map((id) => ({
        id,
        name: `NPC-${id}`,
        role: "citizen",
        gold: 0,
        hunger: 0,
        energy: 0,
        happiness: 0,
        neighborhood: null,
        status: "ACTIVE" as const,
      })),
    }));

    const client = makeMockGrpcClient<{ ids: string[] }, { npcs: NPC[] }>(
      "BatchGetNPCs",
      batchFn
    );

    const { createNpcLoader } = await import("../dataloaders.js");
    const loader = createNpcLoader(client as unknown as import("@grpc/grpc-js").Client);

    // Load same NPC twice — should only hit gRPC once
    await loader.load("npc-001");
    await loader.load("npc-001");

    expect(batchFn).toHaveBeenCalledTimes(1);
  });

  it("returns mock data on gRPC error", async () => {
    const failingClient = {
      BatchGetNPCs: (
        _req: { ids: string[] },
        _meta: unknown,
        _opts: unknown,
        cb: (err: Error, res: { npcs: NPC[] }) => void
      ) => {
        cb(new Error("gRPC connection failed"), { npcs: [] });
      },
    };

    const { createNpcLoader } = await import("../dataloaders.js");
    const loader = createNpcLoader(
      failingClient as unknown as import("@grpc/grpc-js").Client
    );

    const result = await loader.load("npc-001");
    // On error, returns mock NPC (not null)
    expect(result).not.toBeNull();
    expect(result?.id).toBe("npc-001");
    expect(result?.name).toBe("NPC-npc-001");
  });
});

// ============================================================================
// Order DataLoader tests
// ============================================================================

describe("Order DataLoader", () => {
  it("batches order lookups by NPC ID", async () => {
    const orders: Order[] = [
      { id: "order-1", npcId: "npc-001", side: "BUY", resource: "wood", price: 50, quantity: 10, status: "OPEN", createdAt: "2024-01-01T00:00:00Z" },
      { id: "order-2", npcId: "npc-001", side: "SELL", resource: "stone", price: 80, quantity: 5, status: "OPEN", createdAt: "2024-01-01T00:00:00Z" },
      { id: "order-3", npcId: "npc-002", side: "BUY", resource: "food", price: 20, quantity: 20, status: "OPEN", createdAt: "2024-01-01T00:00:00Z" },
    ];

    const batchFn = vi.fn((_req: { npc_ids: string[] }) => ({ orders }));

    const client = makeMockGrpcClient<{ npc_ids: string[] }, { orders: Order[] }>(
      "BatchGetOrders",
      batchFn
    );

    const { createOrderLoader } = await import("../dataloaders.js");
    const loader = createOrderLoader(client as unknown as import("@grpc/grpc-js").Client);

    const [npc1Orders, npc2Orders] = await Promise.all([
      loader.load("npc-001"),
      loader.load("npc-002"),
    ]);

    expect(batchFn).toHaveBeenCalledTimes(1);
    expect(npc1Orders).toHaveLength(2);
    expect(npc2Orders).toHaveLength(1);
    expect(npc1Orders[0]?.npcId).toBe("npc-001");
    expect(npc2Orders[0]?.resource).toBe("food");
  });

  it("returns empty array for NPC with no orders", async () => {
    const client = makeMockGrpcClient<{ npc_ids: string[] }, { orders: Order[] }>(
      "BatchGetOrders",
      () => ({ orders: [] })
    );

    const { createOrderLoader } = await import("../dataloaders.js");
    const loader = createOrderLoader(client as unknown as import("@grpc/grpc-js").Client);

    const result = await loader.load("npc-999");
    expect(result).toHaveLength(0);
  });
});

// ============================================================================
// Dialogue DataLoader tests
// ============================================================================

describe("Dialogue DataLoader", () => {
  it("batches dialogue lookups by NPC ID", async () => {
    const dialogues: Dialogue[] = [
      { id: "d1", npcId: "npc-001", text: "Hello world", context: null, generatedAt: "2024-01-01T00:00:00Z" },
      { id: "d2", npcId: "npc-002", text: "Good day!", context: "market", generatedAt: "2024-01-01T00:00:00Z" },
    ];

    const batchFn = vi.fn((_req: { npc_ids: string[] }) => ({ dialogues }));
    const client = makeMockGrpcClient<{ npc_ids: string[] }, { dialogues: Dialogue[] }>(
      "BatchGetDialogues",
      batchFn
    );

    const { createDialogueLoader } = await import("../dataloaders.js");
    const loader = createDialogueLoader(client as unknown as import("@grpc/grpc-js").Client);

    const [npc1Dialogues, npc2Dialogues] = await Promise.all([
      loader.load("npc-001"),
      loader.load("npc-002"),
    ]);

    expect(batchFn).toHaveBeenCalledTimes(1);
    expect(npc1Dialogues[0]?.text).toBe("Hello world");
    expect(npc2Dialogues[0]?.context).toBe("market");
  });
});

// ============================================================================
// createDataLoaders integration test
// ============================================================================

describe("createDataLoaders", () => {
  it("creates all three loaders", async () => {
    const emptyClient = makeMockGrpcClient("stub", () => ({}));
    const client = emptyClient as unknown as import("@grpc/grpc-js").Client;

    const { createDataLoaders } = await import("../dataloaders.js");
    const loaders = createDataLoaders(client, client, client);

    expect(loaders.npcLoader).toBeDefined();
    expect(loaders.orderLoader).toBeDefined();
    expect(loaders.dialogueLoader).toBeDefined();
    expect(typeof loaders.npcLoader.load).toBe("function");
    expect(typeof loaders.orderLoader.load).toBe("function");
    expect(typeof loaders.dialogueLoader.load).toBe("function");
  });

  it("creates independent loaders per call (separate cache scopes)", async () => {
    const emptyClient = makeMockGrpcClient("stub", () => ({}));
    const client = emptyClient as unknown as import("@grpc/grpc-js").Client;

    const { createDataLoaders } = await import("../dataloaders.js");
    const loaders1 = createDataLoaders(client, client, client);
    const loaders2 = createDataLoaders(client, client, client);

    expect(loaders1.npcLoader).not.toBe(loaders2.npcLoader);
    expect(loaders1.orderLoader).not.toBe(loaders2.orderLoader);
  });
});
