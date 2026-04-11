import pino from "pino";
import type { RedisClient } from "./redis.js";
import type { LeaderboardEntry, LeaderboardType } from "./types.js";

const logger = pino({ name: "leaderboard" });

// ============================================================================
// Redis key definitions
// ============================================================================

const LEADERBOARD_KEYS: Record<LeaderboardType, string> = {
  gold: "qtown:leaderboard:gold",
  happiness: "qtown:leaderboard:happiness",
  crimes: "qtown:leaderboard:crimes",
};

// ============================================================================
// Leaderboard
// ============================================================================

export class Leaderboard {
  constructor(private readonly redis: RedisClient) {}

  // --------------------------------------------------------------------------
  // Update methods — called from Kafka consumer
  // --------------------------------------------------------------------------

  async updateGoldLeaderboard(npcId: string, gold: number): Promise<void> {
    await this.redis.zadd(LEADERBOARD_KEYS.gold, gold, npcId);
    logger.debug({ npcId, gold }, "Updated gold leaderboard");
  }

  async updateHappinessLeaderboard(npcId: string, happiness: number): Promise<void> {
    await this.redis.zadd(LEADERBOARD_KEYS.happiness, happiness, npcId);
    logger.debug({ npcId, happiness }, "Updated happiness leaderboard");
  }

  async updateCrimeLeaderboard(npcId: string, crimes: number): Promise<void> {
    await this.redis.zadd(LEADERBOARD_KEYS.crimes, crimes, npcId);
    logger.debug({ npcId, crimes }, "Updated crime leaderboard");
  }

  // --------------------------------------------------------------------------
  // Query methods
  // --------------------------------------------------------------------------

  /**
   * Returns leaderboard entries sorted by score descending.
   * Returns { npc_id, name, score, rank } — name defaults to npc_id until
   * a NPC name service enrichment layer is added.
   */
  async getLeaderboard(
    type: LeaderboardType,
    offset = 0,
    limit = 10
  ): Promise<LeaderboardEntry[]> {
    const key = LEADERBOARD_KEYS[type];
    const raw = await this.redis.zrevrange(key, offset, offset + limit - 1, true);
    return parseWithScores(raw, offset);
  }

  /**
   * Returns the 1-based rank of an NPC in the given leaderboard.
   * null if the NPC is not ranked.
   */
  async getRank(type: LeaderboardType, npcId: string): Promise<number | null> {
    const key = LEADERBOARD_KEYS[type];
    const rank = await this.redis.zrevrank(key, npcId);
    if (rank === null) return null;
    return rank + 1; // 0-indexed → 1-indexed
  }

  /**
   * Returns all three ranks for a given NPC.
   */
  async getAllRanks(npcId: string): Promise<{
    gold: number | null;
    happiness: number | null;
    crimes: number | null;
  }> {
    const [gold, happiness, crimes] = await Promise.all([
      this.getRank("gold", npcId),
      this.getRank("happiness", npcId),
      this.getRank("crimes", npcId),
    ]);
    return { gold, happiness, crimes };
  }
}

// ============================================================================
// Helpers
// ============================================================================

function parseWithScores(raw: string[], offset: number): LeaderboardEntry[] {
  const entries: LeaderboardEntry[] = [];
  for (let i = 0; i < raw.length; i += 2) {
    const npc_id = raw[i] ?? "";
    const scoreStr = raw[i + 1] ?? "0";
    const score = parseFloat(scoreStr);
    const rank = offset + Math.floor(i / 2) + 1;
    entries.push({ npc_id, name: npc_id, score, rank });
  }
  return entries;
}
