//! Trial system for criminal cases.
//!
//! A TrialEngine conducts proceedings, presents evidence, and renders a verdict
//! based on accumulated guilt probability. Sentences are proportionate to
//! crime severity.

use crate::crime::investigation::{Case, CrimeType, Evidence};
use serde::{Deserialize, Serialize};

/// The outcome of a trial.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum Verdict {
    Guilty,
    InsufficientEvidence,
    NotGuilty,
}

impl std::fmt::Display for Verdict {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Verdict::Guilty => write!(f, "GUILTY"),
            Verdict::InsufficientEvidence => write!(f, "INSUFFICIENT_EVIDENCE"),
            Verdict::NotGuilty => write!(f, "NOT_GUILTY"),
        }
    }
}

/// Type of punishment imposed by the court.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum SentenceType {
    /// Pay a gold fine.
    Fine,
    /// Perform forced work for the community for `duration_ticks` ticks.
    CommunityService,
    /// Expelled from the neighbourhood for `duration_ticks` ticks.
    Exile,
}

/// The court's sentence following a guilty verdict.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Sentence {
    pub sentence_type: SentenceType,
    /// Magnitude in gold (for Fine) or severity multiplier (for others).
    pub magnitude: f64,
    /// Duration in simulation ticks.
    pub duration_ticks: i64,
}

/// A proceeding record for a single trial.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Trial {
    pub case_id: String,
    pub defendant_id: String,
    /// NPC ID of the judge presiding over this trial.
    pub judge_npc_id: String,
    /// All evidence formally presented to the court.
    pub evidence_presented: Vec<Evidence>,
    /// Final guilt probability computed from presented evidence.
    pub guilt_probability: f64,
    pub verdict: Option<Verdict>,
    pub sentence: Option<Sentence>,
}

/// Errors from the trial engine.
#[derive(Debug, Clone, PartialEq)]
pub enum TrialError {
    AlreadyVerdicted,
    NoEvidencePresented,
}

impl std::fmt::Display for TrialError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TrialError::AlreadyVerdicted => write!(f, "verdict has already been rendered"),
            TrialError::NoEvidencePresented => {
                write!(f, "at least one piece of evidence must be presented")
            }
        }
    }
}

/// Deterministic judge pool — selected by case_id hash to avoid randomness in tests.
const JUDGE_POOL: &[&str] = &[
    "judge-aldric",
    "judge-mira",
    "judge-fenwick",
    "judge-callista",
    "judge-dorn",
];

fn select_judge(case_id: &str) -> &'static str {
    let hash: usize = case_id.bytes().fold(0usize, |acc, b| acc.wrapping_add(b as usize));
    JUDGE_POOL[hash % JUDGE_POOL.len()]
}

/// Orchestrates criminal trials.
#[derive(Debug, Default)]
pub struct TrialEngine;

impl TrialEngine {
    /// Creates a new TrialEngine.
    pub fn new() -> Self {
        Self
    }

    /// Begins a new trial for the given case. All evidence already attached
    /// to the case is included in the initial record.
    pub fn begin_trial(&self, case: &Case) -> Trial {
        Trial {
            case_id: case.id.clone(),
            defendant_id: case.suspect_id.clone(),
            judge_npc_id: select_judge(&case.id).to_string(),
            evidence_presented: case.evidence.clone(),
            guilt_probability: case.guilt_probability,
            verdict: None,
            sentence: None,
        }
    }

    /// Adds additional evidence to the trial record and recomputes guilt probability.
    pub fn present_evidence(&self, trial: &mut Trial, evidence: &Evidence) {
        trial.evidence_presented.push(evidence.clone());
        trial.guilt_probability = compute_guilt_probability(&trial.evidence_presented);
    }

    /// Renders a verdict based on the trial's current guilt probability.
    ///
    /// - ≥ 0.7 → GUILTY
    /// - 0.4..0.7 → INSUFFICIENT_EVIDENCE
    /// - < 0.4 → NOT_GUILTY
    ///
    /// If GUILTY, a sentence is automatically imposed based on the case's crime
    /// type. Returns `TrialError::AlreadyVerdicted` if called more than once.
    pub fn render_verdict(&self, trial: &mut Trial) -> Result<Verdict, TrialError> {
        if trial.verdict.is_some() {
            return Err(TrialError::AlreadyVerdicted);
        }

        let p = trial.guilt_probability;
        let verdict = if p >= 0.7 {
            Verdict::Guilty
        } else if p >= 0.4 {
            Verdict::InsufficientEvidence
        } else {
            Verdict::NotGuilty
        };

        trial.verdict = Some(verdict.clone());
        Ok(verdict)
    }

    /// Imposes a sentence appropriate to the crime type and severity.
    ///
    /// Must be called after `render_verdict` produces `Verdict::Guilty`.
    pub fn impose_sentence(&self, trial: &mut Trial, crime_type: &CrimeType) -> Sentence {
        let sentence = sentence_for_crime(crime_type, trial.guilt_probability);
        trial.sentence = Some(sentence.clone());
        sentence
    }
}

/// Computes guilt probability from a slice of evidence (weighted sum, clamped).
fn compute_guilt_probability(evidence: &[Evidence]) -> f64 {
    if evidence.is_empty() {
        return 0.0;
    }
    let weighted_sum: f64 = evidence.iter().map(|e| e.strength * e.type_weight()).sum();
    let max_possible: f64 = evidence.len() as f64 * 1.5;
    (weighted_sum / max_possible).clamp(0.0, 1.0)
}

/// Determines a proportionate sentence given crime type and guilt severity.
fn sentence_for_crime(crime_type: &CrimeType, guilt_probability: f64) -> Sentence {
    // Severity multiplier: higher guilt → harsher sentence.
    let severity = if guilt_probability >= 0.9 {
        3.0
    } else if guilt_probability >= 0.7 {
        2.0
    } else {
        1.0
    };

    match crime_type {
        CrimeType::TaxEvasion => Sentence {
            sentence_type: SentenceType::Fine,
            magnitude: 500.0 * severity,
            duration_ticks: 0,
        },
        CrimeType::Theft => Sentence {
            sentence_type: SentenceType::CommunityService,
            magnitude: severity,
            duration_ticks: (50.0 * severity) as i64,
        },
        CrimeType::Fraud => Sentence {
            sentence_type: SentenceType::Fine,
            magnitude: 1000.0 * severity,
            duration_ticks: 0,
        },
        CrimeType::Smuggling => Sentence {
            sentence_type: SentenceType::Exile,
            magnitude: severity,
            duration_ticks: (200.0 * severity) as i64,
        },
        CrimeType::Assault => Sentence {
            sentence_type: SentenceType::Exile,
            magnitude: severity,
            duration_ticks: (150.0 * severity) as i64,
        },
    }
}
