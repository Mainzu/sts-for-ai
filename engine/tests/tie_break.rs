//! The finish-faster tie break (docs/specs/finish-faster-tiebreak.md): with
//! `tie_break`, exactly equal options go to the sooner win, then to lower
//! enemy HP; values never change.

mod common;

use common::*;
use sts_engine::search::{search, Evaluator, SearchConfig};
use sts_engine::*;

/// Scores every leaf the same.
struct Flat(f32);

impl Evaluator for Flat {
    fn evaluate(&mut self, states: &[CombatState]) -> Vec<f32> {
        vec![self.0; states.len()]
    }
}

fn both(s: &CombatState, leaf: f32) -> (search::SearchResult, search::SearchResult) {
    let off = search(s, &mut Flat(leaf), &SearchConfig::default());
    let on = search(s, &mut Flat(leaf), &SearchConfig { tie_break: true, ..SearchConfig::default() });
    let vals = |r: &search::SearchResult| r.options.iter().map(|o| (o.actions.clone(), o.value)).collect::<Vec<_>>();
    assert_eq!(vals(&off), vals(&on), "the tie break changes no value");
    assert_eq!(off.nodes, on.nodes);
    (off, on)
}

fn first_tied(r: &search::SearchResult) -> Action {
    let best = r.options.iter().map(|o| o.value).fold(f32::MIN, f32::max);
    r.options.iter().find(|o| o.value == best).unwrap().actions[0]
}

/// Two energy, Strike and Bash in hand, an 8 HP monster: Bash wins now
/// (exact 2.0 at full HP); Strike (first in order) leaves 2 HP and no
/// energy for Bash, so it ends the turn on a leaf scored 2.0.
#[test]
fn tie_break_prefers_the_sooner_win() {
    let mut s = with_hand(Encounter::Cultist, &["Strike", "Bash"], 8);
    s.player.energy = 2;
    let (off, on) = both(&s, 2.0);
    assert_eq!(off.action, first_tied(&off), "off: the first tied option, as before");
    assert_ne!(off.action, on.action, "the case ties: off keeps list order");
    assert!(matches!(on.action, Action::Play { card: c, .. } if c == card("Bash")), "on: the kill, got {:?}", on.action);
}

/// A 100 HP monster, every leaf 1.0: Bash leaves it at 92, Strike (first
/// in order, then no energy for Bash) at 94.
#[test]
fn tie_break_prefers_lower_enemy_hp() {
    let mut s = with_hand(Encounter::Cultist, &["Strike", "Bash"], 100);
    s.player.energy = 2;
    let (off, on) = both(&s, 1.0);
    assert_eq!(off.action, first_tied(&off));
    assert_ne!(off.action, on.action, "the case ties: off keeps list order");
    assert!(matches!(on.action, Action::Play { card: c, .. } if c == card("Bash")), "on: the damage, got {:?}", on.action);
    assert_eq!(on.line.first(), Some(&on.action));
}

