import { WebSocketServer, WebSocket } from "ws";
import type { IncomingMessage } from "http";
import type { Server } from "http";
import pino from "pino";
import type { WebSocketClientMessage } from "./types.js";

const logger = pino({ name: "websocket" });

const HEARTBEAT_INTERVAL_MS = 30_000;

// Allowed channel prefixes
const ALLOWED_CHANNELS = new Set(["events", "market", "content", "leaderboard"]);

function isAllowedChannel(channel: string): boolean {
  if (ALLOWED_CHANNELS.has(channel)) return true;
  // npc:{id} pattern
  return /^npc:[a-zA-Z0-9_-]+$/.test(channel);
}

// ============================================================================
// Per-client state
// ============================================================================

interface ClientState {
  subscriptions: Set<string>;
  isAlive: boolean;
  connectedAt: number;
  messageCount: number;
}

// ============================================================================
// Connection metrics
// ============================================================================

export interface WebSocketMetrics {
  totalConnections: number;
  messagesPerSecond: number;
  activeChannels: string[];
}

// ============================================================================
// WebSocketManager
// ============================================================================

export class WebSocketManager {
  private readonly wss: WebSocketServer;
  private readonly clients = new Map<WebSocket, ClientState>();
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private metricsTimer: ReturnType<typeof setInterval> | null = null;

  // Rolling message count for msg/sec calculation
  private messageCount = 0;
  private messagesPerSecond = 0;

  constructor(server: Server) {
    this.wss = new WebSocketServer({ server, path: "/ws" });
    this.wss.on("connection", this.handleConnection.bind(this));
    this.startHeartbeat();
    this.startMetricsRollup();
    logger.info("WebSocketManager initialised");
  }

  // --------------------------------------------------------------------------
  // Connection lifecycle
  // --------------------------------------------------------------------------

  private handleConnection(ws: WebSocket, _req: IncomingMessage): void {
    const state: ClientState = {
      subscriptions: new Set(),
      isAlive: true,
      connectedAt: Date.now(),
      messageCount: 0,
    };
    this.clients.set(ws, state);

    logger.info(
      { totalConnections: this.clients.size },
      "WebSocket client connected"
    );

    // Pong response marks client as alive
    ws.on("pong", () => {
      const s = this.clients.get(ws);
      if (s) s.isAlive = true;
    });

    ws.on("message", (raw) => {
      this.messageCount++;
      const s = this.clients.get(ws);
      if (s) s.messageCount++;
      this.handleMessage(ws, raw.toString());
    });

    ws.on("close", () => {
      this.clients.delete(ws);
      logger.info(
        { totalConnections: this.clients.size },
        "WebSocket client disconnected"
      );
    });

    ws.on("error", (err: Error) => {
      logger.error({ err }, "WebSocket client error");
      ws.terminate();
      this.clients.delete(ws);
    });

    // Welcome message
    this.send(ws, {
      type: "welcome",
      channels: [...ALLOWED_CHANNELS],
      timestamp: new Date().toISOString(),
    });
  }

  // --------------------------------------------------------------------------
  // Message handling
  // --------------------------------------------------------------------------

  private handleMessage(ws: WebSocket, raw: string): void {
    let msg: WebSocketClientMessage;
    try {
      msg = JSON.parse(raw) as WebSocketClientMessage;
    } catch {
      this.send(ws, { type: "error", message: "Invalid JSON" });
      return;
    }

    if (msg.action !== "subscribe" && msg.action !== "unsubscribe") {
      this.send(ws, { type: "error", message: "Unknown action" });
      return;
    }

    if (typeof msg.channel !== "string" || !isAllowedChannel(msg.channel)) {
      this.send(ws, {
        type: "error",
        message: `Unknown or disallowed channel: ${String(msg.channel)}`,
      });
      return;
    }

    const state = this.clients.get(ws);
    if (!state) return;

    if (msg.action === "subscribe") {
      state.subscriptions.add(msg.channel);
      this.send(ws, { type: "subscribed", channel: msg.channel });
      logger.debug({ channel: msg.channel }, "Client subscribed");
    } else {
      state.subscriptions.delete(msg.channel);
      this.send(ws, { type: "unsubscribed", channel: msg.channel });
      logger.debug({ channel: msg.channel }, "Client unsubscribed");
    }
  }

  // --------------------------------------------------------------------------
  // Broadcast
  // --------------------------------------------------------------------------

  /**
   * Broadcasts data to all clients subscribed to the given channel.
   * Clients with an empty subscription set receive nothing (they must
   * explicitly subscribe).
   */
  broadcast(channel: string, data: unknown): void {
    const payload = JSON.stringify({
      channel,
      data,
      timestamp: new Date().toISOString(),
    });

    let sent = 0;

    for (const [ws, state] of this.clients) {
      if (ws.readyState !== WebSocket.OPEN) continue;
      if (!state.subscriptions.has(channel)) continue;

      ws.send(payload, (err) => {
        if (err) logger.warn({ err }, "Failed to send WebSocket message");
      });
      sent++;
    }

    if (sent > 0) {
      logger.debug({ channel, sent }, "Broadcast complete");
    }
  }

  // --------------------------------------------------------------------------
  // Helpers
  // --------------------------------------------------------------------------

  private send(ws: WebSocket, data: Record<string, unknown>): void {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data), (err) => {
        if (err) logger.warn({ err }, "Failed to send WebSocket message");
      });
    }
  }

  // --------------------------------------------------------------------------
  // Metrics
  // --------------------------------------------------------------------------

  getConnectionCount(): number {
    return this.clients.size;
  }

  getMetrics(): WebSocketMetrics {
    const channels = new Set<string>();
    for (const [, state] of this.clients) {
      for (const ch of state.subscriptions) channels.add(ch);
    }
    return {
      totalConnections: this.clients.size,
      messagesPerSecond: this.messagesPerSecond,
      activeChannels: [...channels],
    };
  }

  // --------------------------------------------------------------------------
  // Heartbeat — ping every 30 s, close unresponsive clients
  // --------------------------------------------------------------------------

  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      for (const [ws, state] of this.clients) {
        if (!state.isAlive) {
          logger.warn("Terminating unresponsive WebSocket client");
          ws.terminate();
          this.clients.delete(ws);
          continue;
        }
        state.isAlive = false;
        ws.ping();
      }
    }, HEARTBEAT_INTERVAL_MS);

    // Allow the process to exit even if this timer is running
    this.heartbeatTimer.unref?.();
  }

  // --------------------------------------------------------------------------
  // Metrics rollup — compute messages/sec every second
  // --------------------------------------------------------------------------

  private startMetricsRollup(): void {
    this.metricsTimer = setInterval(() => {
      this.messagesPerSecond = this.messageCount;
      this.messageCount = 0;
    }, 1_000);

    this.metricsTimer.unref?.();
  }

  // --------------------------------------------------------------------------
  // Shutdown
  // --------------------------------------------------------------------------

  async shutdown(): Promise<void> {
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
    if (this.metricsTimer) clearInterval(this.metricsTimer);

    for (const [ws] of this.clients) ws.terminate();
    this.clients.clear();

    await new Promise<void>((resolve, reject) =>
      this.wss.close((err) => (err ? reject(err) : resolve()))
    );

    logger.info("WebSocketManager shut down");
  }
}
