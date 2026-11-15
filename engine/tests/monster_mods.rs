//! Mutated monsters stage B (docs/specs/mutated-monsters-b.md): the bench's
//! monster powers Damage Down, Weak on hit (the `OwnerAttackHit` trigger)
//! and Split Hits.

mod common;

use common::*;
use sts_engine::agent::{intent_damage, lookahead};
use sts_engine::heuristic::damage_rate;
use sts_engine::hooks::{hooks, Trigger, ATTACK_HIT_POWERS};
use sts_engine::monsters::{guardian, MonsterKind as K, CHOMP, NO_MOVE};
use sts_engine::state::Who;
use sts_engine::*;

const M: Who = Who::Monster(0);

#[test]
fn attack_hit_list_matches_the_table() {
    let hit: Vec<Power> =
        Power::ALL.into_iter().filter(|&p| hooks(p).iter().any(|h| h.trigger == Trigger::OwnerAttackHit)).collect();
    assert_eq!(hit, ATTACK_HIT_POWERS);
}

#[test]
fn damage_down_multiplies_once() {
    for stacks in [1, 3] {
        let mut s = vs(&[K::JawWorm], &[], Some(40));
        s.monsters[0].powers.add(Power::DamageDown, stacks);
        assert_eq!(s.attack_damage(M, Who::Player, 10), 8, "stacks {stacks}");
        s.monsters[0].powers.add(Power::Weak, 1);
        assert_eq!(s.attack_damage(M, Who::Player, 10), 6);
        assert_eq!(s.interpret_attack_damage(M, Who::Player, 10), 6);
        s.monsters[0].powers.add(Power::Weak, -1);
        s.monsters[0].powers.add(Power::Strength, 2);
        assert_eq!(s.attack_damage(M, Who::Player, 10), 9);
        assert_eq!(s.interpret_attack_damage(M, Who::Player, 10), 9);
        // The player's attacks on it are unchanged.
        assert_eq!(s.attack_damage(Who::Player, M, 10), 10);
    }
    // Chomp (11) lands as 8.
    let mut s = with_hand(Encounter::JawWorm, &[], 40);
    s.monsters[0].moves = [CHOMP, NO_MOVE];
    s.monsters[0].powers.add(Power::DamageDown, 1);
    s.player.block = 0;
    let hp = s.player.hp;
    end_turn(&mut s);
    assert_eq!(s.player.hp, hp - 8);
}

/// Every reader of a monster's attack (intent, lookahead rate, the
/// heuristic's rate) sees Damage Down: a Cultist with 4 Strength (Dark
/// Strike 6 + 4 = 10) reads 4/5 of its plain damage.
#[test]
fn damage_down_reaches_move_damage() {
    let cultist = |down: bool| {
        let mut s = vs(&[K::Cultist], &[], Some(40));
        s.monsters[0].powers.add(Power::Strength, 4);
        if down {
            s.monsters[0].powers.add(Power::DamageDown, 1);
        }
        s
    };
    let (plain, down) = (cultist(false), cultist(true));
    assert!(lookahead(&plain, 0).rate_damage > 0.0);
    let close = |a: f32, b: f32| assert!((a - b).abs() < 1e-4, "{a} vs {b}");
    close(lookahead(&down, 0).rate_damage, 0.8 * lookahead(&plain, 0).rate_damage);
    assert_eq!(lookahead(&down, 0).rate_hits, lookahead(&plain, 0).rate_hits);
    close(damage_rate(&down, 0).0, 0.8 * damage_rate(&plain, 0).0);
    assert_eq!(damage_rate(&down, 0).1, damage_rate(&plain, 0).1);
}

/// The Guardian about to Whirlwind (5 x 4) with `weak_on_hit` stacks; the
/// player with `block` and `hp`. Returns the player's Weak after the turn.
fn whirlwind(weak_on_hit: i16, block: i16, hp: i16) -> CombatState {
    let mut s = fresh(Encounter::TheGuardian, 1);
    s.hand = Hand::default();
    s.monsters[0].moves = [guardian::WHIRLWIND, guardian::VENT_STEAM];
    s.monsters[0].powers.add(Power::WeakOnHit, weak_on_hit);
    s.player.hp = hp;
    s.player.block = block;
    end_turn(&mut s);
    s
}

#[test]
fn weak_on_hit_unblocked_only() {
    assert_eq!(whirlwind(1, 0, 80).player.powers.get(Power::Weak), 4);
    // 16 block takes the first three hits and 1 of the fourth.
    let s = whirlwind(1, 16, 80);
    assert_eq!((s.player.hp, s.player.powers.get(Power::Weak)), (76, 1));
    assert_eq!(whirlwind(2, 0, 80).player.powers.get(Power::Weak), 8);
    assert_eq!(whirlwind(0, 0, 80).player.powers.get(Power::Weak), 0);
    // The first hit kills: no hook fires.
    let s = whirlwind(1, 0, 5);
    assert!(s.is_over() && !s.won());
    assert_eq!(s.player.powers.get(Power::Weak), 0);
}

#[test]
fn split_hits_doubles_and_halves() {
    let chomp = |split: bool, strength: i16| {
        let mut s = with_hand(Encounter::JawWorm, &[], 40);
        s.monsters[0].moves = [CHOMP, NO_MOVE];
        if split {
            s.monsters[0].powers.add(Power::SplitHits, 1);
        }
        s.monsters[0].powers.add(Power::Strength, strength);
        s.player.block = 0;
        s
    };
    for (strength, want) in [(0, 10), (2, 14)] {
        let mut s = chomp(true, strength);
        assert_eq!(intent_damage(&s, 0), want);
        let hp = s.player.hp;
        end_turn(&mut s);
        assert_eq!(s.player.hp, hp - want, "strength {strength}");
    }
    // The lookahead and the heuristic's rate see twice the hits.
    let (plain, split) = (chomp(false, 0), chomp(true, 0));
    assert_eq!(lookahead(&split, 0).rate_hits, 2.0 * lookahead(&plain, 0).rate_hits);
    assert_eq!(damage_rate(&split, 0).1, 2.0 * damage_rate(&plain, 0).1);
    assert!(damage_rate(&split, 0).0 < damage_rate(&plain, 0).0);
    // Twin Slam (8 x 2) becomes 4 x 4.
    let mut s = fresh(Encounter::TheGuardian, 1);
    s.hand = Hand::default();
    s.monsters[0].moves = [guardian::TWIN_SLAM, guardian::ROLL_ATTACK];
    s.monsters[0].powers.add(Power::SplitHits, 1);
    s.player.block = 0;
    assert_eq!(intent_damage(&s, 0), 16);
    // A player attack on it is unchanged: Strike deals 6.
    let mut s = with_hand(Encounter::JawWorm, &["Strike"], 40);
    s.monsters[0].powers.add(Power::SplitHits, 1);
    play(&mut s, "Strike", Some(0));
    assert_eq!(s.monsters[0].hp, 34);
}

#[test]
fn split_hits_with_sharp_hide() {
    // Sharp Hide still answers each player attack once (per card).
    let mut s = with_hand(Encounter::JawWorm, &["Strike", "Twin Strike"], 40);
    s.monsters[0].powers.add(Power::SplitHits, 1);
    s.monsters[0].powers.add(Power::SharpHide, 3);
    s.player.block = 0;
    let hp = s.player.hp;
    play(&mut s, "Strike", Some(0));
    play(&mut s, "Twin Strike", Some(0));
    assert_eq!(s.player.hp, hp - 6);
    assert_eq!(s.monsters[0].hp, 40 - 6 - 10);
}
