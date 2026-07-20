# Market — load test & measured latency (W1-M7)

**Every number here is measured, not modelled.** It is a *local reference run*, not a
CI-enforced SLO (a continuous over-the-wire perf gate needs a dedicated/stable runner —
tracked as a follow-on below). The in-process engine micro-benchmark (measurement **C**)
*is* run on every CI build (`test-market` job → `go test -bench`).

## Environment

| | |
|---|---|
| Date | 2026-07-15 |
| CPU | 12th Gen Intel Core i9-12900K (16 cores / 24 threads) |
| OS | Windows 11 (10.0.26200) |
| Go | 1.24.2 |
| Load tool | [`ghz`](https://ghz.sh) (built from `github.com/bojand/ghz@latest`) over gRPC, server reflection |
| Kafka | `apache/kafka:3.7.0` (KRaft), single broker, via `docker-compose.deps.yml` |
| Target | one `market-district` server instance, `:50051`, `KAFKA_BROKERS=localhost:9092` |
| Load params | `-n 20000 -c 50 --connections 5` for each gRPC run |

Loopback (client and server on the same box) — so these numbers **exclude real network
latency** and are a lower bound on a deployed system's tail. That is stated, not hidden.

## What was measured, and why three numbers

`PlaceOrder` does three things: insert into the book, run matching, and — *only if a trade
matches* — emit two `trade.settled` events to Kafka **synchronously and inline**
(`internal/grpc/server.go` → `emitTradesSettled`). So the latency depends entirely on
whether the order matches. Reporting one blended number would hide that. Instead:

| # | Path exercised | Isolates |
|---|---|---|
| **A** | gRPC `PlaceOrder`, **non-crossing** workload (all bids, 200 distinct resources) → no match → Kafka never touched | transport + book insert |
| **B** | gRPC `PlaceOrder`, **crossing** workload (alternating bid/ask, one resource) → ~50% match → 2× synchronous Kafka emit per match | the **full production spine** |
| **C** | In-process `OrderBook.PlaceOrder`+`Match` (no gRPC, no Kafka) — the existing `go test -bench` | the matching **engine** alone |

## Results

### A — placement floor (no match, no Kafka)

```
Count:        20000        Requests/sec: 41758
Slowest:      4.80 ms      Average:      0.54 ms
Latency:  p50 0.52 ms · p95 1.59 ms · p99 2.16 ms
Status:   [OK] 20000        (0 errors)
```

### B — full spine (match → 2× synchronous trade.settled emit)

```
Count:        20000        Requests/sec: 4236
Slowest:      71.16 ms     Average:      11.44 ms
Latency:  p50 3.00 ms · p75 22.47 ms · p95 23.67 ms · p99 24.71 ms
Status:   [OK] 20000        (0 errors)
```

The response-time histogram is **bimodal**: one cluster at ~0–3 ms (resting bids that don't
match) and one at ~22–28 ms (asks that cross and pay the emit cost). Confirmed downstream:
the run produced **20,002 `trade.settled` messages** on the real topic (≈10k matches × 2
single-sided events), evenly spread across all 6 partitions, **0 dropped, 0 gRPC errors** —
the spine is proven end-to-end *under load*, not just in the e2e unit gate.

### C — matching engine, in-process (runs in CI on every build)

```
BenchmarkOrderBook-24    1000000    2186 ns/op     (~2.2 µs per place+match cycle)
```

## Reading the numbers

- **The engine is not the bottleneck.** A place+match cycle is ~2.2 µs in-process (C); over
  gRPC without settlement, p99 is **2.16 ms at ~42k rps** (A). The matching engine has
  headroom to spare.
- **The matched-order tail is dominated by the synchronous Kafka emit.** A match emits two
  events inline, and the producer's `BatchTimeout` is 10 ms with `RequiredAcks=all`
  (`internal/kafka/producer.go`), so a matched `PlaceOrder` waits ≈ 2 × 10 ms before
  returning — exactly the ~24 ms p99 and the ~22–28 ms cluster in (B). This is a real
  property of the current *best-effort, inline* emit, surfaced honestly rather than hidden
  behind a favourable single number.

## Follow-ons (tracked, not done)

- **Async emit** would move the two Kafka writes off the `PlaceOrder` hot path (fire-and-forget
  or a small outbox), collapsing the matched-order tail back toward the ~2 ms placement floor.
  This overlaps the durability work in **W1-M5** (match↔emit atomicity) — the emit path is
  redesigned once, for both latency and durability.
- **A continuous over-the-wire perf gate** (this load test in CI, asserting a floor) needs a
  dedicated runner — shared CI runners are too noisy for a stable p99 assertion, and a flaky
  perf gate is worse than none. Until then the engine micro-bench (C) guards the hot path on
  every build, and this report is the reference for the wire numbers.

## Reproduce

```bash
# 1. infra + topic
docker compose -f docker-compose.deps.yml up -d kafka

# 2. server (reflection is registered, so ghz needs no .proto)
cd services/market-district && KAFKA_BROKERS=localhost:9092 go run ./cmd/server

# 3. install ghz once
go install github.com/bojand/ghz/cmd/ghz@latest

# 4A. placement floor — non-crossing (data file: 200 distinct resources, all BID)
ghz --insecure --call qtown.MarketDistrict.PlaceOrder \
    -D ghz-nomatch.json -n 20000 -c 50 --connections 5 localhost:50051

# 4B. full spine — crossing (data file cycles [BID@100, ASK@100] on one resource)
ghz --insecure --call qtown.MarketDistrict.PlaceOrder \
    -D ghz-crossing.json -n 20000 -c 50 --connections 5 localhost:50051

# C. engine micro-bench (also runs in CI)
go test -bench=. -benchtime=2s -run '^$' ./internal/orderbook/
```

`ghz-crossing.json` and the 200-resource `ghz-nomatch.json` are the workload files described
in the table above; regenerate `ghz-nomatch.json` with:
`python -c "import json;print(json.dumps([{'npcId':i%1000+1,'resource':'res-%d'%(i%200),'side':'BID','price':100,'quantity':1} for i in range(200)]))"`.
