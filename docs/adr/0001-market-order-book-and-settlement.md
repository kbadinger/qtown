# ADR 0001 — Market: in-memory order book, single-sided settlement, idempotent consumers

- **Status:** Accepted (2026-07-15)
- **Area / service:** Market → `services/market-district` (Go)
- **Related:** FABLE-PLAN Wave 1A (W1-M1/M3/M4/M6/M8); `docs/v2-audit.md`

## Context

The Market area is qtown v2's distributed-systems proof. It needs to demonstrate,
for real: a concurrent matching engine, a typed cross-service contract, and an
event backbone that survives redelivery — end-to-end, behind a CI gate, without
fabricating data. It is one hop in a larger flow: town-core originates an order
(gRPC), the book matches, and the resulting economic effect must propagate back
to the owning NPCs' gold (Kafka) and to the social/search layers.

## Decision

1. **In-memory limit order book (Go), matched synchronously inside `PlaceOrder`.**
   The order book lives in process memory; a match runs inline and returns the
   fill in the gRPC response. This keeps the matching path allocation-light and
   is the honest shape of the "concurrency" proof; it deliberately trades away
   durability (see Consequences).

2. **gRPC contract from a single generated source of truth.** Wire types come
   from `proto/qtown/*.proto` via `buf generate` into the committed `gen/go`
   module (`module qtown/proto`), consumed with a `replace` directive. A CI
   drift gate fails if the committed `gen/` doesn't match a fresh generate. This
   replaced hand-written placeholder structs that had silently drifted from the
   proto.

3. **Single-sided settlement events.** A match emits **two** independent
   `qtown.economy.trade.settled` messages — one per counterparty —
   `{npc_id, gold_delta, resource, price, quantity, trade_id}` (buyer
   `gold_delta < 0`, seller `> 0`), sharing one `trade_id`. Each consumer only
   needs its own NPC's delta; no consumer has to understand "the other side."

4. **At-least-once emit + idempotent consumers.** Emission is best-effort — a
   Kafka failure is logged and swallowed, never failing a trade. Because that
   makes delivery at-least-once, consumers dedupe: town-core keys idempotency on
   `(trade_id, npc_id)` (buyer and seller share `trade_id`, so the compound key
   is required), applies the gold delta and records the ledger row atomically,
   and routes poison messages to a `<topic>.dlq` with a replay path.

5. **Client-side resilience in the caller (town-core).** The town-core → market
   gRPC client bounds every call with a deadline and trips a circuit breaker
   after repeated failures, so a down market degrades to a fast no-op instead of
   stalling the 30s sim tick.

6. **A blocking e2e gate over real infrastructure.** `e2e-market` (CI) stands up
   Kafka from the deps compose and runs a tagged test that drives a real gRPC
   `PlaceOrder` and asserts both settlement messages arrive on the real topic.
   This is what makes the flow *proven*, not just unit-passing.

## Consequences

- **Positive:** the matching path is simple and fast; the contract can't silently
  drift; consumers are replay-safe; a market outage never breaks a trade or the
  tick; the e2e gate turns "wired" into "provably runs."
- **Negative / deferred:**
  - The in-memory book has **no durability** — a crash loses resting orders and
    any match that hadn't yet emitted. Match↔emit atomicity (an outbox or a
    persisted book) is a tracked follow-on (W1-M5). Until then, settlement is
    at-least-once *if the process survives the emit*, not exactly-once across
    crashes.
  - Producer NPCs currently escrow surplus into resting asks with **no
    cancellation/expiry** yet, so unfilled orders park goods on the exchange
    (order-lifecycle management is tracked with W1-M4/M5).
  - **No measured performance number is published** until the load test (W1-M7)
    commits one — the README states throughput/p99 as "in flight," never a
    guessed figure.

## Alternatives considered

- **Persisted order book (Postgres) from the start** — rejected for now: adds a
  storage dependency to the matching hot path before the flow is even proven
  end-to-end. Revisit via W1-M5 once the outbox/durability requirement is real.
- **Two-sided settlement event** (one message describing both parties) — rejected:
  forces every consumer to parse both sides and match itself against one; the
  single-sided shape is what each consumer actually needs.
