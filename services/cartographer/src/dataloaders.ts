import DataLoader from "dataloader";
import type * as grpc from "@grpc/grpc-js";
import pino from "pino";
import type { NPC, Order } from "./types.js";

const logger = pino({ name: "dataloaders" });

// ---------------------------------------------------------------------------
// NPC DataLoader
// ---------------------------------------------------------------------------
// Batches individual NPC lookups by ID into a single gRPC call, preventing
// the N+1 query problem when resolving NPC fields inside nested resolvers.

export function createNpcLoader(townCoreClient: grpc.Client): DataLoader<string, NPC | null> {
  return new DataLoader<string, NPC | null>(
    async (ids) => {
      logger.debug({ ids }, "NPC DataLoader batch");

      try {
        const npcs = await callGetNpcsByIds(townCoreClient, ids as string[]);
        // Build a lookup map so results align with input ids order
        const map = new Map<string, NPC>(npcs.map((n) => [n.id, n]));
        return ids.map((id) => map.get(id) ?? null);
      } catch (err) {
        logger.error({ err }, "NPC DataLoader batch failed — returning mock data");
        // Return mock NPCs so the resolver still has something to work with
        return ids.map((id) => createMockNpc(id));
      }
    },
    {
      // Cache within a single request to avoid redundant calls
      cache: true,
      // Coalesce all loads within the same tick
      batchScheduleFn: (callback) => setTimeout(callback, 0),
    }
  );
}

// ---------------------------------------------------------------------------
// Order DataLoader
// ---------------------------------------------------------------------------
// Batches order lookups by order ID.

export function createOrderLoader(marketClient: grpc.Client): DataLoader<string, Order | null> {
  return new DataLoader<string, Order | null>(
    async (ids) => {
      logger.debug({ ids }, "Order DataLoader batch");

      try {
        const orders = await callGetOrdersByIds(marketClient, ids as string[]);
        const map = new Map<string, Order>(orders.map((o) => [o.id, o]));
        return ids.map((id) => map.get(id) ?? null);
      } catch (err) {
        logger.error({ err }, "Order DataLoader batch failed — returning nulls");
        return ids.map(() => null);
      }
    },
    {
      cache: true,
      batchScheduleFn: (callback) => setTimeout(callback, 0),
    }
  );
}

// ---------------------------------------------------------------------------
// DataLoader context factory
// ---------------------------------------------------------------------------

export interface Dataloaders {
  npcLoader: DataLoader<string, NPC | null>;
  orderLoader: DataLoader<string, Order | null>;
}

/**
 * Creates a fresh set of DataLoaders per request.
 * Each GraphQL request should call this to get per-request-scoped loaders
 * (prevents cross-request cache bleed).
 */
export function createDataloaders(
  townCoreClient: grpc.Client,
  marketClient: grpc.Client
): Dataloaders {
  return {
    npcLoader: createNpcLoader(townCoreClient),
    orderLoader: createOrderLoader(marketClient),
  };
}

// ---------------------------------------------------------------------------
// gRPC stub calls
// ---------------------------------------------------------------------------
// These are thin wrappers around gRPC unary calls.  They will be wired to
// real proto-generated methods once the .proto files land in /protos.

function callGetNpcsByIds(client: grpc.Client, ids: string[]): Promise<NPC[]> {
  return new Promise((resolve, reject) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const method = (client as any).GetNpcsByIds;
    if (typeof method !== "function") {
      // Proto not loaded yet — return mocks
      logger.debug("GetNpcsByIds not found on client — using mock data");
      return resolve(ids.map(createMockNpc));
    }

    method.call(
      client,
      { ids },
      (err: grpc.ServiceError | null, response: { npcs: NPC[] }) => {
        if (err) return reject(err);
        resolve(response?.npcs ?? []);
      }
    );
  });
}

function callGetOrdersByIds(client: grpc.Client, ids: string[]): Promise<Order[]> {
  return new Promise((resolve, reject) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const method = (client as any).GetOrdersByIds;
    if (typeof method !== "function") {
      logger.debug("GetOrdersByIds not found on client — returning empty orders");
      return resolve([]);
    }

    method.call(
      client,
      { ids },
      (err: grpc.ServiceError | null, response: { orders: Order[] }) => {
        if (err) return reject(err);
        resolve(response?.orders ?? []);
      }
    );
  });
}

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

function createMockNpc(id: string): NPC {
  return {
    id,
    name: `NPC-${id}`,
    gold: 0,
    happiness: 50,
    neighborhood: "unknown",
    location: { x: 0, y: 0 },
  };
}
