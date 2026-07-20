---
review_key: claude-qtown-20260712-architecture
review_status: Awaiting Review
created_by: claude
authority: The architecture-of-record. Source of truth for the Planning Office room and the in-app
  architecture page. Diagrams here are status-honest — they show what is real vs planned, per docs/STATE.md.
---

# Qtown v2 — Architecture of Record

> **Status:** Draft 1, 2026-07-12. This is the **honest** system self-portrait. Node colours track
> `docs/STATE.md` — 🟢 green (works e2e), 🟡 partial (real logic, not wired e2e), ⚫ dormant (stub).
> Mermaid renders natively on GitHub. This file is the source of truth; the in-app
> `dashboard/pages/docs/architecture.vue` and the **Planning Office** area render from the same
> reality. **As of 2026-07-12 no flow is green** — the diagrams say so on purpose.

## Status legend

```
🟢 green    wired end-to-end + e2e CI gate + real proof data (all 6 of REQUIREMENTS.md §3.1)
🟡 partial  real logic exists, but no end-to-end flow / no gate — ships dormant in-app
⚫ dormant   stub / scaffold / not started — visibly labeled, never faking activity
```

## System / container view

Every edge here is a *contract that is supposed to exist*. Solid = implemented and exercised;
dashed = planned or one-sided today. The colours are the current truth, not the aspiration.

```mermaid
flowchart TB
  classDef green   fill:#1e3a2f,stroke:#40916c,color:#d8f3dc;
  classDef partial fill:#3a331e,stroke:#f5a623,color:#ffe8b3;
  classDef dormant fill:#2a2a3a,stroke:#4a4e69,color:#9a9ab0;
  classDef infra   fill:#16213e,stroke:#60a5fa,color:#cfe3ff;

  subgraph CLIENT[Client]
    dashboard["dashboard<br/>Nuxt 3 / Vue"]:::partial
  end

  subgraph EDGE[Gateway / real-time]
    cartographer["cartographer<br/>TS · Apollo GraphQL<br/>fan-out gateway"]:::partial
    tavern["tavern<br/>TS · WebSocket + Redis<br/>broadcast hub"]:::partial
  end

  subgraph CORE[Core services]
    towncore["town-core<br/>Python · FastAPI<br/>30s tick loop · NPCs · economy"]:::partial
    market["market-district<br/>Go · gRPC<br/>order book / matching"]:::partial
    fortress["fortress<br/>Rust · WASM + gRPC<br/>deterministic validation"]:::partial
    academy["academy<br/>Python · LangGraph + Ollama<br/>RAG / dialogue"]:::partial
    library["library<br/>Python · Elasticsearch<br/>search / RAG corpus"]:::dormant
    assets["asset-pipeline<br/>Python · ComfyUI<br/>sprite generation"]:::partial
  end

  subgraph INFRA[Infrastructure]
    kafka["Apache Kafka<br/>event backbone"]:::infra
    redis["Redis 7<br/>cache + pub/sub"]:::infra
    pg["Postgres"]:::infra
    es["Elasticsearch"]:::infra
    ollama["Ollama<br/>local models · GPU box"]:::infra
  end

  subgraph EXT[Capstone — Wave 2, dormant]
    mcp["qtown MCP server"]:::dormant
    saas["Salesforce / Odoo<br/>via MCP"]:::dormant
  end

  %% client edges
  dashboard -->|GraphQL| cartographer
  dashboard -.->|WebSocket| tavern

  %% gateway edges
  cartographer -.->|gRPC fan-out| towncore
  tavern -->|pub/sub| redis

  %% core synchronous contracts (mostly not wired yet = dashed)
  towncore -.->|PlaceOrder gRPC| market
  towncore -.->|Validate gRPC| fortress
  towncore -.->|Decide/Generate| academy
  academy -->|inference| ollama
  academy -.->|retrieve| library
  library --> es

  %% event backbone
  towncore -.->|tick / npc events| kafka
  market -.->|trade.settled| kafka
  fortress -.->|validation.result| kafka
  academy -.->|content.generated| kafka
  kafka -.-> tavern
  kafka -.-> library
  kafka -.-> assets
  towncore --> redis
  towncore --> pg

  %% capstone
  academy -.->|tool call| mcp
  mcp -.->|schema+WASM authorized, HITL| fortress
  mcp -.-> saas
```

## Deployment view

Frontend on the edge, GPU-backed backend on owned hardware behind a tunnel, v1 preserved on its own
subdomain. This is the "local box exposed" option from `REQUIREMENTS.md §10`.

```mermaid
flowchart LR
  classDef live    fill:#1e3a2f,stroke:#40916c,color:#d8f3dc;
  classDef planned fill:#2a2a3a,stroke:#4a4e69,color:#9a9ab0;

  user(("visitor / interviewer"))

  subgraph now[Live today]
    apex["qtown.ai (apex)<br/>Vercel · static landing"]:::live
    v1["v1.qtown.ai<br/>Railway · v1 sim (idle)"]:::live
  end

  subgraph planned_[Planned — flips on Wave 1 green]
    vdash["qtown.ai → v2 dashboard<br/>Vercel"]:::planned
    tunnel["Cloudflare / Tailscale tunnel"]:::planned
    box["3090 box<br/>full compose stack + Ollama"]:::planned
  end

  user --> apex
  user --> v1
  user -.-> vdash
  vdash -.->|NUXT_PUBLIC_* → tunnel URL| tunnel
  tunnel -.-> box
```

## Flagship flow — Market Trade *(⚫ dormant: 0/3 e2e flows work; shown as the target)*

```mermaid
sequenceDiagram
  autonumber
  participant TC as town-core
  participant FT as fortress (WASM)
  participant MK as market-district
  participant KF as Kafka
  participant DB as dashboard
  Note over TC,MK: DORMANT — town-core has no gRPC server and market's handler isn't registered yet (Wave 1A)
  TC->>FT: Validate(order) [gRPC]
  FT-->>TC: {allowed}
  TC->>MK: PlaceOrder [gRPC]
  MK-->>TC: {orderId}
  MK->>KF: economy.trade.settled
  KF->>DB: live order book + measured p99
```

## Flagship flow — AI Dialogue / RAG *(🟡 partial: model call is a facade on some paths — Wave 0 W0-2 / Wave 1B)*

```mermaid
sequenceDiagram
  autonumber
  participant TC as town-core
  participant AC as academy
  participant LB as library (ES)
  participant OL as Ollama (local)
  Note over AC,OL: PARTIAL — Ollama client is real, but paths exist where the model is never called
  TC->>AC: NPCDecide(npc, context) [gRPC]
  AC->>LB: retrieve passages
  LB-->>AC: chunks + citations
  AC->>OL: generate(prompt + retrieved) [format=json]
  OL-->>AC: structured, validated response
  AC-->>TC: decision + citations + token/cost
```

## Corrections this file makes to the old in-app diagram

The previous `architecture.vue` asserted three things that were false (now being fixed):

| Claim in old diagram | Truth |
|---|---|
| `fortress` is **Go** | `fortress` is **Rust / WASM** (+ gRPC). |
| tick loop runs **~500ms** | tick loop runs every **30s**. |
| NPC decisions via **GPT-4o-mini** | decisions route to **local Ollama** models (≥90% local; `REQUIREMENTS.md §6`). |
| all 9 services fully wired | **0/3 flagship flows work** end-to-end (`docs/STATE.md`). |
