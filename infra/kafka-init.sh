#!/bin/bash
# ────────────────────────────────────────────────────────
# Qtown v2 — Kafka Topic Initialization
# ────────────────────────────────────────────────────────
# Usage: ./infra/kafka-init.sh
#
# Creates all Kafka topics with correct partition counts.
# Idempotent — safe to run multiple times.
# Requires: Kafka broker running on localhost:9092

set -euo pipefail

BROKER="${KAFKA_BROKERS:-localhost:9092}"
KAFKA_BIN="${KAFKA_BIN:-/opt/kafka/bin}"

# Use kafka-topics.sh if available, otherwise try docker exec
create_topic() {
    local topic=$1
    local partitions=$2
    local config="${3:-}"

    echo "  Creating topic: $topic (partitions=$partitions)"

    if command -v kafka-topics.sh &>/dev/null; then
        kafka-topics.sh --bootstrap-server "$BROKER" \
            --create --if-not-exists \
            --topic "$topic" \
            --partitions "$partitions" \
            --replication-factor 1 \
            ${config:+--config "$config"}
    elif docker ps --filter name=qtown-kafka --format '{{.Names}}' | grep -q qtown-kafka; then
        docker exec qtown-kafka /opt/kafka/bin/kafka-topics.sh \
            --bootstrap-server localhost:9092 \
            --create --if-not-exists \
            --topic "$topic" \
            --partitions "$partitions" \
            --replication-factor 1 \
            ${config:+--config "$config"}
    else
        echo "  ERROR: No kafka-topics.sh found and no qtown-kafka container running"
        exit 1
    fi
}

echo "═══════════════════════════════════════════════"
echo " Qtown v2 — Kafka Topic Init"
echo " Broker: $BROKER"
echo "═══════════════════════════════════════════════"

# ─── NPC Travel Topics ───
# Partitioned by npc_id for ordering guarantee per NPC
create_topic "qtown.npc.travel"          6
create_topic "qtown.npc.travel.complete" 6
create_topic "qtown.npc.travel.failed"   3

# ─── Economy Topics ───
# Higher partition count for trade volume
create_topic "qtown.economy.trade"          12
create_topic "qtown.economy.trade.settled"  12
create_topic "qtown.economy.price.update"   6

# ─── Events Topics ───
# Broadcast events from the tick loop
create_topic "qtown.events.broadcast" 6

# ─── Validation Topics ───
# Fortress validates events
create_topic "qtown.validation.request" 6
create_topic "qtown.validation.result"  6

# ─── AI Topics ───
# Academy generates content
create_topic "qtown.ai.request"              6
create_topic "qtown.ai.response"             6
create_topic "qtown.ai.content.generated"    3

echo ""
echo "All topics created successfully."
echo ""

# List all topics for verification
echo "─── Current Topics ───"
if command -v kafka-topics.sh &>/dev/null; then
    kafka-topics.sh --bootstrap-server "$BROKER" --list | grep qtown
elif docker ps --filter name=qtown-kafka --format '{{.Names}}' | grep -q qtown-kafka; then
    docker exec qtown-kafka /opt/kafka/bin/kafka-topics.sh \
        --bootstrap-server localhost:9092 --list | grep qtown
fi
