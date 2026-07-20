import { describe, it, expect, beforeAll, afterAll, vi } from "vitest";
import { Kafka } from "kafkajs";
import { WebSocket } from "ws";
import type { AddressInfo } from "net";
import { buildServer } from "../server.js";

// Live end-to-end gate for the Tavern gateway: a real Kafka event flows through
// the real consumer → Redis pub/sub → a real WebSocket client, and lands in the
// read-model. Needs Kafka + Redis, so it is SKIPPED unless TAVERN_E2E is set (the
// e2e-tavern CI job spins the deps compose and sets it). REDIS_URL / KAFKA_BROKERS
// are read by server.ts at import — the job sets them.

const E2E = Boolean(process.env["TAVERN_E2E"]);
const BROKERS = (process.env["KAFKA_BROKERS"] ?? "localhost:9092").split(",");

type Built = Awaited<ReturnType<typeof buildServer>>;

describe.skipIf(!E2E)("tavern content flow (e2e: Kafka + Redis)", () => {
  let built: Built;
  let port: number;

  beforeAll(async () => {
    built = await buildServer();
    await built.fastify.listen({ port: 0, host: "127.0.0.1" });
    port = (built.fastify.server.address() as AddressInfo).port;
    await built.redisPubSub.start((ch, data) => built.wsManager.broadcast(ch, data));
    await built.kafkaConsumer.start();
    // Give the consumer time to join the group (subscribes fromBeginning:false).
    await new Promise((r) => setTimeout(r, 5000));
  }, 45_000);

  afterAll(async () => {
    await built.kafkaConsumer.shutdown().catch(() => {});
    await built.redisPubSub.shutdown().catch(() => {});
    await built.wsManager.shutdown().catch(() => {});
    await built.fastify.close().catch(() => {});
  });

  it("Kafka content event → WebSocket subscriber + /content/recent", async () => {
    const messages: Record<string, unknown>[] = [];
    const ws = new WebSocket(`ws://127.0.0.1:${port}/ws`);
    ws.on("message", (raw: unknown) => messages.push(JSON.parse(String(raw)) as Record<string, unknown>));
    await new Promise<void>((resolve, reject) => {
      ws.once("open", () => resolve());
      ws.once("error", reject);
    });
    ws.send(JSON.stringify({ action: "subscribe", channel: "content" }));
    await new Promise((r) => setTimeout(r, 500));

    const kafka = new Kafka({ clientId: "tavern-e2e", brokers: BROKERS });
    const producer = kafka.producer();
    await producer.connect();
    const event = {
      type: "ai.content.generated",
      content_type: "dialogue",
      content_id: "e2e-dialogue-1",
      text: "NPC 1: e2e hello",
      metadata: { npc_a: 1, npc_b: 2, tone: "friendly", model_used: "qwen3.5:4b" },
    };
    await producer.send({
      topic: "qtown.ai.content.generated",
      messages: [{ value: JSON.stringify(event) }],
    });
    await producer.disconnect();

    // Kafka → consumer → Redis publish → RedisPubSub → wsManager.broadcast → client.
    await vi.waitFor(
      () => {
        const hit = messages.find(
          (m) =>
            m.channel === "content" &&
            (m.payload as { content_id?: string } | undefined)?.content_id === "e2e-dialogue-1"
        );
        expect(hit).toBeTruthy();
      },
      { timeout: 20_000, interval: 300 }
    );

    // The read-model recorded it too.
    const res = await built.fastify.inject({ method: "GET", url: "/content/recent?limit=20" });
    const body = res.json() as { available: boolean; items: { content_id: string }[] };
    expect(body.available).toBe(true);
    expect(body.items.some((i) => i.content_id === "e2e-dialogue-1")).toBe(true);

    ws.close();
  }, 40_000);
});
