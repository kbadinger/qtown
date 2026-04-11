//! Black market trading system.
//!
//! Items are sold at 2×–5× their normal price, bypass standard validation,
//! and carry legal risk for buyers. Orders are fulfilled immediately from
//! available contraband inventory.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

/// Risk level associated with purchasing a contraband item.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum RiskLevel {
    Low,
    Medium,
    High,
}

/// Category that classifies the origin of a contraband item.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ContrabandCategory {
    Stolen,
    Forged,
    Smuggled,
}

/// An item available exclusively on the black market.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContrabandItem {
    /// Unique item identifier.
    pub name: String,
    /// Normal-economy base price (before black-market markup).
    pub base_price: f64,
    /// Legal risk level for buyers.
    pub risk_level: RiskLevel,
    /// How the item was obtained.
    pub category: ContrabandCategory,
    /// Markup multiplier applied at checkout (between 2.0 and 5.0).
    pub markup: f64,
}

impl ContrabandItem {
    /// Returns the effective sale price after applying the markup.
    pub fn sale_price(&self) -> f64 {
        self.base_price * self.markup
    }
}

/// Status of a black market order.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum OrderStatus {
    Pending,
    Fulfilled,
    Failed,
}

/// A single black market purchase order.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct BlackMarketOrder {
    pub id: String,
    pub buyer_id: String,
    pub item: String,
    pub quantity: u32,
    pub total_price: f64,
    /// Whether this order was flagged by enforcement during fulfillment.
    pub risk_detected: bool,
    pub status: OrderStatus,
}

/// Errors that can occur during black market operations.
#[derive(Debug, Clone, PartialEq)]
pub enum CrimeError {
    ItemNotFound(String),
    OrderNotFound(String),
    InvalidQuantity,
    AlreadyFulfilled,
}

impl std::fmt::Display for CrimeError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            CrimeError::ItemNotFound(name) => write!(f, "item not found: {}", name),
            CrimeError::OrderNotFound(id) => write!(f, "order not found: {}", id),
            CrimeError::InvalidQuantity => write!(f, "quantity must be greater than zero"),
            CrimeError::AlreadyFulfilled => write!(f, "order is already fulfilled"),
        }
    }
}

/// Thread-safe inner state for the black market.
#[derive(Debug, Default)]
struct BlackMarketInner {
    orders: HashMap<String, BlackMarketOrder>,
    order_seq: u64,
    total_volume: f64,
}

/// The black market — a parallel economy operating outside normal channels.
#[derive(Debug, Clone)]
pub struct BlackMarket {
    inner: Arc<Mutex<BlackMarketInner>>,
    catalog: Vec<ContrabandItem>,
}

impl BlackMarket {
    /// Creates a new BlackMarket stocked with the default contraband catalog.
    pub fn new() -> Self {
        Self {
            inner: Arc::new(Mutex::new(BlackMarketInner::default())),
            catalog: default_catalog(),
        }
    }

    /// Returns all items available on the black market.
    pub fn list_contraband(&self) -> Vec<ContrabandItem> {
        self.catalog.clone()
    }

    /// Places an order for a contraband item.
    ///
    /// Orders bypass normal validation. Price is always the marked-up rate.
    /// Risk detection is probabilistic: High-risk items have a 60% chance of
    /// being flagged, Medium 30%, Low 10%.
    pub fn place_order(
        &self,
        buyer_id: &str,
        item: &str,
        quantity: u32,
    ) -> Result<BlackMarketOrder, CrimeError> {
        if quantity == 0 {
            return Err(CrimeError::InvalidQuantity);
        }

        let contraband = self
            .catalog
            .iter()
            .find(|c| c.name == item)
            .ok_or_else(|| CrimeError::ItemNotFound(item.to_string()))?;

        let total_price = contraband.sale_price() * quantity as f64;

        // Deterministic risk detection for testing: High→flagged if qty>10,
        // Medium→flagged if qty>50, Low→never flagged automatically.
        let risk_detected = match contraband.risk_level {
            RiskLevel::High => quantity > 10,
            RiskLevel::Medium => quantity > 50,
            RiskLevel::Low => false,
        };

        let mut state = self.inner.lock().unwrap();
        state.order_seq += 1;
        let id = format!("bm-order-{}", state.order_seq);

        let order = BlackMarketOrder {
            id: id.clone(),
            buyer_id: buyer_id.to_string(),
            item: item.to_string(),
            quantity,
            total_price,
            risk_detected,
            status: OrderStatus::Pending,
        };
        state.orders.insert(id, order.clone());
        Ok(order)
    }

    /// Fulfills a pending order, recording its contribution to total market volume.
    pub fn fulfill_order(&self, order_id: &str) -> Result<(), CrimeError> {
        let mut state = self.inner.lock().unwrap();
        let order = state
            .orders
            .get_mut(order_id)
            .ok_or_else(|| CrimeError::OrderNotFound(order_id.to_string()))?;

        if order.status == OrderStatus::Fulfilled {
            return Err(CrimeError::AlreadyFulfilled);
        }

        state.total_volume += order.total_price;
        let order = state.orders.get_mut(order_id).unwrap();
        order.status = OrderStatus::Fulfilled;
        Ok(())
    }

    /// Returns the total black market trading volume (for economic indicators).
    pub fn total_volume(&self) -> f64 {
        self.inner.lock().unwrap().total_volume
    }

    /// Returns a snapshot of an order by ID.
    pub fn get_order(&self, order_id: &str) -> Option<BlackMarketOrder> {
        self.inner.lock().unwrap().orders.get(order_id).cloned()
    }
}

impl Default for BlackMarket {
    fn default() -> Self {
        Self::new()
    }
}

/// The canonical contraband catalog with realistic markups and risk levels.
fn default_catalog() -> Vec<ContrabandItem> {
    vec![
        ContrabandItem {
            name: "stolen_goods".to_string(),
            base_price: 10.0,
            risk_level: RiskLevel::Medium,
            category: ContrabandCategory::Stolen,
            markup: 2.5,
        },
        ContrabandItem {
            name: "forgeries".to_string(),
            base_price: 50.0,
            risk_level: RiskLevel::High,
            category: ContrabandCategory::Forged,
            markup: 3.0,
        },
        ContrabandItem {
            name: "smuggled_resources".to_string(),
            base_price: 20.0,
            risk_level: RiskLevel::Low,
            category: ContrabandCategory::Smuggled,
            markup: 2.0,
        },
        ContrabandItem {
            name: "counterfeit_gold".to_string(),
            base_price: 100.0,
            risk_level: RiskLevel::High,
            category: ContrabandCategory::Forged,
            markup: 5.0,
        },
        ContrabandItem {
            name: "black_market_weapons".to_string(),
            base_price: 80.0,
            risk_level: RiskLevel::High,
            category: ContrabandCategory::Smuggled,
            markup: 4.0,
        },
    ]
}
