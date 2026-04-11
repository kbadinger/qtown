"""Generate worklist.json for Ralph v2 — 194 stories across 6 phases."""

import json
from pathlib import Path

stories = []

# ---------------------------------------------------------------------------
# Phase 0 — Monorepo Foundation (P0-001 to P0-038)
# ---------------------------------------------------------------------------
# Group 0.1 — Monorepo skeleton
stories += [
    {"id": "P0-001", "title": "Create monorepo directory structure", "service": "infra", "language": "shell", "deps": [], "phase": 0, "group": "0.1"},
    {"id": "P0-002", "title": "Add root Makefile with help, build, test, lint targets", "service": "infra", "language": "makefile", "deps": ["P0-001"], "phase": 0, "group": "0.1"},
    {"id": "P0-003", "title": "Add root docker-compose.yml for local dev", "service": "infra", "language": "dockerfile", "deps": ["P0-001"], "phase": 0, "group": "0.1"},
    {"id": "P0-004", "title": "Add docker-compose.deps.yml (Postgres, Redis, Kafka, Zookeeper)", "service": "infra", "language": "dockerfile", "deps": ["P0-001"], "phase": 0, "group": "0.1"},
    {"id": "P0-005", "title": "Add .github/workflows/ci.yml — lint and test on PR", "service": "infra", "language": "yaml", "deps": ["P0-001"], "phase": 0, "group": "0.1"},
    {"id": "P0-006", "title": "Add .github/workflows/cd.yml — build and push on merge to main", "service": "infra", "language": "yaml", "deps": ["P0-005"], "phase": 0, "group": "0.1"},
    {"id": "P0-007", "title": "Add root .gitignore covering all service languages", "service": "infra", "language": "shell", "deps": ["P0-001"], "phase": 0, "group": "0.1"},
    {"id": "P0-008", "title": "Add CODEOWNERS file mapping services to owners", "service": "infra", "language": "shell", "deps": ["P0-001"], "phase": 0, "group": "0.1"},
]

# Group 0.2 — Protobuf setup
stories += [
    {"id": "P0-009", "title": "Scaffold proto/ directory with buf.yaml and buf.gen.yaml", "service": "proto", "language": "protobuf", "deps": ["P0-001"], "phase": 0, "group": "0.2"},
    {"id": "P0-010", "title": "Define qtown/common.proto — shared message types (Timestamp, Money, Pagination)", "service": "proto", "language": "protobuf", "deps": ["P0-009"], "phase": 0, "group": "0.2"},
    {"id": "P0-011", "title": "Define qtown/town_core.proto — WorldState, NPC, Building messages", "service": "proto", "language": "protobuf", "deps": ["P0-010"], "phase": 0, "group": "0.2"},
    {"id": "P0-012", "title": "Define qtown/market.proto — PriceEvent, TradeOrder, MarketSummary messages", "service": "proto", "language": "protobuf", "deps": ["P0-010"], "phase": 0, "group": "0.2"},
    {"id": "P0-013", "title": "Define qtown/fortress.proto — GuardEvent, ThreatLevel, PatrolRoute messages", "service": "proto", "language": "protobuf", "deps": ["P0-010"], "phase": 0, "group": "0.2"},
    {"id": "P0-014", "title": "Define qtown/academy.proto — LessonEvent, SkillGrant, CurriculumUpdate messages", "service": "proto", "language": "protobuf", "deps": ["P0-010"], "phase": 0, "group": "0.2"},
    {"id": "P0-015", "title": "Run buf generate and commit generated stubs for all languages", "service": "proto", "language": "protobuf", "deps": ["P0-011", "P0-012", "P0-013", "P0-014"], "phase": 0, "group": "0.2"},
]

# Group 0.3 — Infra / Terraform
stories += [
    {"id": "P0-016", "title": "Scaffold infra/terraform/ with provider config and remote state", "service": "infra", "language": "hcl", "deps": ["P0-001"], "phase": 0, "group": "0.3"},
    {"id": "P0-017", "title": "Add Terraform module for Postgres (Cloud SQL / RDS)", "service": "infra", "language": "hcl", "deps": ["P0-016"], "phase": 0, "group": "0.3"},
    {"id": "P0-018", "title": "Add Terraform module for Redis (Cloud Memorystore / ElastiCache)", "service": "infra", "language": "hcl", "deps": ["P0-016"], "phase": 0, "group": "0.3"},
    {"id": "P0-019", "title": "Add Terraform module for Kafka (Cloud MSK / Confluent)", "service": "infra", "language": "hcl", "deps": ["P0-016"], "phase": 0, "group": "0.3"},
    {"id": "P0-020", "title": "Add Terraform module for container registry", "service": "infra", "language": "hcl", "deps": ["P0-016"], "phase": 0, "group": "0.3"},
    {"id": "P0-021", "title": "Add Terraform module for Kubernetes cluster", "service": "infra", "language": "hcl", "deps": ["P0-016"], "phase": 0, "group": "0.3"},
]

# Group 0.4 — Kubernetes base
stories += [
    {"id": "P0-022", "title": "Scaffold infra/k8s/base/ with namespace and RBAC manifests", "service": "infra", "language": "yaml", "deps": ["P0-021"], "phase": 0, "group": "0.4"},
    {"id": "P0-023", "title": "Add K8s ConfigMap and Secret templates for all services", "service": "infra", "language": "yaml", "deps": ["P0-022"], "phase": 0, "group": "0.4"},
    {"id": "P0-024", "title": "Add Helm chart scaffold in infra/helm/qtown/", "service": "infra", "language": "yaml", "deps": ["P0-022"], "phase": 0, "group": "0.4"},
    {"id": "P0-025", "title": "Add Linkerd service mesh config for mTLS between services", "service": "infra", "language": "yaml", "deps": ["P0-022"], "phase": 0, "group": "0.4"},
]

