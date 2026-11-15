//! Power cards built from hooks (triggers and conditions, step 5), base and
//! upgraded, with values from slaythespire.wiki.gg.

mod common;
use common::*;
use sts_engine::cards::{deck_cards, held_out_cards};
use sts_engine::monsters::MonsterKind as K;
use sts_engine::*;

/// Cultists at 100 HP, `hand`, 3 energy, 10 Strikes to draw. `attacking`:
/// their intent is Dark Strike (6), else Incantation.
fn cultists(n: usize, hand: &[&str], attacking: bool) -> CombatState {
    let mut s = vs(&vec![K::Cultist; n], hand, Some(100));
    for slot in 0..n {
        s.monsters[slot].set_move(if attacking { 1 } else { 0 });
    }
    s.set_draw(Pile::from_cards(&[card("Strike"); 10]));
    s
}

#[test]
fn combust_loses_1_hp_and_deals_5_or_7_to_all_enemies_unaffected_by_strength() {
    for (name, dmg) in [("Combust", 5), ("Combust+", 7)] {
        let mut s = cultists(2, &[name], false);
        s.player.powers.add(Power::Strength, 5);
        s.monsters[1].powers.add(Power::Vulnerable, 2);
        s.monsters[0].block = 2;
        let hp = s.player.hp;
        play(&mut s, name, None);
        end_turn(&mut s);
        assert_eq!(hp - s.player.hp, 1);
        assert_eq!(100 - s.monsters[0].hp, dmg - 2, "block absorbs it");
        assert_eq!(100 - s.monsters[1].hp, dmg, "Vulnerable doesn't apply");
    }
}

#[test]
fn combust_and_combust_plus_stack_their_hp_loss_and_damage() {
    let mut s = cultists(1, &["Combust", "Combust+"], false);
    let hp = s.player.hp;
    play(&mut s, "Combust", None);
    play(&mut s, "Combust+", None);
    end_turn(&mut s);
    assert_eq!(hp - s.player.hp, 2);
    assert_eq!(100 - s.monsters[0].hp, 12);
}

#[test]
fn brutality_loses_1_hp_and_draws_1_at_turn_start_after_the_draw() {
    let mut s = cultists(1, &["Brutality"], false);
    let hp = s.player.hp;
    play(&mut s, "Brutality", None);
    end_turn(&mut s);
    assert!(s.awaiting_action());
    assert_eq!(hp - s.player.hp, 1);
    assert_eq!(s.hand.len(), 6);
}

#[test]
fn brutality_plus_is_innate() {
    let mut deck = vec![card("Strike"); 10];
    deck.push(card("Brutality+"));
    for seed in 0..20 {
        let s = CombatState::new(&deck, 80, 80, Encounter::Cultist, &mut Rng::new(seed));
        assert_eq!(s.hand.count(card("Brutality+")), 1, "seed {seed}");
        assert_eq!(s.hand.len(), 5, "innate cards count toward the opening hand");
    }
    // Brutality (base) is not.
    let mut deck = vec![card("Strike"); 30];
    deck.push(card("Brutality"));
    let missing = (0..20)
        .filter(|&seed| CombatState::new(&deck, 80, 80, Encounter::Cultist, &mut Rng::new(seed)).hand.count(card("Brutality")) == 0)
        .count();
    assert!(missing > 0);
}

#[test]
fn rupture_gains_strength_when_a_card_costs_hp() {
    for (name, str) in [("Rupture", 1), ("Rupture+", 2)] {
        let mut s = cultists(1, &[name, "Bloodletting"], false);
        play(&mut s, name, None);
        play(&mut s, "Bloodletting", None);
        assert_eq!(s.player.powers.get(Power::Strength), str);
    }
}

