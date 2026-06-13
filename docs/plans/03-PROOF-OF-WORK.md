# Plan 03 — Proof of Work: How Every Service Shows It's Real

> Part of the v2 plan pack (`00-MASTER-PLAN.md`). Owns Phase 6.5 and the proof layer of
> Phase 7-B. Source: `docs/v2-audit.md` (the gap this plan closes) and
> `docs/2026-interview-gap-plan.md` Tier 0 + Tier 2.
> The audit's money quote — *"true per-story; misleading at the system level"* — is the
> failure mode this entire plan exists to make structurally impossible.

Proof operates at four levels, and v2 needs all of them:

| Level | Question it answers | Mechanism |
|---|---|---|
| 1. Flow proof | Does the system work end-to-end? | 3 e2e tests as CI gates |
| 2. Number proof | Are the performance claims true? | Committed load-test report |
| 3. Liveness proof | Is it working *right now*? | Health model + proof panels in rooms |
| 4. Trace proof | Can you see *how* it works? | OTel spans → Jaeger, visualized in the Tower |

## 1. Flow proof — e2e tests as the trust boundary

The three flagship flows (audit §Cross-service flow audit) each get one integration
test that exercises every hop. These exist as stories P6-022/023/024; this section
specs them so Opus implements them consistently.

**Layout:** top-level `tests/e2e/` (pytest + `testcontainers`-style against
`docker-compose.yml`; the compose stack IS the test fixture).

| Test | Asserts (every hop, in order) |
|---|---|
| `test_market_trade_flow.py` | town-core origination fires PlaceOrder (P6-010) → market gRPC reachable (P6-005) → match occurs → `economy.trade.settled` lands (P6-006) → town-core wallet delta → tavern WS client receives broadcast → cartographer `recentTrades` returns it |
| `test_ai_dialogue_flow.py` | dialogue trigger (P6-011) → academy gRPC → Ollama responds (or a recorded fixture model in CI — real model locally, deterministic small model in CI; never a mock of the *flow*) → library RAG queried (P6-012) → `ai.content.generated` (P6-007) → tavern WS receives |
| `test_validation_flow.py` | town-core emits request → fortress consumes → WASM verdict → `qtown.validation.result` → town-core consumer acts (P6-008) → state change observable via API |

**CI wiring:** new job `e2e` in `.github/workflows/ci.yml`: boot
`docker-compose.deps.yml` + the services each flow needs, run the three tests, required
for merge. Slow is acceptable (~5–8 min); wrongness is not. Until all three are green,
the README architecture diagram stays marked live-vs-stubbed (P6-025).

**Definition of done (Gate A):** 3/3 green on main, required check, and a red test
blocks merge — verified by intentionally breaking one hop in a PR and watching CI fail.

## 2. Number proof — the load test

The README claims "<5ms p99 at 10K orders/sec" and it has never been run under load.
The measured number wins interviews; the claimed one loses them.

