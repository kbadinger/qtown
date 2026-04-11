//! Criterion benchmarks for the Fortress validation engine.
//!
//! Targets:
//!   * `validate_batch_100k` — measures sustained throughput for 100 000 events
//!     processed through the full 3-rule pipeline using Rayon parallelism.
//!   * `validate_single` — measures per-event latency for a single call to
//!     `validate_one`, useful for tail-latency analysis.
//!
//! Run with:
//!   cargo bench --bench validation
//!
//! HTML reports are emitted to `target/criterion/`.

use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};
use fortress::{
    types::TownEvent,
    validation::{
        rules::{GoldOverflowRule, NegativeBalanceRule, TradeVolumeRule},
        ValidationEngine,
    },
};
use serde_json::json;

// ─── Helpers ─────────────────────────────────────────────────────────────────

/// Builds a ValidationEngine wired with the three production rules.
fn build_engine() -> ValidationEngine {
    ValidationEngine::new()
        .with_rule(GoldOverflowRule::default())
        .with_rule(NegativeBalanceRule)
        .with_rule(TradeVolumeRule::default())
}

/// Generates `n` synthetic TownEvents with varied amounts to exercise
/// both the passing and failing branches of each rule.
fn generate_events(n: usize) -> Vec<TownEvent> {
    (0..n)
        .map(|i| {
            let amount = match i % 5 {
                0 => 100.0,             // small valid trade
                1 => 5_000.0,           // mid-range valid trade
                2 => 9_999.99,          // just under GoldOverflowRule cap
                3 => 10_001.0,          // triggers GoldOverflowRule (invalid)
                _ => 200.0,             // default valid
            };
            TownEvent {
                event_type: "trade".to_string(),
                npc_id: (i as i64) % 1_000, // 1000 distinct NPC IDs
                amount,
                resource: Some("gold".to_string()),
                metadata: Some(json!({ "seq": i, "region": "qtown-v2" })),
            }
        })
        .collect()
}

// ─── Benchmarks ──────────────────────────────────────────────────────────────

/// Measures validate_batch throughput at 100 000 events per iteration.
///
/// This is the primary benchmark for the 100K events/sec design target.
/// Rayon's thread pool is reused across iterations; cold-start costs are not
/// included in the measured time.
fn bench_validate_batch(c: &mut Criterion) {
    const BATCH_SIZE: usize = 100_000;

    let engine = build_engine();
    let events = generate_events(BATCH_SIZE);

    let mut group = c.benchmark_group("validate_batch");
    group.throughput(Throughput::Elements(BATCH_SIZE as u64));
    group.sample_size(20); // fewer samples — each iteration is ~100 ms

    group.bench_with_input(
        BenchmarkId::new("rayon_parallel", BATCH_SIZE),
        &events,
        |b, evts| {
            b.iter(|| {
                let results = engine.validate_batch(black_box(evts));
                // black_box prevents the compiler from eliding the work.
                black_box(results)
            });
        },
    );

    group.finish();
}

/// Measures single-event validation latency.
///
/// Useful for understanding the per-event cost on the gRPC synchronous path
/// and for catching rule-level regressions.
fn bench_validate_single(c: &mut Criterion) {
    let engine = build_engine();

    // A representative "happy path" event — should pass all rules.
    let happy_event = TownEvent {
        event_type: "trade".to_string(),
        npc_id: 1,
        amount: 500.0,
        resource: Some("gold".to_string()),
        metadata: None,
    };

    // An event that fails GoldOverflowRule — exercises the rejection branch.
    let overflow_event = TownEvent {
        event_type: "trade".to_string(),
        npc_id: 2,
        amount: 99_999.0,
        resource: Some("gold".to_string()),
        metadata: None,
    };

    let mut group = c.benchmark_group("validate_single");
    group.throughput(Throughput::Elements(1));

    group.bench_function("happy_path", |b| {
        b.iter(|| {
            let results = engine.validate_one(black_box(&happy_event));
            black_box(results)
        });
    });

    group.bench_function("overflow_rejection", |b| {
        b.iter(|| {
            let results = engine.validate_one(black_box(&overflow_event));
            black_box(results)
        });
    });

    group.finish();
}

/// Parametric benchmark that sweeps batch sizes to characterise how
/// throughput scales with Rayon's work-stealing scheduler.
fn bench_batch_scaling(c: &mut Criterion) {
    let engine = build_engine();

    let mut group = c.benchmark_group("batch_scaling");

    for &size in &[100_usize, 1_000, 10_000, 100_000] {
        let events = generate_events(size);
        group.throughput(Throughput::Elements(size as u64));
        group.bench_with_input(BenchmarkId::from_parameter(size), &events, |b, evts| {
            b.iter(|| black_box(engine.validate_batch(black_box(evts))));
        });
    }

    group.finish();
}

// ─────────────────────────────────────────────────────────────────────────────

criterion_group!(
    benches,
    bench_validate_batch,
    bench_validate_single,
    bench_batch_scaling
);
criterion_main!(benches);
