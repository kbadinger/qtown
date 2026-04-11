use crate::validation::{Rule, RuleResult, TownEvent};

/// Districts that are locked down and require a travel permit.
const RESTRICTED_DISTRICTS: &[&str] = &["fortress", "vault", "restricted-zone"];

/// Validates that an NPC is allowed to travel to their stated destination.
///
/// Some districts require an explicit permit recorded in the event metadata.
#[derive(Debug, Default)]
pub struct TravelPermittedRule;

impl Rule for TravelPermittedRule {
    fn name(&self) -> &str {
        "TravelPermittedRule"
    }

    fn check(&self, event: &TownEvent) -> RuleResult {
        // Only applies to travel/movement events.
        if !matches!(event.event_type.as_str(), "travel" | "move" | "enter") {
            return RuleResult::Pass;
        }

        let destination = match event.destination.as_deref() {
            Some(d) => d,
            None => return RuleResult::Warn(format!(
                "NPC {} travel event has no destination",
                event.npc_id
            )),
        };

        let is_restricted = RESTRICTED_DISTRICTS
            .iter()
            .any(|d| destination.eq_ignore_ascii_case(d));

        if !is_restricted {
            return RuleResult::Pass;
        }

        // Check for a permit in event metadata.
        let has_permit = event
            .metadata
            .get("travel_permit")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

        if has_permit {
            RuleResult::Pass
        } else {
            RuleResult::Fail(format!(
                "NPC {} does not have a travel permit for restricted district '{}'",
                event.npc_id, destination
            ))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn travel_event(destination: &str, permit: bool) -> TownEvent {
        TownEvent {
            event_type: "travel".to_string(),
            npc_id: "npc_002".to_string(),
            gold: 10.0,
            origin: Some("market".to_string()),
            destination: Some(destination.to_string()),
            trade_volume: None,
            metadata: json!({ "travel_permit": permit }),
        }
    }

    #[test]
    fn passes_unrestricted_destination() {
        let rule = TravelPermittedRule;
        assert_eq!(rule.check(&travel_event("market", false)), RuleResult::Pass);
    }

    #[test]
    fn fails_restricted_without_permit() {
        let rule = TravelPermittedRule;
        let result = rule.check(&travel_event("fortress", false));
        assert!(result.is_fail());
    }

    #[test]
    fn passes_restricted_with_permit() {
        let rule = TravelPermittedRule;
        assert_eq!(rule.check(&travel_event("fortress", true)), RuleResult::Pass);
    }

    #[test]
    fn ignores_non_travel_events() {
        let rule = TravelPermittedRule;
        let event = TownEvent {
            event_type: "trade".to_string(),
            npc_id: "npc_003".to_string(),
            gold: 50.0,
            origin: None,
            destination: Some("fortress".to_string()),
            trade_volume: Some(10.0),
            metadata: json!({}),
        };
        assert_eq!(rule.check(&event), RuleResult::Pass);
    }
}
