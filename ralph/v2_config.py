"""Ralph v2 configuration."""

import os
from pathlib import Path

# ─── Paths ───
PROJECT_ROOT = Path(__file__).parent.parent
WORKLIST_PATH = Path(__file__).parent / "worklist.json"
SERVICES_DIR = PROJECT_ROOT / "services"
PROTO_DIR = PROJECT_ROOT / "proto"
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
INFRA_DIR = PROJECT_ROOT / "infra"

# ─── Ollama ───
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
PRIMARY_MODEL = os.getenv("RALPH_PRIMARY_MODEL", "qwen3-coder-next")
HEAVY_MODEL = os.getenv("RALPH_HEAVY_MODEL", "qwen3.5:27b")
CONTENT_MODEL = os.getenv("RALPH_CONTENT_MODEL", "qwen3.5:35b-a3b")
DEBUG_MODEL = os.getenv("RALPH_DEBUG_MODEL", "deepseek-r1:14b")

# ─── Execution ───
MAX_PARALLEL_WORKERS = int(os.getenv("RALPH_MAX_PARALLEL", "3"))
MAX_ATTEMPTS_PER_STORY = int(os.getenv("RALPH_MAX_ATTEMPTS", "12"))
HELP_WAIT_SECONDS = int(os.getenv("RALPH_HELP_WAIT", "600"))

# ─── Service Config ───
SERVICE_CONFIG = {
    "town-core": {
        "language": "python",
        "test_cmd": "cd services/town-core && python -m pytest tests/ -x",
        "build_cmd": "docker build -t qtown/town-core services/town-core",
        "lint_cmd": "cd services/town-core && ruff check engine/",
        "model": PRIMARY_MODEL,
        "context_globs": ["services/town-core/engine/**/*.py", "proto/qtown/*.proto"],
    },
    "market-district": {
        "language": "go",
        "test_cmd": "cd services/market-district && go test ./... -v -race",
        "build_cmd": "cd services/market-district && go build ./...",
        "lint_cmd": "cd services/market-district && go vet ./...",
        "model": PRIMARY_MODEL,
        "context_globs": ["services/market-district/**/*.go", "proto/qtown/*.proto"],
    },
    "fortress": {
        "language": "rust",
        "test_cmd": "cd services/fortress && cargo test",
        "build_cmd": "cd services/fortress && cargo build",
        "lint_cmd": "cd services/fortress && cargo clippy -- -D warnings",
        "model": PRIMARY_MODEL,
        "context_globs": ["services/fortress/src/**/*.rs", "proto/qtown/*.proto"],
    },
    "academy": {
        "language": "python",
        "test_cmd": "cd services/academy && python -m pytest tests/ -x",
        "build_cmd": "docker build -t qtown/academy services/academy",
        "lint_cmd": "cd services/academy && ruff check .",
        "model": PRIMARY_MODEL,
        "context_globs": ["services/academy/academy/**/*.py", "proto/qtown/*.proto"],
    },
    "tavern": {
        "language": "typescript",
        "test_cmd": "cd services/tavern && npm test",
        "build_cmd": "cd services/tavern && npm run build",
        "lint_cmd": "cd services/tavern && npx tsc --noEmit",
        "model": PRIMARY_MODEL,
        "context_globs": ["services/tavern/src/**/*.ts"],
    },
    "cartographer": {
        "language": "typescript",
        "test_cmd": "cd services/cartographer && npm test",
        "build_cmd": "cd services/cartographer && npm run build",
        "lint_cmd": "cd services/cartographer && npx tsc --noEmit",
        "model": PRIMARY_MODEL,
        "context_globs": ["services/cartographer/src/**/*.ts"],
    },
    "library": {
        "language": "python",
        "test_cmd": "cd services/library && python -m pytest tests/ -x",
        "build_cmd": "docker build -t qtown/library services/library",
        "lint_cmd": "cd services/library && ruff check .",
        "model": PRIMARY_MODEL,
        "context_globs": ["services/library/library/**/*.py"],
    },
    "dashboard": {
        "language": "typescript",
        "test_cmd": "cd dashboard && npm test",
        "build_cmd": "cd dashboard && npx nuxt build",
        "lint_cmd": "cd dashboard && npx tsc --noEmit || npx nuxi typecheck",
        "model": PRIMARY_MODEL,
        "context_globs": ["dashboard/pages/**/*.vue", "dashboard/components/**/*.vue", "dashboard/composables/**/*.ts"],
    },
    "asset-pipeline": {
        "language": "python",
        "test_cmd": "cd services/asset-pipeline && python -m pytest tests/ -x || true",
        "build_cmd": "docker build -t qtown/asset-pipeline services/asset-pipeline",
        "lint_cmd": "cd services/asset-pipeline && ruff check . || true",
        "model": PRIMARY_MODEL,
        "context_globs": ["services/asset-pipeline/**/*.py"],
    },
    "proto": {
        "language": "protobuf",
        "test_cmd": "cd proto && buf lint",
        "build_cmd": "cd proto && buf generate",
        "lint_cmd": "cd proto && buf lint",
        "model": PRIMARY_MODEL,
        "context_globs": ["proto/qtown/*.proto", "proto/buf.yaml", "proto/buf.gen.yaml"],
    },
}
