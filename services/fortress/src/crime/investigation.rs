//! Criminal investigation system.
//!
//! Cases progress through defined stages as evidence accumulates. Cases
//! with low guilt probability are auto-closed as cold cases after 100 ticks.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Types of crimes that can be investigated.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum CrimeType {
    Theft,
    Fraud,
    Smuggling,
    Assault,
    TaxEvasion,
}

impl std::fmt::Display for CrimeType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let s = match self {
            CrimeType::Theft => "Theft",
            CrimeType::Fraud => "Fraud",
            CrimeType::Smuggling => "Smuggling",
            CrimeType::Assault => "Assault",
            CrimeType::TaxEvasion => "TaxEvasion",
        };
        write!(f, "{}", s)
    }
}

/// Category of a piece of evidence.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum EvidenceType {
    Witness,
    Physical,
    Financial,
    Confession,
}

/// A single piece of evidence in a case.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Evidence {
    /// The kind of evidence.
    pub evidence_type: EvidenceType,
    /// How strongly this evidence points to guilt (0.0 = exculpatory, 1.0 = conclusive).
    pub strength: f64,
    /// Human-readable description for the case record.
    pub description: String,
}

impl Evidence {
    /// Creates new evidence, clamping strength to [0.0, 1.0].
    pub fn new(evidence_type: EvidenceType, strength: f64, description: impl Into<String>) -> Self {
        Self {
            evidence_type,
            strength: strength.clamp(0.0, 1.0),
            description: description.into(),
        }
    }

    /// Weight multiplier by evidence type (confessions carry most weight).
    pub fn type_weight(&self) -> f64 {
        match self.evidence_type {
            EvidenceType::Confession => 1.5,
            EvidenceType::Physical => 1.2,
            EvidenceType::Financial => 1.0,
            EvidenceType::Witness => 0.8,
        }
    }
}

/// Investigation lifecycle stage.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum InvestigationStage {
    Open,
    Investigating,
    EvidenceGathered,
    TrialReady,
    Closed,
}

/// A criminal case tracked by the investigation engine.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Case {
    pub id: String,
    pub suspect_id: String,
    pub crime_type: CrimeType,
    pub evidence: Vec<Evidence>,
    pub stage: InvestigationStage,
    /// Tick at which the case was opened (used for cold-case timeout).
    pub opened_at_tick: i64,
    pub guilt_probability: f64,
}

impl Case {
    /// Computes guilt probability from the weighted sum of evidence strengths,
    /// normalised to [0.0, 1.0].
    pub fn compute_guilt_probability(&self) -> f64 {
        if self.evidence.is_empty() {
            return 0.0;
        }
        let weighted_sum: f64 = self.evidence.iter().map(|e| e.strength * e.type_weight()).sum();
        let max_possible: f64 = self.evidence.len() as f64 * 1.5; // max weight × count
        (weighted_sum / max_possible).clamp(0.0, 1.0)
    }
}

/// Result returned after running an investigation step.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InvestigationResult {
    pub case_id: String,
    /// Evidence synthesised during this investigation step.
    pub new_evidence: Vec<Evidence>,
    pub guilt_probability: f64,
    pub stage: InvestigationStage,
}

/// Errors from the investigation engine.
#[derive(Debug, Clone, PartialEq)]
pub enum InvestigationError {
    CaseNotFound(String),
    CaseClosed(String),
}

impl std::fmt::Display for InvestigationError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            InvestigationError::CaseNotFound(id) => write!(f, "case not found: {}", id),
            InvestigationError::CaseClosed(id) => write!(f, "case is closed: {}", id),
        }
    }
}

/// Manages the lifecycle of criminal investigations.
#[derive(Debug, Default)]
pub struct InvestigationEngine {
    cases: HashMap<String, Case>,
    case_seq: u64,
}

impl InvestigationEngine {
    /// Creates an empty investigation engine.
    pub fn new() -> Self {
        Self::default()
    }

    /// Opens a new case with the given initial evidence set.
    pub fn open_case(
        &mut self,
        suspect_id: &str,
        crime_type: CrimeType,
        evidence: Vec<Evidence>,
    ) -> Case {
        self.case_seq += 1;
        let id = format!("case-{}", self.case_seq);
        let mut case = Case {
            id: id.clone(),
            suspect_id: suspect_id.to_string(),
            crime_type,
            evidence,
            stage: InvestigationStage::Open,
            opened_at_tick: 0,
            guilt_probability: 0.0,
        };
        case.guilt_probability = case.compute_guilt_probability();
        self.cases.insert(id, case.clone());
        case
    }

