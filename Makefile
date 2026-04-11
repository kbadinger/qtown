# ────────────────────────────────────────────────────────────
# Qtown v2 — Polyglot Monorepo Makefile
# ────────────────────────────────────────────────────────────

.PHONY: help deps deps-down proto build test lint \
        build-town-core build-market build-fortress build-tavern \
        build-academy build-cartographer build-library build-dashboard build-asset-pipeline \
        test-town-core test-market test-fortress test-tavern \
        test-academy test-cartographer test-library test-dashboard \
        docker-build docker-up docker-down clean observability

# ─── Help ───
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ─── Infrastructure ───
deps: ## Start infrastructure (Kafka, Postgres, Redis, ES)
	docker compose -f docker-compose.deps.yml up -d

deps-down: ## Stop infrastructure
	docker compose -f docker-compose.deps.yml down

deps-logs: ## Tail infrastructure logs
	docker compose -f docker-compose.deps.yml logs -f

# ─── Proto Generation ───
proto: ## Generate protobuf code for all languages
	cd proto && buf generate
	@echo "Proto generated → gen/go, gen/python, gen/ts"

proto-lint: ## Lint proto files
	cd proto && buf lint

proto-breaking: ## Check proto breaking changes
	cd proto && buf breaking --against '.git#subdir=proto'

# ─── Build (per-service) ───
build-town-core: ## Build Town Core (Python — install deps)
	cd services/town-core && pip install -r requirements.txt

build-market: ## Build Market District (Go)
	cd services/market-district && go build -o bin/market-district ./cmd/server/

build-fortress: ## Build Fortress (Rust)
	cd services/fortress && cargo build --release

build-tavern: ## Build Tavern (Node/TS)
	cd services/tavern && npm install && npm run build

build-academy: ## Build Academy (Python)
	cd services/academy && pip install -e ".[dev]"

build-cartographer: ## Build Cartographer (GraphQL/TS)
	cd services/cartographer && npm install && npm run build

build-library: ## Build Library (Python)
	cd services/library && pip install -e ".[dev]" 2>/dev/null || pip install -r requirements.txt

build-dashboard: ## Build Dashboard (Nuxt 3)
	cd dashboard && npm install && npx nuxt build

build-asset-pipeline: ## Build Asset Pipeline (Python)
	cd services/asset-pipeline && pip install -e ".[dev]" 2>/dev/null || pip install -r requirements.txt

build: build-town-core build-market build-fortress build-tavern build-academy build-cartographer build-library build-dashboard build-asset-pipeline ## Build all services

# ─── Test (per-service) ───
test-town-core: ## Test Town Core
	cd services/town-core && python -m pytest tests/ -v

test-market: ## Test Market District
	cd services/market-district && go test ./... -v

test-fortress: ## Test Fortress
	cd services/fortress && cargo test

test-tavern: ## Test Tavern
	cd services/tavern && npm test

test-academy: ## Test Academy
	cd services/academy && python -m pytest tests/ -v

test-cartographer: ## Test Cartographer
	cd services/cartographer && npm test

test-library: ## Test Library
	cd services/library && python -m pytest tests/ -v

test-dashboard: ## Test Dashboard
	cd dashboard && npm test

test: test-town-core test-market test-fortress test-tavern test-academy test-cartographer test-library test-dashboard ## Test all services

# ─── Lint (per-service) ───
lint-market: ## Lint Market District
	cd services/market-district && golangci-lint run

lint-fortress: ## Lint Fortress
	cd services/fortress && cargo clippy -- -D warnings

lint-tavern: ## Lint Tavern
	cd services/tavern && npm run lint

lint-academy: ## Lint Academy
	cd services/academy && ruff check .

lint-cartographer: ## Lint Cartographer
	cd services/cartographer && npm run lint

lint: lint-market lint-fortress lint-tavern lint-academy lint-cartographer ## Lint all services

# ─── Benchmarks ───
bench-market: ## Benchmark Market District order book
	cd services/market-district && go test -bench BenchmarkOrderBook -benchtime=30s -count=5 ./internal/orderbook/

bench-fortress: ## Benchmark Fortress validation engine
	cd services/fortress && cargo bench -- validation

bench: bench-market bench-fortress ## Run all benchmarks

# ─── Proof Tests ───
proof-market: ## Run Market District proof test
	cd services/market-district && go test -bench BenchmarkOrderBook -count 5 ./internal/orderbook/ | grep -E 'ns/op' && echo "PROOF PASS" || echo "PROOF FAIL"

proof-fortress: ## Run Fortress proof test (zero unsafe)
	cd services/fortress && cargo bench -- validation 2>&1 | grep -E 'time:' && \
		grep -r 'unsafe' src/rules/ src/validation/ | wc -l | xargs -I{} test {} -eq 0 && \
		echo "PROOF PASS" || echo "PROOF FAIL"

proof-academy: ## Run Academy proof test (≥85% local model routing)
	cd services/academy && pytest tests/test_rag.py tests/test_model_router.py -v && \
		curl -sf http://localhost:8001/metrics/model-routing | \
		python -c 'import sys,json; d=json.load(sys.stdin); assert d["local_pct"] >= 85' && \
		echo "PROOF PASS" || echo "PROOF FAIL"

proof: proof-market proof-fortress proof-academy ## Run all proof tests

# ─── Docker ───
docker-build: ## Build all service Docker images
	docker build -t qtown/town-core:dev    services/town-core/
	docker build -t qtown/market-district:dev services/market-district/
	docker build -t qtown/fortress:dev     services/fortress/
	docker build -t qtown/tavern:dev       services/tavern/
	docker build -t qtown/academy:dev      services/academy/
	docker build -t qtown/cartographer:dev services/cartographer/
	docker build -t qtown/library:dev      services/library/
	docker build -t qtown/dashboard:dev    dashboard/
	docker build -t qtown/asset-pipeline:dev services/asset-pipeline/

docker-up: deps ## Start all services + deps
	docker compose up -d

docker-down: ## Stop everything
	docker compose down
	docker compose -f docker-compose.deps.yml down

# ─── Observability ───
observability: ## Start observability stack (Jaeger, Prometheus, Grafana, Loki)
	docker compose -f infra/docker-compose.observability.yml up -d

observability-down: ## Stop observability stack
	docker compose -f infra/docker-compose.observability.yml down

# ─── Helm ───
helm-install: ## Install Qtown to K8s via Helm
	helm upgrade --install qtown infra/helm/qtown --atomic

helm-uninstall: ## Uninstall Qtown from K8s
	helm uninstall qtown

# ─── Terraform ───
tf-plan: ## Terraform plan
	cd infra/terraform && terraform plan

tf-apply: ## Terraform apply
	cd infra/terraform && terraform apply

# ─── Clean ───
clean: ## Clean all build artifacts
	rm -rf gen/
	cd services/market-district && rm -rf bin/
	cd services/fortress && cargo clean
	cd services/tavern && rm -rf dist/ node_modules/
	cd services/academy && rm -rf __pycache__ .ruff_cache .mypy_cache
	cd services/cartographer && rm -rf dist/ node_modules/
	cd services/library && rm -rf __pycache__ .ruff_cache
	cd dashboard && rm -rf .nuxt .output node_modules/
	cd services/asset-pipeline && rm -rf __pycache__
	@echo "Cleaned."