# Group 0.5 — Observability stack
stories += [
    {"id": "P0-026", "title": "Add OpenTelemetry Collector config (docker-compose.observability.yml)", "service": "infra", "language": "yaml", "deps": ["P0-004"], "phase": 0, "group": "0.5"},
    {"id": "P0-027", "title": "Add Prometheus scrape config for all services", "service": "infra", "language": "yaml", "deps": ["P0-026"], "phase": 0, "group": "0.5"},
    {"id": "P0-028", "title": "Add Grafana datasource provisioning (Prometheus, Loki, Tempo)", "service": "infra", "language": "yaml", "deps": ["P0-027"], "phase": 0, "group": "0.5"},
    {"id": "P0-029", "title": "Add Grafana dashboard: service health overview", "service": "infra", "language": "yaml", "deps": ["P0-028"], "phase": 0, "group": "0.5"},
    {"id": "P0-030", "title": "Add Grafana dashboard: Kafka consumer lag per topic", "service": "infra", "language": "yaml", "deps": ["P0-028"], "phase": 0, "group": "0.5"},
    {"id": "P0-031", "title": "Add Prometheus alerting rules (service down, high error rate)", "service": "infra", "language": "yaml", "deps": ["P0-027"], "phase": 0, "group": "0.5"},
]

# Group 0.6 — Ralph v2 setup
stories += [
    {"id": "P0-032", "title": "Scaffold ralph/ directory with v2_orchestrator.py skeleton", "service": "ralph", "language": "python", "deps": ["P0-001"], "phase": 0, "group": "0.6"},
    {"id": "P0-033", "title": "Implement v2_worklist.py — load, schedule, and persist worklist.json", "service": "ralph", "language": "python", "deps": ["P0-032"], "phase": 0, "group": "0.6"},
    {"id": "P0-034", "title": "Implement v2_model_router.py — route stories to Ollama models", "service": "ralph", "language": "python", "deps": ["P0-032"], "phase": 0, "group": "0.6"},
    {"id": "P0-035", "title": "Implement v2_cross_service.py — detect proto and multi-service stories", "service": "ralph", "language": "python", "deps": ["P0-032"], "phase": 0, "group": "0.6"},
    {"id": "P0-036", "title": "Add ralph/v2_config.py — centralised env-driven configuration", "service": "ralph", "language": "python", "deps": ["P0-032"], "phase": 0, "group": "0.6"},
    {"id": "P0-037", "title": "Add ralph/worklist.json — 194-story historical record", "service": "ralph", "language": "shell", "deps": ["P0-033"], "phase": 0, "group": "0.6"},
    {"id": "P0-038", "title": "Add ralph/README.md — Ralph v2 architecture and operating guide", "service": "ralph", "language": "shell", "deps": ["P0-036", "P0-037"], "phase": 0, "group": "0.6"},
]

# ---------------------------------------------------------------------------
# Phase 1 — Core Services: town-core, market-district, fortress (P1-001 to P1-042)
# ---------------------------------------------------------------------------
# Group 1.1 — town-core v2 migration
stories += [
    {"id": "P1-001", "title": "Scaffold services/town-core/ as FastAPI service with pyproject.toml", "service": "town-core", "language": "python", "deps": ["P0-007"], "phase": 1, "group": "1.1"},
    {"id": "P1-002", "title": "Add SQLAlchemy models: NPC, Building, WorldState, Transaction (v2 schema)", "service": "town-core", "language": "python", "deps": ["P1-001"], "phase": 1, "group": "1.1"},
    {"id": "P1-003", "title": "Add Alembic migration scaffolding and initial migration", "service": "town-core", "language": "python", "deps": ["P1-002"], "phase": 1, "group": "1.1"},
    {"id": "P1-004", "title": "Implement GET /api/world — returns full WorldState JSON", "service": "town-core", "language": "python", "deps": ["P1-002"], "phase": 1, "group": "1.1"},
    {"id": "P1-005", "title": "Implement POST /api/tick — advances simulation by one tick", "service": "town-core", "language": "python", "deps": ["P1-004"], "phase": 1, "group": "1.1"},
    {"id": "P1-006", "title": "Implement NPC lifecycle: spawn, age, die with Postgres-safe boolean columns", "service": "town-core", "language": "python", "deps": ["P1-003"], "phase": 1, "group": "1.1"},
    {"id": "P1-007", "title": "Implement NPC needs: hunger, energy, happiness decay and recovery", "service": "town-core", "language": "python", "deps": ["P1-006"], "phase": 1, "group": "1.1"},
    {"id": "P1-008", "title": "Implement NPC movement on 50×50 grid with home and work assignment", "service": "town-core", "language": "python", "deps": ["P1-007"], "phase": 1, "group": "1.1"},
    {"id": "P1-009", "title": "Implement building effects: hospital heals, school teaches, tavern restores energy", "service": "town-core", "language": "python", "deps": ["P1-008"], "phase": 1, "group": "1.1"},
    {"id": "P1-010", "title": "Implement economy: gold earning, taxation, treasury, inflation", "service": "town-core", "language": "python", "deps": ["P1-007"], "phase": 1, "group": "1.1"},
    {"id": "P1-011", "title": "Implement weather system: drought, rain, gold rush events", "service": "town-core", "language": "python", "deps": ["P1-010"], "phase": 1, "group": "1.1"},
    {"id": "P1-012", "title": "Add OpenTelemetry instrumentation to all town-core FastAPI routes", "service": "town-core", "language": "python", "deps": ["P1-004"], "phase": 1, "group": "1.1"},
    {"id": "P1-013", "title": "Add Prometheus /metrics endpoint to town-core", "service": "town-core", "language": "python", "deps": ["P1-012"], "phase": 1, "group": "1.1"},
    {"id": "P1-014", "title": "Add Dockerfile for town-core with multi-stage build", "service": "town-core", "language": "dockerfile", "deps": ["P1-001"], "phase": 1, "group": "1.1"},
    {"id": "P1-015", "title": "Publish WorldState events to Kafka topic qtown.world.ticked", "service": "town-core", "language": "python", "deps": ["P1-005", "P0-015"], "phase": 1, "group": "1.1"},
]

