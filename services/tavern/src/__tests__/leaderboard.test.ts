import { describe, it, expect, vi, beforeEach } from "vitest";
import { Leaderboard } from "../leaderboard.js";
import type { RedisClient } from "../redis.js";
import type { LeaderboardType } from "../types.js";

// ============================================================================
// Mock RedisClient
// ============================================================================

/**
 * In-memory implementation of the sorted set operations used by Leaderboard.
 * Stores { key → Map<member, score> }.
 */
class MockRedisClient {
  private readonly sortedSets = new Map<string, Map<string, number>>();

  async zadd(key: string, score: number, member: string): Promise<number> {
    if (!this.sortedSets.has(key)) {
      this.sortedSets.set(key, new Map());
    }
    const isNew = !this.sortedSets.get(key)!.has(member) ? 1 : 0;
    this.sortedSets.get(key)!.set(member, score);
    return isNew;
  }

  async zrevrange(
    key: string,
    start: number,
    stop: number,
    withScores = false
  ): Promise<string[]> {
    const set = this.sortedSets.get(key);
    if (!set) return [];

    const sorted = [...set.entries()].sort(([, a], [, b]) => b - a);
    const endIdx = stop === -1 ? sorted.length : stop + 1;
    const slice = sorted.slice(start, endIdx);

    if (withScores) {
      return slice.flatMap(([member, score]) => [member, score.toString()]);
    }
    return slice.map(([member]) => member);
  }

  async zrevrank(key: string, member: string): Promise<number | null> {
    const set = this.sortedSets.get(key);
    if (!set) return null;

    const sorted = [...set.entries()].sort(([, a], [, b]) => b - a);
    const idx = sorted.findIndex(([m]) => m === member);
    return idx === -1 ? null : idx;
  }

  async zcard(key: string): Promise<number> {
    return this.sortedSets.get(key)?.size ?? 0;
  }

  // Stub out other RedisClient methods we don't need for leaderboard
  async publish(): Promise<number> { return 0; }
  async hset(): Promise<number> { return 0; }
  async hget(): Promise<string | null> { return null; }
  async hgetall(): Promise<Record<string, string> | null> { return null; }
  async scan(): Promise<string[]> { return []; }
  async set(): Promise<string | null> { return "OK"; }
  async get(): Promise<string | null> { return null; }
  async del(): Promise<number> { return 0; }
  async zrange(): Promise<string[]> { return []; }
  async subscribe(): Promise<void> {}
  raw() { return null as unknown; }
  duplicate() { return null as unknown; }
  disconnect() {}
}

// ============================================================================
// Tests
// ============================================================================

