//! Crime economy module for the Fortress service.
//!
//! Exposes black market trading, investigation, and trial systems.

pub mod black_market;
pub mod investigation;
pub mod trial;

#[cfg(test)]
mod tests;
