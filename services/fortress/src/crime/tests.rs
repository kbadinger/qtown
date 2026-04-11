//! Integration tests for the crime economy module.

use crate::crime::black_market::{BlackMarket, CrimeError, OrderStatus};
use crate::crime::investigation::{CrimeType, Evidence, EvidenceType, InvestigationEngine};
use crate::crime::trial::{SentenceType, TrialEngine, Verdict};

// ─── Black Market ─────────────────────────────────────────────────────────────

#[test]
fn test_black_market_order() {
    let bm = BlackMarket::new();

    let order = bm
        .place_order("npc-thief-1", "stolen_goods", 5)
        .expect("order should succeed");

    assert_eq!(order.buyer_id, "npc-thief-1");
    assert_eq!(order.item, "stolen_goods");
    assert_eq!(order.quantity, 5);
    assert!(order.total_price > 0.0);
    assert_eq!(order.status, OrderStatus::Pending);

    bm.fulfill_order(&order.id).expect("fulfillment should succeed");

    let updated = bm.get_order(&order.id).unwrap();
    assert_eq!(updated.status, OrderStatus::Fulfilled);
}

#[test]
fn test_black_market_order_already_fulfilled() {
    let bm = BlackMarket::new();
    let order = bm.place_order("buyer-1", "stolen_goods", 1).unwrap();
    bm.fulfill_order(&order.id).unwrap();

    let result = bm.fulfill_order(&order.id);
    assert_eq!(result, Err(CrimeError::AlreadyFulfilled));
}

#[test]
fn test_black_market_unknown_item() {
    let bm = BlackMarket::new();
    let result = bm.place_order("buyer-1", "dragon_egg", 1);
    assert!(matches!(result, Err(CrimeError::ItemNotFound(_))));
}

#[test]
fn test_black_market_zero_quantity() {
    let bm = BlackMarket::new();
    let result = bm.place_order("buyer-1", "stolen_goods", 0);
    assert_eq!(result, Err(CrimeError::InvalidQuantity));
}

#[test]
fn test_black_market_pricing() {
    let bm = BlackMarket::new();
    let catalog = bm.list_contraband();

    for item in &catalog {
        // Every item must be priced at ≥2× base (minimum markup in spec).
        let sale = item.sale_price();
        let min_expected = item.base_price * 2.0;
        let max_expected = item.base_price * 5.0;
        assert!(
            sale >= min_expected,
            "item '{}' price {} is below 2× base {}",
            item.name,
            sale,
            min_expected
        );
        assert!(
            sale <= max_expected,
            "item '{}' price {} is above 5× base {}",
            item.name,
            sale,
            max_expected
        );
    }
}

#[test]
fn test_black_market_volume_tracking() {
    let bm = BlackMarket::new();

    assert_eq!(bm.total_volume(), 0.0);

    let o1 = bm.place_order("buyer-1", "stolen_goods", 2).unwrap();
    let o2 = bm.place_order("buyer-2", "smuggled_resources", 3).unwrap();
    bm.fulfill_order(&o1.id).unwrap();
    bm.fulfill_order(&o2.id).unwrap();

    let expected = o1.total_price + o2.total_price;
    assert!(
        (bm.total_volume() - expected).abs() < 1e-9,
        "volume mismatch: expected {}, got {}",
        expected,
        bm.total_volume()
    );
}

// ─── Investigation ────────────────────────────────────────────────────────────

#[test]
fn test_investigation_evidence() {
    let mut engine = InvestigationEngine::new();
    let case = engine.open_case(
        "suspect-42",
        CrimeType::Theft,
        vec![Evidence::new(EvidenceType::Witness, 0.6, "eyewitness account")],
    );

    assert!(!case.evidence.is_empty());
    assert!(case.guilt_probability > 0.0);
    assert!(case.guilt_probability <= 1.0);

    let p = engine.calculate_guilt_probability(&case);
    assert!((p - case.guilt_probability).abs() < 1e-9);
}