#[test]
fn rupture_strength_comes_after_hemokinesis_hits() {
    let mut s = cultists(1, &["Rupture", "Hemokinesis"], false);
    play(&mut s, "Rupture", None);
    play(&mut s, "Hemokinesis", Some(0));
    assert_eq!(100 - s.monsters[0].hp, 15, "the game computes the hit before Rupture's Strength");
    assert_eq!(s.player.powers.get(Power::Strength), 1);
}

#[test]
fn rupture_triggers_on_combust_and_brutality_but_not_on_attacks() {
    let mut s = cultists(1, &["Rupture", "Combust", "Brutality"], true);
    play(&mut s, "Rupture", None);
    play(&mut s, "Combust", None);
    play(&mut s, "Brutality", None);
    end_turn(&mut s);
    // Combust at turn end, Brutality at turn start; Dark Strike doesn't count.
    assert_eq!(s.player.powers.get(Power::Strength), 2);
}

#[test]
fn metallicize_gives_3_or_4_block_at_turn_end_ignoring_dexterity() {
    for (name, block) in [("Metallicize", 3), ("Metallicize+", 4)] {
        let mut s = cultists(1, &[name], true);
        s.player.powers.add(Power::Dexterity, 2);
        let hp = s.player.hp;
        play(&mut s, name, None);
        end_turn(&mut s);
        assert_eq!(hp - s.player.hp, 6 - block, "Dark Strike 6 against Metallicize");
    }
}

#[test]
fn demon_form_gains_2_or_3_strength_at_each_turn_start() {
    for (name, str) in [("Demon Form", 2), ("Demon Form+", 3)] {
        let mut s = cultists(1, &[name], false);
        play(&mut s, name, None);
        assert_eq!(s.player.powers.get(Power::Strength), 0);
        end_turn(&mut s);
        assert_eq!(s.player.powers.get(Power::Strength), str);
        end_turn(&mut s);
        assert_eq!(s.player.powers.get(Power::Strength), 2 * str);
    }
}

#[test]
fn rage_gives_block_per_attack_played_this_turn_only() {
    for (name, per) in [("Rage", 3), ("Rage+", 5)] {
        let mut s = cultists(1, &[name, "Strike", "Defend", "Strike"], false);
        s.player.energy = 4;
        play(&mut s, name, None);
        assert_eq!(s.player.block, 0, "Rage is a Skill");
        play(&mut s, "Strike", Some(0));
        assert_eq!(s.player.block, per);
        play(&mut s, "Defend", None);
        assert_eq!(s.player.block, per + 5);
        play(&mut s, "Strike", Some(0));
        assert_eq!(s.player.block, 2 * per + 5);
        end_turn(&mut s);
        assert_eq!(s.player.powers.get(Power::Rage), 0, "removed at turn end");
        let strike = card("Strike");
        assert!(s.hand.count(strike) > 0);
        play(&mut s, "Strike", Some(0));
        assert_eq!(s.player.block, 0);
    }
}

#[test]
fn body_slam_does_not_count_rage_block_from_its_own_play() {
    let mut s = cultists(1, &["Rage", "Defend", "Body Slam"], false);
    play(&mut s, "Rage", None);
    play(&mut s, "Defend", None);
    play(&mut s, "Body Slam", Some(0));
    assert_eq!(100 - s.monsters[0].hp, 5);
    assert_eq!(s.player.block, 8);
}

#[test]
fn training_pool_and_held_out_power_cards() {
    let pool: Vec<&str> = deck_cards().map(|c| c.name()).collect();
    for name in ["Combust", "Combust+", "Brutality", "Brutality+", "Rupture", "Rupture+"] {
        assert!(pool.contains(&name), "{name} in the training pool");
    }
    let held: Vec<&str> = held_out_cards().map(|c| c.name()).collect();
    for name in ["Metallicize", "Metallicize+", "Demon Form", "Demon Form+", "Rage", "Rage+"] {
        assert!(held.contains(&name), "{name} held out");
        assert!(!pool.contains(&name), "{name} not in the training pool");
    }
}