# Group 1.2 — market-district
stories += [
    {"id": "P1-016", "title": "Scaffold services/market-district/ as Go service with go.mod", "service": "market-district", "language": "go", "deps": ["P0-007"], "phase": 1, "group": "1.2"},
    {"id": "P1-017", "title": "Implement dynamic pricing engine: supply/demand curves, price history", "service": "market-district", "language": "go", "deps": ["P1-016"], "phase": 1, "group": "1.2"},
    {"id": "P1-018", "title": "Add REST API: GET /prices, POST /trade, GET /history/:resource", "service": "market-district", "language": "go", "deps": ["P1-017"], "phase": 1, "group": "1.2"},
    {"id": "P1-019", "title": "Implement gRPC MarketService with PriceStream and PlaceOrder RPCs", "service": "market-district", "language": "go", "deps": ["P1-018", "P0-012"], "phase": 1, "group": "1.2"},
    {"id": "P1-020", "title": "Consume qtown.world.ticked events from Kafka to update market state", "service": "market-district", "language": "go", "deps": ["P1-016", "P1-015"], "phase": 1, "group": "1.2"},
    {"id": "P1-021", "title": "Publish PriceEvent to Kafka topic qtown.market.price_updated", "service": "market-district", "language": "go", "deps": ["P1-020"], "phase": 1, "group": "1.2"},
    {"id": "P1-022", "title": "Add go test suite: pricing engine unit tests with race detector", "service": "market-district", "language": "go", "deps": ["P1-017"], "phase": 1, "group": "1.2"},
    {"id": "P1-023", "title": "Add OpenTelemetry tracing to market-district gRPC and HTTP handlers", "service": "market-district", "language": "go", "deps": ["P1-018"], "phase": 1, "group": "1.2"},
    {"id": "P1-024", "title": "Add Dockerfile for market-district with distroless base", "service": "market-district", "language": "dockerfile", "deps": ["P1-016"], "phase": 1, "group": "1.2"},
]

# Group 1.3 — fortress
stories += [
    {"id": "P1-025", "title": "Scaffold services/fortress/ as Rust service with Cargo.toml", "service": "fortress", "language": "rust", "deps": ["P0-007"], "phase": 1, "group": "1.3"},
    {"id": "P1-026", "title": "Implement guard patrol scheduler: assign routes, detect threats", "service": "fortress", "language": "rust", "deps": ["P1-025"], "phase": 1, "group": "1.3"},
    {"id": "P1-027", "title": "Implement threat level calculator: crime rate, external events, guard count", "service": "fortress", "language": "rust", "deps": ["P1-026"], "phase": 1, "group": "1.3"},
    {"id": "P1-028", "title": "Add REST API: GET /threat-level, POST /incident, GET /patrols", "service": "fortress", "language": "rust", "deps": ["P1-027"], "phase": 1, "group": "1.3"},
    {"id": "P1-029", "title": "Implement gRPC FortressService with GuardStream and ReportIncident RPCs", "service": "fortress", "language": "rust", "deps": ["P1-028", "P0-013"], "phase": 1, "group": "1.3"},
    {"id": "P1-030", "title": "Add cargo test suite with clippy clean and zero-warning policy", "service": "fortress", "language": "rust", "deps": ["P1-026"], "phase": 1, "group": "1.3"},
    {"id": "P1-031", "title": "Add OpenTelemetry tracing to fortress Actix-Web handlers", "service": "fortress", "language": "rust", "deps": ["P1-028"], "phase": 1, "group": "1.3"},
    {"id": "P1-032", "title": "Publish GuardEvent to Kafka topic qtown.fortress.guard_event", "service": "fortress", "language": "rust", "deps": ["P1-028"], "phase": 1, "group": "1.3"},
    {"id": "P1-033", "title": "Add Dockerfile for fortress with Rust multi-stage build", "service": "fortress", "language": "dockerfile", "deps": ["P1-025"], "phase": 1, "group": "1.3"},
]

