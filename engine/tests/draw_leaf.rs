//! The sampled-draw leaf (docs/specs/draw-leaf.md): with `draw_k > 0`,
//! end-of-turn leaves are scored after the next hand is drawn.

mod common;

use common::*;
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

fn mid_fight() -> CombatState {
    let mut s = fresh(Encounter::JawWorm, 3);
    end_turn(&mut s);
    assert!(s.awaiting_action() && !s.is_over());
    s
}

fn draw(k: u32) -> SearchConfig {
    SearchConfig { draw_k: k, seed: 11, ..SearchConfig::default() }
}

#[test]
fn draw_leaf_off_is_unchanged() {
    let s = mid_fight();
    let a = search(&s, &mut Heuristic, &SearchConfig { seed: 11, ..SearchConfig::default() });
    let b = search(&s, &mut Heuristic, &draw(0));
    assert_eq!((a.nodes, a.leaves, a.cuts, &a.line), (b.nodes, b.leaves, b.cuts, &b.line));
    let va: Vec<_> = a.options.iter().map(|o| (o.actions.clone(), o.value)).collect();
    let vb: Vec<_> = b.options.iter().map(|o| (o.actions.clone(), o.value)).collect();
    assert_eq!(va, vb);
}

#[test]
fn draw_leaf_scores_drawn_states() {
    let s = mid_fight();
    let mut rec = Record(Vec::new());
    let r = search(&s, &mut rec, &draw(2));
    assert!(!rec.0.is_empty());
    for t in &rec.0 {
        assert!(t.awaiting_action(), "a leaf is paused, not drawn");
        assert_eq!(t.turn, s.turn + 1, "a leaf is not the next turn's decision");
    }
    let plain = search(&s, &mut Heuristic, &SearchConfig { seed: 11, ..SearchConfig::default() });
    assert!(r.leaves > plain.leaves);
}

#[test]
fn draw_leaf_common_draws() {
    // The draws depend on the seed, the turn and the event's order only:
    // two roots that differ in nothing a draw sees get the same hands.
    let s = mid_fight();
    let mut t = s.clone();
    t.player.hp -= 5;
    let hands = |root: &CombatState| {
        let mut rec = Record(Vec::new());
        search(root, &mut rec, &draw(3));
        let mut h: Vec<String> = rec.0.iter().map(|x| format!("{:?}", x.hand)).collect();
        h.sort();
        h
    };
    assert_eq!(hands(&s), hands(&t));
    let a = search(&s, &mut Heuristic, &draw(3));
    let b = search(&s, &mut Heuristic, &draw(3));
    let va: Vec<_> = a.options.iter().map(|o| o.value).collect();
    let vb: Vec<_> = b.options.iter().map(|o| o.value).collect();
    assert_eq!(va, vb);
}

#[test]
fn draw_leaf_line_stops_at_end_turn() {
    let r = search(&mid_fight(), &mut Heuristic, &draw(2));
    assert_eq!(r.line.last(), Some(&Action::EndTurn));
}
