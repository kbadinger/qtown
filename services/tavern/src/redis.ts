import Redis from "ioredis";
import pino from "pino";

const logger = pino({ name: "redis" });

// ============================================================================
// Config
// ============================================================================

export interface RedisConfig {
  url?: string;
  host?: string;
  port?: number;
  password?: string;
  db?: number;
  retryDelayMs?: number;
  maxRetries?: number;
}

function buildConfig(): RedisConfig {
  return {
    url: process.env["REDIS_URL"],
    host: process.env["REDIS_HOST"] ?? "localhost",
    port: parseInt(process.env["REDIS_PORT"] ?? "6379", 10),
    password: process.env["REDIS_PASSWORD"] ?? undefined,
    db: parseInt(process.env["REDIS_DB"] ?? "0", 10),
    retryDelayMs: 500,
    maxRetries: 10,
  };
}

// ============================================================================
// RedisClient wrapper
// ============================================================================

export class RedisClient {
  private readonly client: Redis;

  constructor(config?: RedisConfig) {
    const cfg = config ?? buildConfig();

    this.client = cfg.url
      ? new Redis(cfg.url, {
          maxRetriesPerRequest: 3,
          enableReadyCheck: true,
          retryStrategy: this.buildRetryStrategy(
            cfg.maxRetries ?? 10,
            cfg.retryDelayMs ?? 500
          ),
        })
      : new Redis({
          host: cfg.host ?? "localhost",
          port: cfg.port ?? 6379,
          password: cfg.password,
          db: cfg.db ?? 0,
          maxRetriesPerRequest: 3,
          enableReadyCheck: true,
          retryStrategy: this.buildRetryStrategy(
            cfg.maxRetries ?? 10,
            cfg.retryDelayMs ?? 500
          ),
        });

    this.client.on("connect", () => logger.info("Redis connected"));
    this.client.on("ready", () => logger.info("Redis ready"));
    this.client.on("error", (err: Error) => logger.error({ err }, "Redis error"));
    this.client.on("close", () => logger.warn("Redis connection closed"));
    this.client.on("reconnecting", () => logger.warn("Redis reconnecting"));
  }

  private buildRetryStrategy(
    maxRetries: number,
    baseDelayMs: number
  ): (times: number) => number | null {
    return (times: number): number | null => {
      if (times > maxRetries) {
        logger.error({ times }, "Redis: exceeded max retries, giving up");
        return null;
      }
      const delay = Math.min(baseDelayMs * Math.pow(2, times - 1), 30_000);
      logger.warn({ times, delay }, "Redis: scheduling retry");
      return delay;
    };
  }

  // --------------------------------------------------------------------------
  // Pub/Sub
  // --------------------------------------------------------------------------

  async publish(channel: string, message: string): Promise<number> {
    return this.client.publish(channel, message);
  }

  async subscribe(channel: string, callback: (message: string) => void): Promise<void> {
    // Note: this mutates the client into subscriber mode.
    // Use a separate connection for subscribing (see RedisPubSub).
    await this.client.subscribe(channel);
    this.client.on("message", (_ch: string, msg: string) => {
      if (_ch === channel) callback(msg);
    });
  }

  // --------------------------------------------------------------------------
  // Sorted Sets (Leaderboards)
  // --------------------------------------------------------------------------

  async zadd(key: string, score: number, member: string): Promise<number> {
    return this.client.zadd(key, score, member);
  }

  async zrange(
    key: string,
    start: number,
    stop: number,
    withScores = false
  ): Promise<string[]> {
    if (withScores) {
      return this.client.zrange(key, start, stop, "WITHSCORES");
    }
    return this.client.zrange(key, start, stop);
  }

  async zrevrange(
    key: string,
    start: number,
    stop: number,
    withScores = false
  ): Promise<string[]> {
    if (withScores) {
      return this.client.zrevrange(key, start, stop, "WITHSCORES");
    }
    return this.client.zrevrange(key, start, stop);
  }

  async zrevrank(key: string, member: string): Promise<number | null> {
    return this.client.zrevrank(key, member);
  }

  async zcard(key: string): Promise<number> {
    return this.client.zcard(key);
  }

  // --------------------------------------------------------------------------
  // Hashes (NPC Presence)
  // --------------------------------------------------------------------------

  async hset(key: string, fields: Record<string, string>): Promise<number> {
    return this.client.hset(key, fields);
  }

  async hget(key: string, field: string): Promise<string | null> {
    return this.client.hget(key, field);
  }

  async hgetall(key: string): Promise<Record<string, string> | null> {
    const result = await this.client.hgetall(key);
    // ioredis returns {} for missing keys
    return Object.keys(result).length === 0 ? null : result;
  }

  // --------------------------------------------------------------------------
  // Key scanning
  // --------------------------------------------------------------------------

  async scan(pattern: string): Promise<string[]> {
    const keys: string[] = [];
    let cursor = "0";
    do {
      const [nextCursor, batch] = await this.client.scan(cursor, "MATCH", pattern, "COUNT", 100);
      cursor = nextCursor;
      keys.push(...batch);
    } while (cursor !== "0");
    return keys;
  }

  // --------------------------------------------------------------------------
  // Generic
  // --------------------------------------------------------------------------

  async set(key: string, value: string, ttlSeconds?: number): Promise<string | null> {
    if (ttlSeconds !== undefined) {
      return this.client.set(key, value, "EX", ttlSeconds);
    }
    return this.client.set(key, value);
  }

  async get(key: string): Promise<string | null> {
    return this.client.get(key);
  }

  async del(key: string): Promise<number> {
    return this.client.del(key);
  }

  // --------------------------------------------------------------------------
  // Internals
  // --------------------------------------------------------------------------

  /** Raw ioredis client for advanced use. */
  raw(): Redis {
    return this.client;
  }

  /** Create a duplicate client for pub/sub subscriber use. */
  duplicate(): Redis {
    return this.client.duplicate();
  }

  disconnect(): void {
    this.client.disconnect();
  }
}
