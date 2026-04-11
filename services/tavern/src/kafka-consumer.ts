import { Kafka, Consumer, EachMessagePayload, KafkaConfig } from "kafkajs";
import type Redis from "ioredis";
import pino from "pino";
import { Leaderboard } from "./leaderboard.js";
import type { WebSocketManager } from "./websocket.js";
import type { TownEvent } from "./types.js";

const logger = pino({ name: "kafka-consumer" });

const SUBSCRIBED_TOPICS_REGEX = /^qtown\.(economy|events)\..+/;
const KAFKA_TOPICS = [
  // Kafka JS requires explicit topic names or regex; we use a pattern-based approach.
  // Add concrete topic names here as they are defined in the schema registry.
  "qtown.economy.gold-transfers",
  "qtown.economy.market-trades",
  "qtown.events.npc-actions",
  "qtown.events.world-updates",
];

const RECONNECT_BASE_MS = 2_000;
const RECONNECT_MAX_MS = 30_000;

export class KafkaConsumerService {
  private consumer: Consumer;
  private leaderboard: Leaderboard;
  private wsManager: WebSocketManager;
  private publisher: Redis;
  private running = false;
  private reconnectDelay = RECONNECT_BASE_MS;

  constructor(
    kafkaConfig: KafkaConfig,
    redis: Redis,
    publisher: Redis,
    wsManager: WebSocketManager
  ) {
    const kafka = new Kafka(kafkaConfig);
    this.consumer = kafka.consumer({ groupId: "tavern-consumer-group" });
    this.leaderboard = new Leaderboard(redis);
    this.wsManager = wsManager;
    this.publisher = publisher;
  }

  async start(): Promise<void> {
    this.running = true;
    await this.connectWithRetry();
  }

  private async connectWithRetry(): Promise<void> {
    while (this.running) {
      try {
        await this.consumer.connect();
        logger.info("Kafka consumer connected");

        await this.consumer.subscribe({
          topics: KAFKA_TOPICS,
          fromBeginning: false,
        });

        this.reconnectDelay = RECONNECT_BASE_MS; // reset backoff on success

        await this.consumer.run({
          eachMessage: async (payload) => this.handleMessage(payload),
        });

        // run() resolves when the consumer is stopped
        break;
      } catch (err) {
        if (!this.running) break;
        logger.error({ err, delay: this.reconnectDelay }, "Kafka connection failed, retrying");
        await sleep(this.reconnectDelay);
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, RECONNECT_MAX_MS);

        // Recreate consumer to force clean reconnect
        try {
          await this.consumer.disconnect();
        } catch {
          // ignore errors during disconnect-before-reconnect
        }
      }
    }
  }

  private async handleMessage({ topic, partition, message }: EachMessagePayload): Promise<void> {
    const raw = message.value?.toString();
    if (!raw) return;

    let event: TownEvent;
    try {
      event = JSON.parse(raw) as TownEvent;
    } catch (err) {
      logger.warn({ topic, partition, err }, "Failed to parse Kafka message");
      return;
    }

    logger.debug({ topic, type: event.type }, "Received Kafka message");

    try {
      // 1. Update leaderboard if the event carries gold information
      if (event.type === "gold-transfer" && typeof event.data["npcId"] === "string") {
        const npcId = event.data["npcId"] as string;
        const gold = Number(event.data["gold"] ?? 0);
        await this.leaderboard.updateGold(npcId, gold);
      }

      // 2. Publish to Redis pub/sub so other services and the pub/sub listener can fan out
      await this.publisher.publish("events:live", JSON.stringify(event));

      // 3. Direct WebSocket fan-out for real-time clients
      const channel = topic.startsWith("qtown.economy") ? "economy" : "events";
      this.wsManager.broadcast(channel, event);
    } catch (err) {
      logger.error({ err, topic }, "Error processing Kafka message");
    }
  }

  async shutdown(): Promise<void> {
    this.running = false;
    try {
      await this.consumer.disconnect();
      logger.info("Kafka consumer disconnected");
    } catch (err) {
      logger.error({ err }, "Error disconnecting Kafka consumer");
    }
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
