import Redis from "ioredis";
import pino from "pino";
import type { WebSocketManager } from "./websocket.js";
import type { TownEvent } from "./types.js";

const logger = pino({ name: "redis-pubsub" });

const LIVE_CHANNEL = "events:live";

/**
 * RedisPubSub subscribes to the Redis `events:live` channel and forwards every
 * message to the WebSocket manager for real-time fan-out to browser clients.
 *
 * Redis requires a **dedicated** connection for pub/sub — a subscribed client
 * cannot issue regular commands.  We therefore accept a separate `Redis`
 * instance configured identically to the main client.
 */
export class RedisPubSub {
  private readonly subscriber: Redis;
  private wsManager: WebSocketManager | null = null;

  constructor(redisOptions: ConstructorParameters<typeof Redis>[0]) {
    // Separate connection — never shared with the main command client
    this.subscriber = new Redis(redisOptions as ConstructorParameters<typeof Redis>[0]);

    this.subscriber.on("error", (err) => {
      logger.error({ err }, "Redis subscriber error");
    });

    this.subscriber.on("connect", () => {
      logger.info("Redis subscriber connected");
    });
  }

  /**
   * Attaches the WebSocket manager and begins listening for messages.
   */
  async start(wsManager: WebSocketManager): Promise<void> {
    this.wsManager = wsManager;

    await this.subscriber.subscribe(LIVE_CHANNEL, (err, count) => {
      if (err) {
        logger.error({ err }, "Failed to subscribe to Redis channel");
        return;
      }
      logger.info({ channel: LIVE_CHANNEL, count }, "Subscribed to Redis channel");
    });

    this.subscriber.on("message", (channel, message) => {
      if (channel !== LIVE_CHANNEL) return;
      this.handleMessage(message);
    });
  }

  private handleMessage(raw: string): void {
    let event: TownEvent;
    try {
      event = JSON.parse(raw) as TownEvent;
    } catch (err) {
      logger.warn({ err }, "Failed to parse pub/sub message");
      return;
    }

    if (!this.wsManager) return;

    // Fan out to all connected WebSocket clients on the appropriate channel
    const channel = `events:${event.type}`;
    this.wsManager.broadcast(channel, event);
    // Also broadcast on the catch-all channel
    this.wsManager.broadcast("events:live", event);

    logger.debug({ type: event.type, channel }, "Forwarded pub/sub message to WebSocket clients");
  }

  async shutdown(): Promise<void> {
    try {
      await this.subscriber.unsubscribe(LIVE_CHANNEL);
      this.subscriber.disconnect();
      logger.info("Redis subscriber shut down");
    } catch (err) {
      logger.error({ err }, "Error shutting down Redis subscriber");
    }
  }
}
