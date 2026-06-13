# qtown v2 — 2026 Interview Gap Plan (2026-06-12)

**Question this answers:** what is qtown v2 missing to win any 2026 senior/principal/AI-architect interview *on paper* (repo + docs + claims that survive a reader who clicks)?

**Ground truth as of today** (from `docs/v2-audit.md` + `ralph/worklist.json` + `ci.yml`):
- v2 is **scaffolded, not delivered**: 0/3 cross-service flows work end-to-end; market-district gRPC handler unregistered; Kafka topology one-sided.
- **All 26 Phase 6 remediation stories: `pending`** since May 5. Phase 7 design assets were seeded May 26 — new shiny before finished wiring.
- CI runs builds/tests + a 5-second micro-benchmark. **No security scanning, no e2e tests (none exist), no load test.**
- README claims that are currently falsifiable: "<5ms p99 at 10K orders/sec" (never run under load), "zero unsafe" (audit found 27 blocks), implied working 9-service system (0/3 flows).

**The prize if closed:** almost no candidate in 2026 can show a polyglot event-driven system, with measured SLOs, a service mesh, IaC, chaos config, an autonomous local-model dev loop with a human-steering protocol, a self-audit that caught the agent's system-level gaps, AND the remediation receipts. That's not a portfolio piece; that's a thesis.

---

## TIER 0 — TRUTH LAYER (blocks quoting anything; Ralph does ~90% of it)

The audit already wrote the backlog. **The move is not Kevin-coding — it's pointing Ralph at P6 tonight and reviewing PRs.**

1. **Run Phase 6 groups 6.1–6.3 + 6.7** (wire gRPC servers, close Kafka topology, add flow entrypoints, write the 3 e2e flow tests). Ralph executes; you review risk-weighted diffs. e2e tests become CI gates — that's the new control-plane story for "how do you stop per-story-true/system-level-false."
2. **Load test for real** — not `go test -bench`. Add `perf/` with a ghz (gRPC) or k6 script against market-district under compose; commit `perf/REPORT.md`: methodology, hardware, p50/p99/p999 at stated throughput. **Whatever the number is, the measured number wins interviews; the claimed one loses them.** Update README with measured values.
3. **The unsafe claim** — execute P6-003 (confine unsafe to one audited WASM wrapper module), then reword: "unsafe confined to a single audited WASM-boundary module (N blocks)." That's a *better* Rust answer than "zero" anyway — it shows you know where unsafe legitimately lives.
4. **`docs/STATE.md`** — what runs today, what doesn't, the numbers, 5-minute quickstart that actually works (`make deps && make build && ...`). Interviewers and recruiters click; this is the page they land on.
5. **Truth the README + landing** (P6-025/026): mark live vs stubbed contracts until e2e goes green, then flip.

## TIER 1 — SENIOR-SIGNAL DOCUMENTS (Kevin-hours; ~one weekend total; highest paper-ROI per hour)

6. **ADRs — `docs/adr/` (10 × ~half-page):** ① Go for the order book ② Rust+WASM for validation ③ Kafka + at-least-once + idempotent consumers (vs exactly-once myth) ④ GraphQL gateway as sole public entry ⑤ polyglot-by-domain vs resume-driven engineering ⑥ v1 deliberate monolith → v2 decomposition triggers ⑦ local-model routing (Qwen tiers by task type) ⑧ fail-loud over fail-soft (the cartographer `tryLoadPackage` lesson) ⑨ Linkerd/mTLS service authz ⑩ agent-written code: CI as the trust boundary. Senior interviewers read ADRs the way VCs read cap tables.
7. **Postmortem: `docs/postmortems/2026-05-30-committed-secrets.md`** — what leaked, blast radius, rotation, and the CI guard you add now (gitleaks + trivy image scan + dependency audit in `ci.yml`). Converts a visible negative in your git history into elite operational signal. ~1 hour plus the CI wiring.
8. **`docs/agent-ops.md` — the differentiator doc.** Ralph architecture; the **model-routing policy in production** (architect/design → 27b, debug/root-cause → r1:14b, default → qwen3-coder-next — it's literally keyword-routed in the worklist convention); HUMAN.md steering protocol; intervention log; BigQuery commit-stream analytics; cost-per-story methodology; and the audit's money quote — *"true per-story; misleading at the system level"* — plus what changed (e2e gates). Nobody else interviews with this document.
9. **`SECURITY.md` + 1-page threat model** — trust boundaries diagram; the Linkerd authorization policies that already exist in `infra/linkerd/`; what's honestly not done (no auth on internal RPCs yet, no rate limit on the gateway) with the plan. Honest partial > silent absence.

## TIER 2 — COVERAGE ADDS (evenings, weeks 2–3; each closes a standard 2026 probe)

10. **OTel spans in 3 services** (Py/Go/TS) flowing to the existing Jaeger; one committed trace screenshot. Proves polyglot observability without instrumenting all nine.
11. **Academy eval harness in CI** — golden dialogue set, rubric scoring (port the DecisionForge pattern). Closes "how do you test LLM output" with a repo answer.
12. **`make k8s-local`** — the existing `infra/helm/` installing on kind, readiness/liveness real. One GIF. (Multi-region Terraform stays code + ADR; don't apply it.)
13. **`proto-breaking` + gitleaks + trivy as PR gates** in ci.yml (targets already exist for proto).
14. **Cartographer hardening:** fail-loud clients (P6-017), API key + rate limit on the gateway. The "your gateway is the front door" answer.
15. **qtown MCP server** — expose town state queries via MCP. Small; ties the MCP story to the flagship; very 2026.

## TIER 3 — EXPLICITLY NOT FOR INTERVIEWS (park; do not let these eat hours)

CDN/sprite delivery, v1 snapshot parity, multi-region deploy, dashboard features, **Phase 7 rooms/style** (product work, zero interview signal), landing redesign.

---

## Operating rules (these matter more than the list)

- **Ralph codes, Kevin steers.** P6 is already written as agent stories — the whole point of owning an autonomous dev loop is that the wiring backlog costs you review time, not build time. Kevin's keyboard hours go to Tier 1 docs + the perf run only.
- **Time box:** qtown ≤ 2 evenings/week + one weekend chunk, always AFTER the Block, the sends, and interview reps. This list is interview-conversion work, not the mission. The mission is the pipeline.
- **Claim hygiene until Tier 0 lands** (also added to `interview/STUDY-PLAN-2026-06-12.md`): say *"designed to sub-5ms p99 — bench suite is committed, the load validation is landing this month"*, not "<5ms in production." Say *"unsafe confined to the WASM boundary"*, not "zero unsafe." Say *"9 services, final cross-service wiring in flight (Phase 6), e2e tests as the gate"*, not "fully wired." The 88% / 1,451-commit / 550-story v1 numbers are verified — quote freely.
- **Lead with the audit story in interviews even before the fixes land.** "My agent closed 194/194 stories and the system still didn't work end-to-end — here's the audit I wrote, the e2e gates I added, and the remediation backlog" is a *stronger* senior answer than a repo that pretends it was always perfect.
