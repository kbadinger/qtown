use crate::validation::{Rule, RuleResult, TownEvent};

/// Minimum gold required to participate in any economic action.
const MIN_GOLD: f64 = 0.0;

/// Validates that an NPC has a non-negative gold balance for economic events.
///
/// A negative balance indicates a bug in the ledger or a cheating attempt.
#[derive(Debug, Default)]
pub struct GoldSufficientRule {
    /// Override the minimum gold threshold (useful in tests).
    pub min_gold: Option<f64>,
}

impl Rule for GoldSufficientRule {
    fn name(&self) -> &str {
        "GoldSufficientRule"
    }

    fn check(&self, event: &TownEvent) -> RuleResult {
        let threshold = self.min_gold.unwrap_or(MIN_GOLD);

        if event.gold < threshold {
            return RuleResult::Fail(format!(
                "NPC {} has insufficient gold: {:.2} (minimum required: {:.2})",
                event.npc_id, event.gold, threshold
            ));
        }

        // Warn if gold is zero but the event is a purchase/trade.
        if event.gold == 0.0
            && matches!(event.event_type.as_str(), "purchase" | "trade" | "bid")
        {
            return RuleResult::Warn(format!(
                "NPC {} has zero gold for event type '{}'",
                event.npc_id, event.event_type
            ));
        }

        RuleResult::Pass
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn make_event(gold: f64, event_type: &str) -> TownEvent {
        TownEvent {
            event_type: event_type.to_string(),
            npc_id: "npc_001".to_string(),
            gold,
            origin: None,
            destination: None,
            trade_volume: None,
            metadata: json!({}),
        }
    }

    #[test]
    fn passes_with_positive_gold() {
        let rule = GoldSufficientRule::default();
        assert_eq!(rule.check(&make_event(100.0, "walk")), RuleResult::Pass);
    }

    #[test]
    fn fails_with_negative_gold() {
        let rule = GoldSufficientRule::default();
        let result = rule.check(&make_event(-1.0, "trade"));
        assert!(result.is_fail());
    }

    #[test]
    fn warns_on_zero_gold_purchase() {
        let rule = GoldSufficientRule::default();
        let result = rule.check(&make_event(0.0, "purchase"));
        assert!(matches!(result, RuleResult::Warn(_)));
    }
}
