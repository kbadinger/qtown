import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { createServer, type Server } from "http";
import type { AddressInfo } from "net";
import { WebSocket } from "ws";
import { WebSocketManager } from "../websocket.js";

// Real coverage of the WebSocket layer: a real HTTP server + real `ws` clients
// driven through the actual WebSocketManager (subscribe handshake, channel
// gating, broadcast fan-out, metrics). This LOCKS the outbound wire contract so a
// later contract change is a visible, test-guarded diff.

type Json = Record<string, unknown>;

interface TestClient {
  ws: WebSocket;
  // Next message from the server (queued from connect time, so the welcome is
  // never lost to a listener-attach race).
  next(timeoutMs?: number): Promise<Json>;
  subscribe(channel: string): Promise<Json>;
}

function makeClient(port: number): Promise<TestClient> {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}/ws`);
    const queue: Json[] = [];
    let waiter: ((m: Json) => void) | null = null;

    ws.on("message", (raw: unknown) => {
      const m = JSON.parse(String(raw)) as Json;
      if (waiter) {
        const w = waiter;
        waiter = null;
        w(m);
      } else {
        queue.push(m);
      }
    });

    const client: TestClient = {
      ws,
      next(timeoutMs = 2000): Promise<Json> {
        const queued = queue.shift();
        if (queued) return Promise.resolve(queued);
        return new Promise<Json>((res, rej) => {
          const t = setTimeout(() => {
            waiter = null;
            rej(new Error("timeout waiting for message"));
          }, timeoutMs);
          waiter = (m) => {
            clearTimeout(t);
            res(m);
          };
        });
      },
      subscribe(channel: string): Promise<Json> {
        ws.send(JSON.stringify({ action: "subscribe", channel }));
        return client.next();
      },
    };

    ws.once("open", () => resolve(client));
    ws.once("error", reject);
  });
}

describe("WebSocketManager (real server + clients)", () => {
  let server: Server;
  let manager: WebSocketManager;
  let port: number;

  beforeEach(async () => {
    server = createServer();
    manager = new WebSocketManager(server);
    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
    port = (server.address() as AddressInfo).port;
  });

  afterEach(async () => {
    await manager.shutdown();
    await new Promise<void>((resolve) => server.close(() => resolve()));
  });

  it("sends a welcome listing the allowed channels on connect", async () => {
    const c = await makeClient(port);
    const welcome = await c.next();
    expect(welcome.type).toBe("welcome");
    expect(welcome.channels).toContain("content");
    c.ws.close();
  });

  it("acks a subscribe and delivers a broadcast on that channel", async () => {
    const c = await makeClient(port);
    await c.next(); // welcome
    const ack = await c.subscribe("content");
    expect(ack).toEqual({ type: "subscribed", channel: "content" });

    const event = { content_type: "dialogue", content_id: "d-1", text: "hi" };
    manager.broadcast("content", event);

    const msg = await c.next();
    // Outbound wire contract (locked): { channel, data, timestamp }.
    expect(msg.channel).toBe("content");
    expect(msg.data).toEqual(event);
    expect(typeof msg.timestamp).toBe("string");
    c.ws.close();
  });

  it("does not deliver to a client not subscribed to the channel", async () => {
    const c = await makeClient(port);
    await c.next(); // welcome
    await c.subscribe("market");

    manager.broadcast("content", { content_type: "dialogue" });
    await expect(c.next(400)).rejects.toThrow(/timeout/);
    c.ws.close();
  });

  it("rejects an unknown action", async () => {
    const c = await makeClient(port);
    await c.next(); // welcome
    c.ws.send(JSON.stringify({ action: "frobnicate", channel: "content" }));
    const err = await c.next();
    expect(err.type).toBe("error");
    c.ws.close();
  });

  it("rejects a disallowed channel", async () => {
    const c = await makeClient(port);
    await c.next(); // welcome
    c.ws.send(JSON.stringify({ action: "subscribe", channel: "admin" }));
    const err = await c.next();
    expect(err.type).toBe("error");
    expect(String(err.message)).toMatch(/channel/i);
    c.ws.close();
  });

  it("allows npc:{id} channels and delivers to them", async () => {
    const c = await makeClient(port);
    await c.next(); // welcome
    await c.subscribe("npc:npc-001");

    manager.broadcast("npc:npc-001", { npc_id: "npc-001", status: "traveling" });
    const msg = await c.next();
    expect(msg.channel).toBe("npc:npc-001");
    expect((msg.data as { npc_id: string }).npc_id).toBe("npc-001");
    c.ws.close();
  });

  it("reports connection count and active channels", async () => {
    const c = await makeClient(port);
    await c.next(); // welcome
    await c.subscribe("events");
    expect(manager.getConnectionCount()).toBe(1);
    expect(manager.getMetrics().activeChannels).toContain("events");
    c.ws.close();
  });
});
