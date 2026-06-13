# Plan 05 — 2026 Tech Gap Analysis

> Part of the v2 plan pack (`00-MASTER-PLAN.md`). Owns Phase 8.
> Method: the matrix below crosses what a strong 2026 senior/AI-architect interview
> probes (per `docs/2026-interview-gap-plan.md` and the standard 2026 question set)
> against what v2 actually demonstrates. Every gap gets a concrete story AND a place in
> the town — per the master-plan thesis, new tech isn't covered until a room shows it
> working.
> Status key: ✅ Covered (exists + provable) · 🟡 Partial (exists, proof or depth
> missing) · ❌ Missing.

## 1. Coverage matrix

### Architecture & distributed systems

| Tech | Status | Evidence / gap | Shown in |
|---|---|---|---|
| Polyglot microservices by domain | ✅ | 9 services, 5 languages; ADR-05 makes it deliberate | The whole town (Plan 01 §1) |
| gRPC + Protobuf contracts | 🟡 | Contracts exist; servers being wired in P6; add `buf breaking` gate (P6.5) | Market, Citadel |
| Event-driven architecture (Kafka) | 🟡 | 27 topics; topology one-sided until P6-006..009; catalog doc landing (Plan 04 §5) | Warehouse |
| GraphQL federation/gateway | ✅ | Cartographer fan-out (1 query → 5 services) | Tower beams |
| Realtime (WebSocket + Redis pub/sub) | ✅ | Tavern service | Tavern bar |
| WASM sandboxing of untrusted code | ✅ | Fortress; unsafe-confinement P6-003 makes the claim audit-proof | Citadel chamber |
| Idempotency / delivery semantics | 🟡 | Needs the idempotent-consumer tests + ADR-03 | Warehouse docs |
| Distributed tracing across languages | ❌→plan | Plan 03 §5 (OTel ×3 services) | Tower deck |
| Load testing + published SLOs | ❌→plan | Plan 03 §2 (ghz/k6 + REPORT.md) | Market panel |
| Chaos engineering | 🟡 | `infra/chaos/` config exists, never run; one scripted compose-kill demo in Plan 03 §7 step 5 suffices for now | Clinic |

### AI / LLM engineering (the 2026 differentiator set)

| Tech | Status | Evidence / gap | Shown in |
|---|---|---|---|
| Local model inference + quantization | ✅ | Ollama fleet (fp8/q4), 5-model lineup | Academy panel |
| Model routing by task | ✅ | `ralph/v2_model_router.py` — production config, ADR-07 | Agent-ops doc |
| Agentic orchestration (graphs) | 🟡 | LangGraph is a declared dep with no compiled graph — P6-013 closes | Academy classroom |
| RAG pipeline | 🟡 | Retriever/reranker dirs exist; library client P6-012 + index pipeline P6-014/015 close | Academy library |
| **MCP** | ❌ | The 2026 table-stakes integration story — see G-01 | Tower holo-array |
| **LLM evals in CI** | ❌ | "How do you test LLM output" is a guaranteed probe — G-02 | Academy laboratory |
| **Structured outputs / schema-constrained generation** | ❌ | Academy returns free text — G-03 | Classroom projector |
| **Guardrails / OWASP-LLM (prompt injection, content safety)** | ❌ | RAG content is an injection surface; generated NPC content is unmoderated — G-05 | Citadel arbitration |
| LLM observability (GenAI OTel conventions, tokens/sec, cost) | ❌ | G-11, rides on Plan 03 §5 | Academy panel |
| Streaming token UX | ❌ | G-08 | Classroom projector |
| Agent memory / context engineering | 🟡 | Gossip graph is a real social-memory substrate; episodic NPC memory is the 2026-shaped extension — G-09 | Temple, Home |
| Multi-agent interaction | 🟡 | NPCs are sim-driven; true agent-to-agent negotiation is G-10 (showpiece, not table stakes) | Market haggle |
| Autonomous dev loop + human steering | ✅ | Ralph + HUMAN.md + the audit story; agent-ops.md (Plan 04 §3) is the proof artifact | Agent-ops doc |
| Embeddings | ✅ | nomic-embed-text in the lineup; hybrid search depth is G-04 | Library console |

### Generative media

| Tech | Status | Evidence / gap | Shown in |
|---|---|---|---|
| Diffusion pipeline (Flux + ComfyUI) | 🟡 | Style spec + taxonomy locked; workflows/batch are Phase 7-A (Plan 02) | Workshop |
| ControlNet / IP-Adapter / LoRA | ❌→plan | Specced in Plan 02 §1.2/1.4; P7A-001/006 | Workshop board |
| Asset provenance / reproducibility | ❌→plan | genlog.jsonl (Plan 02 §4) — the "AI content provenance" answer | Workshop docs |

### Platform, infra, security

| Tech | Status | Evidence / gap | Shown in |
|---|---|---|---|
| Kubernetes (Helm) | 🟡 | Charts exist, never installed — G-13 (`make k8s-local` on kind + real probes) | Clinic feeds |
| Service mesh (Linkerd, mTLS, authz) | 🟡 | Policies in `infra/linkerd/`; exercised only once k8s-local runs — ADR-09 documents | SECURITY.md |
| IaC (Terraform) | 🟡 | Code exists; stays code + ADR, deliberately not applied (cost) | SECURITY.md |
| Supply-chain security (gitleaks, trivy, SBOM, pinned deps) | ❌→plan | Plan 03 §6 + postmortem (Plan 04 §4) — G-06 | Citadel docs |
| API gateway hardening (authn, rate limits, GraphQL depth limits) | ❌ | G-07 — "your gateway is the front door" | Tower docs |
| Secrets management + incident postmortem | 🟡 | Keys rotated (commit `280d792`); postmortem P7.5-014 converts it to signal | SECURITY.md |

