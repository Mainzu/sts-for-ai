//! The rest of the in-scope cards, base and upgraded, with values from
//! slaythespire.wiki.gg; plus Status cards.

mod common;
use common::*;
use sts_engine::monsters::MonsterKind as K;
use sts_engine::*;

/// One Jaw Worm at 100 HP, `hand`, 3 energy.
fn worm(hand: &[&str]) -> CombatState {
    vs(&[K::JawWorm], hand, Some(100))
}

fn auto_play(s: &mut CombatState, name: &str) {
    let target = card(name).def().targeted().then_some(0);
    play(s, name, target);
}

/// Monster 0's HP lost and the energy spent when `name` is played alone.
fn damage_and_cost(name: &str) -> (i16, i16) {
    let mut s = worm(&[name]);
    auto_play(&mut s, name);
    (100 - s.monsters[0].hp, 3 - s.player.energy)
}

#[test]
fn anger_deals_6_or_8_and_adds_a_copy_to_discard() {
    for (name, dmg) in [("Anger", 6), ("Anger+", 8)] {
        assert_eq!(damage_and_cost(name), (dmg, 0));
        let mut s = worm(&[name]);
        auto_play(&mut s, name);
        assert_eq!(s.discard().count(card(name)), 2); // the played card and its copy
        assert_eq!(s.created, 1);
    }
}

#[test]
fn body_slam_deals_block_plus_strength() {
    for (name, cost) in [("Body Slam", 1), ("Body Slam+", 0)] {
        let mut s = worm(&[name]);
        s.player.block = 13;
        s.player.powers.add(Power::Strength, 2);
        auto_play(&mut s, name);
        assert_eq!(s.monsters[0].hp, 85);
        assert_eq!(3 - s.player.energy, cost);
    }
}

#[test]
fn clash_deals_14_or_18_only_with_all_attacks_in_hand() {
    for (name, dmg) in [("Clash", 14), ("Clash+", 18)] {
        assert_eq!(damage_and_cost(name), (dmg, 0));
        let s = worm(&[name, "Strike"]);
        assert!(s.is_legal(Action::Play { card: card(name), target: Some(0) }));
        let s = worm(&[name, "Defend"]);
        assert!(!s.is_legal(Action::Play { card: card(name), target: Some(0) }));
        let s = worm(&[name, "Wound"]);
        assert!(!s.is_legal(Action::Play { card: card(name), target: Some(0) }));
    }
}

#[test]
fn cleave_hits_all_enemies_for_8_or_11() {
    for (name, dmg) in [("Cleave", 8), ("Cleave+", 11)] {
        let mut s = vs(&[K::JawWorm, K::Cultist, K::FungiBeast], &[name], Some(50));
        assert!(!card(name).def().targeted());
        auto_play(&mut s, name);
        for m in &s.monsters[..3] {
            assert_eq!(m.hp, 50 - dmg);
        }
        assert_eq!(s.player.energy, 2);
    }
}

#[test]
fn clothesline_deals_12_or_14_and_applies_2_or_3_weak() {
    for (name, dmg, weak) in [("Clothesline", 12, 2), ("Clothesline+", 14, 3)] {
        assert_eq!(damage_and_cost(name), (dmg, 2));
        let mut s = worm(&[name]);
        auto_play(&mut s, name);
        assert_eq!(s.monsters[0].powers.get(Power::Weak), weak);
    }
}

#[test]
fn iron_wave_blocks_and_deals_5_or_7() {
    for (name, n) in [("Iron Wave", 5), ("Iron Wave+", 7)] {
        assert_eq!(damage_and_cost(name), (n, 1));
        let mut s = worm(&[name]);
        auto_play(&mut s, name);
        assert_eq!(s.player.block, n);
    }
}

#[test]
fn pommel_strike_deals_9_or_10_and_draws_1_or_2() {
    for (name, dmg, draws) in [("Pommel Strike", 9, 1), ("Pommel Strike+", 10, 2)] {
        assert_eq!(damage_and_cost(name), (dmg, 1));
        let mut s = worm(&[name]);
        s.set_draw(Pile::from_cards(&[card("Defend"); 3]));
        auto_play(&mut s, name);
        assert_eq!(s.hand.len(), draws);
    }
}

