//! `heuristic::strength_hits_left` (docs/specs/strength-hits-price.md): the
//! hits living monsters' Strength will still land, from the heuristic's kill
//! order; the heuristic's own estimates stay as they were.

mod common;

use common::*;
use sts_engine::heuristic::{damage_rate, estimate, strength_hits_left, hp_loss_estimate, turns_left_estimate};
use sts_engine::monsters::MonsterKind as K;
use sts_engine::powers::Power;

fn nob(strength: i16) -> sts_engine::CombatState {
    let mut s = vs(&[K::GremlinNob], &["Defend", "Defend", "Strike", "Strike", "Strike"], Some(85));
    s.monsters[0].powers.add(Power::Strength, strength);
    s
}

#[test]
fn one_monster_is_strength_times_hits_times_rounds() {
    let s = nob(3);
    let h = strength_hits_left(&s);
    let (_, hits) = damage_rate(&s, 0);
    let want = 3.0 * hits * turns_left_estimate(&s);
    assert!(h > 0.0);
    assert!((h - want).abs() < 1e-4, "{h} vs {want}");
}

#[test]
fn zero_without_strength_or_monster() {
    assert_eq!(strength_hits_left(&nob(0)), 0.0);
    let mut dead = nob(3);
    dead.monsters[0].hp = 0;
    assert_eq!(strength_hits_left(&dead), 0.0);
}

#[test]
fn negative_strength_is_a_credit() {
    assert!(strength_hits_left(&nob(-2)) < 0.0);
}

#[test]
fn player_death_caps_the_rounds() {
    let mut s = nob(3);
    s.player.hp = 3;
    let (_, hits) = damage_rate(&s, 0);
    assert!(strength_hits_left(&s) < 3.0 * hits * turns_left_estimate(&s));
}

#[test]
fn estimates_unchanged() {
    // Pinned from the code before strength_hits_left existed.
    let s = nob(3);
    let bits = |s: &sts_engine::CombatState| [estimate(s).to_bits(), hp_loss_estimate(s).to_bits(), turns_left_estimate(s).to_bits()];
    assert_eq!(bits(&s), [0x3f6fc84f, 0x428599ea, 0x4127e6b7]);
    let mut low = nob(3);
    low.player.hp = 3;
    assert_eq!(bits(&low), [0x36a3cac0, 0x428599ea, 0x4127e6b7]);
}