## 2. Gap items → stories (Phase 8, `P8-0xx`)

### Tier 1 — interview-critical (do all)

| ID | Gap | Story + done-when | Room |
|---|---|---|---|
| **G-01** | MCP | P8-001: `services/mcp-gateway` (or a town-core module) — an MCP server exposing read-only tools: `query_town_state`, `get_npc`, `get_room_activity`, `search_library`, `get_trace_summary`. TS or Python SDK, stdio + SSE transports. Done when Claude Code connects and answers "who's in the tavern right now" from live state | Tower: the holo-array gains an "agent uplink" visual; docs hook explains MCP |
| **G-02** | LLM evals in CI | P8-002: `evals/` — golden dialogue set (~30 cases), rubric scoring via a local judge model (r1:14b), thresholds as a CI gate behind a recorded-fixture mode for determinism. Done when a deliberately degraded prompt fails CI | Academy laboratory renders latest eval run (experiments = eval cases) |
| **G-06** | Supply chain | Already storied as P6.5-013..017 (Plan 03 §6); counted here for matrix completeness | Citadel docs |
| **G-07** | Gateway hardening | P8-003: cartographer — API-key auth for mutating ops, rate limit (Redis sliding window), query-depth + complexity limits. Done when k6 abuse script gets 429s and depth-bomb queries are rejected | Tower docs hook |
| **G-03** | Structured outputs | P8-004: academy emits schema-validated JSON (Ollama structured-output / format=json + pydantic validation + retry-on-invalid). NPC dialogue gets `{speaker, text, mood, refs[]}`. Done when invalid-schema rate <1% over the eval set | Classroom projector shows the parsed fields (mood drives the NPC sprite pose!) |

### Tier 2 — strong adds (cherry-pick by energy)

| ID | Gap | Story sketch | Room |
|---|---|---|---|
| **G-05** | Guardrails / OWASP-LLM | P8-005: moderation pass on `ai.content.generated` **as a fortress WASM rule** (content policy as just another validation) + prompt-injection canary tests on the RAG path | Citadel arbitration — rejected content gets adjudicated, on-theme |
| **G-04** | Hybrid retrieval | P8-006: ES dense-vector kNN (nomic embeddings) + BM25 + existing reranker; A/B on the eval set | Library console gains a "retrieval mode" toggle |
| **G-08** | Streaming UX | P8-007: Ollama stream → academy → WS `stream:<dialogue_id>` → classroom projector types token-by-token | Classroom |
| **G-11** | LLM observability | P8-008: GenAI semantic-convention attributes on academy spans (model, tokens in/out, duration); Grafana panel | Academy proof panel |
| **G-13** | k8s-local | P8-009: `make k8s-local` — kind + Helm install + Linkerd, readiness/liveness real (Plan 03 §3 endpoints), one GIF in docs | Clinic (probes are its feed) |
| **G-09** | Agent memory | P8-010: episodic NPC memory — per-NPC event log embedded + retrieved into dialogue prompts; gossip graph becomes the *social* memory layer; ADR on context engineering | Temple constellation + Home |

### Tier 3 — parked (explicitly, with reasons — do not let these eat hours)

| Gap | Why parked |
|---|---|
| G-10 multi-agent negotiation (true A2A haggling) | Showpiece economics: high effort, the sim-driven haggle already *demonstrates* the flow; revisit post-Gate D if v2 needs a wow-feature |
| G-12 runtime inference FinOps | Cost story already strong via Ralph cost-per-story; runtime version needs prod traffic to be meaningful |
| G-14 durable execution (checkpoint/resume) | Document Ralph's existing resume behavior in agent-ops.md; a Temporal-style rebuild proves nothing new |
| Voice (local TTS NPC voices), persona fine-tune (LoRA on a small LLM), sprite animation loops, day/night asset variants | Product polish, zero interview signal (gap-plan Tier 3); Phase 9 candidates |
| Edge/serverless, multi-region | Deliberate non-goal — ADR-worthy one-liner in SECURITY.md/STATE.md: a self-hosted polyglot sim optimizes for depth-of-stack, not edge distribution |
| Blockchain/web3 anything | The bank vault stays a Postgres table, as nature intended |

## 3. What the matrix says in one paragraph

v2's spine — polyglot EDA, gRPC, gateway, WASM, local-LLM agentic loop, diffusion
pipeline, mesh/IaC — is already 2026-credible *on architecture*; what's missing is
almost entirely the **proof layer** (Plans 03/04 close that) plus five genuinely absent
2026 capabilities: **MCP, LLM evals in CI, structured outputs, guardrails, and gateway
hardening** (G-01/02/03/05/07). All five are small relative to what's built — each is
one service-local story — and each lands in an existing room, so closing them
simultaneously upgrades the interview matrix and the product. Nothing in the gap list
requires new infrastructure.

## 4. Sequencing note

G-01 (MCP) and G-02 (evals) are independent of everything — they can start before
Phase 6 closes if parallel capacity exists. G-03/05/08/11 want the dialogue flow live
(Gate A). G-07 wants cartographer stable. G-13 wants the Plan 03 §3 health endpoints.