#[test]
fn thunderclap_hits_all_for_4_or_7_and_applies_1_vulnerable() {
    for (name, dmg) in [("Thunderclap", 4), ("Thunderclap+", 7)] {
        let mut s = vs(&[K::JawWorm, K::Cultist], &[name], Some(50));
        auto_play(&mut s, name);
        for m in &s.monsters[..2] {
            assert_eq!(m.hp, 50 - dmg);
            assert_eq!(m.powers.get(Power::Vulnerable), 1);
        }
        assert_eq!(s.player.energy, 2);
    }
}

#[test]
fn twin_strike_hits_twice_for_5_or_7_with_strength_each_time() {
    for (name, dmg) in [("Twin Strike", 5), ("Twin Strike+", 7)] {
        assert_eq!(damage_and_cost(name), (2 * dmg, 1));
        let mut s = worm(&[name]);
        s.player.powers.add(Power::Strength, 3);
        auto_play(&mut s, name);
        assert_eq!(s.monsters[0].hp, 100 - 2 * (dmg + 3));
    }
}

#[test]
fn wild_strike_deals_12_or_17_and_shuffles_a_wound_into_draw() {
    for (name, dmg) in [("Wild Strike", 12), ("Wild Strike+", 17)] {
        assert_eq!(damage_and_cost(name), (dmg, 1));
        let mut s = worm(&[name]);
        auto_play(&mut s, name);
        assert_eq!(s.draw().count(card("Wound")), 1);
        assert_eq!(s.created, 1);
    }
}

#[test]
fn heavy_blade_counts_strength_3_or_5_times() {
    for (name, mult) in [("Heavy Blade", 3), ("Heavy Blade+", 5)] {
        assert_eq!(damage_and_cost(name), (14, 2));
        let mut s = worm(&[name]);
        s.player.powers.add(Power::Strength, 2);
        auto_play(&mut s, name);
        assert_eq!(s.monsters[0].hp, 100 - (14 + 2 * mult));
    }
}

#[test]
fn perfected_strike_adds_2_or_3_per_strike_card_counting_itself() {
    for (name, per) in [("Perfected Strike", 2), ("Perfected Strike+", 3)] {
        assert_eq!(damage_and_cost(name), (6 + per, 2)); // only itself
        let mut s = worm(&[name, "Strike", "Defend"]);
        s.set_draw(Pile::from_cards(&[card("Twin Strike+"), card("Bash")]));
        s.set_discard(Pile::from_cards(&[card("Pommel Strike"), card("Wild Strike")]));
        s.set_exhaust(Pile::from_cards(&[card("Strike")])); // exhausted cards don't count
        auto_play(&mut s, name);
        assert_eq!(s.monsters[0].hp, 100 - (6 + per * 5));
    }
}

#[test]
fn sword_boomerang_hits_a_random_enemy_3_or_4_times_for_3() {
    for (name, hits) in [("Sword Boomerang", 3), ("Sword Boomerang+", 4)] {
        // One enemy: no chance involved.
        assert_eq!(damage_and_cost(name), (3 * hits, 1));
        // Two enemies: each hit is a chance node over the living enemies.
        let mut s = vs(&[K::JawWorm, K::Cultist], &[name], Some(50));
        assert!(!card(name).def().targeted());
        auto_play(&mut s, name);
        assert_eq!(s.pending, Some(ChanceEvent::RandomTarget { amount: 3 }));
        let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(16) else { panic!() };
        assert_eq!(v.len(), 2);
        let mut rng = Rng::new(3);
        s.advance(&mut rng);
        assert!(s.awaiting_action());
        assert_eq!(100 - s.monsters[0].hp - s.monsters[1].hp, 3 * hits);
    }
}

#[test]
fn bloodletting_loses_3_hp_and_gains_2_or_3_energy() {
    for (name, energy) in [("Bloodletting", 2), ("Bloodletting+", 3)] {
        let mut s = worm(&[name]);
        let hp = s.player.hp;
        auto_play(&mut s, name);
        assert_eq!(s.player.hp, hp - 3);
        assert_eq!(s.player.energy, 3 + energy);
    }
}

#[test]
fn hemokinesis_loses_2_hp_and_deals_15_or_20() {
    for (name, dmg) in [("Hemokinesis", 15), ("Hemokinesis+", 20)] {
        assert_eq!(damage_and_cost(name), (dmg, 1));
        let mut s = worm(&[name]);
        let hp = s.player.hp;
        auto_play(&mut s, name);
        assert_eq!(s.player.hp, hp - 2);
    }
}