# Group 1.4 — cross-service integration
stories += [
    {"id": "P1-034", "title": "Wire town-core NPC crime rate to fortress threat calculator via Kafka", "service": "multi", "language": "multi", "deps": ["P1-015", "P1-032"], "phase": 1, "group": "1.4"},
    {"id": "P1-035", "title": "Wire market price shocks to town-core NPC buying behaviour via gRPC", "service": "multi", "language": "multi", "deps": ["P1-021", "P1-019"], "phase": 1, "group": "1.4"},
    {"id": "P1-036", "title": "Add integration test: full tick → market update → fortress response cycle", "service": "multi", "language": "python", "deps": ["P1-034", "P1-035"], "phase": 1, "group": "1.4"},
    {"id": "P1-037", "title": "Add K8s Deployment and Service manifests for town-core", "service": "infra", "language": "yaml", "deps": ["P1-014", "P0-022"], "phase": 1, "group": "1.4"},
    {"id": "P1-038", "title": "Add K8s Deployment and Service manifests for market-district", "service": "infra", "language": "yaml", "deps": ["P1-024", "P0-022"], "phase": 1, "group": "1.4"},
    {"id": "P1-039", "title": "Add K8s Deployment and Service manifests for fortress", "service": "infra", "language": "yaml", "deps": ["P1-033", "P0-022"], "phase": 1, "group": "1.4"},
    {"id": "P1-040", "title": "Add HorizontalPodAutoscaler for town-core (CPU and custom tick-rate metric)", "service": "infra", "language": "yaml", "deps": ["P1-037"], "phase": 1, "group": "1.4"},
    {"id": "P1-041", "title": "Add Grafana dashboard: Phase 1 service health and tick latency", "service": "infra", "language": "yaml", "deps": ["P0-029", "P1-013", "P1-023"], "phase": 1, "group": "1.4"},
    {"id": "P1-042", "title": "Run buf lint and buf generate after all Phase 1 proto updates", "service": "proto", "language": "protobuf", "deps": ["P1-019", "P1-029"], "phase": 1, "group": "1.4"},
]

# ---------------------------------------------------------------------------
# Phase 2 — Supporting Services: academy, tavern, cartographer (P2-001 to P2-030)
# ---------------------------------------------------------------------------
# Group 2.1 — academy
stories += [
    {"id": "P2-001", "title": "Scaffold services/academy/ as Python FastAPI service with pyproject.toml", "service": "academy", "language": "python", "deps": ["P0-007"], "phase": 2, "group": "2.1"},
    {"id": "P2-002", "title": "Implement curriculum engine: skill trees, lesson plans, prerequisites", "service": "academy", "language": "python", "deps": ["P2-001"], "phase": 2, "group": "2.1"},
    {"id": "P2-003", "title": "Implement NPC enrollment: assign NPCs to lessons based on role and skill gap", "service": "academy", "language": "python", "deps": ["P2-002"], "phase": 2, "group": "2.1"},
    {"id": "P2-004", "title": "Implement lesson completion and SkillGrant event emission", "service": "academy", "language": "python", "deps": ["P2-003"], "phase": 2, "group": "2.1"},
    {"id": "P2-005", "title": "Add REST API: GET /curriculum, POST /enroll, GET /skills/:npc_id", "service": "academy", "language": "python", "deps": ["P2-002"], "phase": 2, "group": "2.1"},
    {"id": "P2-006", "title": "Implement gRPC AcademyService with SkillStream and EnrollNPC RPCs", "service": "academy", "language": "python", "deps": ["P2-005", "P0-014"], "phase": 2, "group": "2.1"},
    {"id": "P2-007", "title": "Publish LessonEvent to Kafka topic qtown.academy.lesson_completed", "service": "academy", "language": "python", "deps": ["P2-004"], "phase": 2, "group": "2.1"},
    {"id": "P2-008", "title": "Consume SkillGrant events in town-core to boost NPC productivity", "service": "town-core", "language": "python", "deps": ["P2-007", "P1-005"], "phase": 2, "group": "2.1"},
    {"id": "P2-009", "title": "Add pytest suite for academy curriculum and enrollment logic", "service": "academy", "language": "python", "deps": ["P2-003"], "phase": 2, "group": "2.1"},
    {"id": "P2-010", "title": "Add Dockerfile for academy service", "service": "academy", "language": "dockerfile", "deps": ["P2-001"], "phase": 2, "group": "2.1"},
]

# Group 2.2 — tavern
stories += [
    {"id": "P2-011", "title": "Scaffold services/tavern/ as TypeScript Fastify service with package.json", "service": "tavern", "language": "typescript", "deps": ["P0-007"], "phase": 2, "group": "2.2"},
    {"id": "P2-012", "title": "Implement NPC dialogue engine: template-based conversations with personality", "service": "tavern", "language": "typescript", "deps": ["P2-011"], "phase": 2, "group": "2.2"},
    {"id": "P2-013", "title": "Add REST API: GET /dialogue/:npc_id, POST /rumour, GET /menu", "service": "tavern", "language": "typescript", "deps": ["P2-012"], "phase": 2, "group": "2.2"},
    {"id": "P2-014", "title": "Implement rumour propagation: NPCs spread news across the tavern", "service": "tavern", "language": "typescript", "deps": ["P2-013"], "phase": 2, "group": "2.2"},
    {"id": "P2-015", "title": "Implement Kafka consumer: ingest WorldState events and generate rumours", "service": "tavern", "language": "typescript", "deps": ["P2-014", "P1-015"], "phase": 2, "group": "2.2"},
    {"id": "P2-016", "title": "Add WebSocket endpoint for real-time NPC dialogue stream", "service": "tavern", "language": "typescript", "deps": ["P2-013"], "phase": 2, "group": "2.2"},
    {"id": "P2-017", "title": "Add Jest test suite for dialogue engine and rumour propagation", "service": "tavern", "language": "typescript", "deps": ["P2-012"], "phase": 2, "group": "2.2"},
    {"id": "P2-018", "title": "Add Dockerfile for tavern service with Node.js Alpine base", "service": "tavern", "language": "dockerfile", "deps": ["P2-011"], "phase": 2, "group": "2.2"},
]

