import { Kafka, Consumer, EachMessagePayload, KafkaConfig } from "kafkajs";
import pino from "pino";
import type { RedisClient } from "./redis.js";
import { Leaderboard } from "./leaderboard.js";
import { NPCPresenceTracker } from "./npc-presence.js";
import type { WebSocketManager } from "./websocket.js";
import type {
  KafkaEvent,
  TradeSettled,
  PriceUpdate,
  ContentGenerated,
  EventBroadcast,
  NPCTravelDepart,
  NPCTravelComplete,
} from "./types.js";

const logger = pino({ name: "kafka-consumer" });

// ============================================================================
// Topic definitions
// ============================================================================

export const KAFKA_TOPICS = [
  "events.broadcast",
  "economy.trade.settled",
  "economy.price.update",
  "ai.content.generated",
  "npc.travel.depart",
  "npc.travel.complete",
] as const;

type KafkaTopic = (typeof KAFKA_TOPICS)[number];

// ============================================================================
// Topic → Redis channel routing
// ============================================================================

const TOPIC_TO_REDIS_CHANNEL: Record<KafkaTopic, string | null> = {
  "events.broadcast": "events",
  "economy.trade.settled": "market",
  "economy.price.update": "market",
  "ai.content.generated": "content",
  "npc.travel.depart": null, // dynamic: npc:{id}
  "npc.travel.complete": null, // dynamic: npc:{id}
};

const RECONNECT_BASE_MS = 2_000;
const RECONNECT_MAX_MS = 30_000;

// ============================================================================
// KafkaConsumerService
// ============================================================================

export class KafkaConsumerService {
  private consumer: Consumer;
  private readonly leaderboard: Leaderboard;
  private readonly presence: NPCPresenceTracker;
  private readonly wsManager: WebSocketManager;
  private readonly redis: RedisClient;
  private running = false;
  private reconnectDelay = RECONNECT_BASE_MS;

  constructor(
    kafkaConfig: KafkaConfig,
    redis: RedisClient,
    wsManager: WebSocketManager
  ) {
    const kafka = new Kafka(kafkaConfig);
    this.consumer = kafka.consumer({ groupId: "tavern-consumer-group" });
    this.leaderboard = new Leaderboard(redis);
    this.presence = new NPCPresenceTracker(redis);
    this.wsManager = wsManager;
    this.redis = redis;
  }

  // --------------------------------------------------------------------------
  // Start / retry loop
  // --------------------------------------------------------------------------

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
          topics: [...KAFKA_TOPICS],
          fromBeginning: false,
        });

        this.reconnectDelay = RECONNECT_BASE_MS;

        await this.consumer.run({
          eachMessage: (payload) => this.handleMessage(payload),
        });

        break; // run() resolves on clean stop
      } catch (err) {
        if (!this.running) break;
        logger.error(
          { err, delay: this.reconnectDelay },
          "Kafka connection failed, retrying"
        );
        await sleep(this.reconnectDelay);
        this.reconnectDelay = Math.min(
          this.reconnectDelay * 2,
          RECONNECT_MAX_MS
        );

        try {
          await this.consumer.disconnect();
        } catch {
          // ignore
        }
      }
    }
  }

  // --------------------------------------------------------------------------
  // Message dispatch
  // --------------------------------------------------------------------------

  private async handleMessage({
    topic,
    message,
  }: EachMessagePayload): Promise<void> {
    const raw = message.value?.toString();
    if (!raw) return;

    let event: KafkaEvent;
    try {
      event = JSON.parse(raw) as KafkaEvent;
    } catch (err) {
      logger.warn({ topic, err }, "Failed to parse Kafka message");
      return;
    }

    logger.debug({ topic, type: event.type }, "Received Kafka message");

    try {
      switch (topic as KafkaTopic) {
        case "events.broadcast":
          await this.handleEventsBroadcast(event as EventBroadcast);
          break;
        case "economy.trade.settled":
          await this.handleTradeSettled(event as TradeSettled);
          break;
        case "economy.price.update":
          await this.handlePriceUpdate(event as PriceUpdate);
          break;
        case "ai.content.generated":
          await this.handleContentGenerated(event as ContentGenerated);
          break;
        case "npc.travel.depart":
          await this.handleTravelDepart(event as NPCTravelDepart);
          break;
        case "npc.travel.complete":
          await this.handleTravelComplete(event as NPCTravelComplete);
          break;
        default:
          logger.warn({ topic }, "Unhandled Kafka topic");
      }
    } catch (err) {
      logger.error({ err, topic }, "Error processing Kafka message");
    }
  }

  // --------------------------------------------------------------------------
  // Handlers
  // --------------------------------------------------------------------------

  private async handleEventsBroadcast(event: EventBroadcast): Promise<void> {
    const channel = "events";

    // Publish to Redis (for other services subscribed to pub/sub)
    await this.redis.publish(channel, JSON.stringify(event));

    // Direct WebSocket broadcast
    this.wsManager.broadcast(channel, event);

    // Crime leaderboard update
    if (event.crime && event.npc_id && event.crime_count !== undefined) {
      await this.leaderboard.updateCrimeLeaderboard(
        event.npc_id,
        event.crime_count
      );
    }
  }

  private async handleTradeSettled(event: TradeSettled): Promise<void> {
    const channel = "market";

    await this.redis.publish(channel, JSON.stringify(event));
    this.wsManager.broadcast(channel, event);

    // Update gold leaderboard for both buyer and seller
    await Promise.all([
      this.leaderboard.updateGoldLeaderboard(
        event.buyer_id,
        event.buyer_gold_after
      ),
      this.leaderboard.updateGoldLeaderboard(
        event.seller_id,
        event.seller_gold_after
      ),
    ]);
  }

  private async handlePriceUpdate(event: PriceUpdate): Promise<void> {
    const channel = "market";
    await this.redis.publish(channel, JSON.stringify(event));
    this.wsManager.broadcast(channel, event);
  }

  private async handleContentGenerated(event: ContentGenerated): Promise<void> {
    const channel = "content";
    await this.redis.publish(channel, JSON.stringify(event));
    this.wsManager.broadcast(channel, event);
  }

  private async handleTravelDepart(event: NPCTravelDepart): Promise<void> {
    const channel = `npc:${event.npc_id}`;

    // Update presence: status → traveling
    await this.presence.updatePresence(
      event.npc_id,
      event.from_neighborhood,
      event.from_building,
      "traveling"
    );

    await this.redis.publish(channel, JSON.stringify(event));
    this.wsManager.broadcast(channel, event);
  }

  private async handleTravelComplete(event: NPCTravelComplete): Promise<void> {
    const channel = `npc:${event.npc_id}`;

    // Update presence: new neighborhood/building, status → active
    await this.presence.updatePresence(
      event.npc_id,
      event.neighborhood,
      event.building,
      "active"
    );

    await this.redis.publish(channel, JSON.stringify(event));
    this.wsManager.broadcast(channel, event);
  }

  // --------------------------------------------------------------------------
  // Shutdown
  // --------------------------------------------------------------------------

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

// ============================================================================
// Helpers
// ============================================================================

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