#[test]
fn pummel_hits_4_or_5_times_for_2_and_exhausts() {
    for (name, hits) in [("Pummel", 4), ("Pummel+", 5)] {
        assert_eq!(damage_and_cost(name), (2 * hits, 1));
        let mut s = worm(&[name]);
        auto_play(&mut s, name);
        assert_eq!(s.exhaust().count(card(name)), 1);
        assert!(s.discard().is_empty());
    }
}

#[test]
fn uppercut_deals_13_and_applies_weak_and_vulnerable() {
    for (name, n) in [("Uppercut", 1), ("Uppercut+", 2)] {
        assert_eq!(damage_and_cost(name), (13, 2));
        let mut s = worm(&[name]);
        auto_play(&mut s, name);
        assert_eq!(s.monsters[0].powers.get(Power::Weak), n);
        assert_eq!(s.monsters[0].powers.get(Power::Vulnerable), n);
    }
}

#[test]
fn inflame_gains_2_or_3_strength_and_leaves_combat() {
    for (name, n) in [("Inflame", 2), ("Inflame+", 3)] {
        let mut s = worm(&[name]);
        auto_play(&mut s, name);
        assert_eq!(s.player.powers.get(Power::Strength), n);
        assert_eq!(s.player.energy, 2);
        assert_eq!(total_cards(&s), 0); // not discarded, not exhausted
        assert_eq!(s.removed, 1);
    }
}

#[test]
fn flex_gains_2_or_4_strength_for_this_turn() {
    for (name, n) in [("Flex", 2), ("Flex+", 4)] {
        let mut s = worm(&[name, "Strike"]);
        s.player.hp = 500;
        auto_play(&mut s, name);
        assert_eq!(s.player.energy, 3);
        assert_eq!(s.player.powers.get(Power::Strength), n);
        auto_play(&mut s, "Strike");
        assert_eq!(s.monsters[0].hp, 100 - (6 + n));
        s.monsters[0].moves = [sts_engine::monsters::CHOMP, sts_engine::monsters::NO_MOVE];
        end_turn(&mut s);
        assert_eq!(s.player.powers.get(Power::Strength), 0);
        assert_eq!(s.player.powers.get(Power::LoseStrength), 0);
    }
}

#[test]
fn carnage_deals_20_or_28_and_is_exhausted_if_held_at_end_of_turn() {
    for (name, dmg) in [("Carnage", 20), ("Carnage+", 28)] {
        assert_eq!(damage_and_cost(name), (dmg, 2));
        let mut s = worm(&[name]);
        s.player.hp = 500;
        s.monsters[0].moves = [sts_engine::monsters::CHOMP, sts_engine::monsters::NO_MOVE];
        s.apply_action(Action::EndTurn).unwrap();
        assert_eq!(s.exhaust().count(card(name)), 1);
        assert_eq!(s.discard().count(card(name)), 0);
    }
}

#[test]
fn status_cards() {
    // Slimed: costs 1, does nothing, exhausts.
    let mut s = worm(&["Slimed"]);
    auto_play(&mut s, "Slimed");
    assert_eq!(s.player.energy, 2);
    assert_eq!(s.exhaust().count(card("Slimed")), 1);
    // Wound and Dazed can't be played; Dazed is exhausted at end of turn, Wound discarded.
    let mut s = worm(&["Wound", "Dazed"]);
    s.player.hp = 500;
    assert_eq!(s.legal_actions(), vec![Action::EndTurn]);
    s.monsters[0].moves = [sts_engine::monsters::CHOMP, sts_engine::monsters::NO_MOVE];
    s.apply_action(Action::EndTurn).unwrap();
    assert_eq!(s.exhaust().count(card("Dazed")), 1);
    assert_eq!(s.discard().count(card("Wound")), 1);
}

#[test]
fn every_in_scope_card_is_defined_base_and_upgraded() {
    let names = [
        "Strike", "Defend", "Bash", "Anger", "Body Slam", "Clash", "Cleave", "Clothesline", "Iron Wave",
        "Pommel Strike", "Shrug It Off", "Thunderclap", "Twin Strike", "Wild Strike", "Heavy Blade",
        "Perfected Strike", "Sword Boomerang", "Bloodletting", "Hemokinesis", "Pummel", "Uppercut", "Inflame",
        "Flex", "Carnage", "Spot Weakness", "Dropkick", "Combust", "Brutality", "Rupture",
    ];
    for n in names {
        let base = card(n);
        let up = card(&format!("{n}+"));
        assert!(!base.upgraded() && up.upgraded() && base.kind() == up.kind());
    }
    assert_eq!(sts_engine::cards::deck_cards().count(), names.len() * 2);
}
