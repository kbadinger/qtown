use crate::validation::{Rule, RuleResult, TownEvent};

/// Maximum trade volume allowed per single event before it is flagged.
const MAX_VOLUME: f64 = 10_000.0;
/// Volume above which a warning is emitted (but the trade is not blocked).
const WARN_VOLUME: f64 = 5_000.0;

/// Validates that trade volumes are within acceptable bounds.
///
/// Excessive volume may indicate market manipulation or a data error.
#[derive(Debug)]
pub struct TradeVolumeRule {
    pub max_volume: f64,
    pub warn_volume: f64,
}

impl Default for TradeVolumeRule {
    fn default() -> Self {
        TradeVolumeRule {
            max_volume: MAX_VOLUME,
            warn_volume: WARN_VOLUME,
        }
    }
}

impl Rule for TradeVolumeRule {
    fn name(&self) -> &str {
        "TradeVolumeRule"
    }

    fn check(&self, event: &TownEvent) -> RuleResult {
        // Only applies to events that carry a trade volume.
        let volume = match event.trade_volume {
            Some(v) => v,
            None => return RuleResult::Pass,
        };

        if volume < 0.0 {
            return RuleResult::Fail(format!(
                "NPC {} submitted a trade with negative volume: {:.2}",
                event.npc_id, volume
            ));
        }

        if volume > self.max_volume {
            return RuleResult::Fail(format!(
                "NPC {} trade volume {:.2} exceeds maximum allowed {:.2}",
                event.npc_id, volume, self.max_volume
            ));
        }

        if volume > self.warn_volume {
            return RuleResult::Warn(format!(
                "NPC {} trade volume {:.2} is unusually large (warn threshold: {:.2})",
                event.npc_id, volume, self.warn_volume
            ));
        }

        RuleResult::Pass
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn trade_event(volume: f64) -> TownEvent {
        TownEvent {
            event_type: "trade".to_string(),
            npc_id: "npc_004".to_string(),
            gold: 500.0,
            origin: None,
            destination: None,
            trade_volume: Some(volume),
            metadata: json!({}),
        }
    }

    #[test]
    fn passes_normal_volume() {
        let rule = TradeVolumeRule::default();
        assert_eq!(rule.check(&trade_event(100.0)), RuleResult::Pass);
    }

    #[test]
    fn warns_on_high_volume() {
        let rule = TradeVolumeRule::default();
        let result = rule.check(&trade_event(7_000.0));
        assert!(matches!(result, RuleResult::Warn(_)));
    }

    #[test]
    fn fails_on_excessive_volume() {
        let rule = TradeVolumeRule::default();
        let result = rule.check(&trade_event(15_000.0));
        assert!(result.is_fail());
    }

    #[test]
    fn fails_on_negative_volume() {
        let rule = TradeVolumeRule::default();
        let result = rule.check(&trade_event(-1.0));
        assert!(result.is_fail());
    }

    #[test]
    fn passes_events_without_volume() {
        let rule = TradeVolumeRule::default();
        let event = TownEvent {
            event_type: "walk".to_string(),
            npc_id: "npc_005".to_string(),
            gold: 10.0,
            origin: None,
            destination: None,
            trade_volume: None,
            metadata: json!({}),
        };
        assert_eq!(rule.check(&event), RuleResult::Pass);
    }
}
