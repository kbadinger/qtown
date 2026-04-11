import { WebSocketServer, WebSocket } from "ws";
import type { IncomingMessage } from "http";
import type { Server } from "http";
import pino from "pino";

const logger = pino({ name: "websocket-manager" });

const HEARTBEAT_INTERVAL_MS = 30_000;

interface ClientState {
  ws: WebSocket;
  subscriptions: Set<string>;
  isAlive: boolean;
}

export class WebSocketManager {
  private readonly wss: WebSocketServer;
  private readonly clients = new Map<WebSocket, ClientState>();
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;

  constructor(server: Server) {
    this.wss = new WebSocketServer({ server });
    this.wss.on("connection", this.handleConnection.bind(this));
    this.startHeartbeat();
    logger.info("WebSocketManager initialised");
  }

  // ---------------------------------------------------------------------------
  // Connection lifecycle
  // ---------------------------------------------------------------------------

  private handleConnection(ws: WebSocket, _req: IncomingMessage): void {
    const state: ClientState = { ws, subscriptions: new Set(), isAlive: true };
    this.clients.set(ws, state);
    logger.info({ connections: this.clients.size }, "Client connected");

    ws.on("pong", () => {
      const s = this.clients.get(ws);
      if (s) s.isAlive = true;
    });

    ws.on("message", (raw) => this.handleMessage(ws, raw.toString()));

    ws.on("close", () => {
      this.clients.delete(ws);
      logger.info({ connections: this.clients.size }, "Client disconnected");
    });

    ws.on("error", (err) => {
      logger.error({ err }, "WebSocket client error");
      ws.terminate();
      this.clients.delete(ws);
    });
  }

  private handleMessage(ws: WebSocket, raw: string): void {
    try {
      const msg = JSON.parse(raw) as { action?: string; channel?: string };

      if (msg.action === "subscribe" && typeof msg.channel === "string") {
        const state = this.clients.get(ws);
        if (state) {
          state.subscriptions.add(msg.channel);
          logger.debug({ channel: msg.channel }, "Client subscribed");
        }
      } else if (msg.action === "unsubscribe" && typeof msg.channel === "string") {
        const state = this.clients.get(ws);
        if (state) {
          state.subscriptions.delete(msg.channel);
          logger.debug({ channel: msg.channel }, "Client unsubscribed");
        }
      }
    } catch {
      // Ignore malformed messages
    }
  }

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  /**
   * Broadcasts a payload to all clients subscribed to the given channel.
   * If a client has no subscriptions at all it is treated as subscribed to everything.
   */
  broadcast(channel: string, data: unknown): void {
    const payload = JSON.stringify({ channel, data });
    let sent = 0;

    for (const [ws, state] of this.clients) {
      if (ws.readyState !== WebSocket.OPEN) continue;
      if (state.subscriptions.size > 0 && !state.subscriptions.has(channel)) continue;

      ws.send(payload, (err) => {
        if (err) logger.warn({ err }, "Failed to send to client");
      });
      sent++;
    }

    logger.debug({ channel, sent }, "Broadcast complete");
  }

  getConnectionCount(): number {
    return this.clients.size;
  }

  // ---------------------------------------------------------------------------
  // Heartbeat
  // ---------------------------------------------------------------------------

  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      for (const [ws, state] of this.clients) {
        if (!state.isAlive) {
          logger.warn("Terminating unresponsive client");
          ws.terminate();
          this.clients.delete(ws);
          continue;
        }
        state.isAlive = false;
        ws.ping();
      }
    }, HEARTBEAT_INTERVAL_MS);
  }

  async shutdown(): Promise<void> {
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
    for (const [ws] of this.clients) ws.terminate();
    this.clients.clear();
    await new Promise<void>((resolve, reject) =>
      this.wss.close((err) => (err ? reject(err) : resolve()))
    );
    logger.info("WebSocketManager shut down");
  }
}