# Group 2.3 — cartographer
stories += [
    {"id": "P2-019", "title": "Scaffold services/cartographer/ as TypeScript service with package.json", "service": "cartographer", "language": "typescript", "deps": ["P0-007"], "phase": 2, "group": "2.3"},
    {"id": "P2-020", "title": "Implement map tile generator: 50×50 grid serialisation with building overlays", "service": "cartographer", "language": "typescript", "deps": ["P2-019"], "phase": 2, "group": "2.3"},
    {"id": "P2-021", "title": "Add REST API: GET /map, GET /tile/:x/:y, GET /buildings-geojson", "service": "cartographer", "language": "typescript", "deps": ["P2-020"], "phase": 2, "group": "2.3"},
    {"id": "P2-022", "title": "Implement path-finding: A* shortest path between two tiles", "service": "cartographer", "language": "typescript", "deps": ["P2-020"], "phase": 2, "group": "2.3"},
    {"id": "P2-023", "title": "Add WebSocket endpoint: subscribe to NPC position updates", "service": "cartographer", "language": "typescript", "deps": ["P2-021"], "phase": 2, "group": "2.3"},
    {"id": "P2-024", "title": "Consume town-core tick events to refresh NPC positions on map", "service": "cartographer", "language": "typescript", "deps": ["P2-023", "P1-015"], "phase": 2, "group": "2.3"},
    {"id": "P2-025", "title": "Add Jest test suite for tile generator and path-finding", "service": "cartographer", "language": "typescript", "deps": ["P2-020"], "phase": 2, "group": "2.3"},
    {"id": "P2-026", "title": "Add Dockerfile for cartographer service", "service": "cartographer", "language": "dockerfile", "deps": ["P2-019"], "phase": 2, "group": "2.3"},
]

# Group 2.4 — Phase 2 infra
stories += [
    {"id": "P2-027", "title": "Add K8s manifests for academy, tavern, cartographer", "service": "infra", "language": "yaml", "deps": ["P2-010", "P2-018", "P2-026"], "phase": 2, "group": "2.4"},
    {"id": "P2-028", "title": "Add proto extension: qtown/tavern.proto — DialogueEvent, RumourMessage", "service": "proto", "language": "protobuf", "deps": ["P0-015"], "phase": 2, "group": "2.4"},
    {"id": "P2-029", "title": "Run buf generate after Phase 2 proto additions", "service": "proto", "language": "protobuf", "deps": ["P2-028"], "phase": 2, "group": "2.4"},
    {"id": "P2-030", "title": "Add Grafana dashboard: Phase 2 NPC activity and dialogue throughput", "service": "infra", "language": "yaml", "deps": ["P2-027", "P0-028"], "phase": 2, "group": "2.4"},
]

# ---------------------------------------------------------------------------
# Phase 3 — Advanced Features: library, asset-pipeline, dashboard (P3-001 to P3-036)
# ---------------------------------------------------------------------------
# Group 3.1 — library (RAG / knowledge store)
stories += [
    {"id": "P3-001", "title": "Scaffold services/library/ as Python service with FastAPI and pgvector", "service": "library", "language": "python", "deps": ["P0-007"], "phase": 3, "group": "3.1"},
    {"id": "P3-002", "title": "Implement document ingestion pipeline: chunk, embed, upsert to pgvector", "service": "library", "language": "python", "deps": ["P3-001"], "phase": 3, "group": "3.1"},
    {"id": "P3-003", "title": "Implement semantic search: query embedding → cosine similarity → top-k results", "service": "library", "language": "python", "deps": ["P3-002"], "phase": 3, "group": "3.1"},
    {"id": "P3-004", "title": "Add REST API: POST /ingest, GET /search?q=, GET /document/:id", "service": "library", "language": "python", "deps": ["P3-003"], "phase": 3, "group": "3.1"},
    {"id": "P3-005", "title": "Implement Kafka consumer: auto-ingest NPC dialogue and world events", "service": "library", "language": "python", "deps": ["P3-002", "P1-015", "P2-007"], "phase": 3, "group": "3.1"},
    {"id": "P3-006", "title": "Add connector: sync academy lesson content to library knowledge base", "service": "library", "language": "python", "deps": ["P3-002", "P2-007"], "phase": 3, "group": "3.1"},
    {"id": "P3-007", "title": "Add nomic-embed-text integration for embedding generation via Ollama", "service": "library", "language": "python", "deps": ["P3-002"], "phase": 3, "group": "3.1"},
    {"id": "P3-008", "title": "Add pytest suite for ingestion pipeline and semantic search", "service": "library", "language": "python", "deps": ["P3-003"], "phase": 3, "group": "3.1"},
    {"id": "P3-009", "title": "Add Dockerfile for library service", "service": "library", "language": "dockerfile", "deps": ["P3-001"], "phase": 3, "group": "3.1"},
]

# Group 3.2 — asset-pipeline
stories += [
    {"id": "P3-010", "title": "Scaffold services/asset-pipeline/ as Python service with Celery", "service": "asset-pipeline", "language": "python", "deps": ["P0-007"], "phase": 3, "group": "3.2"},
    {"id": "P3-011", "title": "Implement sprite generation worker: call Ollama vision model for NPC sprites", "service": "asset-pipeline", "language": "python", "deps": ["P3-010"], "phase": 3, "group": "3.2"},
    {"id": "P3-012", "title": "Implement building sprite generator with 16 building type templates", "service": "asset-pipeline", "language": "python", "deps": ["P3-011"], "phase": 3, "group": "3.2"},
    {"id": "P3-013", "title": "Add Celery task queue backed by Redis for async sprite jobs", "service": "asset-pipeline", "language": "python", "deps": ["P3-010"], "phase": 3, "group": "3.2"},
    {"id": "P3-014", "title": "Add REST API: POST /generate/npc, POST /generate/building, GET /status/:job_id", "service": "asset-pipeline", "language": "python", "deps": ["P3-013"], "phase": 3, "group": "3.2"},
    {"id": "P3-015", "title": "Implement S3-compatible object storage upload for generated assets", "service": "asset-pipeline", "language": "python", "deps": ["P3-014"], "phase": 3, "group": "3.2"},
    {"id": "P3-016", "title": "Add Kafka consumer: auto-generate sprites for new NPC roles and building types", "service": "asset-pipeline", "language": "python", "deps": ["P3-013", "P1-015"], "phase": 3, "group": "3.2"},
    {"id": "P3-017", "title": "Add workflow definitions for sprite generation pipelines (Temporal/Celery)", "service": "asset-pipeline", "language": "python", "deps": ["P3-013"], "phase": 3, "group": "3.2"},
    {"id": "P3-018", "title": "Add Dockerfile for asset-pipeline with GPU support annotation", "service": "asset-pipeline", "language": "dockerfile", "deps": ["P3-010"], "phase": 3, "group": "3.2"},
]

