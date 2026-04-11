import Fastify from "fastify";
import type { FastifyInstance } from "fastify";
import { createServer } from "http";
import pino from "pino";
import { RedisClient } from "./redis.js";
import { RedisPubSub } from "./redis-pubsub.js";
import { WebSocketManager } from "./websocket.js";
import { KafkaConsumerService } from "./kafka-consumer.js";
import { Leaderboard } from "./leaderboard.js";
import { NPCPresenceTracker } from "./npc-presence.js";
import type { LeaderboardType } from "./types.js";

// ============================================================================
// Config
// ============================================================================

const logger = pino({ name: "tavern-server" });

const PORT = parseInt(process.env["PORT"] ?? "3001", 10);
const REDIS_URL = process.env["REDIS_URL"] ?? "redis://localhost:6379";
const KAFKA_BROKERS = (process.env["KAFKA_BROKERS"] ?? "localhost:9092").split(",");

// ============================================================================
// Bootstrap
// ============================================================================

export async function buildServer(): Promise<{
  fastify: FastifyInstance;
  wsManager: WebSocketManager;
  kafkaConsumer: KafkaConsumerService;
  redisPubSub: RedisPubSub;
  redis: RedisClient;
  redisPublisher: RedisClient;
}> {
  // --------------------------------------------------------------------------
  // Redis clients
  // --------------------------------------------------------------------------
  // Two separate clients: one for commands, one for publishing.
  // The pub/sub subscriber is internal to RedisPubSub.
  const redis = new RedisClient({ url: REDIS_URL });
  const redisPublisher = new RedisClient({ url: REDIS_URL });

  // --------------------------------------------------------------------------
  // Fastify + raw HTTP server
  // --------------------------------------------------------------------------
  const fastify = Fastify({ loggerInstance: logger });
  const httpServer = createServer(fastify.server);

  // --------------------------------------------------------------------------
  // WebSocket manager (attaches to the HTTP server)
  // --------------------------------------------------------------------------
  const wsManager = new WebSocketManager(httpServer);

  // --------------------------------------------------------------------------
  // Services
  // --------------------------------------------------------------------------
  const leaderboard = new Leaderboard(redis);
  const presence = new NPCPresenceTracker(redis);
  const redisPubSub = new RedisPubSub(REDIS_URL);

  const kafkaConsumer = new KafkaConsumerService(
    {
      clientId: "tavern",
      brokers: KAFKA_BROKERS,
      retry: { retries: 5 },
    },
    redis,
    wsManager
  );

  // --------------------------------------------------------------------------
  // Routes
  // --------------------------------------------------------------------------

  // Health
  fastify.get("/health", async (_req, _reply) => {
    const metrics = wsManager.getMetrics();
    return {
      status: "ok",
      service: "tavern",
      connections: metrics.totalConnections,
      messagesPerSecond: metrics.messagesPerSecond,
      activeChannels: metrics.activeChannels,
    };
  });

  // WebSocket metrics
  fastify.get("/metrics", async (_req, _reply) => {
    return wsManager.getMetrics();
  });

  // Leaderboard REST endpoint
  fastify.get<{
    Params: { type: string };
    Querystring: { limit?: string; offset?: string };
  }>("/leaderboard/:type", async (req, reply) => {
    const type = req.params.type as LeaderboardType;
    if (!["gold", "happiness", "crimes"].includes(type)) {
      return reply.status(400).send({ error: "Invalid leaderboard type" });
    }
    const limit = Math.min(parseInt(req.query.limit ?? "10", 10), 100);
    const offset = parseInt(req.query.offset ?? "0", 10);
    const entries = await leaderboard.getLeaderboard(type, offset, limit);
    return { type, entries };
  });

  // NPC presence
  fastify.get<{ Params: { id: string } }>(
    "/npc/:id/presence",
    async (req, reply) => {
      const p = await presence.getPresence(req.params.id);
      if (!p) return reply.status(404).send({ error: "NPC not found" });
      return p;
    }
  );

  fastify.get("/presence", async (_req, _reply) => {
    const all = await presence.getAllPresence();
    return { count: all.length, presence: all };
  });

  // WebSocket upgrade — the WebSocketManager handles the actual upgrade via
  // the 'ws' library listening on the same HTTP server as Fastify.
  // Fastify's server is passed to WebSocketManager constructor above.
  // We also expose a redirect hint at /ws for documentation purposes.
  fastify.get("/ws", async (_req, reply) => {
    return reply.status(426).send({
      error: "Upgrade Required",
      message: "Connect via WebSocket at ws://<host>/ws",
    });
  });

  return {
    fastify,
    wsManager,
    kafkaConsumer,
    redisPubSub,
    redis,
    redisPublisher,
  };
}

// ============================================================================
// Main entry point
// ============================================================================

export async function start(): Promise<void> {
  const { fastify, wsManager, kafkaConsumer, redisPubSub, redis, redisPublisher } =
    await buildServer();

  try {
    await fastify.ready();

    await new Promise<void>((resolve, reject) => {
      fastify.server.listen({ port: PORT, host: "0.0.0.0" }, (err) => {
        if (err) reject(err);
        else resolve();
      });
    });

    logger.info({ port: PORT }, "Tavern HTTP server listening");

    // Start Redis pub/sub: forward published messages to WebSocket clients
    await redisPubSub.start((channel, data) => {
      wsManager.broadcast(channel, data);
    });

    // Start Kafka consumer (non-blocking; retries internally)
    kafkaConsumer.start().catch((err: unknown) => {
      logger.error({ err }, "Kafka consumer fatal error");
    });

    logger.info("Tavern service fully started");
  } catch (err) {
    logger.fatal({ err }, "Failed to start Tavern");
    process.exit(1);
  }

  // --------------------------------------------------------------------------
  // Graceful shutdown
  // --------------------------------------------------------------------------

  async function shutdown(signal: string): Promise<void> {
    logger.info({ signal }, "Shutdown signal received");
    try {
      await kafkaConsumer.shutdown();
      await redisPubSub.shutdown();
      await wsManager.shutdown();
      redis.disconnect();
      redisPublisher.disconnect();
      await fastify.close();
      logger.info("Tavern shut down cleanly");
      process.exit(0);
    } catch (err) {
      logger.error({ err }, "Error during shutdown");
      process.exit(1);
    }
  }

  process.on("SIGTERM", () => {
    shutdown("SIGTERM").catch((err) => {
      logger.error({ err }, "Shutdown failed");
      process.exit(1);
    });
  });
  process.on("SIGINT", () => {
    shutdown("SIGINT").catch((err) => {
      logger.error({ err }, "Shutdown failed");
      process.exit(1);
    });
  });
}
