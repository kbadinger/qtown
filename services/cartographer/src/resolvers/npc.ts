import DataLoader from "dataloader";
import type { IResolvers } from "@graphql-tools/utils";

// ---------------------------------------------------------------------------
// Types (local approximations until gRPC stubs are generated)
// ---------------------------------------------------------------------------

export interface NPCRecord {
  id: string;
  name: string;
  district: string;
  gold: number;
  occupation?: string;
  mood?: string;
}

export interface OrderRecord {
  id: string;
  npcId: string;
  resource: string;
  side: "BID" | "ASK";
  price: number;
  quantity: number;
  timestamp: string;
}

export interface DialogueRecord {
  id: string;
  npcId: string;
  speaker: string;
  text: string;
  timestamp: string;
  context?: Record<string, unknown>;
}

export interface LeaderboardEntryRecord {
  metric: string;
  npcId: string;
  npcName: string;
  score: number;
  rank: number;
}

// ---------------------------------------------------------------------------
// gRPC client stubs (replace with real generated stubs)
// ---------------------------------------------------------------------------

/**
 * Placeholder — fetches NPC records from the NPC gRPC service.
 * Replace with a real tonic/grpc-js channel call.
 */
async function fetchNPCsFromGRPC(ids: readonly string[]): Promise<NPCRecord[]> {
  // TODO: implement gRPC call to npc-service:50054
  // const channel = grpc.credentials.createInsecure();
  // const client = new NPCServiceClient("npc-service:50054", channel);
  // return client.batchGetNPCs({ ids });
  return ids.map((id) => ({
    id,
    name: `NPC-${id}`,
    district: "market",
    gold: 100,
    occupation: "merchant",
    mood: "content",
  }));
}

/**
 * Placeholder — fetches open orders for a list of NPC IDs from Market District.
 */
async function fetchOrdersForNPCs(npcIds: readonly string[]): Promise<Map<string, OrderRecord[]>> {
  // TODO: implement gRPC call to market-district:50051
  const result = new Map<string, OrderRecord[]>();
  for (const npcId of npcIds) {
    result.set(npcId, []);
  }
  return result;
}

/**
 * Placeholder — fetches recent dialogues for a list of NPC IDs from Academy.
 */
async function fetchDialoguesForNPCs(npcIds: readonly string[]): Promise<Map<string, DialogueRecord[]>> {
  // TODO: implement gRPC call to academy:50053
  const result = new Map<string, DialogueRecord[]>();
  for (const npcId of npcIds) {
    result.set(npcId, []);
  }
  return result;
}

/**
 * Placeholder — fetches leaderboard rank from Redis (via Tavern service or directly).
 */
async function fetchLeaderboardRank(
  npcId: string,
  metric: string
): Promise<LeaderboardEntryRecord | null> {
  // TODO: connect to Redis and use ZREVRANK + ZSCORE on lb:<metric>
  return null;
}

// ---------------------------------------------------------------------------
// DataLoaders
// ---------------------------------------------------------------------------

/**
 * Batch-loads NPC records by ID.  One gRPC call per batch rather than N.
 */
export function createNPCLoader(): DataLoader<string, NPCRecord | null> {
  return new DataLoader<string, NPCRecord | null>(async (ids) => {
    const records = await fetchNPCsFromGRPC(ids);
    const byId = new Map(records.map((r) => [r.id, r]));
    return ids.map((id) => byId.get(id) ?? null);
  });
}

/**
 * Batch-loads all open orders grouped by NPC ID.
 */
export function createOrdersLoader(): DataLoader<string, OrderRecord[]> {
  return new DataLoader<string, OrderRecord[]>(async (npcIds) => {
    const map = await fetchOrdersForNPCs(npcIds);
    return npcIds.map((id) => map.get(id) ?? []);
  });
}

/**
 * Batch-loads dialogue history grouped by NPC ID.
 */
export function createDialoguesLoader(): DataLoader<string, DialogueRecord[]> {
  return new DataLoader<string, DialogueRecord[]>(async (npcIds) => {
    const map = await fetchDialoguesForNPCs(npcIds);
    return npcIds.map((id) => map.get(id) ?? []);
  });
}

// ---------------------------------------------------------------------------
// Resolver context type
// ---------------------------------------------------------------------------

export interface ResolverContext {
  loaders: {
    npc: DataLoader<string, NPCRecord | null>;
    orders: DataLoader<string, OrderRecord[]>;
    dialogues: DataLoader<string, DialogueRecord[]>;
  };
}

export function createLoaders(): ResolverContext["loaders"] {
  return {
    npc: createNPCLoader(),
    orders: createOrdersLoader(),
    dialogues: createDialoguesLoader(),
  };
}

// ---------------------------------------------------------------------------
// NPC resolvers
// ---------------------------------------------------------------------------

export const npcResolvers: IResolvers<unknown, ResolverContext> = {
  Query: {
    npc: async (_parent, args: { id: string }, ctx) => {
      return ctx.loaders.npc.load(args.id);
    },

    npcs: async (
      _parent,
      args: { district?: string; occupation?: string; limit?: number; offset?: number },
      _ctx
    ) => {
      // TODO: delegate to npc-service gRPC with filter args.
      const { limit = 20, offset = 0 } = args;
      console.log("[cartographer] npcs query", { ...args, limit, offset });
      return [];
    },
  },

  NPC: {
    orders: async (parent: NPCRecord, _args, ctx) => {
      return ctx.loaders.orders.load(parent.id);
    },

    dialogues: async (parent: NPCRecord, _args, ctx) => {
      return ctx.loaders.dialogues.load(parent.id);
    },

    leaderboardRank: async (
      parent: NPCRecord,
      args: { metric: string },
      _ctx
    ) => {
      return fetchLeaderboardRank(parent.id, args.metric);
    },
  },
};