# Group 3.3 — dashboard (Nuxt/Vue)
stories += [
    {"id": "P3-019", "title": "Scaffold dashboard/ as Nuxt 3 app with Tailwind, Pinia, and nuxt.config.ts", "service": "dashboard", "language": "vue", "deps": ["P0-007"], "phase": 3, "group": "3.3"},
    {"id": "P3-020", "title": "Add dashboard layout: sidebar nav, top bar, main content area", "service": "dashboard", "language": "vue", "deps": ["P3-019"], "phase": 3, "group": "3.3"},
    {"id": "P3-021", "title": "Add map page: render 50×50 grid with PixiJS, consume cartographer WebSocket", "service": "dashboard", "language": "vue", "deps": ["P3-020", "P2-023"], "phase": 3, "group": "3.3"},
    {"id": "P3-022", "title": "Add NPC inspector panel: click NPC on map to view stats, history, relationships", "service": "dashboard", "language": "vue", "deps": ["P3-021"], "phase": 3, "group": "3.3"},
    {"id": "P3-023", "title": "Add market page: live price charts (Chart.js) from market-district WebSocket feed", "service": "dashboard", "language": "vue", "deps": ["P3-020", "P1-019"], "phase": 3, "group": "3.3"},
    {"id": "P3-024", "title": "Add tavern page: real-time NPC dialogue feed via WebSocket", "service": "dashboard", "language": "vue", "deps": ["P3-020", "P2-016"], "phase": 3, "group": "3.3"},
    {"id": "P3-025", "title": "Add knowledge search page: query library service and display results", "service": "dashboard", "language": "vue", "deps": ["P3-020", "P3-004"], "phase": 3, "group": "3.3"},
    {"id": "P3-026", "title": "Add admin controls: pause/resume tick, adjust simulation speed, trigger events", "service": "dashboard", "language": "vue", "deps": ["P3-020", "P1-004"], "phase": 3, "group": "3.3"},
    {"id": "P3-027", "title": "Add Pinia store: world-state, market-prices, active-npcs", "service": "dashboard", "language": "typescript", "deps": ["P3-020"], "phase": 3, "group": "3.3"},
    {"id": "P3-028", "title": "Add nuxt server routes: BFF proxy for all backend service calls", "service": "dashboard", "language": "typescript", "deps": ["P3-019"], "phase": 3, "group": "3.3"},
    {"id": "P3-029", "title": "Add Dockerfile for dashboard with Nuxt SSR build", "service": "dashboard", "language": "dockerfile", "deps": ["P3-019"], "phase": 3, "group": "3.3"},
]

# Group 3.4 — Phase 3 infra
stories += [
    {"id": "P3-030", "title": "Add K8s manifests for library, asset-pipeline, dashboard", "service": "infra", "language": "yaml", "deps": ["P3-009", "P3-018", "P3-029"], "phase": 3, "group": "3.4"},
    {"id": "P3-031", "title": "Add Grafana dashboard: asset pipeline job queue depth and latency", "service": "infra", "language": "yaml", "deps": ["P0-028", "P3-017"], "phase": 3, "group": "3.4"},
    {"id": "P3-032", "title": "Add Grafana dashboard: library search latency and embedding throughput", "service": "infra", "language": "yaml", "deps": ["P0-028", "P3-004"], "phase": 3, "group": "3.4"},
    {"id": "P3-033", "title": "Add Ingress manifest for dashboard with TLS termination", "service": "infra", "language": "yaml", "deps": ["P3-030"], "phase": 3, "group": "3.4"},
    {"id": "P3-034", "title": "Add HPA for asset-pipeline based on Celery queue depth custom metric", "service": "infra", "language": "yaml", "deps": ["P3-030"], "phase": 3, "group": "3.4"},
    {"id": "P3-035", "title": "Add Helm chart values for Phase 3 services", "service": "infra", "language": "yaml", "deps": ["P3-030", "P0-024"], "phase": 3, "group": "3.4"},
    {"id": "P3-036", "title": "Add end-to-end smoke test: dashboard loads, map renders, NPC inspector shows data", "service": "multi", "language": "typescript", "deps": ["P3-021", "P3-022", "P3-030"], "phase": 3, "group": "3.4"},
]

