//! Replacement hooks (docs/specs/replacement-hooks.md): Artifact and
//! Intangible as replacement rows, Wraith Form, Thorns (Caltrops) with the
//! `OwnerAttacked` trigger and the attacker target, and a monster dying
//! mid-move.

mod common;

use common::*;
use sts_engine::hooks::{hooks, replacements, Replace, Replaced, Trigger, ATTACKED_POWERS, REPLACEMENT_POWERS, ROUND_END_POWERS};
use sts_engine::monsters::{hexaghost, MonsterKind as K};
use sts_engine::*;

#[test]
fn round_end_and_replacement_lists_match_the_tables() {
    let round_end: Vec<Power> = Power::ALL.into_iter().filter(|&p| hooks(p).iter().any(|h| h.trigger == Trigger::RoundEnd)).collect();
    assert_eq!(round_end, ROUND_END_POWERS);
    let attacked: Vec<Power> =
        Power::ALL.into_iter().filter(|&p| hooks(p).iter().any(|h| h.trigger == Trigger::OwnerAttacked)).collect();
    assert_eq!(attacked, ATTACKED_POWERS);
    let replacing: Vec<Power> = Power::ALL.into_iter().filter(|&p| !replacements(p).is_empty()).collect();
    assert_eq!(replacing, REPLACEMENT_POWERS);
}

#[test]
fn artifact_is_a_replacement_row() {
    let r = replacements(Power::Artifact);
    assert_eq!((r.len(), r[0].event, r[0].action), (1, Replaced::DebuffApplied, Replace::Cancel));
    let mut s = vs(&[K::Sentry], &["Bash", "Bash"], Some(40));
    s.player.energy = 4;
    assert_eq!(s.monsters[0].powers.get(Power::Artifact), 1);
    play(&mut s, "Bash", Some(0));
    assert_eq!((s.monsters[0].powers.get(Power::Vulnerable), s.monsters[0].powers.get(Power::Artifact)), (0, 0));
    play(&mut s, "Bash", Some(0));
    assert_eq!(s.monsters[0].powers.get(Power::Vulnerable), 2);
}

#[test]
fn intangible_caps_attacks_and_hp_loss() {
    // Jaw Worm opens with Chomp (11): one HP through Intangible.
    let mut s = with_hand(Encounter::JawWorm, &[], 40);
    s.player.powers.add(Power::Intangible, 2);
    let hp = s.player.hp;
    end_turn(&mut s);
    assert_eq!(s.player.hp, hp - 1);
    // With block the capped 1 is absorbed.
    let mut s = with_hand(Encounter::JawWorm, &[], 40);
    s.player.powers.add(Power::Intangible, 2);
    s.player.block = 1;
    let hp = s.player.hp;
    end_turn(&mut s);
    assert_eq!(s.player.hp, hp);
    // HP loss from a card: Bloodletting's 3 becomes 1.
    let mut s = with_hand(Encounter::JawWorm, &["Bloodletting"], 40);
    s.player.powers.add(Power::Intangible, 1);
    let hp = s.player.hp;
    play(&mut s, "Bloodletting", None);
    assert_eq!(s.player.hp, hp - 1);
    // Poison on an Intangible monster: 1 a tick.
    let mut s = with_hand(Encounter::JawWorm, &[], 40);
    s.monsters[0].powers.add(Power::Poison, 5);
    s.monsters[0].powers.add(Power::Intangible, 1);
    end_turn(&mut s);
    assert_eq!(s.monsters[0].hp, 39);
}

#[test]
fn intangible_counts_down_at_round_end() {
    let mut s = with_hand(Encounter::JawWorm, &[], 40);
    s.player.powers.add(Power::Intangible, 2);
    end_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Intangible), 1);
    end_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Intangible), 0);
}

#[test]
fn wraith_form_loses_dexterity_each_turn() {
    let mut s = with_hand(Encounter::JawWorm, &["Wraith Form"], 40);
    play(&mut s, "Wraith Form", None);
    assert_eq!((s.player.powers.get(Power::Intangible), s.player.powers.get(Power::WraithForm)), (2, 1));
    end_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Dexterity), -1);
    end_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Dexterity), -2);
    // Two copies: two a turn.
    let mut s = with_hand(Encounter::JawWorm, &["Wraith Form+"], 40);
    s.player.powers.add(Power::WraithForm, 1);
    play(&mut s, "Wraith Form+", None);
    assert_eq!(s.player.powers.get(Power::Intangible), 3);
    end_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Dexterity), -2);
}

/// Hexaghost about to Tackle (5 x 2), with `block` on it.
fn tackling_hexaghost(block: i16) -> CombatState {
    let mut s = vs(&[K::Hexaghost], &[], Some(200));
    s.monsters[0].set_move(hexaghost::CYCLE + 1);
    assert_eq!(s.monsters[0].intent_def().unwrap().name, "Tackle");
    s.monsters[0].block = block;
    s
}

#[test]
fn caltrops_hits_back_every_hit() {
    let mut s = tackling_hexaghost(0);
    s.player.powers.add(Power::Thorns, 3);
    s.player.block = 20; // both hits fully blocked: Thorns still fires
    end_turn(&mut s);
    assert_eq!(s.monsters[0].hp, 200 - 6);
    // Strength doesn't add to Thorns (non-attack damage). (A monster's
    // block is gone by its own turn; Thorns is `PlainDamage`, which block
    // absorbs like any other.)
    let mut s = tackling_hexaghost(0);
    s.player.powers.add(Power::Thorns, 3);
    s.player.powers.add(Power::Strength, 5);
    end_turn(&mut s);
    assert_eq!(s.monsters[0].hp, 200 - 6);
    // Played as a card.
    let mut s = with_hand(Encounter::JawWorm, &["Caltrops+"], 40);
    play(&mut s, "Caltrops+", None);
    assert_eq!(s.player.powers.get(Power::Thorns), 5);
}

#[test]
fn attacker_dying_mid_move_stops_its_hits() {
    // A second monster with no move keeps the combat going (a won combat
    // heals the Ironclad, which would hide the damage).
    let mut s = vs(&[K::Hexaghost, K::JawWorm], &[], Some(200));
    s.monsters[0].set_move(hexaghost::CYCLE + 1);
    s.monsters[0].hp = 3;
    s.player.powers.add(Power::Thorns, 3);
    let hp = s.player.hp;
    end_turn(&mut s);
    assert!(!s.monsters[0].alive() && !s.is_over());
    assert_eq!(s.player.hp, hp - 5, "only the first hit lands");
}
