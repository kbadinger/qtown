#!/usr/bin/env python3
"""
build_v2_backlog.py — Materialize the v2 plan pack (docs/plans/00-05) into the
Ralph worklist, and enrich every story with an execution grade.

Operating model (Kevin, 2026-06-12):
  - Opus in-session authors stories + runs periodic cleanup passes.
  - Ralph (local Ollama loop) is the bulk executor of mechanical code stories.
  - Cadence: Ralph runs -> stop -> Opus cleanup fixes/restructures -> resume.

Grades (carried in labels[], which round-trips through Story.to_dict):
  - grade:opus   judgment-heavy. Architecture, perf methodology, proof design,
                 security, ADR/postmortem voice, distributed tracing, evals,
                 novel product surface. A local model will get these subtly
                 wrong; an Opus cleanup pass must scrutinize them hard.
  - grade:ralph  mechanical. Codegen, endpoint wiring, component scaffolding,
                 config — safe to let the loop run, light cleanup.
Other labels:
  - gate:A|B|C|D   ties a story to the master-plan gate it serves.
  - track:kevin-gpu  must be executed by Kevin on the 3090 box (physical GPU).
  - voice-pass     Opus drafts; Kevin edits the prose before merge.
  - proto          touches proto/ — used by the orchestrator's conflict detector.

This script is idempotent: re-running re-grades and re-syncs the new stories
without duplicating them.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WORKLIST = Path(__file__).with_name("worklist.json")

# ---------------------------------------------------------------------------
# Grade heuristic for the 220 EXISTING stories (the new ones set labels直接).
# ---------------------------------------------------------------------------
OPUS_SIGNALS = re.compile(
    r"\b("
    r"architect|design|refactor|restructure|migrate|schema|contract|proto|"
    r"grpc server|grpc service|cross-service|orchestrat|interface|"
    r"security|secret|threat|audit|sandbox|unsafe|confine|"
    r"perf|benchmark|load test|latency|observability|trace|tracing|otel|"
    r"eval|guardrail|structured output|mcp|"
    r"adr|postmortem|snapshot|replay|deploy|federation|gateway|"
    r"investigate|integration test|end-to-end|e2e"
    r")\b",
    re.IGNORECASE,
)


def grade_for(story: dict) -> str:
    blob = f"{story.get('title','')} {story.get('description','')}"
    return "grade:opus" if OPUS_SIGNALS.search(blob) else "grade:ralph"


def set_grade(story: dict) -> None:
    labels = [l for l in story.get("labels", []) if not l.startswith("grade:")]
    labels.append(grade_for(story))
    story["labels"] = labels


# ---------------------------------------------------------------------------
# The new backlog. Each story:
#   id,title,service,language,deps,phase,group,description,
#   acceptance_criteria[],labels[],status="pending",attempts=0,
#   last_error=None
# Acceptance criteria are machine-checkable: a test goes green, a file exists,
# an endpoint returns X. "Looks done" is not done.
# ---------------------------------------------------------------------------

def S(id, title, service, language, deps, phase, group, description, ac, labels):
    return {
        "id": id, "title": title, "service": service, "language": language,
        "deps": deps, "phase": phase, "group": group, "description": description,
        "acceptance_criteria": ac, "labels": labels,
        "status": "pending", "attempts": 0, "last_error": None,
    }


NEW: list[dict] = []

# ===========================================================================
# PHASE 6.5 — PROVE IT (Plan 03 + Plan 04 Tier-0). Gate B.
# ===========================================================================

# --- 6.5.1 Number proof: the load test (Plan 03 §2) ---
NEW += [
 S("P6.5-001","Build ghz load-test harness for market-district PlaceOrder gRPC path",
   "market-district","go",["P6-005"],"6.5","6.5.1",
   "The README claims '<5ms p99 at 10K orders/sec' and it has never been run under load. "
   "Create perf/market-district/ with a ghz (https://ghz.sh) script driving the gRPC "
   "PlaceOrder path under docker-compose. Include warmup, 3 measured runs, and recorded "
   "hardware/notes. perf/run.sh must reproduce deterministically on Kevin's machine.",
   ["perf/market-district/run.sh exists and reproduces on a fresh checkout",
    "Script does warmup + 3 runs at stepped load (1K/5K/10K orders/sec)",
    "Raw ghz JSON output committed under perf/market-district/results/"],
   ["grade:opus","gate:B"]),
 S("P6.5-002","Write perf/REPORT.md with measured p50/p99/p999 and saturation analysis",
   "infra","markdown",["P6.5-001"],"6.5","6.5.1",
   "Author perf/REPORT.md: methodology, exact hardware, p50/p99/p999 at 1K/5K/10K "
   "orders/sec, where the engine saturates, and a flamegraph of the hot path. The "
   "measured number wins interviews; the claimed one loses them. Numbers must come from "
   "P6.5-001 output, not estimates.",
   ["perf/REPORT.md committed with real numbers traceable to results/ JSON",
    "Saturation point and flamegraph (or pprof svg) included",
    "Every number cites the run that produced it"],
   ["grade:opus","gate:B"]),
 S("P6.5-003","Rewrite README + landing perf claims to the measured number",
   "infra","markdown",["P6.5-002"],"6.5","6.5.1",
   "Replace every unmeasured perf claim in README and dashboard landing with the "
   "measured value from perf/REPORT.md (whatever it is). The Market room proof panel "
   "(Plan 01 §4.1) reads the same constants from a single committed source so copy and "
   "panel can never diverge.",
   ["No unmeasured perf claim remains anywhere in the repo (grep clean)",
    "README perf line links to perf/REPORT.md",
    "A single perf-constants source feeds README + Market proof panel"],
   ["grade:opus","gate:B"]),
 S("P6.5-004","Add k6 gateway load script for GraphQL townOverview fan-out",
   "cartographer","javascript",["P6-017"],"6.5","6.5.1",
   "Add a k6 script hitting the cartographer GraphQL townOverview fan-out at 100 rps — "
   "the user-facing latency number. Commit the k6 summary alongside perf/REPORT.md.",
   ["perf/gateway/townOverview.k6.js exists",
    "k6 summary JSON committed; p95 fan-out latency recorded in REPORT.md"],
   ["grade:ralph","gate:B"]),
]

# --- 6.5.2 Liveness proof: the health model (Plan 03 §3) ---
NEW += [
 S("P6.5-005","Standardize /healthz + /readyz across all 9 services",
   "infra","python",[],"6.5","6.5.2",
   "Today there is no uniform health story. Every service must answer two questions the "
   "same way: /healthz (process up) and /readyz (dependencies reachable — Kafka producer "
   "connected, ES green, Ollama tags listed, Redis ping). Use the gRPC Health Checking "
   "Protocol for market-district + fortress; HTTP for the rest. readyz lists each "
   "dependency with its own status.",
   ["make health prints a 9-row status table",
    "Each service exposes both endpoints; readyz enumerates per-dependency status",
    "market-district + fortress implement grpc.health.v1.Health"],
   ["grade:opus","gate:B"]),
 S("P6.5-006","Aggregate town-core GET /system/health fanning out to all services",
   "town-core","python",["P6.5-005","P6-001"],"6.5","6.5.2",
   "town-core GET /system/health fans out to all 9 service health endpoints and returns "
   "the matrix. This is the Clinic room's feed (Plan 01 §4.2): the examination table "
   "renders real statuses and a sick patient NPC appears when a service is degraded.",
   ["GET /system/health returns a 9-service status matrix",
    "Killing tavern turns its row red within 15s",
    "Response shape documented for the Clinic ProofPanel"],
   ["grade:ralph","gate:B"]),
 S("P6.5-007","CI job that proves world-snapshot restore actually works",
   "infra","yaml",["P6-020"],"6.5","6.5.2",
   "P6-020's snapshot system gets a CI job: snapshot a world, wipe a scratch world, "
   "restore, and diff. The Bank vault panel's 'restore-tested ✅' must be earned, not "
   "asserted. NEVER run against any real/durable data — scratch world only.",
   ["CI job snapshots -> wipes scratch -> restores -> diffs clean",
    "Job fails if restore diverges from snapshot",
    "Runs only against an ephemeral scratch world (no durable data touched)"],
   ["grade:opus","gate:B"]),
]

# --- 6.5.3 Trace proof: observability (Plan 03 §5) ---
NEW += [
 S("P6.5-008","Instrument town-core (Python) with OpenTelemetry spans",
   "town-core","python",["P6-001"],"6.5","6.5.3",
   "Jaeger/Prometheus/Grafana are configured in infra/ but no service emits spans. "
   "Add the OTel SDK to town-core: tick loop, gRPC server, and Kafka produce. Inject "
   "W3C traceparent into Kafka message headers so the trace can continue downstream.",
   ["Spans for tick loop + gRPC + Kafka produce visible in Jaeger",
    "traceparent injected into Kafka headers on every produced message"],
   ["grade:opus","gate:B"]),
 S("P6.5-009","Instrument market-district (Go) continuing the inbound trace context",
   "market-district","go",["P6.5-008","P6-005"],"6.5","6.5.3",
   "Add OTel to market-district: a gRPC server interceptor and Kafka emit instrumentation "
   "that continues the trace context arriving from town-core. One trace ID must span "
   "town-core -> market.",
   ["One trace ID spans town-core -> market-district in Jaeger",
    "Kafka emit propagates the same traceparent forward"],
   ["grade:opus","gate:B"]),
 S("P6.5-010","Instrument tavern (TS) closing the polyglot market-trade trace",
   "tavern","typescript",["P6.5-009","P6-006"],"6.5","6.5.3",
   "Add OTel to tavern: Kafka consume -> WS broadcast, continuing the same trace. The "
   "result is one market-trade trace crossing 3 languages and gRPC + Kafka hops as a "
   "single Jaeger waterfall.",
   ["Full market-trade trace: 3 languages, gRPC + Kafka hops, one waterfall",
    "tavern consumer span is a child of the market emit span"],
   ["grade:opus","gate:B"]),
 S("P6.5-011","Read-only Jaeger query proxy + commit the trace screenshot",
   "town-core","python",["P6.5-010"],"6.5","6.5.3",
   "Add a small read-only proxy for the Jaeger query API (Jaeger is never exposed raw) so "
   "the Tower observation deck (P7-016) can render the live waterfall. Commit the trace "
   "screenshot to docs/img/trace-market-flow.png for the README.",
   ["Read-only proxy returns the latest trace tagged flow=market-trade",
    "docs/img/trace-market-flow.png committed and referenced in README"],
   ["grade:ralph","gate:B"]),
 S("P6.5-012","Wire kafka-exporter -> Prometheus -> Warehouse room feed",
   "infra","yaml",[],"6.5","6.5.3",
   "Add kafka-exporter to the existing Prometheus config so per-topic throughput and "
   "consumer lag are scraped. This is the Warehouse room's feed: holo-tags show real lag "
   "numbers (Plan 01 §4.2).",
   ["kafka-exporter scraped by Prometheus; per-topic lag query returns data",
    "A read-only endpoint exposes topic throughput/lag for the Warehouse panel"],
   ["grade:ralph","gate:B"]),
]

# --- 6.5.4 CI gates: supply chain + contracts (Plan 03 §6, Plan 05 G-06) ---
NEW += [
 S("P6.5-013","Add gitleaks secret-scanning CI gate",
   "infra","yaml",[],"6.5","6.5.4",
   "Add a required gitleaks job to .github/workflows/ci.yml. This is the secrets "
   "postmortem's structural guard (commit 280d792 leaked keys). The gate must block merge "
   "on any detected secret.",
   ["gitleaks job is a required check on every PR",
   "CI fails on a seeded fake secret in a test PR",
   "Baseline/allowlist documented if any historical match is intentionally ignored"],
   ["grade:opus","gate:B"]),
 S("P6.5-014","Add trivy container/image vulnerability scan CI gate",
   "infra","yaml",[],"6.5","6.5.4",
   "Add a required trivy scan over built images to ci.yml, failing on HIGH/CRITICAL "
   "with a documented, time-boxed allowlist mechanism.",
   ["trivy job required; fails on a seeded HIGH/CRITICAL vuln",
    "Allowlist file documented with expiry dates"],
   ["grade:ralph","gate:B"]),
 S("P6.5-015","Add buf breaking-change gate on proto/",
   "infra","yaml",[],"6.5","6.5.4",
   "Add a required `buf breaking` check against the main branch baseline so proto "
   "contract changes can't silently break a consumer.",
   ["buf breaking job required; fails on a seeded incompatible proto change",
    "buf.yaml/buf.gen.yaml baseline configured"],
   ["grade:ralph","gate:B","proto"]),
 S("P6.5-016","Add per-language dependency-audit CI gates",
   "infra","yaml",[],"6.5","6.5.4",
   "Add dependency vulnerability audits per language as required checks: pip-audit "
   "(Python), govulncheck (Go), cargo audit (Rust), npm audit --audit-level=high (TS).",
   ["All four audit jobs run and are required",
    "Each fails on a seeded known-vulnerable dependency"],
   ["grade:ralph","gate:B"]),
 S("P6.5-017","Make the 3 e2e flow tests a required merge gate (Gate A wiring in CI)",
   "infra","yaml",["P6-022","P6-023","P6-024"],"6.5","6.5.4",
   "Add the `e2e` job to ci.yml: boot docker-compose.deps.yml + the services each flow "
   "needs, run test_market_trade_flow / test_ai_dialogue_flow / test_validation_flow, "
   "required for merge. Slow (~5-8 min) is acceptable; wrongness is not. Verify by "
   "intentionally breaking one hop and watching CI fail.",
   ["e2e job required on every PR; all 3 flows green on main",
    "Intentionally breaking one hop in a PR turns the check red",
    "README architecture diagram drops the live-vs-stubbed marker once green"],
   ["grade:opus","gate:A"]),
]

# ===========================================================================
# PHASE 7-A — ASSETS (Plan 02). Gate C. Runs on the 3090 box, ∥ everything.
# ===========================================================================
NEW += [
 S("P7A-001","Author 4 ComfyUI workflow JSONs (classes A-D) with Flux + IP-Adapter + ControlNet",
   "asset-pipeline","json",[],"7A","7A.1",
   "workflows/ has only INSTALL.md. Author 4 ComfyUI workflow JSONs (one per asset class "
   "A-D) per the INSTALL.md model layout: Flux.1-dev fp8, IP-Adapter (identity), "
   "ControlNet-OpenPose (activity poses), with parameterized prompt/size/seed inputs so "
   "run_batch.py can drive them.",
   ["4 workflow JSONs validate via the ComfyUI /prompt API dry-run",
    "Prompt/size/seed are externally parameterized inputs",
    "IP-Adapter present in B/D workflows; ControlNet-OpenPose present in D"],
   ["grade:opus","gate:C","track:kevin-gpu"]),
 S("P7A-002","Add interior_cast matrix + class-E extras to taxonomy.yaml (additive only)",
   "asset-pipeline","yaml",[],"7A","7A.1",
   "Add the curated per-room (role x activity) cast matrix as a new ADDITIVE interior_cast "
   "field on each room in taxonomy.yaml (taxonomy stays locked — this adds, never changes), "
   "plus the class-E extras list (ground tiles, props, landing hero, OG, favicon). "
   "Curation rule: 1-2 roles per activity. Dedupe by (role, activity).",
   ["run_batch.py --plan prints the full manifest with counts matching Plan 02 §1.6 ±10%",
    "taxonomy.yaml `locked: true` preserved; only additive fields added",
    "Class-D unique sprite count resolves to ~95-110 after dedupe"],
   ["grade:opus","gate:C","track:kevin-gpu"]),
 S("P7A-003","Finish run_batch.py: manifest expansion, submit/poll/download, retry, filters",
   "asset-pipeline","python",["P7A-001","P7A-002"],"7A","7A.1",
   "Complete run_batch.py: expand the manifest from taxonomy, submit jobs to ComfyUI, "
   "poll, download, retry-on-failure, --only-new, --only-class, and deterministic seeds "
   "logged per asset. Reads taxonomy at run time (no second source of truth).",
   ["run_batch.py --mode test --limit 10 produces 10 correctly named files",
    "--only-new and --only-class filters work",
    "Every generation logs prompt+seed+workflow+model-hash to output/genlog.jsonl"],
   ["grade:opus","gate:C","track:kevin-gpu"]),
 S("P7A-004","Post-process: rembg transparency, WebP convert, per-class contact sheets",
   "asset-pipeline","python",["P7A-003"],"7A","7A.1",
   "Add postprocess.py: rembg for class B/D transparency, WebP conversion, and a "
   "contact-sheet generator (one grid PNG per class) for Kevin's QA review.",
   ["postprocess.py runs clean on the test batch",
    "Contact sheets render one grid per class",
    "B/D outputs have clean transparent edges"],
   ["grade:ralph","gate:C","track:kevin-gpu"]),
 S("P7A-005","Emit assets/manifest.json consumed by the dashboard InteriorRenderer",
   "asset-pipeline","python",["P7A-003"],"7A","7A.1",
   "Emit assets/manifest.json mapping building/room/sprite -> relative path, served via "
   "asset-pipeline storage (P6-016) and consumed by the dashboard (Plan 01 §5). The "
   "dashboard must render any room with zero hardcoded asset paths.",
   ["manifest.json covers 100% of taxonomy rooms/roles",
    "Dashboard InteriorRenderer loads a room purely from the manifest",
    "Manifest schema documented for the dashboard composable"],
   ["grade:ralph","gate:C"]),
 S("P7A-006","LoRA A/B decision: evaluate solarpunk LoRA vs none, record in DECISIONS.md",
   "asset-pipeline","python",["P7A-003"],"7A","7A.1",
   "Run A/B test-gens with vs without a solarpunk LoRA from config.yaml's candidate slots; "
   "pick or drop. Record the decision + seeds in asset-gen/DECISIONS.md.",
   ["A/B contact sheet generated for both arms",
    "Decision + seeds + reasoning recorded in asset-gen/DECISIONS.md"],
   ["grade:opus","gate:C","track:kevin-gpu"]),
]

# ===========================================================================
# PHASE 7-B — ROOMS (Plan 01 + Plan 03 proof layer). Gate D.
# ===========================================================================

# --- 7B.1 Sim room model (ordered) ---
NEW += [
 S("P7-001","Architect room/activity projection in town-core (rooms.yaml + simulation/rooms.py)",
   "town-core","python",["P6-001"],"7B","7B.1",
   "The sim does not track rooms. Add a projection layer (NOT a new simulation system): "
   "rooms.yaml generated from taxonomy.yaml (single source of truth, synced by script), "
   "simulation/rooms.py with Room{building_id,room_id,activities,capacity}, NPC gains "
   "current_building/current_room/current_activity/activity_since, and a deterministic "
   "action->(building,room,activity) mapping table living in rooms.yaml.",
   ["Unit test: every taxonomy room is reachable",
    "Unit test: every sim action maps to a valid (building, room, activity)",
    "rooms.yaml is generated from taxonomy.yaml, never hand-duplicated"],
   ["grade:opus","gate:D"]),
 S("P7-002","Add rooms.proto + buf codegen (Python + TS)",
   "town-core","proto",["P7-001"],"7B","7B.1",
   "Add proto/qtown/town/v1/rooms.proto with RoomState, Occupant, "
   "GetRoomStateRequest/Response. Run buf codegen for Python (town-core) + TS "
   "(cartographer).",
   ["buf generate is clean",
    "Generated stubs imported by town-core + cartographer"],
   ["grade:ralph","gate:D","proto"]),
 S("P7-003","Emit qtown.town.room.activity per tick; register topic in kafka-init",
   "town-core","python",["P7-001"],"7B","7B.1",
   "town-core emits qtown.town.room.activity to Kafka once per tick (30s), one message per "
   "OCCUPIED room: {building_id,room_id,occupants:[{npc_id,role,activity,since}],tick}. "
   "Register the topic in infra/kafka-init.sh.",
   ["Topic shows >=1 msg/tick with valid schema in an integration test",
    "Topic registered in kafka-init.sh",
    "Only occupied rooms emit (no empty-room spam)"],
   ["grade:ralph","gate:D"]),
 S("P7-004","Implement GetRoomState RPC on the town-core gRPC server",
   "town-core","python",["P7-002","P6-001"],"7B","7B.1",
   "Implement the GetRoomState RPC on town-core's gRPC server (P6-001) returning live "
   "occupants for a building, for the dashboard's initial page load.",
   ["grpcurl GetRoomState returns occupants matching sim state",
    "Empty building returns an empty-but-valid response, not an error"],
   ["grade:ralph","gate:D"]),
]

# --- 7B.2 Gateway + fan-out (ordered, after 7B.1) ---
NEW += [
 S("P7-005","Add cartographer roomState(buildingId) GraphQL query",
   "cartographer","typescript",["P7-004","P6-017"],"7B","7B.2",
   "Add a cartographer roomState(buildingId) query resolving to town-core's GetRoomState "
   "gRPC. Fail loud if town-core is down (the P6-017 strict-load pattern) — no soft-fail.",
   ["GraphQL roomState query returns live data",
    "Resolver errors loudly when town-core is unreachable (no silent empty)"],
   ["grade:ralph","gate:D"]),
 S("P7-006","Add tavern room:<building> WS channels from the new topic",
   "tavern","typescript",["P7-003"],"7B","7B.2",
   "tavern consumes qtown.town.room.activity and broadcasts to a new WS channel "
   "room:<building_id> (the pattern already exists in src/kafka-consumer.ts).",
   ["A WS test client subscribed to room:tavern receives deltas within 1 tick",
    "Channel name pattern matches the dashboard composable's expectation"],
   ["grade:ralph","gate:D"]),
]

# --- 7B.3 Dashboard primitives (∥ within group, after 7B.2) ---
NEW += [
 S("P7-007","Drill-in route + ZoomTransition + overhead click-targets",
   "dashboard","typescript",["P7-005"],"7B","7B.3",
   "Add the full-page route /town/<building_id> (deep-linkable, browser-history aware). "
   "Overhead camera tweens to the building footprint (~400ms) then crossfades to the "
   "interior; Esc/back-arrow/browser-back zooms out. No modal — interiors are a place. "
   "Add building click-targets + a hover affordance to the existing PixiRenderer.",
   ["Click tavern -> animated zoom -> /town/tavern interior; back returns",
    "Deep-link to /town/tavern loads the interior directly",
    "Esc and browser-back both zoom out"],
   ["grade:opus","gate:D"]),
 S("P7-008","InteriorRenderer: 2.5D parallax scene + NPC sprite layer + tween system",
   "dashboard","typescript",["P7A-005"],"7B","7B.3",
   "New PixiJS InteriorRenderer.client.vue: side-view dollhouse with parallax layers "
   "(background plate -> mid props -> NPC layer -> foreground accents at differing scroll "
   "factors). Liveness via cheap tweens (idle bob ±2px, walk slide, flip) + speech "
   "bubbles — not sprite-sheet animation. Must hit the Plan 01 §3.7 perf budget.",
   ["Renders a room from manifest assets at 60fps with 15 sprites (M-series)",
    "<=2.5MB transferred per room first-visit; LRU cache of 3 visited rooms",
    "Overhead view unloads while inside"],
   ["grade:opus","gate:D"]),
 S("P7-009","useRoomState composable: GraphQL snapshot + WS delta merge + dormant mode",
   "dashboard","typescript",["P7-005","P7-006"],"7B","7B.3",
   "composables/useRoomState.ts: initial snapshot via GraphQL roomState, live updates via "
   "WS room:<id>. When a feed is absent, return dormant state (never fabricate occupants).",
   ["Occupants update without a page refresh",
    "Dormant mode returns when the feed is absent (no fabricated data)"],
   ["grade:ralph","gate:D"]),
 S("P7-010","ProofPanel component + per-room panel configs (no-fake-data enforced)",
   "dashboard","typescript",["P7-008"],"7B","7B.3",
   "components/ProofPanel.vue, data-driven by dashboard/proof-panels/<building>.<room>.ts "
   "({title,metrics:[{label,source,format,staleAfterSec}],docsLink}). Hard rules: no "
   "fabricated values ever (errored source -> '—' + reason on hover); staleness visible "
   "(dim + age past staleAfterSec); dormant mode names the missing gate; every panel links "
   "to its ops page + room doc.",
   ["Panel renders real metrics for all 5 flagship rooms",
    "An errored metric source renders '—' with reason, never a fabricated value",
    "Stale values dim and show their age"],
   ["grade:opus","gate:D"]),
 S("P7-011","RoomDocs drawer + content loader",
   "dashboard","typescript",["P7-008"],"7B","7B.3",
   "components/RoomDocs.vue: the ⓘ drawer that loads docs/rooms/<building>.<room>.md "
   "(content authored in Plan 04 §6) for the room currently in view.",
   ["ⓘ opens the room's doc drawer with the right content",
    "Drawer closes on Esc and does not block the scene"],
   ["grade:ralph","gate:D"]),
]

# --- 7B.4 Flagship five integration (ordered) ---
for sid, rid, name, dep_extra, feed in [
    ("P7-012","tavern.bar_room","Tavern bar room",["P7-006"],
     "WS room:tavern occupants + real tavern broadcast events as bar chatter; proof panel "
     "shows live WS connection count, events/5min, Kafka consumer lag."),
    ("P7-013","market.trading_floor","Market trading floor",["P6-006"],
     "roomState(market) + cartographer orderBook/recentTrades; WS deltas via "
     "economy.trade.settled; proof panel shows measured p50/p99 match latency, orders/sec, "
     "trades settled today."),
    ("P7-014","academy.classroom","Academy classroom",["P6-011","P6-012"],
     "dialogue trigger -> academy GenerateDialogue -> ai.content.generated -> tavern WS; "
     "projector renders latest generated content + clickable RAG citations; proof panel "
     "shows model name, tokens/sec, RAG hit count."),
    ("P7-015","validation_citadel.verification_chamber","Validation Citadel chamber",["P6-024"],
     "qtown.validation.result (works today); proof panel shows validations/min, accept "
     "rate, p99 WASM exec time, 'unsafe confined to wasm_sandbox: N blocks'."),
    ("P7-016","tower.observation_deck","Tower observation deck",["P6.5-011"],
     "Jaeger query proxy for the latest flow=market-trade trace waterfall + cartographer "
     "fan-out beams; proof panel shows end-to-end trade latency, span count, services "
     "touched."),
]:
    NEW.append(S(sid, f"Wire flagship room: {name} with live data + proof panel",
        "dashboard","typescript",["P7-010","P7-011"]+dep_extra,"7B","7B.4",
        f"Integrate {name} ({rid}) end to end per Plan 01 §4.1. Feed: {feed} A room may "
        "not fake its feed — if the backing flow isn't green yet, ship dormant (labeled, "
        "NPCs idle, panel says 'awaiting Phase 6 wiring').",
        [f"{name} shows live data cross-checked against the source API in an e2e test",
         "Proof panel renders only real/labeled values; dormant if feed not wired",
         "ⓘ docs hook present"],
        ["grade:opus","gate:D"]))

NEW += [
 S("P7-017","E2E room test: sim tick -> room.activity -> WS -> DOM assertion (Gate D check)",
   "infra","python",["P7-012","P7-013","P7-014","P7-015","P7-016"],"7B","7B.4",
   "tests/e2e/test_room_flow.py: drive a sim tick, assert qtown.town.room.activity emits, "
   "assert the WS delta arrives, assert the DOM updates. This becomes the Gate D check.",
   ["Green in CI as a required check",
    "Breaking the room.activity emit turns the test red"],
   ["grade:opus","gate:D"]),
]

# --- 7B.5 Second ring (∥, one story per building, order by data-readiness) ---
SECOND_RING = [
 ("P7-018","warehouse.storage_floor","Warehouse storage floor",["P6.5-012"],
  "27 storage lanes = Kafka topics; height = depth; holo-tags show topic name, msg/min, "
  "consumer lag; proof panel flags any zero-consumer topic (audit's one-sided topology)."),
 ("P7-019","academy.library","Academy library + working search console",["P6-015"],
  "Real library service search; typed query pulls glowing books from shelves; proof panel "
  "shows docs indexed, last index write, search p50."),
 ("P7-020","town_hall.assembly","Town Hall assembly",[],
  "Election candidates on stage with live vote tallies; proof panel shows current tick, "
  "ticks/day uptime, election schedule (the tick loop's heartbeat)."),
 ("P7-021","bank.lobby","Bank lobby + vault",["P6-020"],
  "Tellers process real wallet deltas from settlements; vault shelves world snapshots; "
  "proof panel shows money supply, settlements today, snapshot count + restore-tested."),
 ("P7-022","clinic.examination","Clinic examination + dispensary",["P6.5-006"],
  "Healer's diagnostic table = the 9-service health board; sick patient NPC on degrade; "
  "dispensary links remediation runbooks; proof panel shows overall status, slowest check."),
 ("P7-023","workshop.workspace","Workshop workspace",["P6-016","P7A-005"],
  "Skill-share board cycles the latest real asset-pipeline outputs; proof panel shows "
  "assets generated, last gen duration, queue depth."),
 ("P7-024","theater.stage","Theater stage",[],
  "Performer NPC reads the latest newspaper edition / generated narrative; proof panel "
  "shows editions published, stories generated this week."),
 ("P7-025","temple.sanctuary","Temple sanctuary",[],
  "Gossip/rumor graph as a constellation above the altar (nodes=NPCs, edges=rumors); "
  "proof panel shows active rumors, most-believed rumor, decay rate."),
 ("P7-026","courthouse.courtroom","Courthouse courtroom",["P6-008","P6-024"],
  "Docket = recent ❌ verdicts from fortress that town-core acted on; proof panel shows "
  "cases this week, overturn rate."),
 ("P7-027","restoration_center.counseling","Restoration Center",[],
  "Sim crime/justice restorative outcomes; proof panel shows incidents, completion rate."),
 ("P7-028","home.living_room","Home (drill into a specific NPC)",[],
  "Needs bars, current goal, today's action log; bedroom shows real sleep state at night. "
  "Feed: town-core NPC state."),
 ("P7-029","blacksmith.forge","Blacksmith forge/showroom",[],
  "Production-chain room: goods/tick, inventory, 'sold at Market' counters reconciling "
  "with market-district settlements (cross-service consistency proof). Sim-fed."),
 ("P7-030","bakery.bakehouse","Bakery bakehouse/shopfront",[],
  "Production-chain room reconciling produced goods against Market settlements. Sim-fed."),
 ("P7-031","farm.barn","Farm barn/greenhouse",[],
  "Production-chain room reconciling produced goods against Market settlements. Sim-fed."),
]
for sid, rid, name, dep_extra, desc in SECOND_RING:
    NEW.append(S(sid, f"Second-ring room: {name}",
        "dashboard","typescript",["P7-017"]+dep_extra,"7B","7B.5",
        f"{desc} Same done-when pattern as the flagship five: real feed or labeled "
        "dormant; proof panel live; ⓘ docs hook present.",
        [f"{name} renders a real feed or a labeled dormant state (never fabricated)",
         "Proof panel live; ⓘ docs hook present",
         "Cross-checked against its source API"],
        ["grade:ralph","gate:D"]))

# ===========================================================================
# PHASE 7.5 — DOCUMENT IT (Plan 04).
# ===========================================================================
NEW += [
 S("P7.5-001","Write docs/STATE.md + CI quickstart smoke job",
   "infra","markdown",["P6.5-017"],"7.5","7.5.1",
   "docs/STATE.md: What works now (green e2e flows, live rooms) · What's in flight (phase "
   "+ gate) · The numbers (measured only, linked to perf/REPORT.md) · 5-minute quickstart "
   "(make deps && make build && make run) · Honest gaps (audit summary). A CI smoke job "
   "runs the quickstart so it can never rot.",
   ["A stranger reproduces the quickstart from a fresh clone",
    "Every number on the page links to its proof",
    "CI smoke job executes the quickstart and is required"],
   ["grade:opus"]),
]
ADRS = [
 ("P7.5-002","ADR-01 Go for the order book","perf/REPORT.md numbers; orderbook.go"),
 ("P7.5-003","ADR-02 Rust + WASM for untrusted validation","confined-unsafe module (P6-003); sandbox tests"),
 ("P7.5-004","ADR-03 Kafka at-least-once + idempotent consumers","consumer idempotency tests; topic catalog"),
 ("P7.5-005","ADR-04 GraphQL gateway as sole public entry","cartographer authz + rate limit (P8-003)"),
 ("P7.5-006","ADR-05 Polyglot-by-domain vs resume-driven","the building->service map (Plan 01 §1)"),
 ("P7.5-007","ADR-06 v1 monolith -> v2 decomposition triggers","v1 closeout post; audit parity table"),
 ("P7.5-008","ADR-07 Local-model routing by task type","ralph/v2_model_router.py in production"),
 ("P7.5-009","ADR-08 Fail-loud over fail-soft","the cartographer tryLoadPackage lesson (P6-017)"),
 ("P7.5-010","ADR-09 Linkerd mTLS + service authz","infra/linkerd/ policies"),
 ("P7.5-011","ADR-10 Agent-written code: CI as the trust boundary","the e2e gates (Plan 03 §1); the audit"),
]
for sid, title, receipt in ADRS:
    NEW.append(S(sid, f"Write {title}",
        "infra","markdown",[],"7.5","7.5.2",
        f"Draft {title} using the template Context -> Decision -> Consequences -> Receipts. "
        f"Receipt that makes it credible: {receipt}. <=1 page, zero aspirational statements; "
        "every Consequences claim links to a receipt. Kevin voice-passes before merge.",
        ["ADR is <=1 page",
         "Every Consequences claim links to a real receipt (code/test/report)",
         "No aspirational/unproven statements"],
        ["grade:opus","voice-pass"]))
NEW += [
 S("P7.5-012","Write docs/agent-ops.md — the differentiator document",
   "infra","markdown",[],"7.5","7.5.3",
   "Nobody else interviews with this doc. Cover: Ralph architecture (orchestrator, "
   "worklist, conflict detection) · the model-routing policy as production config · the "
   "HUMAN.md steering protocol + intervention log · cost-per-story methodology · THE AUDIT "
   "STORY (194/194 'complete' while 0/3 flows worked — 'true per-story, misleading at the "
   "system level' — and the structural fix: e2e gates) · how Opus + Ralph divide work in "
   "this very plan pack (the doc describes the process that produced it).",
   ["agent-ops.md covers all six sections with real artifacts linked",
    "The audit story is told honestly with the structural fix",
    "The Opus-plans / Ralph-executes / Opus-cleanup cadence is documented"],
   ["grade:opus","voice-pass"]),
 S("P7.5-013","Write SECURITY.md + STRIDE-lite threat model",
   "infra","markdown",["P6.5-013","P6.5-016"],"7.5","7.5.3",
   "SECURITY.md: trust-boundary diagram (public -> cartographer -> mesh; Kafka internal; "
   "Ollama/ComfyUI local-only), what's enforced today (Linkerd mTLS/authz), and what's "
   "honestly NOT done (no auth on internal RPCs, no gateway rate limit — with the P8-003 "
   "plan attached). Plus a 1-page STRIDE-lite threat model mapping mitigations to the CI "
   "gates and OWASP-LLM items. Honest partial > silent absence.",
   ["SECURITY.md states enforced vs not-done honestly with linked plans",
    "Threat model maps each mitigation to a CI gate or OWASP-LLM item"],
   ["grade:opus","voice-pass"]),
 S("P7.5-014","Write docs/postmortems/2026-05-30-committed-secrets.md",
   "infra","markdown",["P6.5-013"],"7.5","7.5.3",
   "Convert the leaked-secrets incident (commit 280d792) into operational signal: what "
   "leaked, blast radius, rotation timeline, and the guards now in CI (gitleaks, trivy, "
   "dependency audit). Opus drafts from git history; Kevin confirms the rotation facts.",
   ["Postmortem covers leak, blast radius, rotation timeline, and CI guards",
    "Rotation facts confirmed by Kevin before merge"],
   ["grade:opus","voice-pass"]),
 S("P7.5-015","Per-service README template + 9 service READMEs",
   "infra","markdown",[],"7.5","7.5.3",
   "docs/templates/service-readme.md (What this is + its building · Interface gRPC/HTTP/"
   "Kafka in+out linked to proto+topic catalog · Run/test locally · How it proves itself · "
   "Design notes -> owning ADRs · Honest status per feature), then fill it for all 9 "
   "services.",
   ["Template exists; all 9 services have a README against it",
    "Each README's status column is honest (live/dormant per feature)"],
   ["grade:opus"]),
 S("P7.5-016","Kafka topic catalog (checked-in YAML + generated markdown)",
   "infra","markdown",["P6-022","P6-023","P6-024"],"7.5","7.5.3",
   "docs/kafka-topics.md generated from a checked-in YAML: all 27 topics — producer, "
   "consumers, schema, and the e2e test that exercises it. Single source so catalog, "
   "kafka-init.sh, and the Warehouse feed can't drift. This is the Warehouse docs hook.",
   ["All 27 topics listed with producer + consumers + schema + exercising test",
    "Catalog generated from YAML; CI checks it matches kafka-init.sh"],
   ["grade:ralph"]),
]
FLAGSHIP_DOCS = [
 ("P7.5-017","market","trading_floor","P7-013"),
 ("P7.5-018","tavern","bar_room","P7-012"),
 ("P7.5-019","academy","classroom","P7-014"),
 ("P7.5-020","validation_citadel","verification_chamber","P7-015"),
 ("P7.5-021","tower","observation_deck","P7-016"),
]
for sid, b, r, dep in FLAGSHIP_DOCS:
    NEW.append(S(sid, f"Room doc: {b}.{r}",
        "infra","markdown",[dep],"7.5","7.5.4",
        f"docs/rooms/{b}.{r}.md (~200 words, frontmatter with building/service/sources). "
        "Body: What you're watching · How it flows (3-5 hops, each naming a real file) · "
        "Why it's built this way (distilled from the owning ADR) · Go deeper (ops page, "
        "ADR, README, e2e test). CI checks the source links resolve.",
        ["Doc <=200 words with resolving source links (CI link-check passes)",
         "A non-engineer can read it and explain what the room demonstrates"],
        ["grade:ralph"]))
NEW += [
 S("P7.5-022","Room docs for the second ring (batch)",
   "infra","markdown",["P7-018"],"7.5","7.5.4",
   "Author docs/rooms/*.md for every second-ring room with a live feed, same content "
   "schema and CI link-check as the flagship five.",
   ["Every second-ring room with a live feed has a doc",
    "CI link-check passes for all room docs"],
   ["grade:ralph"]),
 S("P7.5-023","Refresh docs/index.json + docs IA; README links the full pack",
   "infra","markdown",["P7.5-001","P7.5-012"],"7.5","7.5.4",
   "Update docs/index.json and the docs information architecture; README links the plan "
   "pack, STATE.md, ADRs, agent-ops.md, SECURITY.md, perf report, and topic catalog.",
   ["docs/index.json regenerated and valid",
    "README links every top-level doc artifact"],
   ["grade:opus"]),
]

# ===========================================================================
# PHASE 8 — 2026 GAP CLOSE (Plan 05). Tiered.
# ===========================================================================
# Tier 1 — interview-critical (do all)
NEW += [
 S("P8-001","Build MCP server exposing read-only town tools",
   "mcp-gateway","python",["P6-001","P7-004"],"8","8.1",
   "services/mcp-gateway (or a town-core module): an MCP server exposing read-only tools — "
   "query_town_state, get_npc, get_room_activity, search_library, get_trace_summary. "
   "Python or TS SDK, stdio + SSE transports. The 2026 table-stakes integration story. "
   "Tower's holo-array gains an 'agent uplink' visual + MCP docs hook.",
   ["Claude Code connects and answers 'who is in the tavern right now' from live state",
    "Both stdio and SSE transports work",
    "All exposed tools are read-only (no mutation surface)"],
   ["grade:opus"]),
 S("P8-002","LLM evals in CI: golden dialogue set + local judge + threshold gate",
   "academy","python",["P6-013"],"8","8.1",
   "evals/: ~30-case golden dialogue set, rubric scoring via a local judge model "
   "(deepseek-r1:14b), thresholds as a CI gate behind a recorded-fixture mode for "
   "determinism. 'How do you test LLM output' is a guaranteed interview probe. Academy "
   "laboratory room renders the latest eval run.",
   ["A deliberately degraded prompt fails the CI eval gate",
    "Eval gate is deterministic in CI via recorded fixtures",
    "Rubric + thresholds documented"],
   ["grade:opus"]),
 S("P8-003","Gateway hardening: API-key auth, rate limit, query-depth/complexity limits",
   "cartographer","typescript",["P6-017"],"8","8.1",
   "cartographer: API-key auth for mutating ops, a Redis sliding-window rate limit, and "
   "GraphQL query-depth + complexity limits. 'Your gateway is the front door.'",
   ["A k6 abuse script gets 429s",
    "A depth-bomb query is rejected by the depth/complexity limiter",
    "Mutating ops require a valid API key"],
   ["grade:opus"]),
 S("P8-004","Structured outputs: academy emits schema-validated dialogue JSON",
   "academy","python",["P6-007"],"8","8.1",
   "academy emits schema-validated JSON (Ollama format=json + pydantic validation + "
   "retry-on-invalid). NPC dialogue gets {speaker,text,mood,refs[]}; mood drives the NPC "
   "sprite pose in the classroom projector.",
   ["Invalid-schema rate <1% over the eval set",
    "mood field drives the rendered NPC pose",
    "Invalid generations are retried, never emitted raw"],
   ["grade:opus"]),
]
# Tier 2 — strong adds (cherry-pick by energy)
NEW += [
 S("P8-005","Guardrails: moderation as a fortress WASM rule + prompt-injection canaries",
   "fortress","rust",["P6-007","P6-012"],"8","8.2",
   "Add a moderation pass on qtown.ai.content.generated AS a fortress WASM rule (content "
   "policy = just another validation), plus prompt-injection canary tests on the RAG path. "
   "Rejected content gets adjudicated in the Citadel — on theme. OWASP-LLM coverage.",
   ["Disallowed generated content is rejected by the WASM moderation rule",
    "Prompt-injection canary cases are caught on the RAG path",
    "Rejected content surfaces in the Courthouse docket"],
   ["grade:opus"]),
 S("P8-006","Hybrid retrieval: ES dense-vector kNN + BM25 + reranker, A/B on the eval set",
   "library","python",["P6-014","P6-015","P8-002"],"8","8.2",
   "library: ES dense-vector kNN (nomic embeddings) + BM25 + the existing reranker; A/B on "
   "the eval set. Library console gains a retrieval-mode toggle.",
   ["Hybrid retrieval beats BM25-only on the eval set (recorded A/B)",
    "Retrieval-mode toggle works in the Library console"],
   ["grade:opus"]),
 S("P8-007","Streaming token UX: Ollama stream -> academy -> WS -> classroom projector",
   "academy","python",["P6-007"],"8","8.2",
   "Stream Ollama tokens: academy -> WS stream:<dialogue_id> -> classroom projector types "
   "token-by-token.",
   ["Classroom projector renders generation token-by-token over WS",
    "Stream cleanly terminates and finalizes the message"],
   ["grade:ralph"]),
 S("P8-008","LLM observability: GenAI OTel semantic-convention attributes on academy spans",
   "academy","python",["P6.5-008"],"8","8.2",
   "Add GenAI semantic-convention attributes (model, tokens in/out, duration) to academy "
   "spans; add a Grafana panel. Feeds the Academy proof panel.",
   ["academy spans carry model + token + duration attributes per GenAI conventions",
    "Grafana panel renders tokens/sec + cost; Academy proof panel reads it"],
   ["grade:ralph"]),
 S("P8-009","make k8s-local: kind + Helm + Linkerd with real probes",
   "infra","shell",["P6.5-005"],"8","8.2",
   "make k8s-local: kind cluster + Helm install + Linkerd, with the Plan 03 §3 "
   "readiness/liveness endpoints wired as real probes. One GIF in docs. Clinic probes "
   "become its feed.",
   ["make k8s-local brings up the stack on kind with Linkerd",
    "Liveness/readiness probes use the real health endpoints",
    "A short demo GIF is committed"],
   ["grade:opus"]),
 S("P8-010","Episodic NPC memory: per-NPC event log embedded + retrieved into dialogue",
   "town-core","python",["P6-012","P8-006"],"8","8.2",
   "Per-NPC episodic memory: an event log embedded and retrieved into dialogue prompts; "
   "the gossip graph becomes the SOCIAL memory layer. Add an ADR on context engineering. "
   "Shown in the Temple constellation + Home.",
   ["NPC dialogue references retrieved episodic memories",
    "ADR on context engineering written",
    "Temple/Home visualize the memory layer"],
   ["grade:opus"]),
]

# ---------------------------------------------------------------------------
# Merge + enrich + validate
# ---------------------------------------------------------------------------

def main() -> int:
    data = json.loads(WORKLIST.read_text())
    stories = data["stories"]
    by_id = {s["id"]: s for s in stories}

    # 1. Enrich ALL existing stories with a grade tag (idempotent).
    for s in stories:
        set_grade(s)

    # 2. Upsert the new stories (idempotent: replace if id already present).
    for ns in NEW:
        if ns["id"] in by_id:
            existing = by_id[ns["id"]]
            existing.update(ns)
        else:
            stories.append(ns)
            by_id[ns["id"]] = ns

    # 3. Validate.
    ids = [s["id"] for s in stories]
    dupes = {i for i in ids if ids.count(i) > 1}
    assert not dupes, f"duplicate story ids: {dupes}"

    id_set = set(ids)
    dangling = {}
    for s in stories:
        missing = [d for d in s.get("deps", []) if d not in id_set]
        if missing:
            dangling[s["id"]] = missing
    assert not dangling, f"dangling deps: {dangling}"

    # cycle check (Kahn)
    indeg = {i: 0 for i in id_set}
    adj = {i: [] for i in id_set}
    for s in stories:
        for d in s.get("deps", []):
            adj[d].append(s["id"])
            indeg[s["id"]] += 1
    q = [i for i in id_set if indeg[i] == 0]
    seen = 0
    while q:
        n = q.pop()
        seen += 1
        for m in adj[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    assert seen == len(id_set), f"dependency cycle detected ({seen}/{len(id_set)} resolved)"

    new_id_set = {ns["id"] for ns in NEW}
    for s in stories:
        if s["id"] in new_id_set:
            assert s.get("acceptance_criteria"), f"{s['id']} missing acceptance_criteria"
        assert any(l.startswith("grade:") for l in s.get("labels", [])), \
            f"{s['id']} missing grade label"

    data["stories"] = stories
    WORKLIST.write_text(json.dumps(data, indent=2) + "\n")

    # Report
    from collections import Counter
    grades = Counter(
        l for s in stories for l in s["labels"] if l.startswith("grade:"))
    new_ids = [ns["id"] for ns in NEW]
    print(f"OK  total={len(stories)} new={len(new_ids)} "
          f"opus={grades['grade:opus']} ralph={grades['grade:ralph']}")
    print("new phases:", sorted({ns['phase'] for ns in NEW}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
