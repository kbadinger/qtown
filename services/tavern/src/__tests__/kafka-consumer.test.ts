import { describe, it, expect, vi } from "vitest";
import { KafkaConsumerService } from "../kafka-consumer.js";
import { ContentBuffer } from "../content-buffer.js";
import type { RedisClient } from "../redis.js";

// Deterministic gate for the Kafka → content path (no live broker): feed a
// synthetic record through the consumer's dispatch() and assert the single Redis
// publish (the fan-out path) + the read-model ring buffer.

function mockRedis(): RedisClient {
  return { publish: vi.fn().mockResolvedValue(1) } as unknown as RedisClient;
}

function makeConsumer(redis: RedisClient, buffer: ContentBuffer): KafkaConsumerService {
  return new KafkaConsumerService(
    { clientId: "test", brokers: ["localhost:9092"] },
    redis,
    buffer
  );
}

describe("ContentBuffer", () => {
  it("keeps newest-first and bounds to max", () => {
    const buf = new ContentBuffer(3);
    for (let i = 1; i <= 5; i++) {
      buf.add({ content_type: "dialogue", content_id: `d-${i}`, received_at: String(i) });
    }
    expect(buf.size()).toBe(3);
    expect(buf.recent(10).map((it) => it.content_id)).toEqual(["d-5", "d-4", "d-3"]);
  });

  it("recent(limit) slices from the newest", () => {
    const buf = new ContentBuffer(10);
    buf.add({ content_type: "dialogue", content_id: "a", received_at: "1" });
    buf.add({ content_type: "dialogue", content_id: "b", received_at: "2" });
    expect(buf.recent(1).map((it) => it.content_id)).toEqual(["b"]);
  });
});

describe("KafkaConsumerService content path", () => {
  it("publishes a content event ONCE to the 'content' channel and records it", async () => {
    const redis = mockRedis();
    const buffer = new ContentBuffer(100);
    const consumer = makeConsumer(redis, buffer);

    const event = {
      type: "ai.content.generated",
      content_type: "dialogue",
      content_id: "dialogue-1-2-99",
      content: [{ npc_id: 1, text: "hi", emotion: "happy" }],
      text: "NPC 1: hi",
      metadata: { npc_a: 1, npc_b: 2, tone: "friendly", model_used: "qwen3.5:4b" },
    };
    await consumer.dispatch("qtown.ai.content.generated", JSON.stringify(event));

    // Single fan-out path (no double-publish): exactly one publish to 'content'.
    expect(redis.publish).toHaveBeenCalledTimes(1);
    expect(redis.publish).toHaveBeenCalledWith("content", expect.any(String));

    // Read-model: recorded with mapped fields.
    const items = buffer.recent(10);
    expect(items).toHaveLength(1);
    expect(items[0]!.content_id).toBe("dialogue-1-2-99");
    expect(items[0]!.text).toBe("NPC 1: hi");
    expect(items[0]!.metadata).toEqual(event.metadata);
    expect(typeof items[0]!.received_at).toBe("string");
  });

  it("does not record non-content events in the content buffer", async () => {
    const redis = mockRedis();
    const buffer = new ContentBuffer(100);
    const consumer = makeConsumer(redis, buffer);

    const event = {
      type: "events.broadcast",
      event_id: "e1",
      event_type: "fire",
      description: "A fire broke out",
      tick: 5,
    };
    await consumer.dispatch("qtown.events.broadcast", JSON.stringify(event));

    expect(redis.publish).toHaveBeenCalledWith("events", expect.any(String));
    expect(buffer.size()).toBe(0);
  });

  it("ignores malformed JSON without throwing or publishing", async () => {
    const redis = mockRedis();
    const buffer = new ContentBuffer(100);
    const consumer = makeConsumer(redis, buffer);

    await expect(
      consumer.dispatch("qtown.ai.content.generated", "{not json")
    ).resolves.toBeUndefined();
    expect(redis.publish).not.toHaveBeenCalled();
    expect(buffer.size()).toBe(0);
  });
});