#[test]
fn test_guilt_probability_increases_with_evidence() {
    let mut engine = InvestigationEngine::new();
    let case = engine.open_case(
        "suspect-7",
        CrimeType::Fraud,
        vec![Evidence::new(EvidenceType::Financial, 0.3, "minor discrepancy")],
    );

    let initial_prob = case.guilt_probability;

    // Add strong evidence.
    let new_prob = engine
        .add_evidence(
            &case.id,
            Evidence::new(EvidenceType::Confession, 0.95, "written confession"),
        )
        .unwrap();

    assert!(
        new_prob > initial_prob,
        "guilt probability should increase with strong evidence: {} → {}",
        initial_prob,
        new_prob
    );
}

#[test]
fn test_investigation_stages() {
    let mut engine = InvestigationEngine::new();
    let case = engine.open_case("suspect-9", CrimeType::Smuggling, vec![]);

    let r1 = engine.investigate(&case.id).unwrap();
    assert_eq!(
        r1.stage,
        crate::crime::investigation::InvestigationStage::Investigating
    );

    let r2 = engine.investigate(&case.id).unwrap();
    assert_eq!(
        r2.stage,
        crate::crime::investigation::InvestigationStage::EvidenceGathered
    );

    let r3 = engine.investigate(&case.id).unwrap();
    assert_eq!(
        r3.stage,
        crate::crime::investigation::InvestigationStage::TrialReady
    );
}

// ─── Trial ────────────────────────────────────────────────────────────────────

fn build_guilty_case() -> crate::crime::investigation::Case {
    crate::crime::investigation::Case {
        id: "case-guilty".to_string(),
        suspect_id: "villain-1".to_string(),
        crime_type: CrimeType::Theft,
        evidence: vec![
            Evidence::new(EvidenceType::Confession, 0.95, "confession obtained"),
            Evidence::new(EvidenceType::Physical, 0.90, "stolen goods in possession"),
            Evidence::new(EvidenceType::Witness, 0.80, "multiple witnesses"),
        ],
        stage: crate::crime::investigation::InvestigationStage::TrialReady,
        opened_at_tick: 0,
        // Pre-set to a high value matching the evidence above.
        guilt_probability: 0.85,
    }
}

fn build_innocent_case() -> crate::crime::investigation::Case {
    crate::crime::investigation::Case {
        id: "case-innocent".to_string(),
        suspect_id: "innocent-npc".to_string(),
        crime_type: CrimeType::Theft,
        evidence: vec![Evidence::new(
            EvidenceType::Witness,
            0.1,
            "unreliable rumour",
        )],
        stage: crate::crime::investigation::InvestigationStage::Open,
        opened_at_tick: 0,
        guilt_probability: 0.05,
    }
}

#[test]
fn test_trial_guilty_verdict() {
    let engine = TrialEngine::new();
    let case = build_guilty_case();

    let mut trial = engine.begin_trial(&case);
    let verdict = engine.render_verdict(&mut trial).unwrap();

    assert_eq!(verdict, Verdict::Guilty, "high evidence should yield GUILTY");

    let sentence = engine.impose_sentence(&mut trial, &case.crime_type);
    assert!(trial.sentence.is_some());
    // Theft → community service.
    assert_eq!(sentence.sentence_type, SentenceType::CommunityService);
    assert!(sentence.duration_ticks > 0);
}

#[test]
fn test_trial_acquittal() {
    let engine = TrialEngine::new();
    let case = build_innocent_case();

    let mut trial = engine.begin_trial(&case);
    let verdict = engine.render_verdict(&mut trial).unwrap();

    assert_eq!(
        verdict,
        Verdict::NotGuilty,
        "low evidence should yield NOT_GUILTY"
    );
    assert!(trial.sentence.is_none());
}

#[test]
fn test_trial_insufficient_evidence() {
    let engine = TrialEngine::new();
    let case = crate::crime::investigation::Case {
        id: "case-unclear".to_string(),
        suspect_id: "grey-npc".to_string(),
        crime_type: CrimeType::Fraud,
        evidence: vec![
            Evidence::new(EvidenceType::Witness, 0.5, "conflicting accounts"),
            Evidence::new(EvidenceType::Financial, 0.4, "some discrepancy"),
        ],
        stage: crate::crime::investigation::InvestigationStage::EvidenceGathered,
        opened_at_tick: 0,
        guilt_probability: 0.45,
    };

    let mut trial = engine.begin_trial(&case);
    let verdict = engine.render_verdict(&mut trial).unwrap();

    assert_eq!(verdict, Verdict::InsufficientEvidence);
}

