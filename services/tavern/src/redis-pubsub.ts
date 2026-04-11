import Redis from "ioredis";
import pino from "pino";

const logger = pino({ name: "redis-pubsub" });

// Channels that map to WebSocket channels
const EXACT_CHANNELS = ["events", "market", "content", "leaderboard"] as const;
const NPC_PATTERN = "npc:*";

// ============================================================================
// RedisPubSub
// ============================================================================

/**
 * Manages a dedicated Redis subscriber connection (ioredis requirement: a
 * subscribed client cannot issue normal commands).
 *
 * Supports both exact channel subscriptions and pattern subscriptions for
 * the npc:{id} namespace.
 *
 * The broadcast function is injected so that this module remains decoupled
 * from the WebSocket implementation.
 */
export class RedisPubSub {
  private readonly subscriber: Redis;
  private broadcastFn: ((channel: string, data: unknown) => void) | null = null;
  private started = false;

  constructor(redisUrl: string) {
    this.subscriber = new Redis(redisUrl, {
      maxRetriesPerRequest: null,
      enableReadyCheck: true,
      retryStrategy: (times: number): number | null => {
        if (times > 15) return null;
        return Math.min(500 * times, 10_000);
      },
    });

    this.subscriber.on("error", (err: Error) =>
      logger.error({ err }, "Redis subscriber error")
    );
    this.subscriber.on("connect", () =>
      logger.info("Redis subscriber connected")
    );
    this.subscriber.on("reconnecting", () =>
      logger.warn("Redis subscriber reconnecting")
    );
  }

  // --------------------------------------------------------------------------
  // Start
  // --------------------------------------------------------------------------

  async start(
    broadcastFn: (channel: string, data: unknown) => void
  ): Promise<void> {
    if (this.started) return;
    this.started = true;
    this.broadcastFn = broadcastFn;

    // Subscribe to exact channels
    await this.subscriber.subscribe(...EXACT_CHANNELS);
    logger.info({ channels: EXACT_CHANNELS }, "Subscribed to Redis channels");

    // Pattern subscribe for npc:* channels
    await this.subscriber.psubscribe(NPC_PATTERN);
    logger.info({ pattern: NPC_PATTERN }, "Pattern-subscribed to Redis npc channels");

    // Exact channel messages
    this.subscriber.on("message", (channel: string, message: string) => {
      this.handleMessage(channel, message);
    });

    // Pattern channel messages (npc:*)
    this.subscriber.on(
      "pmessage",
      (_pattern: string, channel: string, message: string) => {
        this.handleMessage(channel, message);
      }
    );
  }

  // --------------------------------------------------------------------------
  // Message handling
  // --------------------------------------------------------------------------

  private handleMessage(channel: string, raw: string): void {
    if (!this.broadcastFn) return;

    let data: unknown;
    try {
      data = JSON.parse(raw) as unknown;
    } catch (err) {
      logger.warn({ channel, err }, "Failed to parse Redis pub/sub message");
      return;
    }

    logger.debug({ channel }, "Forwarding Redis pub/sub message to WebSocket");
    this.broadcastFn(channel, data);
  }

  // --------------------------------------------------------------------------
  // Shutdown
  // --------------------------------------------------------------------------

  async shutdown(): Promise<void> {
    try {
      await this.subscriber.unsubscribe(...EXACT_CHANNELS);
      await this.subscriber.punsubscribe(NPC_PATTERN);
      this.subscriber.disconnect();
      logger.info("Redis pub/sub subscriber shut down");
    } catch (err) {
      logger.error({ err }, "Error shutting down Redis pub/sub subscriber");
    }
  }
}