    /// Advances a case through the investigation pipeline.
    ///
    /// Each call moves the stage forward by one step and synthesises new
    /// circumstantial evidence appropriate to the crime type.
    pub fn investigate(&mut self, case_id: &str) -> Result<InvestigationResult, InvestigationError> {
        let case = self
            .cases
            .get_mut(case_id)
            .ok_or_else(|| InvestigationError::CaseNotFound(case_id.to_string()))?;

        if case.stage == InvestigationStage::Closed {
            return Err(InvestigationError::CaseClosed(case_id.to_string()));
        }

        // Synthesise new evidence based on the crime type.
        let new_evidence = synthesise_evidence(&case.crime_type, &case.stage);
        for e in &new_evidence {
            case.evidence.push(e.clone());
        }

        // Advance stage.
        case.stage = match case.stage {
            InvestigationStage::Open => InvestigationStage::Investigating,
            InvestigationStage::Investigating => InvestigationStage::EvidenceGathered,
            InvestigationStage::EvidenceGathered => InvestigationStage::TrialReady,
            InvestigationStage::TrialReady => InvestigationStage::TrialReady,
            InvestigationStage::Closed => InvestigationStage::Closed,
        };

        case.guilt_probability = case.compute_guilt_probability();

        Ok(InvestigationResult {
            case_id: case_id.to_string(),
            new_evidence,
            guilt_probability: case.guilt_probability,
            stage: case.stage.clone(),
        })
    }

    /// Returns the guilt probability for the given case.
    pub fn calculate_guilt_probability(&self, case: &Case) -> f64 {
        case.compute_guilt_probability()
    }

    /// Returns a snapshot of the case, if it exists.
    pub fn get_case(&self, case_id: &str) -> Option<&Case> {
        self.cases.get(case_id)
    }

    /// Adds external evidence directly to an existing case.
    pub fn add_evidence(
        &mut self,
        case_id: &str,
        evidence: Evidence,
    ) -> Result<f64, InvestigationError> {
        let case = self
            .cases
            .get_mut(case_id)
            .ok_or_else(|| InvestigationError::CaseNotFound(case_id.to_string()))?;

        if case.stage == InvestigationStage::Closed {
            return Err(InvestigationError::CaseClosed(case_id.to_string()));
        }

        case.evidence.push(evidence);
        case.guilt_probability = case.compute_guilt_probability();
        Ok(case.guilt_probability)
    }

    /// Ticks the investigation engine, auto-closing cold cases.
    ///
    /// Cases opened at tick `current_tick - 100` (or earlier) with
    /// guilt_probability < 0.2 are closed as cold cases.
    pub fn tick(&mut self, current_tick: i64) {
        for case in self.cases.values_mut() {
            if case.stage == InvestigationStage::Closed {
                continue;
            }
            let age = current_tick - case.opened_at_tick;
            if age >= 100 && case.guilt_probability < 0.2 {
                case.stage = InvestigationStage::Closed;
            }
        }
    }

    /// Opens a case at a specific tick (for cold-case testing).
    pub fn open_case_at_tick(
        &mut self,
        suspect_id: &str,
        crime_type: CrimeType,
        evidence: Vec<Evidence>,
        tick: i64,
    ) -> Case {
        let mut case = self.open_case(suspect_id, crime_type, evidence);
        case.opened_at_tick = tick;
        if let Some(c) = self.cases.get_mut(&case.id) {
            c.opened_at_tick = tick;
        }
        case
    }
}

/// Generates crime-appropriate circumstantial evidence for an investigation step.
fn synthesise_evidence(crime_type: &CrimeType, stage: &InvestigationStage) -> Vec<Evidence> {
    match stage {
        InvestigationStage::Open => match crime_type {
            CrimeType::Theft => vec![Evidence::new(
                EvidenceType::Witness,
                0.3,
                "Neighbour reported seeing suspect near scene",
            )],
            CrimeType::Fraud => vec![Evidence::new(
                EvidenceType::Financial,
                0.35,
                "Ledger discrepancy identified by city accountant",
            )],
            CrimeType::Smuggling => vec![Evidence::new(
                EvidenceType::Physical,
                0.4,
                "Unauthorised goods found near city gate",
            )],
            CrimeType::Assault => vec![Evidence::new(
                EvidenceType::Witness,
                0.5,
                "Victim identified suspect to guard captain",
            )],
            CrimeType::TaxEvasion => vec![Evidence::new(
                EvidenceType::Financial,
                0.4,
                "Missing tax records for three seasons",
            )],
        },
        InvestigationStage::Investigating => match crime_type {
            CrimeType::Theft => vec![Evidence::new(
                EvidenceType::Physical,
                0.45,
                "Stolen items found in suspect's residence",
            )],
            CrimeType::Fraud => vec![Evidence::new(
                EvidenceType::Financial,
                0.5,
                "Forged merchant seal discovered",
            )],
            CrimeType::Smuggling => vec![Evidence::new(
                EvidenceType::Witness,
                0.35,
                "Guard bribed by suspect — witness confirmed",
            )],
            CrimeType::Assault => vec![Evidence::new(
                EvidenceType::Physical,
                0.6,
                "Weapon matching suspect's trade confiscated",
            )],
            CrimeType::TaxEvasion => vec![Evidence::new(
                EvidenceType::Financial,
                0.55,
                "Hidden gold cache discovered in warehouse",
            )],
        },
        _ => vec![],
    }
}
