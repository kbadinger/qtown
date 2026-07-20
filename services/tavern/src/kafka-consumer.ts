import { Kafka, Consumer, EachMessagePayload, KafkaConfig } from "kafkajs";
import pino from "pino";
import type { RedisClient } from "./redis.js";
import { Leaderboard } from "./leaderboard.js";
import { NPCPresenceTracker } from "./npc-presence.js";
import type { ContentBuffer } from "./content-buffer.js";
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
  "qtown.events.broadcast",
  "qtown.economy.trade.settled",
  "qtown.economy.price.update",
  "qtown.ai.content.generated",
  "qtown.npc.travel",
  "qtown.npc.travel.complete",
] as const;

type KafkaTopic = (typeof KAFKA_TOPICS)[number];

// ============================================================================
// Topic → Redis channel routing
// ============================================================================

const TOPIC_TO_REDIS_CHANNEL: Record<KafkaTopic, string | null> = {
  "qtown.events.broadcast": "events",
  "qtown.economy.trade.settled": "market",
  "qtown.economy.price.update": "market",
  "qtown.ai.content.generated": "content",
  "qtown.npc.travel": null, // dynamic: npc:{id}
  "qtown.npc.travel.complete": null, // dynamic: npc:{id}
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
  private readonly redis: RedisClient;
  private readonly contentBuffer: ContentBuffer;
  private running = false;
  private reconnectDelay = RECONNECT_BASE_MS;

  // The consumer publishes to Redis ONLY; RedisPubSub is the single WebSocket
  // fan-out path (server.ts wires it to wsManager.broadcast). Broadcasting here
  // too would double-deliver every event to same-node clients, since the pub/sub
  // subscriber echoes this process's own publishes back.
  constructor(
    kafkaConfig: KafkaConfig,
    redis: RedisClient,
    contentBuffer: ContentBuffer
  ) {
    const kafka = new Kafka(kafkaConfig);
    this.consumer = kafka.consumer({ groupId: "tavern-consumer-group" });
    this.leaderboard = new Leaderboard(redis);
    this.presence = new NPCPresenceTracker(redis);
    this.redis = redis;
    this.contentBuffer = contentBuffer;
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
    await this.dispatch(topic, raw);
  }

  /**
   * Parse + route a single record to its handler. Public so the content /
   * fan-out path can be tested without a live Kafka broker (feed a synthetic
   * record and assert the Redis publish + content buffer).
   */
  async dispatch(topic: string, raw: string): Promise<void> {
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
        case "qtown.events.broadcast":
          await this.handleEventsBroadcast(event as EventBroadcast);
          break;
        case "qtown.economy.trade.settled":
          await this.handleTradeSettled(event as TradeSettled);
          break;
        case "qtown.economy.price.update":
          await this.handlePriceUpdate(event as PriceUpdate);
          break;
        case "qtown.ai.content.generated":
          await this.handleContentGenerated(event as ContentGenerated);
          break;
        case "qtown.npc.travel":
          await this.handleTravelDepart(event as NPCTravelDepart);
          break;
        case "qtown.npc.travel.complete":
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

    // Publish to Redis — RedisPubSub fans this out to WebSocket subscribers.
    await this.redis.publish(channel, JSON.stringify(event));

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

    // Single-sided settlement: two messages arrive per trade, one per
    // counterparty. Each carries this NPC's gold_delta — apply it to the
    // NPC's running gold-leaderboard total (mirrors town-core's `gold += delta`).
    await this.leaderboard.applyGoldDelta(
      String(event.npc_id),
      event.gold_delta
    );
  }

  private async handlePriceUpdate(event: PriceUpdate): Promise<void> {
    const channel = "market";
    await this.redis.publish(channel, JSON.stringify(event));
  }

  private async handleContentGenerated(event: ContentGenerated): Promise<void> {
    const channel = "content";
    await this.redis.publish(channel, JSON.stringify(event));

    // Keep the last N content events for the read-model / proof panel.
    this.contentBuffer.add({
      content_type: event.content_type,
      content_id: event.content_id,
      text: event.text,
      content: event.content,
      metadata: event.metadata,
      received_at: new Date().toISOString(),
    });
  }

  private async handleTravelDepart(event: NPCTravelDepart): Promise<void> {
    const channel = `npc:${event.npc_id}`;

    // Update presence: status → traveling. The travel payload carries the
    // origin neighborhood in `from`; there is no building granularity.
    await this.presence.updatePresence(
      String(event.npc_id),
      event.from,
      "",
      "traveling"
    );

    await this.redis.publish(channel, JSON.stringify(event));
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
