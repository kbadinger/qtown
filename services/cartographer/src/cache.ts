import Redis from "ioredis";
import pino from "pino";
import { createHash } from "crypto";

const logger = pino({ name: "cache" });

// ============================================================================
// TTL presets (seconds)
// ============================================================================

export const CACHE_TTL = {
  worldState: 5,
  leaderboard: 10,
  newspaper: 60,
  npcRanks: 10,
  orderBook: 3,
  searchResults: 30,
} as const;

// ============================================================================
// RedisCache type (thin ioredis wrapper passed around context)
// ============================================================================

export type RedisCache = Redis;

// ============================================================================
// Factory
// ============================================================================

export function createRedisCache(redisUrl: string): RedisCache {
  const client = new Redis(redisUrl, {
    maxRetriesPerRequest: 2,
    enableReadyCheck: false,
    lazyConnect: true,
  });

  client.on("error", (err: Error) =>
    logger.warn({ err }, "Cache Redis error — cache miss will be returned")
  );

  client.connect().catch((err: unknown) => {
    logger.warn({ err }, "Cache Redis initial connection failed — running uncached");
  });

  return client;
}

// ============================================================================
// Cache operations
// ============================================================================

/**
 * Returns cached value or null on miss/error.
 * Key is used as-is (caller should namespace appropriately).
 */
export async function cacheGet<T>(
  redis: RedisCache,
  key: string
): Promise<T | null> {
  try {
    const raw = await redis.get(key);
    if (raw === null) return null;
    return JSON.parse(raw) as T;
  } catch (err) {
    logger.debug({ key, err }, "Cache get failed — returning null");
    return null;
  }
}

/**
 * Stores a value in the cache with a TTL in seconds.
 * Silently fails on error so cache misses degrade gracefully.
 */
export async function cacheSet<T>(
  redis: RedisCache,
  key: string,
  value: T,
  ttlSeconds: number
): Promise<void> {
  try {
    await redis.set(key, JSON.stringify(value), "EX", ttlSeconds);
    logger.debug({ key, ttlSeconds }, "Cache set");
  } catch (err) {
    logger.debug({ key, err }, "Cache set failed — continuing without cache");
  }
}

/**
 * Generates a stable cache key from a query string by hashing it.
 * Useful for caching resolver results keyed on arbitrary query parameters.
 */
export function makeCacheKey(namespace: string, query: string): string {
  const hash = createHash("sha256").update(query).digest("hex").slice(0, 16);
  return `cartographer:${namespace}:${hash}`;
}