describe("Leaderboard", () => {
  let redis: MockRedisClient;
  let leaderboard: Leaderboard;

  beforeEach(() => {
    redis = new MockRedisClient();
    leaderboard = new Leaderboard(redis as unknown as RedisClient);
  });

  // --------------------------------------------------------------------------
  // Gold leaderboard
  // --------------------------------------------------------------------------

  describe("gold leaderboard", () => {
    it("adds and retrieves a gold entry", async () => {
      await leaderboard.updateGoldLeaderboard("npc-001", 500);
      const entries = await leaderboard.getLeaderboard("gold", 0, 10);
      expect(entries).toHaveLength(1);
      expect(entries[0]!.npc_id).toBe("npc-001");
      expect(entries[0]!.score).toBe(500);
      expect(entries[0]!.rank).toBe(1);
    });

    it("returns entries sorted by score descending", async () => {
      await leaderboard.updateGoldLeaderboard("npc-001", 100);
      await leaderboard.updateGoldLeaderboard("npc-002", 500);
      await leaderboard.updateGoldLeaderboard("npc-003", 300);

      const entries = await leaderboard.getLeaderboard("gold", 0, 10);
      expect(entries[0]!.npc_id).toBe("npc-002");
      expect(entries[0]!.score).toBe(500);
      expect(entries[1]!.npc_id).toBe("npc-003");
      expect(entries[2]!.npc_id).toBe("npc-001");
    });

    it("respects limit parameter", async () => {
      for (let i = 1; i <= 5; i++) {
        await leaderboard.updateGoldLeaderboard(`npc-00${i}`, i * 100);
      }
      const entries = await leaderboard.getLeaderboard("gold", 0, 3);
      expect(entries).toHaveLength(3);
    });

    it("respects offset parameter", async () => {
      await leaderboard.updateGoldLeaderboard("npc-001", 300);
      await leaderboard.updateGoldLeaderboard("npc-002", 200);
      await leaderboard.updateGoldLeaderboard("npc-003", 100);

      const entries = await leaderboard.getLeaderboard("gold", 1, 2);
      expect(entries).toHaveLength(2);
      expect(entries[0]!.npc_id).toBe("npc-002"); // rank 2
      expect(entries[0]!.rank).toBe(2);
    });

    it("updates existing gold score", async () => {
      await leaderboard.updateGoldLeaderboard("npc-001", 100);
      await leaderboard.updateGoldLeaderboard("npc-001", 999);

      const entries = await leaderboard.getLeaderboard("gold", 0, 10);
      expect(entries).toHaveLength(1);
      expect(entries[0]!.score).toBe(999);
    });
  });

  // --------------------------------------------------------------------------
  // Happiness leaderboard
  // --------------------------------------------------------------------------

  describe("happiness leaderboard", () => {
    it("tracks happiness separately from gold", async () => {
      await leaderboard.updateGoldLeaderboard("npc-001", 1000);
      await leaderboard.updateHappinessLeaderboard("npc-002", 95);

      const gold = await leaderboard.getLeaderboard("gold", 0, 10);
      const happiness = await leaderboard.getLeaderboard("happiness", 0, 10);

      expect(gold).toHaveLength(1);
      expect(gold[0]!.npc_id).toBe("npc-001");

      expect(happiness).toHaveLength(1);
      expect(happiness[0]!.npc_id).toBe("npc-002");
    });
  });

  // --------------------------------------------------------------------------
  // Crime leaderboard
  // --------------------------------------------------------------------------

  describe("crime leaderboard", () => {
    it("tracks crime counts", async () => {
      await leaderboard.updateCrimeLeaderboard("npc-villain", 10);
      await leaderboard.updateCrimeLeaderboard("npc-petty", 2);

      const entries = await leaderboard.getLeaderboard("crimes", 0, 10);
      expect(entries[0]!.npc_id).toBe("npc-villain");
      expect(entries[0]!.score).toBe(10);
    });
  });

  // --------------------------------------------------------------------------
  // getRank
  // --------------------------------------------------------------------------

  describe("getRank", () => {
    it("returns correct 1-based rank", async () => {
      await leaderboard.updateGoldLeaderboard("npc-001", 300);
      await leaderboard.updateGoldLeaderboard("npc-002", 100);
      await leaderboard.updateGoldLeaderboard("npc-003", 200);

      expect(await leaderboard.getRank("gold", "npc-001")).toBe(1);
      expect(await leaderboard.getRank("gold", "npc-003")).toBe(2);
      expect(await leaderboard.getRank("gold", "npc-002")).toBe(3);
    });

    it("returns null for unknown NPC", async () => {
      const rank = await leaderboard.getRank("gold", "npc-unknown");
      expect(rank).toBeNull();
    });
  });

  // --------------------------------------------------------------------------
  // getAllRanks
  // --------------------------------------------------------------------------

  describe("getAllRanks", () => {
    it("returns all three ranks in one call", async () => {
      await leaderboard.updateGoldLeaderboard("npc-001", 500);
      await leaderboard.updateHappinessLeaderboard("npc-001", 80);
      // no crime entry

      const ranks = await leaderboard.getAllRanks("npc-001");
      expect(ranks.gold).toBe(1);
      expect(ranks.happiness).toBe(1);
      expect(ranks.crimes).toBeNull();
    });
  });

  // --------------------------------------------------------------------------
  // Empty leaderboard
  // --------------------------------------------------------------------------

  it("returns empty array for empty leaderboard", async () => {
    const entries = await leaderboard.getLeaderboard("gold", 0, 10);
    expect(entries).toHaveLength(0);
  });

  // --------------------------------------------------------------------------
  // Type safety: rejects invalid type at runtime guard level
  // --------------------------------------------------------------------------

  it("accepts all valid leaderboard types", async () => {
    const types: LeaderboardType[] = ["gold", "happiness", "crimes"];
    for (const type of types) {
      const result = await leaderboard.getLeaderboard(type, 0, 1);
      expect(Array.isArray(result)).toBe(true);
    }
  });
});