#[test]
fn test_trial_already_verdicted() {
    let engine = TrialEngine::new();
    let case = build_guilty_case();
    let mut trial = engine.begin_trial(&case);

    engine.render_verdict(&mut trial).unwrap();
    let result = engine.render_verdict(&mut trial);
    assert_eq!(result, Err(crate::crime::trial::TrialError::AlreadyVerdicted));
}

#[test]
fn test_smuggling_sentence_is_exile() {
    let engine = TrialEngine::new();
    let case = crate::crime::investigation::Case {
        id: "case-smuggler".to_string(),
        suspect_id: "smuggler-5".to_string(),
        crime_type: CrimeType::Smuggling,
        evidence: vec![
            Evidence::new(EvidenceType::Physical, 0.9, "contraband found"),
            Evidence::new(EvidenceType::Witness, 0.8, "border guard testimony"),
        ],
        stage: crate::crime::investigation::InvestigationStage::TrialReady,
        opened_at_tick: 0,
        guilt_probability: 0.80,
    };
    let mut trial = engine.begin_trial(&case);
    engine.render_verdict(&mut trial).unwrap();
    let sentence = engine.impose_sentence(&mut trial, &case.crime_type);
    assert_eq!(sentence.sentence_type, SentenceType::Exile);
    assert!(sentence.duration_ticks > 0);
}

#[test]
fn test_tax_evasion_sentence_is_fine() {
    let engine = TrialEngine::new();
    let case = crate::crime::investigation::Case {
        id: "case-tax".to_string(),
        suspect_id: "merchant-rich".to_string(),
        crime_type: CrimeType::TaxEvasion,
        evidence: vec![
            Evidence::new(EvidenceType::Financial, 0.9, "hidden ledger"),
            Evidence::new(EvidenceType::Financial, 0.85, "offshore gold"),
        ],
        stage: crate::crime::investigation::InvestigationStage::TrialReady,
        opened_at_tick: 0,
        guilt_probability: 0.85,
    };
    let mut trial = engine.begin_trial(&case);
    engine.render_verdict(&mut trial).unwrap();
    let sentence = engine.impose_sentence(&mut trial, &case.crime_type);
    assert_eq!(sentence.sentence_type, SentenceType::Fine);
    assert!(sentence.magnitude > 0.0);
}

// ─── Cold Case ────────────────────────────────────────────────────────────────

#[test]
fn test_cold_case_closure() {
    let mut engine = InvestigationEngine::new();

    // Open a case with very weak evidence at tick 0.
    let case = engine.open_case_at_tick(
        "suspect-cold",
        CrimeType::Theft,
        vec![Evidence::new(EvidenceType::Witness, 0.05, "vague rumour")],
        0,
    );

    // Guilt probability should be well below 0.2.
    assert!(
        case.guilt_probability < 0.2,
        "guilt_probability should be < 0.2 for cold-case test, got {}",
        case.guilt_probability
    );

    // Advance to tick 100 — should trigger auto-closure.
    engine.tick(100);

    let updated = engine.get_case(&case.id).unwrap();
    assert_eq!(
        updated.stage,
        crate::crime::investigation::InvestigationStage::Closed,
        "case should be closed as cold case after 100 ticks with low guilt probability"
    );
}

#[test]
fn test_case_not_closed_if_guilt_high() {
    let mut engine = InvestigationEngine::new();

    let case = engine.open_case_at_tick(
        "suspect-hot",
        CrimeType::Fraud,
        vec![
            Evidence::new(EvidenceType::Confession, 0.9, "full confession"),
            Evidence::new(EvidenceType::Financial, 0.85, "clear paper trail"),
        ],
        0,
    );

    assert!(
        case.guilt_probability >= 0.2,
        "guilt_probability should be ≥ 0.2, got {}",
        case.guilt_probability
    );

    engine.tick(200);

    let updated = engine.get_case(&case.id).unwrap();
    assert_ne!(
        updated.stage,
        crate::crime::investigation::InvestigationStage::Closed,
        "high-guilt case should not be closed as cold case"
    );
}