# ---------------------------------------------------------------------------
# Phase 4 — Observability, Security, Performance (P4-001 to P4-028)
# ---------------------------------------------------------------------------
# Group 4.1 — OpenTelemetry deep instrumentation
stories += [
    {"id": "P4-001", "title": "Add distributed trace propagation across all Kafka message boundaries", "service": "multi", "language": "multi", "deps": ["P1-012", "P1-023", "P1-031"], "phase": 4, "group": "4.1"},
    {"id": "P4-002", "title": "Add custom OTel span attributes: NPC ID, tick number, service version", "service": "multi", "language": "multi", "deps": ["P4-001"], "phase": 4, "group": "4.1"},
    {"id": "P4-003", "title": "Add OTel SDK to tavern (TypeScript) and cartographer (TypeScript)", "service": "multi", "language": "typescript", "deps": ["P2-017", "P2-025"], "phase": 4, "group": "4.1"},
    {"id": "P4-004", "title": "Add OTel SDK to academy (Python) and library (Python)", "service": "multi", "language": "python", "deps": ["P2-009", "P3-008"], "phase": 4, "group": "4.1"},
    {"id": "P4-005", "title": "Add OTel SDK to asset-pipeline (Python) with job trace context", "service": "asset-pipeline", "language": "python", "deps": ["P3-017"], "phase": 4, "group": "4.1"},
    {"id": "P4-006", "title": "Configure Tempo trace backend and Grafana Tempo datasource", "service": "infra", "language": "yaml", "deps": ["P0-028"], "phase": 4, "group": "4.1"},
    {"id": "P4-007", "title": "Add Grafana dashboard: distributed trace heatmap and service dependency graph", "service": "infra", "language": "yaml", "deps": ["P4-006"], "phase": 4, "group": "4.1"},
]

# Group 4.2 — Security hardening
stories += [
    {"id": "P4-008", "title": "Add JWT authentication middleware to all HTTP-facing services", "service": "multi", "language": "multi", "deps": ["P1-004", "P1-018", "P2-005", "P2-013"], "phase": 4, "group": "4.2"},
    {"id": "P4-009", "title": "Add RBAC: admin role for tick control and world reset; viewer role for reads", "service": "town-core", "language": "python", "deps": ["P4-008"], "phase": 4, "group": "4.2"},
    {"id": "P4-010", "title": "Add rate limiting to all public POST endpoints (token bucket via Redis)", "service": "multi", "language": "multi", "deps": ["P4-008"], "phase": 4, "group": "4.2"},
    {"id": "P4-011", "title": "Add input validation with Pydantic v2 strict mode on all Python services", "service": "multi", "language": "python", "deps": ["P1-004", "P2-005", "P3-004"], "phase": 4, "group": "4.2"},
    {"id": "P4-012", "title": "Add Dependabot config for all package ecosystems (pip, go, npm, cargo)", "service": "infra", "language": "yaml", "deps": ["P0-005"], "phase": 4, "group": "4.2"},
    {"id": "P4-013", "title": "Add container image scanning with Trivy in CI pipeline", "service": "infra", "language": "yaml", "deps": ["P0-006"], "phase": 4, "group": "4.2"},
    {"id": "P4-014", "title": "Add mTLS via Linkerd for all gRPC connections between services", "service": "infra", "language": "yaml", "deps": ["P0-025", "P1-019", "P1-029", "P2-006"], "phase": 4, "group": "4.2"},
]

# Group 4.3 — Performance benchmarks
stories += [
    {"id": "P4-015", "title": "Add Rust criterion benchmark suite for fortress guard scheduler", "service": "fortress", "language": "rust", "deps": ["P1-026"], "phase": 4, "group": "4.3"},
    {"id": "P4-016", "title": "Add Go benchmark suite for market-district pricing engine", "service": "market-district", "language": "go", "deps": ["P1-017"], "phase": 4, "group": "4.3"},
    {"id": "P4-017", "title": "Add k6 load test: 1000 concurrent tick requests to town-core", "service": "town-core", "language": "typescript", "deps": ["P1-005"], "phase": 4, "group": "4.3"},
    {"id": "P4-018", "title": "Add k6 load test: 500 concurrent price queries to market-district", "service": "market-district", "language": "typescript", "deps": ["P1-018"], "phase": 4, "group": "4.3"},
    {"id": "P4-019", "title": "Add library embedding throughput benchmark: target 100 embeds/sec", "service": "library", "language": "python", "deps": ["P3-007"], "phase": 4, "group": "4.3"},
    {"id": "P4-020", "title": "Add Grafana dashboard: p50/p95/p99 latency per service from k6 results", "service": "infra", "language": "yaml", "deps": ["P4-017", "P4-018", "P0-028"], "phase": 4, "group": "4.3"},
]

# Group 4.4 — Advanced infra
stories += [
    {"id": "P4-021", "title": "Add chaos engineering script: kill random service pod and verify recovery", "service": "infra", "language": "shell", "deps": ["P3-030"], "phase": 4, "group": "4.4"},
    {"id": "P4-022", "title": "Add PostgreSQL connection pooling via PgBouncer sidecar", "service": "infra", "language": "yaml", "deps": ["P1-037", "P2-027", "P3-030"], "phase": 4, "group": "4.4"},
    {"id": "P4-023", "title": "Add Redis Sentinel config for high-availability Redis", "service": "infra", "language": "yaml", "deps": ["P0-023"], "phase": 4, "group": "4.4"},
    {"id": "P4-024", "title": "Add Kafka topic retention and compaction policy config", "service": "infra", "language": "yaml", "deps": ["P0-019"], "phase": 4, "group": "4.4"},
    {"id": "P4-025", "title": "Add Terraform workspace for production environment", "service": "infra", "language": "hcl", "deps": ["P0-021"], "phase": 4, "group": "4.4"},
    {"id": "P4-026", "title": "Add GitHub Actions CD workflow: deploy to staging on merge to main", "service": "infra", "language": "yaml", "deps": ["P0-006"], "phase": 4, "group": "4.4"},
    {"id": "P4-027", "title": "Add SLI/SLO definitions: 99.5% uptime, p95 tick latency < 200ms", "service": "infra", "language": "yaml", "deps": ["P4-020"], "phase": 4, "group": "4.4"},
    {"id": "P4-028", "title": "Add runbooks: service-down recovery, Kafka consumer lag, OOM kill", "service": "infra", "language": "shell", "deps": ["P4-027"], "phase": 4, "group": "4.4"},
]

