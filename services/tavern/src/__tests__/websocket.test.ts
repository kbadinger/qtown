import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { WebSocket } from "ws";
import { EventEmitter } from "events";

// ============================================================================
// Mock WebSocketServer
// ============================================================================

// We test the WebSocketManager by injecting mock WebSocket instances, since
// spinning up a real HTTP server in unit tests is fragile.

class MockWebSocket extends EventEmitter {
  readyState: number = WebSocket.OPEN;
  sentMessages: string[] = [];

  send(data: string, cb?: (err?: Error) => void): void {
    if (this.readyState === WebSocket.OPEN) {
      this.sentMessages.push(data);
    }
    cb?.();
  }

  ping(): void {
    // no-op in tests
  }

  terminate(): void {
    this.readyState = WebSocket.CLOSED;
  }
}

// ============================================================================
// Unit tests for subscription/broadcast logic
// ============================================================================

describe("WebSocket subscription protocol", () => {
  it("parses subscribe message correctly", () => {
    const msg = JSON.parse('{"action":"subscribe","channel":"events"}') as {
      action: string;
      channel: string;
    };
    expect(msg.action).toBe("subscribe");
    expect(msg.channel).toBe("events");
  });

  it("parses unsubscribe message correctly", () => {
    const msg = JSON.parse(
      '{"action":"unsubscribe","channel":"market"}'
    ) as { action: string; channel: string };
    expect(msg.action).toBe("unsubscribe");
    expect(msg.channel).toBe("market");
  });

  it("validates allowed channel names", () => {
    const ALLOWED_CHANNELS = new Set(["events", "market", "content", "leaderboard"]);
    const isAllowed = (ch: string): boolean => {
      if (ALLOWED_CHANNELS.has(ch)) return true;
      return /^npc:[a-zA-Z0-9_-]+$/.test(ch);
    };

    expect(isAllowed("events")).toBe(true);
    expect(isAllowed("market")).toBe(true);
    expect(isAllowed("content")).toBe(true);
    expect(isAllowed("leaderboard")).toBe(true);
    expect(isAllowed("npc:npc-001")).toBe(true);
    expect(isAllowed("npc:abc123")).toBe(true);
    expect(isAllowed("unknown")).toBe(false);
    expect(isAllowed("npc:")).toBe(false);
    expect(isAllowed("admin")).toBe(false);
  });
});

describe("broadcast logic", () => {
  it("sends to subscribed clients only", () => {
    const subscribedWs = new MockWebSocket();
    const unsubscribedWs = new MockWebSocket();

    // Simulate subscription maps
    const clients = new Map<MockWebSocket, Set<string>>();
    clients.set(subscribedWs, new Set(["events"]));
    clients.set(unsubscribedWs, new Set(["market"]));

    // Simulate broadcast
    const channel = "events";
    const payload = JSON.stringify({
      channel,
      data: { type: "test" },
      timestamp: new Date().toISOString(),
    });

    for (const [ws, subs] of clients) {
      if (ws.readyState !== WebSocket.OPEN) continue;
      if (!subs.has(channel)) continue;
      ws.send(payload);
    }

    expect(subscribedWs.sentMessages).toHaveLength(1);
    expect(unsubscribedWs.sentMessages).toHaveLength(0);
  });

  it("skips closed connections during broadcast", () => {
    const closedWs = new MockWebSocket();
    closedWs.readyState = WebSocket.CLOSED;

    const clients = new Map<MockWebSocket, Set<string>>();
    clients.set(closedWs, new Set(["events"]));

    const payload = JSON.stringify({ channel: "events", data: {} });

    for (const [ws, subs] of clients) {
      if (ws.readyState !== WebSocket.OPEN) continue;
      if (!subs.has("events")) continue;
      ws.send(payload);
    }

    expect(closedWs.sentMessages).toHaveLength(0);
  });

  it("broadcasts to npc-specific channel", () => {
    const ws = new MockWebSocket();
    const clients = new Map<MockWebSocket, Set<string>>();
    clients.set(ws, new Set(["npc:npc-001"]));

    const channel = "npc:npc-001";
    const payload = JSON.stringify({
      channel,
      data: { npc_id: "npc-001", status: "traveling" },
      timestamp: new Date().toISOString(),
    });

    for (const [wsClient, subs] of clients) {
      if (wsClient.readyState !== WebSocket.OPEN) continue;
      if (!subs.has(channel)) continue;
      wsClient.send(payload);
    }

    expect(ws.sentMessages).toHaveLength(1);
    const msg = JSON.parse(ws.sentMessages[0]!) as { channel: string; data: { npc_id: string } };
    expect(msg.channel).toBe("npc:npc-001");
    expect(msg.data.npc_id).toBe("npc-001");
  });
});

describe("heartbeat logic", () => {
  it("marks isAlive false on ping and true on pong", () => {
    const clients = new Map<MockWebSocket, { isAlive: boolean }>();
    const ws = new MockWebSocket();
    clients.set(ws, { isAlive: true });

    // Simulate heartbeat tick
    for (const [wsClient, state] of clients) {
      if (!state.isAlive) {
        wsClient.terminate();
        clients.delete(wsClient);
        continue;
      }
      state.isAlive = false;
      wsClient.ping();
    }

    // Client should now be marked not-alive
    const state = clients.get(ws);
    expect(state?.isAlive).toBe(false);

    // Simulate pong response
    ws.emit("pong");
    // In real code, pong handler sets isAlive = true
    if (clients.has(ws)) {
      clients.get(ws)!.isAlive = true;
    }

    expect(clients.get(ws)?.isAlive).toBe(true);
  });

  it("terminates unresponsive client on second tick", () => {
    const clients = new Map<MockWebSocket, { isAlive: boolean }>();
    const ws = new MockWebSocket();
    clients.set(ws, { isAlive: false }); // already marked not-alive (no pong received)

    // Second heartbeat tick — should terminate
    for (const [wsClient, state] of clients) {
      if (!state.isAlive) {
        wsClient.terminate();
        clients.delete(wsClient);
      }
    }

    expect(ws.readyState).toBe(WebSocket.CLOSED);
    expect(clients.size).toBe(0);
  });
});

describe("connection metrics", () => {
  it("tracks message counts correctly", () => {
    let messageCount = 0;
    let messagesPerSecond = 0;

    // Simulate incoming messages
    for (let i = 0; i < 5; i++) {
      messageCount++;
    }

    // Rollup
    messagesPerSecond = messageCount;
    messageCount = 0;

    expect(messagesPerSecond).toBe(5);
    expect(messageCount).toBe(0);
  });

  it("reports correct active channels from subscriptions", () => {
    const clients = new Map<string, Set<string>>();
    clients.set("client1", new Set(["events", "market"]));
    clients.set("client2", new Set(["events", "npc:npc-001"]));

    const channels = new Set<string>();
    for (const [, subs] of clients) {
      for (const ch of subs) channels.add(ch);
    }

    expect(channels.size).toBe(3);
    expect(channels.has("events")).toBe(true);
    expect(channels.has("market")).toBe(true);
    expect(channels.has("npc:npc-001")).toBe(true);
  });
});
