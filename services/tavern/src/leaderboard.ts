import type Redis from "ioredis";
import type { LeaderboardEntry } from "./types.js";

const LEADERBOARD_KEY = "qtown:leaderboard:gold";

export class Leaderboard {
  constructor(private readonly redis: Redis) {}

  /**
   * Upserts an NPC's gold score in the sorted set.
   */
  async updateGold(npcId: string, gold: number): Promise<void> {
    await this.redis.zadd(LEADERBOARD_KEY, gold, npcId);
  }

  /**
   * Returns the top N NPCs by gold, highest first.
   */
  async getTopN(n: number): Promise<LeaderboardEntry[]> {
    // ZREVRANGE with WITHSCORES returns alternating [member, score, ...]
    const raw = await this.redis.zrevrange(LEADERBOARD_KEY, 0, n - 1, "WITHSCORES");
    return parseRangeWithScores(raw, 0);
  }

  /**
   * Returns the 1-based rank of an NPC (rank 1 = highest gold), or null if not present.
   */
  async getRank(npcId: string): Promise<number | null> {
    const rank = await this.redis.zrevrank(LEADERBOARD_KEY, npcId);
    if (rank === null) return null;
    return rank + 1; // convert 0-based to 1-based
  }

  /**
   * Returns a snapshot of the top 50 NPCs.
   */
  async getLeaderboardSnapshot(): Promise<LeaderboardEntry[]> {
    return this.getTopN(50);
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parseRangeWithScores(raw: string[], rankOffset: number): LeaderboardEntry[] {
  const entries: LeaderboardEntry[] = [];
  for (let i = 0; i < raw.length; i += 2) {
    const npcId = raw[i];
    const score = parseFloat(raw[i + 1]);
    entries.push({ npcId, score, rank: rankOffset + i / 2 + 1 });
  }
  return entries;
}
