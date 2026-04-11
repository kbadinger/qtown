import Redis from "ioredis";

export interface RedisConfig {
  host: string;
  port: number;
  password?: string;
  db?: number;
}

function loadConfig(): RedisConfig {
  return {
    host: process.env["REDIS_HOST"] ?? "localhost",
    port: parseInt(process.env["REDIS_PORT"] ?? "6379", 10),
    password: process.env["REDIS_PASSWORD"] ?? undefined,
    db: parseInt(process.env["REDIS_DB"] ?? "0", 10),
  };
}

let _client: Redis | null = null;

/**
 * Returns a singleton Redis client.  Call once at startup so that all
 * modules share the same connection pool.
 */
export function getRedisClient(): Redis {
  if (_client) return _client;

  const cfg = loadConfig();

  _client = new Redis({
    host: cfg.host,
    port: cfg.port,
    password: cfg.password,
    db: cfg.db,
    lazyConnect: false,
    maxRetriesPerRequest: 3,
    enableReadyCheck: true,
    retryStrategy: (times: number) => {
      if (times > 5) {
        console.error("[redis] giving up after 5 retries");
        return null;
      }
      const delay = Math.min(times * 200, 2000);
      console.warn(`[redis] retry #${times} in ${delay}ms`);
      return delay;
    },
  });

  _client.on("connect", () => console.log("[redis] connected"));
  _client.on("ready", () => console.log("[redis] ready"));
  _client.on("error", (err: Error) => console.error("[redis] error:", err.message));
  _client.on("close", () => console.warn("[redis] connection closed"));
  _client.on("reconnecting", () => console.warn("[redis] reconnecting…"));

  return _client;
}

/**
 * Creates a duplicate of the shared client — useful for Pub/Sub
 * because a subscribed client cannot issue other commands.
 */
export function createSubscriberClient(): Redis {
  const base = getRedisClient();
  return base.duplicate();
}
