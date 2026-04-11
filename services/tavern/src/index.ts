import Fastify from "fastify";
import { createServer } from "http";
import Redis from "ioredis";
import pino from "pino";
import { WebSocketManager } from "./websocket.js";
import { KafkaConsumerService } from "./kafka-consumer.js";
import { RedisPubSub } from "./redis-pubsub.js";
import { Leaderboard } from "./leaderboard.js";

// ---------------------------------------------------------------------------
// Logger
// ---------------------------------------------------------------------------
const logger = pino({ name: "tavern" });

// ---------------------------------------------------------------------------
// Config (env-driven)
// ---------------------------------------------------------------------------
const PORT = parseInt(process.env["PORT"] ?? "3001", 10);
const REDIS_URL = process.env["REDIS_URL"] ?? "redis://localhost:6379";
const KAFKA_BROKERS = (process.env["KAFKA_BROKERS"] ?? "localhost:9092").split(",");

// ---------------------------------------------------------------------------
// Redis clients
// ---------------------------------------------------------------------------
// One client for commands, a separate one for pub/sub (Redis requirement)
const redis = new Redis(REDIS_URL);
const redisPub = new Redis(REDIS_URL); // used by KafkaConsumerService to publish

redis.on("error", (err) => logger.error({ err }, "Redis command client error"));
redisPub.on("error", (err) => logger.error({ err }, "Redis publisher error"));

// ---------------------------------------------------------------------------
// Fastify + HTTP server
// ---------------------------------------------------------------------------
const fastify = Fastify({ loggerInstance: logger });
const httpServer = createServer(fastify.server);

// ---------------------------------------------------------------------------
// WebSocket manager (attached to the shared HTTP server)
// ---------------------------------------------------------------------------
const wsManager = new WebSocketManager(httpServer);

// ---------------------------------------------------------------------------
// Services
// ---------------------------------------------------------------------------
const leaderboard = new Leaderboard(redis);
const redisPubSub = new RedisPubSub(REDIS_URL);

const kafkaConsumer = new KafkaConsumerService(
  {
    clientId: "tavern",
    brokers: KAFKA_BROKERS,
    retry: { retries: 5 },
  },
  redis,
  redisPub,
  wsManager
);

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

fastify.get("/health", async (_req, _reply) => {
  return {
    status: "ok",
    service: "tavern",
    connections: wsManager.getConnectionCount(),
  };
});

fastify.get("/metrics", async (_req, _reply) => {
  const lag = await measureEventLoopLag();
  return {
    event_loop_lag_ms: lag,
  };
});

// ---------------------------------------------------------------------------
// Startup
// ---------------------------------------------------------------------------

async function start(): Promise<void> {
  try {
    // Register Fastify routes (must be done before listen)
    await fastify.ready();

    // Attach WebSocket to the raw HTTP server that Fastify manages
    // Fastify wraps Node's http.Server; we attach WS directly to it
    await new Promise<void>((resolve, reject) => {
      // Fastify creates its own server; use the underlying server for WS
      fastify.server.listen({ port: PORT, host: "0.0.0.0" }, (err) => {
        if (err) reject(err);
        else resolve();
      });
    });

    logger.info({ port: PORT }, "Tavern HTTP server listening");

    // Start Redis pub/sub listener
    await redisPubSub.start(wsManager);

    // Start Kafka consumer (non-blocking; reconnects internally)
    kafkaConsumer.start().catch((err) => {
      logger.error({ err }, "Kafka consumer fatal error");
    });

    logger.info("Tavern started");
  } catch (err) {
    logger.fatal({ err }, "Failed to start Tavern");
    process.exit(1);
  }
}

// ---------------------------------------------------------------------------
// Graceful shutdown
// ---------------------------------------------------------------------------

async function shutdown(signal: string): Promise<void> {
  logger.info({ signal }, "Shutdown signal received");
  try {
    await kafkaConsumer.shutdown();
    await redisPubSub.shutdown();
    await wsManager.shutdown();
    redis.disconnect();
    redisPub.disconnect();
    await fastify.close();
    logger.info("Tavern shut down cleanly");
    process.exit(0);
  } catch (err) {
    logger.error({ err }, "Error during shutdown");
    process.exit(1);
  }
}

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function measureEventLoopLag(): Promise<number> {
  return new Promise((resolve) => {
    const start = process.hrtime.bigint();
    setImmediate(() => {
      const lag = Number(process.hrtime.bigint() - start) / 1_000_000;
      resolve(Math.round(lag * 100) / 100);
    });
  });
}

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------
start();
