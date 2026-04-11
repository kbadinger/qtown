import pino from "pino";
import type { NPC, Order, Dialogue, DecisionTrace, Event, LeaderboardRanks } from "../types.js";
import type { ResolverContext } from "../context.js";
import { grpcUnary } from "../grpc-clients.js";
import { cacheGet, cacheSet } from "../cache.js";

const logger = pino({ name: "npc-resolvers" });

// ============================================================================
// NPC field resolvers
// ============================================================================
// These resolvers are invoked per-NPC parent when the corresponding fields
// are requested. DataLoader is used to batch gRPC calls and prevent N+1.

export const NpcFieldResolvers = {
  /**
   * NPC.recentEvents — fetches events for this NPC from town-core.
   * DataLoader not applied here as events are fetched per-NPC;
   * an event loader could be added if this becomes a hotspot.
   */
  async recentEvents(
    parent: NPC,
    args: { limit?: number | null },
    ctx: ResolverContext
  ): Promise<Event[]> {
    const limit = args.limit ?? 10;
    logger.debug({ npcId: parent.id, limit }, "NPC.recentEvents");

    try {
      const response = await grpcUnary<
        { npc_id: string; limit: number },
        { events: Event[] }
      >(ctx.townCoreClient, "GetNPCEvents", { npc_id: parent.id, limit });
      return response.events ?? [];
    } catch (err) {
      logger.warn({ err, npcId: parent.id }, "NPC.recentEvents gRPC failed");
      return [];
    }
  },

  /**
   * NPC.orders — uses DataLoader to batch by npc_id.
   * Complexity cost: 10 per NPC field.
   */
  async orders(
    parent: NPC,
    args: { limit?: number | null },
    ctx: ResolverContext
  ): Promise<Order[]> {
    const limit = args.limit ?? 20;
    logger.debug({ npcId: parent.id, limit }, "NPC.orders (via DataLoader)");

    const orders = await ctx.dataLoaders.orderLoader.load(parent.id);
    return orders.slice(0, limit);
  },

  /**
   * NPC.dialogues — uses DataLoader to batch by npc_id.
   * Complexity cost: 10 per NPC field.
   */
  async dialogues(
    parent: NPC,
    args: { limit?: number | null },
    ctx: ResolverContext
  ): Promise<Dialogue[]> {
    const limit = args.limit ?? 10;
    logger.debug({ npcId: parent.id, limit }, "NPC.dialogues (via DataLoader)");

    const dialogues = await ctx.dataLoaders.dialogueLoader.load(parent.id);
    return dialogues.slice(0, limit);
  },

  /**
   * NPC.leaderboardRanks — fetches all three ranks via HTTP to Tavern's
   * leaderboard endpoint (cached for 10 s).
   */
  async leaderboardRanks(
    parent: NPC,
    _args: Record<string, never>,
    ctx: ResolverContext
  ): Promise<LeaderboardRanks> {
    const cacheKey = `leaderboard_ranks:${parent.id}`;
    const cached = await cacheGet<LeaderboardRanks>(ctx.redisCache, cacheKey);
    if (cached !== null) return cached;

    try {
      const response = await grpcUnary<
        { npc_id: string },
        { gold: number | null; happiness: number | null; crimes: number | null }
      >(ctx.townCoreClient, "GetNPCRanks", { npc_id: parent.id });

      const ranks: LeaderboardRanks = {
        gold: response.gold ?? null,
        happiness: response.happiness ?? null,
        crimes: response.crimes ?? null,
      };

      await cacheSet(ctx.redisCache, cacheKey, ranks, 10);
      return ranks;
    } catch (err) {
      logger.warn({ err, npcId: parent.id }, "NPC.leaderboardRanks failed");
      return { gold: null, happiness: null, crimes: null };
    }
  },

  /**
   * NPC.decisionTrace — fetches from academy service.
   */
  async decisionTrace(
    parent: NPC,
    args: { tick?: number | null },
    ctx: ResolverContext
  ): Promise<DecisionTrace | null> {
    logger.debug({ npcId: parent.id, tick: args.tick }, "NPC.decisionTrace");

    try {
      const response = await grpcUnary<
        { npc_id: string; tick?: number },
        { trace: DecisionTrace | null }
      >(ctx.academyClient, "GetDecisionTrace", {
        npc_id: parent.id,
        ...(args.tick !== null && args.tick !== undefined ? { tick: args.tick } : {}),
      });
      return response.trace ?? null;
    } catch (err) {
      logger.warn({ err, npcId: parent.id }, "NPC.decisionTrace gRPC failed");
      return null;
    }
  },
};
