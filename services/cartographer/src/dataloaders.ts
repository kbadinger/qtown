import DataLoader from "dataloader";
import pino from "pino";
import type * as grpc from "@grpc/grpc-js";
import { grpcUnary } from "./grpc-clients.js";
import type { NPC, Order, Dialogue, DataLoaders } from "./types.js";

const logger = pino({ name: "dataloaders" });

// ============================================================================
// NPC DataLoader
// ============================================================================

/**
 * Batches individual NPC lookups by ID into a single gRPC BatchGetNPCs call.
 * Prevents N+1 queries when resolving NPC fields on nested types.
 */
export function createNpcLoader(
  townCoreClient: grpc.Client
): DataLoader<string, NPC | null> {
  return new DataLoader<string, NPC | null>(
    async (ids) => {
      const idList = [...ids];
      logger.info(
        { count: idList.length, ids: idList },
        `batched ${idList.length} npc_ids into 1 gRPC call`
      );

      try {
        const response = await grpcUnary<{ ids: string[] }, { npcs: NPC[] }>(
          townCoreClient,
          "BatchGetNPCs",
          { ids: idList }
        );
        const npcMap = new Map<string, NPC>(
          (response.npcs ?? []).map((n) => [n.id, n])
        );
        return idList.map((id) => npcMap.get(id) ?? null);
      } catch (err) {
        logger.error({ err }, "NPC DataLoader batch failed — returning mock data");
        return idList.map((id) => makeMockNpc(id));
      }
    },
    {
      cache: true,
      batchScheduleFn: (cb) => setTimeout(cb, 0),
    }
  );
}

// ============================================================================
// Order DataLoader
// ============================================================================

/**
 * Batches order lookups by NPC ID into a single gRPC BatchGetOrders call.
 * Returns an array of orders per NPC ID.
 */
export function createOrderLoader(
  marketDistrictClient: grpc.Client
): DataLoader<string, Order[]> {
  return new DataLoader<string, Order[]>(
    async (npcIds) => {
      const idList = [...npcIds];
      logger.info(
        { count: idList.length, npc_ids: idList },
        `batched ${idList.length} npc_ids into 1 gRPC call (orders)`
      );

      try {
        const response = await grpcUnary<
          { npc_ids: string[] },
          { orders: Order[] }
        >(marketDistrictClient, "BatchGetOrders", { npc_ids: idList });

        const ordersByNpc = new Map<string, Order[]>();
        for (const order of response.orders ?? []) {
          const list = ordersByNpc.get(order.npcId) ?? [];
          list.push(order);
          ordersByNpc.set(order.npcId, list);
        }

        return idList.map((id) => ordersByNpc.get(id) ?? []);
      } catch (err) {
        logger.error({ err }, "Order DataLoader batch failed — returning empty arrays");
        return idList.map(() => []);
      }
    },
    {
      cache: true,
      batchScheduleFn: (cb) => setTimeout(cb, 0),
    }
  );
}

// ============================================================================
// Dialogue DataLoader
// ============================================================================

/**
 * Batches dialogue lookups by NPC ID into a single gRPC BatchGetDialogues call.
 * Returns an array of dialogues per NPC ID.
 */
export function createDialogueLoader(
  academyClient: grpc.Client
): DataLoader<string, Dialogue[]> {
  return new DataLoader<string, Dialogue[]>(
    async (npcIds) => {
      const idList = [...npcIds];
      logger.info(
        { count: idList.length, npc_ids: idList },
        `batched ${idList.length} npc_ids into 1 gRPC call (dialogues)`
      );

      try {
        const response = await grpcUnary<
          { npc_ids: string[] },
          { dialogues: Dialogue[] }
        >(academyClient, "BatchGetDialogues", { npc_ids: idList });

        const dialoguesByNpc = new Map<string, Dialogue[]>();
        for (const d of response.dialogues ?? []) {
          const list = dialoguesByNpc.get(d.npcId) ?? [];
          list.push(d);
          dialoguesByNpc.set(d.npcId, list);
        }

        return idList.map((id) => dialoguesByNpc.get(id) ?? []);
      } catch (err) {
        logger.error({ err }, "Dialogue DataLoader batch failed — returning empty arrays");
        return idList.map(() => []);
      }
    },
    {
      cache: true,
      batchScheduleFn: (cb) => setTimeout(cb, 0),
    }
  );
}

// ============================================================================
// DataLoader context factory
// ============================================================================

/**
 * Creates a fresh set of per-request DataLoaders.
 * Must be called once per GraphQL request to ensure correct cache scoping.
 */
export function createDataLoaders(
  townCoreClient: grpc.Client,
  marketDistrictClient: grpc.Client,
  academyClient: grpc.Client
): DataLoaders {
  return {
    npcLoader: createNpcLoader(townCoreClient),
    orderLoader: createOrderLoader(marketDistrictClient),
    dialogueLoader: createDialogueLoader(academyClient),
  };
}

// ============================================================================
// Mock factories (fallback when gRPC services are unavailable)
// ============================================================================

function makeMockNpc(id: string): NPC {
  return {
    id,
    name: `NPC-${id}`,
    role: "citizen",
    gold: 0,
    hunger: 50,
    energy: 80,
    happiness: 50,
    neighborhood: null,
    status: "ACTIVE",
  };
}
