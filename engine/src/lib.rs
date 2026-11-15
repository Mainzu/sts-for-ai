//! Slay the Spire 1 combat engine built for search and learning.
//! See SPEC.md at the repository root.

pub mod agent;
pub mod bound;
pub mod card_sets;
pub mod cf;
pub mod cards;
pub mod chance;
pub mod codec;
pub mod character;
pub mod effects;
pub mod fxhash;
pub mod heuristic;
pub mod hooks;
pub mod monsters;
pub mod options;
pub mod potions;
pub mod powers;
pub mod registry;
pub mod relics;
pub mod rng;
pub mod runner;
pub mod search;
pub mod solve;
pub mod state;
pub mod threshold;
pub mod upgrade;

pub use cards::{starter_deck, CardId, CardKind};
pub use chance::{ChanceEvent, ChanceOutcomes};
pub use character::Character;
pub use monsters::{EliteBuff, Encounter, MonsterKind};
pub use powers::Power;
pub use rng::Rng;
pub use state::{Action, CombatState, Hand, Pile, PileRef, Stage, Who};
