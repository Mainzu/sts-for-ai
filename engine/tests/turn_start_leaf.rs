//! The turn-start leaf (docs/specs/turn-start-leaf.md): with
//! `turn_start_leaf`, an end-of-turn leaf is scored after the player's
//! turn-start hooks that need no chance.

mod common;

use common::*;
use sts_engine::monsters::MonsterKind as K;
use sts_engine::search::{search, Evaluator, Heuristic, SearchConfig};
use sts_engine::*;

/// Records every state it scores; scores by the heuristic.
struct Record(Vec<CombatState>);

impl Evaluator for Record {
    fn evaluate(&mut self, states: &[CombatState]) -> Vec<f32> {
        self.0.extend_from_slice(states);
        Heuristic.evaluate(states)
    }
}

/// A cultist at 100 HP, `hand`, 3 energy, a mixed draw pile (so the next
/// draw is a chance event), and the player holding `powers`.
fn setup(hand: &[&str], powers: &[(Power, i16)]) -> CombatState {
    let mut s = vs(&[K::Cultist], hand, Some(100));
    s.monsters[0].set_move(0);
    s.set_draw(Pile::from_cards(&[card("Strike"), card("Strike"), card("Defend"), card("Defend"), card("Bash"), card("Strike"), card("Defend")]));
    for &(p, n) in powers {
        s.player.powers.add(p, n);
    }
    s
}

/// The state right after `EndTurn`, paused at the next turn's draw.
fn after_end_turn(mut s: CombatState) -> CombatState {
    s.apply_action(Action::EndTurn).expect("end turn");
    assert!(s.pending.is_some() && !s.awaiting_action(), "paused at the draw");
    s
}

fn tsl() -> SearchConfig {
    SearchConfig { turn_start_leaf: true, ..SearchConfig::default() }
}

#[test]
fn turn_start_leaf_off_is_unchanged() {
    let s = setup(&["Strike", "Defend", "Bash"], &[(Power::DemonForm, 2)]);
    let a = search(&s, &mut Heuristic, &SearchConfig::default());
    let b = search(&s, &mut Heuristic, &SearchConfig { turn_start_leaf: false, ..SearchConfig::default() });
    assert_eq!((a.nodes, a.leaves, a.cuts, &a.line), (b.nodes, b.leaves, b.cuts, &b.line));
    let va: Vec<_> = a.options.iter().map(|o| (o.actions.clone(), o.value)).collect();
    let vb: Vec<_> = b.options.iter().map(|o| (o.actions.clone(), o.value)).collect();
    assert_eq!(va, vb);
}

#[test]
fn demon_form_tick_lands_in_the_leaf() {
    let s = after_end_turn(setup(&["Strike"], &[(Power::DemonForm, 2)]));
    let t = s.turn_start_leaf().expect("a turn-start hook is due");
    assert_eq!(t.player.powers.get(Power::Strength), s.player.powers.get(Power::Strength) + 2);
    assert_eq!((t.hand.len(), t.draw().len(), &t.pending), (s.hand.len(), s.draw().len(), &s.pending));
    // The real turn start gives the same Strength.
    let mut real = s.clone();
    real.resolve_chance(&mut Rng::new(3));
    assert_eq!(real.player.powers.get(Power::Strength), t.player.powers.get(Power::Strength));

    let plain = after_end_turn(setup(&["Strike"], &[(Power::Metallicize, 3)]));
    assert!(plain.turn_start_leaf().is_none(), "no turn-start hook: the leaf stays");
}

#[test]
fn drawn_effects_left_out() {
    let s = after_end_turn(setup(&["Strike"], &[(Power::Brutality, 1)]));
    let t = s.turn_start_leaf().expect("Brutality ticks");
    assert_eq!(t.player.hp, s.player.hp - 1);
    assert_eq!((t.hand.len(), t.draw().len(), &t.pending), (s.hand.len(), s.draw().len(), &s.pending), "no draw");
}

#[test]
fn past_turn_start_is_none() {
    let s = setup(&["Strike"], &[(Power::DemonForm, 2)]);
    assert!(s.awaiting_action());
    assert!(s.turn_start_leaf().is_none());
    let mut drawn = after_end_turn(s);
    drawn.resolve_chance(&mut Rng::new(5));
    assert!(drawn.awaiting_action());
    assert!(drawn.turn_start_leaf().is_none(), "the hooks already ran");
}

#[test]
fn search_scores_ticked_leaves() {
    let s = setup(&["Strike", "Defend"], &[(Power::DemonForm, 2)]);
    let base = s.player.powers.get(Power::Strength);
    let mut rec = Record(Vec::new());
    search(&s, &mut rec, &tsl());
    assert!(!rec.0.is_empty());
    for t in &rec.0 {
        assert_eq!(t.player.powers.get(Power::Strength), base + 2, "every leaf holds the tick");
    }
    let mut off = Record(Vec::new());
    search(&s, &mut off, &SearchConfig::default());
    assert!(off.0.iter().all(|t| t.player.powers.get(Power::Strength) == base));
}
