mod gold;
mod trade_volume;
mod travel;

pub use gold::GoldSufficientRule;
pub use trade_volume::TradeVolumeRule;
pub use travel::TravelPermittedRule;

use crate::validation::ValidationEngine;

/// Returns a [`ValidationEngine`] pre-loaded with all production rules.
pub fn default_engine() -> ValidationEngine {
    let mut engine = ValidationEngine::new();
    engine.add_rule(GoldSufficientRule::default());
    engine.add_rule(TravelPermittedRule::default());
    engine.add_rule(TradeVolumeRule::default());
    engine
}
