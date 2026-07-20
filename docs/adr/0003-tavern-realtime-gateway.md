# ADR 0003 — Tavern: real-time gateway, single Redis fan-out, read-model proof

- **Status:** Accepted (2026-07-18)
- **Area / service:** Tavern → `services/tavern` (TypeScript)
- **Related:** FABLE-PLAN Wave 1 (Flow 2); ADR-0002 (Academy RAG); `docs/v2-audit.md`

## Context

The Tavern area is framed in the area plan as "grounded multi-agent dialogue with
memory". The Tavern *service* as built is something narrower and real: the
**real-time gateway** that turns the town's Kafka event stream into live browser
updates. Rather than re-implement memory/social-graph in tavern (a separate,
much larger build), this increment scopes tavern's Definition of Done to what the
service uniquely and truthfully does — deliver events to browsers — and
**cross-links** the "why this NPC said this" grounding to where it actually lives:
Academy's cited answers + town-core's context-building.

## Decision

1. **Tavern is a delivery gateway, not a generator.** It consumes six town topics
   and routes each to a WebSocket channel (`events`, `market`, `content`,
   `npc:{id}`). It does not generate or ground dialogue; the content event carries
   its lineage (participants, tone, model) so the UI can attribute it honestly.

2. **Redis pub/sub is the single fan-out path.** Each handler publishes the event
   to Redis; a dedicated Redis subscriber forwards it to the WebSocket layer
   (`server.ts` wires `redisPubSub.start(...)` → `wsManager.broadcast`). Handlers
   used to *also* broadcast directly, which double-delivered every event to
   same-node clients (the subscriber echoes this process's own publishes back).
   One path removes the duplication and is what lets multiple tavern instances
   share clients — any instance's event reaches every instance's subscribers.

3. **The WebSocket envelope conforms to the dashboard.** Broadcast frames are
   `{ channel, type, payload, timestamp }` (matching the dashboard's `WsMessage`,
   which reads `message.payload`), and the subscribe handshake accepts the verb as
   either `action` (tavern-native) or `type` (what the dashboard sends). Before
   this, tavern sent `{ channel, data }` and switched on `action`, so it rejected
   every dashboard subscription and delivered an undefined payload.

4. **The proof panel reads a read-model, not the live socket.** Tavern keeps a
   bounded in-memory ring of recent content events and serves it at
   `GET /content/recent`; the dashboard `TavernProofPanel` polls it (via a
   dormant-safe BFF) and shows live gateway metrics. Polling a read-model is
   dormant-safe — it can render an explicit `—` when tavern is down — which the
   live WebSocket cannot distinguish from "idle". The live WS path is the gateway's
   real job (and is now correct); the *proof* rides the read-model.

5. **A deterministic gate, no live broker in CI.** `test-tavern` drives the real
   `WebSocketManager` over a real HTTP server + real `ws` clients (subscribe,
   channel gating, the envelope), and feeds a synthetic `ContentGenerated` through
   the consumer's `dispatch()` to assert one Redis publish + the ring buffer. Live
   multi-client delivery (Redis + Kafka) is honestly stated as *not* gated.

## Consequences

- **Positive:** the live dialogue path from Kafka to the browser now actually
  works (correct envelope + accepted handshake); no double-delivery; the gateway
  scales across instances via the single Redis path; the proof panel is
  dormant-safe and never fabricates; the area's DoD is scoped to what's true.
- **Negative / deferred:**
  - **Live delivery depends on Redis.** With the single fan-out path, WebSocket
    delivery rides the Redis pub/sub loopback; if Redis is down, tavern (which
    already hard-depends on Redis) delivers nothing. This is the intended
    multi-instance architecture, not a regression.
  - **The read-model is in-memory and lost on restart.** Fine for a "recent
    activity" panel; a durable content history would need a store.
  - **OpenTelemetry is dormant.** `src/telemetry.ts` defines OTel + Prometheus
    but nothing initialises it; it is labelled dormant in code and the README, and
    no surface claims tavern has tracing (principle 3).
  - **The `world`/`metrics` dashboard channels remain broken** — they aren't in
    tavern's allowed set; that pre-existing mismatch is documented, not silently
    "fixed" by loosening the gate.

## Alternatives considered

- **Keep the direct broadcast, dedupe by tagging Redis messages with an origin id**
  — rejected: the Redis channel payload is a shared event shape; tagging it risks
  other subscribers, and Redis is already required, so the single-path design is
  simpler and correct.
- **Render the proof from a live WebSocket subscription** — rejected for the proof
  surface: a live socket can't cleanly show a dormant `—` vs idle. The live path is
  kept correct for real delivery; the panel polls the read-model.
- **Build memory / social-graph in tavern to own "why this NPC said this"** —
  deferred: that's a knowledge-graph + memory pipeline, far larger than a gateway
  6/6. The grounding is cross-linked to Academy + town-core where it truly lives.
