//! `agent::lookahead` (docs/specs/monster-lookahead.md): its 4-move rate is
//! the heuristic's `damage_rate`, step 1 is the first roll after the move
//! history (the pending roll itself when the shown intent is stale), and a
//! swapped history gives the AI's real next-move distribution.

mod common;
use common::*;
use sts_engine::agent::{intent_known, lookahead};
use sts_engine::chance::ChanceEvent;
use sts_engine::heuristic::damage_rate;
use sts_engine::*;

const ENCOUNTERS: [Encounter; 6] = [
    Encounter::Cultist,
    Encounter::JawWorm,
    Encounter::SlimeBoss,
    Encounter::Lagavulin,
    Encounter::GremlinNob,
    Encounter::ThreeSentries,
];

#[test]
fn lookahead_rate_matches_damage_rate() {
    for enc in ENCOUNTERS {
        for seed in 0..3 {
            let mut s = fresh(enc, seed);
            for _ in 0..3 {
                for slot in s.living_slots().collect::<Vec<_>>() {
                    let l = lookahead(&s, slot);
                    let (d, h) = damage_rate(&s, slot);
                    assert!((l.rate_damage - d).abs() < 1e-5 && (l.rate_hits - h).abs() < 1e-5, "{enc:?} {seed} {slot}");
                    for step in [&l.next1, &l.next2] {
                        let p: f32 = step.iter().map(|&(_, p)| p).sum();
                        assert!((p - 1.0).abs() < 1e-6, "{enc:?}: step probabilities sum to {p}");
                    }
                }
                end_turn(&mut s);
                if s.is_over() {
                    break;
                }
            }
        }
    }
}

#[test]
fn step1_follows_the_shown_intent() {
    // Cultist: Incantation shown, Dark Strike after it, and every move after.
    let s = fresh(Encounter::Cultist, 1);
    assert!(intent_known(&s, 0));
    let dark_strike = s.monsters[0].def().moves.iter().position(|m| m.name == "Dark Strike").unwrap() as u8;
    let l = lookahead(&s, 0);
    assert_eq!(l.next1, vec![(dark_strike, 1.0)]);
    assert_eq!(l.next2, vec![(dark_strike, 1.0)]);
}

#[test]
fn step1_is_the_pending_roll_when_stale() {
    // Jaw Worm after End turn, paused at its own roll: the shown intent is
    // the move it just used, and step 1 is the roll's distribution.
    let mut s = fresh(Encounter::JawWorm, 2);
    s.apply_action(Action::EndTurn).expect("end turn");
    assert!(matches!(s.pending, Some(ChanceEvent::MonsterMove { slot: 0 })), "{:?}", s.pending);
    assert!(!intent_known(&s, 0));
    let want: Vec<(u8, f32)> = s.move_distribution(0).into_iter().map(|(m, p)| (m, p as f32)).collect();
    let mut got = lookahead(&s, 0).next1;
    got.sort_by_key(|&(m, _)| m);
    let mut want = want;
    want.sort_by_key(|&(m, _)| m);
    assert_eq!(got.len(), want.len());
    for ((a, p), (b, q)) in got.iter().zip(&want) {
        assert!(a == b && (p - q).abs() < 1e-6, "{got:?} vs {want:?}");
    }
}

#[test]
fn swapped_history_matches_sampled_rolls() {
    // Outside assumption: from a known intent, step 1's distribution is what
    // the monster really rolls next (2,000 rolls, each share within 3 points).
    let s = fresh(Encounter::JawWorm, 3);
    assert!(intent_known(&s, 0));
    let l = lookahead(&s, 0);
    let n = 2000;
    let mut counts = std::collections::HashMap::new();
    for seed in 0..n {
        let mut t = s.clone();
        t.player.hp = t.player.max_hp; // survive the hit
        t.step(Action::EndTurn, &mut Rng::new(seed)).expect("end turn");
        *counts.entry(t.monsters[0].intent()).or_insert(0usize) += 1;
    }
    for &(m, p) in &l.next1 {
        let share = *counts.get(&m).unwrap_or(&0) as f32 / n as f32;
        assert!((share - p).abs() < 0.03, "move {m}: sampled {share}, lookahead {p}");
    }
    assert_eq!(counts.values().sum::<usize>(), n as usize);
    assert!(counts.keys().all(|m| l.next1.iter().any(|&(x, _)| x == *m)), "{counts:?} vs {:?}", l.next1);
}

#[test]
fn dead_monster_has_no_lookahead() {
    let mut s = fresh(Encounter::Cultist, 1);
    s.monsters[0].hp = 0;
    let l = lookahead(&s, 0);
    assert!(l.next1.is_empty() && l.next2.is_empty() && l.rate_damage == 0.0 && l.rate_hits == 0.0);
}
