#!/bin/bash
# Pull all required Ollama models for Ralph v2
set -euo pipefail

echo "Setting up Ollama models for Ralph v2..."

models=(
    "qwen3-coder-next"    # Primary: 80B MoE, 3B active, ~8GB — coding agent
    "qwen3.5:27b"         # Heavy: 27B dense, ~20GB — architecture decisions
    "qwen3.5:35b-a3b"     # Content: 35B MoE, 3B active, ~16GB — NPC dialogue
    "deepseek-r1:14b"     # Debug: 14B dense, ~16GB — reasoning/debugging
    "nomic-embed-text"    # Embeddings: for RAG pipeline
)

for model in "${models[@]}"; do
    echo ""
    echo "Pulling: $model"
    ollama pull "$model"
done

echo ""
echo "All models ready. Run ./v2_start.sh to begin."