| ID | Story | Done when |
|---|---|---|
| P6.5-001 | `perf/market-district/`: [ghz](https://ghz.sh) script against the gRPC PlaceOrder path under compose; warmup, 3 runs, fixed hardware notes | `perf/run.sh` reproduces on Kevin's machine |
| P6.5-002 | `perf/REPORT.md`: methodology, hardware, p50/p99/p999 at stepped load (1K/5K/10K orders/sec), where it saturates, flamegraph of the hot path | Report committed with real numbers |
| P6.5-003 | README + landing updated to the measured number, whatever it is; Market room proof panel (Plan 01 §4.1) reads from the same report constants | No unmeasured perf claim anywhere in the repo |
| P6.5-004 | Gateway-level k6 script: GraphQL `townOverview` fan-out at 100 rps — the user-facing latency number | k6 summary committed alongside |

## 3. Liveness proof — the health model

Today: no uniform health story. Target: every service answers the same two questions.

- **`/healthz`** (or gRPC health protocol where the service is gRPC-only): process up.
- **`/readyz`**: dependencies reachable (Kafka producer connected, ES green, Ollama
  tags listed, Redis ping). Readiness lists each dependency with its own status.

| ID | Story | Done when |
|---|---|---|
| P6.5-005 | Standard health/ready endpoints across all 9 services (use gRPC Health Checking Protocol for market/fortress; HTTP for the rest) | `make health` prints a 9-row status table |
| P6.5-006 | Aggregate: town-core `GET /system/health` fans out to all services, returns the matrix — this is the **Clinic room's feed** (Plan 01 §4.2) | Clinic examination table renders real statuses; killing tavern turns its row red within 15s |
| P6.5-007 | Snapshot restore test: P6-020's snapshot system gets a CI job that snapshots, wipes a scratch world, restores, diffs | Bank vault panel's "restore-tested ✅" is earned, not asserted |

Compose/k8s probes (`infra/helm/`) point at these same endpoints — one health truth,
three consumers (orchestrator, clinic room, CI smoke).

## 4. Proof panels — liveness made visible in-world

One Vue component (`ProofPanel.vue`, P7-010), data-driven by a per-room config:

```ts
// dashboard/proof-panels/<building>.<room>.ts
{ title: string,
  metrics: [{ label, source, format, staleAfterSec }],
  docsLink: string }       // → RoomDocs drawer
```

`source` is a typed reference to a real endpoint: a cartographer GraphQL field, a
Prometheus instant query (proxied via a tiny read-only endpoint — Prometheus is never
exposed raw), the Jaeger query API (Tower only), or a committed constant **explicitly
labeled with its provenance** (e.g. perf report numbers render as "measured 2026-06-xx").

Hard rules (these are what make panels *proof* rather than decoration):
1. **No fabricated values, ever.** A metric whose source errors renders as `—` with the
   error reason on hover. (CLAUDE.md rule 10.)
2. **Staleness is visible.** Values older than `staleAfterSec` dim and show their age.
3. **Dormant mode.** If a room's backing flow isn't wired yet, the panel says exactly
   that ("awaiting Phase 6 Gate A") — the honest-audit ethos, productized.
4. **Panel → console.** Every panel links to the full ops page (`/market`, `/fortress`,
   …) and to its room doc. Curious visitors can always go one level deeper.

Per-room metric assignments live in Plan 01 §4 (each room's "Proof panel" line).

## 5. Trace proof — observability

Jaeger/Prometheus/Grafana/Loki are configured in `infra/` but **no service emits spans**
(audit §not-covered). Phase 6.5 instruments exactly three services — one per language —
which proves polyglot observability without boiling all nine:

| ID | Story | Done when |
|---|---|---|
| P6.5-008 | OTel SDK in town-core (Python): tick loop, gRPC server, Kafka produce — W3C traceparent injected into Kafka headers | Spans visible in Jaeger |
| P6.5-009 | OTel in market-district (Go): gRPC interceptor + Kafka emit, continuing the inbound trace context | One trace ID spans town-core → market |
| P6.5-010 | OTel in tavern (TS): Kafka consume → WS broadcast, same trace continued | Full market-trade trace: 3 languages, gRPC + Kafka hops, one waterfall |
| P6.5-011 | Tower feed: small read-only proxy for Jaeger query API + the trace-screenshot committed to `docs/img/trace-market-flow.png` | Tower observation deck renders the live waterfall (P7-016); the screenshot lands in README |
| P6.5-012 | kafka-exporter + the existing Prometheus config → Warehouse room feed (topic throughput/lag) | Warehouse holo-tags show real lag numbers |

## 6. CI gates — the full set after this plan

`ci.yml` ends with these required checks: build+unit (exists) · `e2e` (×3 flows, §1) ·
`gitleaks` (secrets — the postmortem's guard, Plan 04) · `trivy` image scan ·
`buf breaking` on proto/ · dependency audit (`pip-audit`/`govulncheck`/`cargo audit`/
`npm audit --audit-level=high`) · eval harness (Phase 8, Plan 05 G-02). Each gate is
one story (P6.5-013..017), each "done when CI fails on a seeded violation."

## 7. The 5-minute demo script (`docs/DEMO.md`)

The scripted walkthrough that *is* the product proof — written once, used for
interviews, the landing video, and manual QA:

1. **Open qtown.ai** → overhead solarpunk town, NPCs moving. (Asset reboot + sim alive.)
2. **Click the Market** → zoom into the trading floor → point at the haggle pair →
   "that animation is a real order matched in the Go order book; panel shows the
   measured p99 from the committed perf report."
3. **Click a citation in the Academy classroom** → library room opens with the RAG
   search pre-run → "local Ollama generation, Elasticsearch retrieval, real citations."
4. **Climb the Tower** → live Jaeger waterfall of the trade you just watched → "one
   trace ID across Python, Go, and TypeScript, crossing gRPC and Kafka."
5. **Open the Clinic** → 9/9 green → kill a service in another tab → row goes red,
   a patient NPC appears. (Optional flourish; compose-only, never prod.)
6. **Close on the Warehouse** → 27 topics, all with producers AND consumers → "the
   audit found one-sided topology; these tags are the receipt that it's closed."

Done when: a stranger can run the script from a fresh clone using only `docs/STATE.md`'s
quickstart, and every claim made aloud is backed by something visible on screen.

## 8. Claim hygiene (interim wording until gates flip)

| Instead of | Say (until) |
|---|---|
| "<5ms p99 at 10K orders/sec" | "designed to sub-5ms p99 — bench suite committed, load validation landing" (until P6.5-002) |
| "zero unsafe" | "unsafe confined to a single audited WASM-boundary module (N blocks)" (after P6-003; this is permanently the *better* claim) |
| "9 services, fully wired" | "9 services, final cross-service wiring in flight (Phase 6), e2e tests as the gate" (until Gate A) |
| "194/194 stories complete" | "Phase 6 remediation in progress — here's the audit that caught it" (the stronger story anyway) |
