import http from "http";
import { WebSocketServer, WebSocket } from "ws";
import { Kafka } from "kafkajs";
import { getRedisClient } from "./redis.js";
import { LeaderboardManager } from "./leaderboard.js";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SubscribeMessage {
  type: "subscribe";
  channels: string[];
}

interface UnsubscribeMessage {
  type: "unsubscribe";
  channels: string[];
}

interface PublishMessage {
  type: "publish";
  channel: string;
  data: unknown;
}

type ClientMessage = SubscribeMessage | UnsubscribeMessage | PublishMessage;

interface ConnectedClient {
  ws: WebSocket;
  subscriptions: Set<string>;
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const WS_PORT = parseInt(process.env["WS_PORT"] ?? "8002", 10);
const HTTP_PORT = parseInt(process.env["HTTP_PORT"] ?? "8082", 10);
const KAFKA_BROKERS = (process.env["KAFKA_BROKERS"] ?? "localhost:9092").split(",");
const KAFKA_TOPIC = process.env["KAFKA_TOPIC"] ?? "qtown.events";

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const clients = new Map<WebSocket, ConnectedClient>();
/** channel → set of connected clients */
const channelIndex = new Map<string, Set<ConnectedClient>>();

// ---------------------------------------------------------------------------
// Channel subscription helpers
// ---------------------------------------------------------------------------

function subscribe(client: ConnectedClient, channels: string[]): void {
  for (const channel of channels) {
    client.subscriptions.add(channel);
    if (!channelIndex.has(channel)) {
      channelIndex.set(channel, new Set());
    }
    channelIndex.get(channel)!.add(client);
  }
}

function unsubscribe(client: ConnectedClient, channels: string[]): void {
  for (const channel of channels) {
    client.subscriptions.delete(channel);
    channelIndex.get(channel)?.delete(client);
  }
}

function removeClient(ws: WebSocket): void {
  const client = clients.get(ws);
  if (!client) return;
  unsubscribe(client, [...client.subscriptions]);
  clients.delete(ws);
}

/**
 * Broadcast a payload to every client subscribed to the given channel.
 * Clients that have disconnected are cleaned up lazily.
 */
export function broadcast(channel: string, data: unknown): void {
  const subscribers = channelIndex.get(channel);
  if (!subscribers || subscribers.size === 0) return;

  const payload = JSON.stringify({ channel, data });

  for (const client of subscribers) {
    if (client.ws.readyState === WebSocket.OPEN) {
      client.ws.send(payload);
    } else {
      // Lazy cleanup of stale references.
      unsubscribe(client, [channel]);
    }
  }
}

// ---------------------------------------------------------------------------
// WebSocket server
// ---------------------------------------------------------------------------

const wss = new WebSocketServer({ port: WS_PORT });

wss.on("listening", () => {
  console.log(`[tavern] WebSocket server listening on ws://0.0.0.0:${WS_PORT}`);
});

wss.on("connection", (ws: WebSocket) => {
  const client: ConnectedClient = { ws, subscriptions: new Set() };
  clients.set(ws, client);

  ws.on("message", (raw) => {
    let msg: ClientMessage;
    try {
      msg = JSON.parse(raw.toString()) as ClientMessage;
    } catch {
      ws.send(JSON.stringify({ error: "invalid JSON" }));
      return;
    }

    switch (msg.type) {
      case "subscribe":
        subscribe(client, msg.channels);
        ws.send(JSON.stringify({ type: "subscribed", channels: msg.channels }));
        break;

      case "unsubscribe":
        unsubscribe(client, msg.channels);
        ws.send(JSON.stringify({ type: "unsubscribed", channels: msg.channels }));
        break;

      case "publish":
        // Allow clients to publish to channels they are subscribed to.
        if (client.subscriptions.has(msg.channel)) {
          broadcast(msg.channel, msg.data);
        } else {
          ws.send(JSON.stringify({ error: `not subscribed to channel: ${msg.channel}` }));
        }
        break;

      default:
        ws.send(JSON.stringify({ error: "unknown message type" }));
    }
  });

  ws.on("close", () => removeClient(ws));
  ws.on("error", (err) => {
    console.error("[tavern] ws error:", err.message);
    removeClient(ws);
  });
});

// ---------------------------------------------------------------------------
// HTTP health check server
// ---------------------------------------------------------------------------

const healthServer = http.createServer((req, res) => {
  if (req.url === "/health" && req.method === "GET") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(
      JSON.stringify({
        status: "ok",
        service: "tavern",
        clients: clients.size,
        channels: channelIndex.size,
      })
    );
    return;
  }
  res.writeHead(404);
  res.end();
});

healthServer.listen(HTTP_PORT, () => {
  console.log(`[tavern] HTTP health server listening on http://0.0.0.0:${HTTP_PORT}`);
});

// ---------------------------------------------------------------------------
// Kafka consumer (placeholder)
// ---------------------------------------------------------------------------

async function startKafkaConsumer(): Promise<void> {
  const kafka = new Kafka({
    clientId: "qtown-tavern",
    brokers: KAFKA_BROKERS,
  });

  const consumer = kafka.consumer({ groupId: "tavern-consumer-group" });

  try {
    await consumer.connect();
    await consumer.subscribe({ topic: KAFKA_TOPIC, fromBeginning: false });

    console.log(`[tavern] Kafka consumer connected — topic: ${KAFKA_TOPIC}`);

    await consumer.run({
      eachMessage: async ({ topic, partition, message }) => {
        const value = message.value?.toString();
        if (!value) return;

        // TODO: parse and route real event types.
        // For now broadcast raw JSON to an 'events' channel.
        try {
          const parsed: unknown = JSON.parse(value);
          broadcast("events", parsed);
        } catch {
          console.warn(
            `[tavern] kafka unparseable message at ${topic}[${partition}]:`,
            value
          );
        }
      },
    });
  } catch (err) {
    console.warn("[tavern] Kafka unavailable, consumer not started:", err);
  }
}

// ---------------------------------------------------------------------------
// Redis + Leaderboard
// ---------------------------------------------------------------------------

const redis = getRedisClient();
export const leaderboard = new LeaderboardManager(redis);

// ---------------------------------------------------------------------------
// Startup
// ---------------------------------------------------------------------------

startKafkaConsumer().catch((err) => {
  console.warn("[tavern] kafka consumer error:", err);
});

// Graceful shutdown
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

function shutdown(): void {
  console.log("[tavern] shutting down…");
  wss.close(() => console.log("[tavern] WebSocket server closed"));
  healthServer.close(() => console.log("[tavern] HTTP server closed"));
  redis.quit().catch(() => undefined);
  process.exit(0);
}

console.log("[tavern] startup complete");
