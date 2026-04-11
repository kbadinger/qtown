//! Kafka consumer for the Fortress service.
//!
//! Subscribes to `qtown.validation.request` and validates each inbound event
//! through the `FortressService` validation pipeline, then produces per-rule
//! results back to `qtown.validation.result`.
//!
//! # Topics
//!
//! | Topic                       | Direction | Format              |
//! |-----------------------------|-----------|---------------------|
//! | `qtown.validation.request`  | inbound   | JSON `TownEvent`    |
//! | `qtown.validation.result`   | outbound  | JSON validation bag |
//!
//! # Kafka message key
//!
//! Outbound messages are keyed by `npc_id` (decimal string) so that all
//! results for a given NPC land on the same partition, enabling ordered
//! downstream processing.

use std::sync::Arc;
use std::time::Duration;

use rdkafka::config::ClientConfig;
use rdkafka::consumer::{Consumer, StreamConsumer};
use rdkafka::message::Message;
use rdkafka::producer::{FutureProducer, FutureRecord};
use tracing::{error, info, warn};

use crate::grpc_service::FortressService;
use crate::types::TownEvent;

// ─── Topic / group constants ──────────────────────────────────────────────────

const TOPIC_VALIDATION_REQUEST: &str = "qtown.validation.request";
const TOPIC_VALIDATION_RESULT: &str = "qtown.validation.result";
const GROUP_ID: &str = "fortress";

// ─────────────────────────────────────────────────────────────────────────────

/// Start the Kafka consumer loop.
///
/// This function is designed to run as a long-lived `tokio::spawn` task. It:
///
/// 1. Reads `KAFKA_BROKERS` from the environment (default: `localhost:9092`).
/// 2. Creates an rdkafka `StreamConsumer` subscribed to
///    `qtown.validation.request`.
/// 3. Creates an rdkafka `FutureProducer` to emit results.
/// 4. Enters a `while let` loop that drives the stream until the consumer is
///    dropped (e.g., on process shutdown).
///
/// Deserialization errors are logged and the message is skipped; producer
/// send failures are logged as warnings but do not halt the consumer loop.
pub async fn run_consumer(service: Arc<FortressService>) {
    let brokers = std::env::var("KAFKA_BROKERS")
        .unwrap_or_else(|_| "localhost:9092".to_string());

    // ── Consumer ──────────────────────────────────────────────────────────────
    let consumer: StreamConsumer = match ClientConfig::new()
        .set("group.id", GROUP_ID)
        .set("bootstrap.servers", &brokers)
        .set("auto.offset.reset", "latest")
        .set("enable.auto.commit", "true")
        // Keep session alive while a Rayon batch is running.
        .set("session.timeout.ms", "30000")
        .set("heartbeat.interval.ms", "3000")
        .create()
    {
        Ok(c) => c,
        Err(e) => {
            error!("Failed to create Kafka consumer: {}", e);
            return;
        }
    };

    if let Err(e) = consumer.subscribe(&[TOPIC_VALIDATION_REQUEST]) {
        error!("Failed to subscribe to {}: {}", TOPIC_VALIDATION_REQUEST, e);
        return;
    }

    // ── Producer ──────────────────────────────────────────────────────────────
    let producer: FutureProducer = match ClientConfig::new()
        .set("bootstrap.servers", &brokers)
        .set("message.timeout.ms", "5000")
        // Retry transient send failures up to 3 times.
        .set("retries", "3")
        .create()
    {
        Ok(p) => p,
        Err(e) => {
            error!("Failed to create Kafka producer: {}", e);
            return;
        }
    };

    info!(
        brokers = %brokers,
        topic = TOPIC_VALIDATION_REQUEST,
        "Fortress Kafka consumer started"
    );

    // ── Message loop ──────────────────────────────────────────────────────────
    //
    // `StreamConsumer::stream()` returns an `impl Stream` that yields
    // `KafkaResult<BorrowedMessage>`. We drive it with a `while let` loop
    // using `StreamExt::next()`.

    use futures::StreamExt;
    let mut stream = consumer.stream();

    while let Some(result) = stream.next().await {
        match result {
            Ok(msg) => {
                let payload = match msg.payload() {
                    Some(p) => p,
                    None => {
                        warn!(
                            partition = msg.partition(),
                            offset = msg.offset(),
                            "Received Kafka message with empty payload — skipping"
                        );
                        continue;
                    }
                };

                match serde_json::from_slice::<TownEvent>(payload) {
                    Ok(event) => {
                        // Run validation — returns one result per registered rule.
                        let rule_results = service.validate_event(&event);

                        // Determine overall validity (all rules must pass).
                        let overall_valid = rule_results.iter().all(|r| r.valid);

                        // Collect per-rule details for the result message.
                        let rule_verdicts: Vec<serde_json::Value> = rule_results
                            .iter()
                            .map(|r| {
                                serde_json::json!({
                                    "rule": r.rule_name,
                                    "valid": r.valid,
                                    "message": r.message,
                                })
                            })
                            .collect();

                        let result_json = serde_json::json!({
                            "npc_id":     event.npc_id,
                            "event_type": event.event_type,
                            "valid":      overall_valid,
                            "rules":      rule_verdicts,
                        });

                        let key = event.npc_id.to_string();
                        let payload_str = result_json.to_string();

                        let record = FutureRecord::to(TOPIC_VALIDATION_RESULT)
                            .key(&key)
                            .payload(&payload_str);

                        if let Err((e, _)) =
                            producer.send(record, Duration::from_secs(5)).await
                        {
                            warn!(
                                npc_id = %event.npc_id,
                                error = %e,
                                "Failed to produce validation result"
                            );
                        }
                    }
                    Err(e) => {
                        warn!(
                            partition = msg.partition(),
                            offset = msg.offset(),
                            error = %e,
                            "Failed to deserialize validation request — skipping"
                        );
                    }
                }
            }
            Err(e) => {
                error!("Kafka consumer error: {}", e);
                // Continue the loop — transient broker errors should not
                // terminate the consumer.
            }
        }
    }

    info!("Fortress Kafka consumer stream ended");
}
