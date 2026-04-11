#!/bin/bash
# Ralph v2 — Polyglot AI Developer
# Usage: ./v2_start.sh [--dry-run] [--max-parallel N]

set -euo pipefail
cd "$(dirname "$0")/.."

echo "╔══════════════════════════════════════╗"
echo "║  Ralph v2 — Polyglot AI Developer    ║"
echo "╠══════════════════════════════════════╣"
echo "║  Services: 9 + dashboard             ║"
echo "║  Languages: 12+                      ║"
echo "║  Model: qwen3-coder-next (primary)   ║"
echo "╚══════════════════════════════════════╝"

# Check Ollama
if ! curl -sf http://localhost:11434/api/version > /dev/null 2>&1; then
    echo "ERROR: Ollama not running at localhost:11434"
    echo "Start Ollama first: ollama serve"
    exit 1
fi

# Check required models
for model in qwen3-coder-next qwen3.5:27b deepseek-r1:14b; do
    if ! ollama list | grep -q "$model"; then
        echo "Pulling model: $model"
        ollama pull "$model"
    fi
done

# Check infrastructure
if ! docker compose -f docker-compose.deps.yml ps | grep -q "running"; then
    echo "Starting infrastructure..."
    docker compose -f docker-compose.deps.yml up -d
    sleep 10
fi

# Parse args
DRY_RUN=""
MAX_PARALLEL=3
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN="--dry-run"; shift ;;
        --max-parallel) MAX_PARALLEL="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

export RALPH_MAX_PARALLEL=$MAX_PARALLEL

echo ""
echo "Starting Ralph v2..."
echo "  Max parallel: $MAX_PARALLEL"
echo "  Dry run: ${DRY_RUN:-no}"
echo ""

python -m ralph.v2_orchestrator $DRY_RUN