# ---------------------------------------------------------------------------
# Phase 5 — Polish, Docs, Demo (P5-001 to P5-020)
# ---------------------------------------------------------------------------
# Group 5.1 — Documentation
stories += [
    {"id": "P5-001", "title": "Write root README.md: architecture diagram, quickstart, service table", "service": "infra", "language": "shell", "deps": ["P4-026"], "phase": 5, "group": "5.1"},
    {"id": "P5-002", "title": "Write docs/adr/001-go-for-market-district.md", "service": "infra", "language": "shell", "deps": ["P1-016"], "phase": 5, "group": "5.1"},
    {"id": "P5-003", "title": "Write docs/adr/002-rust-for-fortress.md", "service": "infra", "language": "shell", "deps": ["P1-025"], "phase": 5, "group": "5.1"},
    {"id": "P5-004", "title": "Write docs/adr/003-pgvector-over-dedicated-vectordb.md", "service": "infra", "language": "shell", "deps": ["P3-003"], "phase": 5, "group": "5.1"},
    {"id": "P5-005", "title": "Write docs/adr/004-kafka-for-event-bus.md", "service": "infra", "language": "shell", "deps": ["P1-015"], "phase": 5, "group": "5.1"},
    {"id": "P5-006", "title": "Write docs/adr/005-grpc-internal-rest-external.md", "service": "infra", "language": "shell", "deps": ["P1-019"], "phase": 5, "group": "5.1"},
    {"id": "P5-007", "title": "Write per-service README.md for all 9 services and dashboard", "service": "multi", "language": "shell", "deps": ["P5-001"], "phase": 5, "group": "5.1"},
    {"id": "P5-008", "title": "Write docs/architecture.md: C4 diagrams, data flows, technology choices", "service": "infra", "language": "shell", "deps": ["P5-001"], "phase": 5, "group": "5.1"},
]

# Group 5.2 — Demo and polish
stories += [
    {"id": "P5-009", "title": "Add scripts/seed.sh: populate world with 50 NPCs, 20 buildings, starter economy", "service": "infra", "language": "shell", "deps": ["P1-002"], "phase": 5, "group": "5.2"},
    {"id": "P5-010", "title": "Add scripts/setup.sh: one-command dev environment setup", "service": "infra", "language": "shell", "deps": ["P0-004"], "phase": 5, "group": "5.2"},
    {"id": "P5-011", "title": "Add demo walkthrough script: automated tick sequence with narration output", "service": "infra", "language": "python", "deps": ["P5-009"], "phase": 5, "group": "5.2"},
    {"id": "P5-012", "title": "Add dashboard loading screen and animated NPC sprite intro sequence", "service": "dashboard", "language": "vue", "deps": ["P3-021"], "phase": 5, "group": "5.2"},
    {"id": "P5-013", "title": "Add dashboard dark mode toggle with Tailwind dark: class support", "service": "dashboard", "language": "vue", "deps": ["P3-020"], "phase": 5, "group": "5.2"},
    {"id": "P5-014", "title": "Add dashboard mobile responsive layout for map and market pages", "service": "dashboard", "language": "vue", "deps": ["P3-020"], "phase": 5, "group": "5.2"},
]

# Group 5.3 — Final quality gates
stories += [
    {"id": "P5-015", "title": "Run full test suite across all services and fix any regressions", "service": "multi", "language": "multi", "deps": ["P5-009"], "phase": 5, "group": "5.3"},
    {"id": "P5-016", "title": "Run buf lint and ensure proto/ has no breaking changes", "service": "proto", "language": "protobuf", "deps": ["P5-015"], "phase": 5, "group": "5.3"},
    {"id": "P5-017", "title": "Run cargo clippy --all with zero warnings on fortress", "service": "fortress", "language": "rust", "deps": ["P5-015"], "phase": 5, "group": "5.3"},
    {"id": "P5-018", "title": "Run go vet ./... with zero errors on market-district", "service": "market-district", "language": "go", "deps": ["P5-015"], "phase": 5, "group": "5.3"},
    {"id": "P5-019", "title": "Run ruff check on all Python services with zero violations", "service": "multi", "language": "python", "deps": ["P5-015"], "phase": 5, "group": "5.3"},
    {"id": "P5-020", "title": "Tag v2.0.0 release: update CHANGELOG.md, create GitHub release with artifact links", "service": "infra", "language": "shell", "deps": ["P5-015", "P5-016", "P5-017", "P5-018", "P5-019"], "phase": 5, "group": "5.3"},
]

# ---------------------------------------------------------------------------
# Validate count
# ---------------------------------------------------------------------------
assert len(stories) == 194, f"Expected 194 stories, got {len(stories)}"

# Build final JSON with status=complete for all stories
worklist = {
    "version": "2.0",
    "project": "qtown-v2",
    "stories": [
        {
            "id": s["id"],
            "title": s["title"],
            "service": s["service"],
            "language": s["language"],
            "deps": s["deps"],
            "status": "complete",
            "phase": s["phase"],
            "group": s["group"],
        }
        for s in stories
    ],
}

output_path = Path("/home/user/workspace/qtown/ralph/worklist.json")
output_path.write_text(json.dumps(worklist, indent=2), encoding="utf-8")
print(f"Written {len(stories)} stories to {output_path}")

# Validate phase counts
from collections import Counter
phase_counts = Counter(s["phase"] for s in stories)
print("Phase counts:", dict(sorted(phase_counts.items())))
print("Total:", sum(phase_counts.values()))
