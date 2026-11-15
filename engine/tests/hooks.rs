//! Hook powers (spec triggers-and-conditions): the hook table and the
//! turn-start / turn-end timing of the powers converted to hooks.

mod common;
use common::*;
use sts_engine::hooks::{hooks, Condition, Trigger};
use sts_engine::monsters::MonsterKind as K;
use sts_engine::*;

/// A state whose player just ends turns: no cards, lots of HP.
fn idle(enc: Encounter) -> CombatState {
    let mut s = with_hand(enc, &[], 40);
    s.player.hp = 500;
    s.player.max_hp = 500;
    s
}

#[test]
fn converted_powers_have_hooks_and_modifiers_have_none() {
    let turn_end = [Power::Ritual, Power::Metallicize, Power::LoseStrength];
    for p in turn_end {
        assert!(hooks(p).iter().any(|h| h.trigger == Trigger::OwnerTurnEnd), "{p:?}");
    }
    assert!(hooks(Power::Poison).iter().any(|h| h.trigger == Trigger::OwnerTurnStart));
    // Built-in modifiers: no hooks but their countdown (static-modifiers spec).
    for p in [Power::Strength, Power::Dexterity, Power::Vulnerable, Power::Weak, Power::Frail, Power::Artifact] {
        assert!(hooks(p).iter().all(|h| h.trigger == Trigger::RoundEnd), "{p:?} stays a built-in modifier");
    }
}

#[test]
fn metallicize_on_lagavulin_gives_8_block_at_its_turn_end() {
    let mut s = idle(Encounter::Lagavulin);
    s.monsters[0].block = 0;
    end_turn(&mut s);
    assert_eq!(s.monsters[0].block, 8);
}

#[test]
fn metallicize_block_scales_with_stacks() {
    let mut s = vs(&[K::Cultist], &[], None);
    s.player.hp = 500;
    s.monsters[0].powers.add(Power::Metallicize, 5);
    end_turn(&mut s);
    assert_eq!(s.monsters[0].block, 5);
}

#[test]
fn ritual_3_gives_cultist_3_strength_from_its_second_turn() {
    let mut s = idle(Encounter::Cultist);
    end_turn(&mut s); // Incantation: Ritual 3, skipped the turn it lands
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 0);
    end_turn(&mut s);
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 3);
    end_turn(&mut s);
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 6);
}

#[test]
fn lose_strength_takes_its_stacks_of_strength_at_turn_end_then_goes() {
    let mut s = vs(&[K::Cultist], &[], None);
    s.player.hp = 500;
    s.player.powers.add(Power::Strength, 5);
    s.player.powers.add(Power::LoseStrength, 3);
    end_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Strength), 2);
    assert_eq!(s.player.powers.get(Power::LoseStrength), 0);
}

#[test]
fn poison_3_loses_3_hp_then_leaves_poison_2() {
    let mut s = vs(&[K::Cultist], &[], Some(50));
    s.player.hp = 500;
    s.monsters[0].powers.add(Power::Poison, 3);
    end_turn(&mut s);
    assert_eq!((s.monsters[0].hp, s.monsters[0].powers.get(Power::Poison)), (47, 2));
}

// ---- event hooks (step 3) ----

#[test]
fn event_powers_have_their_hooks() {
    use sts_engine::cards::CardType;
    use sts_engine::hooks::{HpLossFrom, Side};
    let enrage = hooks(Power::Enrage);
    assert!(enrage.iter().any(|h| h.trigger == Trigger::CardPlayed { by: Side::Opponent }
        && h.condition == Condition::CardType(CardType::Skill)));
    assert!(hooks(Power::CurlUp).iter().any(|h| h.trigger == Trigger::OwnerLostHp { from: HpLossFrom::Attack }));
    assert!(hooks(Power::SporeCloud).iter().any(|h| h.trigger == Trigger::OwnerDied));
}

#[test]
fn enrage_2_and_playing_defend_gives_2_strength() {
    let mut s = vs(&[K::GremlinNob], &["Defend", "Strike"], Some(80));
    s.monsters[0].powers.add(Power::Enrage, 2);
    play(&mut s, "Strike", Some(0));
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 0, "Attacks don't enrage");
    play(&mut s, "Defend", None);
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 2);
}

#[test]
fn curl_up_triggers_once_on_nonlethal_attack_hp_loss() {
    let mut s = vs(&[K::RedLouse], &["Strike", "Strike"], Some(20));
    s.monsters[0].powers.add(Power::CurlUp, 5);
    play(&mut s, "Strike", Some(0));
    assert_eq!((s.monsters[0].hp, s.monsters[0].block), (14, 5));
    assert_eq!(s.monsters[0].powers.get(Power::CurlUp), 0);
    s.monsters[0].block = 0;
    play(&mut s, "Strike", Some(0));
    assert_eq!((s.monsters[0].hp, s.monsters[0].block), (8, 0), "only once");
}

#[test]
fn self_inflicted_hp_loss_does_not_trigger_curl_up() {
    // Bloodletting's HP loss is the player's own and only player hooks see it.
    let mut s = vs(&[K::RedLouse], &["Bloodletting"], Some(20));
    s.monsters[0].powers.add(Power::CurlUp, 5);
    play(&mut s, "Bloodletting", None);
    assert_eq!(s.monsters[0].powers.get(Power::CurlUp), 5);
}

#[test]
fn spore_cloud_applies_2_vulnerable_on_death() {
    let mut s = vs(&[K::FungiBeast, K::Cultist], &["Strike"], Some(6));
    s.monsters[1].hp = 50;
    play(&mut s, "Strike", Some(0));
    assert!(!s.monsters[0].alive());
    assert_eq!(s.player.powers.get(Power::Vulnerable), 2);
}
