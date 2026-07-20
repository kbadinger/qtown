# tavern

The **Tavern** area's backing service — a TypeScript real-time **gateway** that
turns the town's Kafka event stream into live browser updates. It consumes town
topics, fans them out over Redis pub/sub (so many instances can share clients),
and broadcasts them to WebSocket channels. It is the delivery layer for the AI
dialogue flow (Flow 2): Academy generates a conversation → `qtown.ai.content.generated`
→ tavern → the dashboard.

## What it does

- **Consumes** six Kafka topics and routes each to a WebSocket channel
  (`src/kafka-consumer.ts`): `qtown.events.broadcast` → `events`,
  `qtown.economy.trade.settled` / `qtown.economy.price.update` → `market`,
  `qtown.ai.content.generated` → `content`, and the two travel topics → a
  per-NPC `npc:{id}` channel.
- **Fans out over Redis pub/sub** (`src/redis-pubsub.ts`): each handler publishes
  the event to Redis; a dedicated subscriber forwards it to the WebSocket layer.
  This is the **single** fan-out path — broadcasting directly as well would
  double-deliver, since the subscriber echoes this process's own publishes back.
- **Broadcasts** to channel subscribers over WebSocket (`src/websocket.ts`):
  clients subscribe to channels; an event is sent only to that channel's
  subscribers, in a `{ channel, type, payload, timestamp }` envelope. A 30 s
  ping/pong heartbeat reaps dead connections.
- **Serves a read-model** for dashboards: recent content that passed through the
  gateway (`GET /content/recent`) + live gateway metrics (`GET /metrics`).
- Maintains real Redis-backed **leaderboards** (gold/happiness/crimes) and **NPC
  presence** as a side effect of the events it sees.

## Contract

- **WebSocket (`ws://<host>/ws`)**
  - **Subscribe:** send `{ "action"|"type": "subscribe", "channel": "content" }`
    (both verbs accepted). Allowed channels: `events`, `market`, `content`,
    `leaderboard`, `npc:{id}`.
  - **Receive:** `{ channel, type, payload, timestamp }` — `payload` is the event;
    `type` is the event's own `type` when present, else the channel.
- **HTTP (:3001)** — `GET /health`, `GET /metrics`
  (`{ totalConnections, messagesPerSecond, activeChannels }`),
  `GET /content/recent?limit=` (`{ available, items[] }`),
  `GET /leaderboard/:type`, `GET /npc/:id/presence`, `GET /presence`.
- **Kafka — consumes** the six topics above (group `tavern-consumer-group`).
- **Env:** `PORT` (3001), `REDIS_URL`, `KAFKA_BROKERS`.

## Run

```bash
cd services/tavern
npm install
npm run build        # tsc → dist/
npm test             # vitest — WS layer + content-flow gate + leaderboard

# run (needs Redis + Kafka)
REDIS_URL=redis://localhost:6379 KAFKA_BROKERS=localhost:9092 npm start
```

## Status (honest)

| Capability | State |
|---|---|
| Kafka consume → channel routing | ✅ real (`src/kafka-consumer.ts`) |
| Redis pub/sub fan-out (single path, multi-instance) | ✅ real (`src/redis-pubsub.ts`); the double-broadcast defect is fixed |
| Channel-scoped WebSocket delivery + heartbeat | ✅ real (`src/websocket.ts`) |
| WS layer + content-flow gate | ✅ **blocking CI job** `test-tavern` — real `ws` clients drive the actual manager; a synthetic `ContentGenerated` asserts one publish + the ring buffer |
| Live end-to-end gate (Kafka → consumer → Redis → WebSocket + read-model) | ✅ **blocking CI job** `e2e-tavern` — real Kafka event flows to a real WebSocket subscriber and the read-model (deps from `docker-compose.deps.yml`) |
| Content read-model (`/content/recent`) + dashboard proof panel | ✅ real (W1-T) — `TavernProofPanel.vue` renders live metrics + recent content or an honest dormant `—` |
| In-app teaching layer | ✅ real (W1-T) — `TavernTeaching.vue`, honestly cross-linking the "why this NPC said this" grounding to Academy + town-core |
| Redis leaderboards + NPC presence | ✅ real |
| Multi-instance fan-out (2+ tavern nodes sharing clients via Redis) | ⏳ the architecture is Redis-based + correct, but a multi-node topology isn't exercised by a gate (the single-node live path IS — see `e2e-tavern`) |
| OpenTelemetry / Prometheus tracing (`src/telemetry.ts`) | ⚠️ **dormant** — defined but never initialised; not wired into the running service |
| Leaderboard name enrichment | ⏳ `name` is stubbed to the npc_id pending a lookup layer |

See `docs/adr/0003-tavern-realtime-gateway.md` for the design rationale, and
`docs/v2-audit.md` for the cross-service flow status.
