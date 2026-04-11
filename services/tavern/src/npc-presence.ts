import pino from "pino";
import type { RedisClient } from "./redis.js";
import type { NPCPresence, NPCStatus } from "./types.js";

const logger = pino({ name: "npc-presence" });

const PRESENCE_KEY_PREFIX = "npc_presence:";

// ============================================================================
// NPCPresenceTracker
// ============================================================================

export class NPCPresenceTracker {
  constructor(private readonly redis: RedisClient) {}

  // --------------------------------------------------------------------------
  // Write
  // --------------------------------------------------------------------------

  /**
   * Upserts an NPC's presence data in Redis.
   * Key: npc_presence:{npc_id}
   * Fields: neighborhood, building, status, updated_at
   */
  async updatePresence(
    npcId: string,
    neighborhood: string,
    building: string,
    status: NPCStatus
  ): Promise<void> {
    const key = `${PRESENCE_KEY_PREFIX}${npcId}`;
    const updated_at = new Date().toISOString();

    await this.redis.hset(key, {
      npc_id: npcId,
      neighborhood,
      building,
      status,
      updated_at,
    });

    logger.debug({ npcId, neighborhood, building, status }, "Updated NPC presence");
  }

  // --------------------------------------------------------------------------
  // Read single
  // --------------------------------------------------------------------------

  /**
   * Returns an NPC's current presence data, or null if not tracked.
   */
  async getPresence(npcId: string): Promise<NPCPresence | null> {
    const key = `${PRESENCE_KEY_PREFIX}${npcId}`;
    const fields = await this.redis.hgetall(key);
    if (!fields) return null;
    return parsePresence(fields);
  }

  // --------------------------------------------------------------------------
  // Read all
  // --------------------------------------------------------------------------

  /**
   * Returns all NPC presence records via SCAN on the npc_presence:* pattern.
   * May return stale entries if NPCs have not been cleaned up.
   */
  async getAllPresence(): Promise<NPCPresence[]> {
    const keys = await this.redis.scan(`${PRESENCE_KEY_PREFIX}*`);

    if (keys.length === 0) return [];

    const results = await Promise.all(
      keys.map(async (key) => {
        const fields = await this.redis.hgetall(key);
        return fields ? parsePresence(fields) : null;
      })
    );

    const presences = results.filter(
      (p): p is NPCPresence => p !== null
    );

    logger.debug({ count: presences.length }, "Fetched all NPC presences");
    return presences;
  }
}

// ============================================================================
// Helpers
// ============================================================================

function parsePresence(fields: Record<string, string>): NPCPresence {
  return {
    npc_id: fields["npc_id"] ?? "",
    neighborhood: fields["neighborhood"] ?? "",
    building: fields["building"] ?? "",
    status: (fields["status"] ?? "active") as NPCStatus,
    updated_at: fields["updated_at"] ?? new Date().toISOString(),
  };
}
