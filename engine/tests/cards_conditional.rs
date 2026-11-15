//! Cards with conditional rows (triggers and conditions, step 4), base and
//! upgraded, with values from slaythespire.wiki.gg.

mod common;
use common::*;
use sts_engine::cards::{class_cards, deck_cards, held_out_cards, CardClass};
use sts_engine::monsters::MonsterKind as K;
use sts_engine::*;

/// A Cultist at 100 HP, `hand`, 3 energy. `attacking`: its intent is Dark
/// Strike (an attack), else Incantation (a buff).
fn cultist(hand: &[&str], attacking: bool) -> CombatState {
    let mut s = vs(&[K::Cultist], hand, Some(100));
    s.monsters[0].set_move(if attacking { 1 } else { 0 });
    s
}

#[test]
fn spot_weakness_gains_3_or_4_strength_only_against_an_attack_intent() {
    for (name, str) in [("Spot Weakness", 3), ("Spot Weakness+", 4)] {
        assert!(card(name).def().targeted());
        let mut s = cultist(&[name], true);
        play(&mut s, name, Some(0));
        assert_eq!(s.player.powers.get(Power::Strength), str);
        assert_eq!(s.player.energy, 2);
        let mut s = cultist(&[name], false);
        play(&mut s, name, Some(0));
        assert_eq!(s.player.powers.get(Power::Strength), 0);
        assert_eq!(s.discard().count(card(name)), 1);
    }
}

#[test]
fn dropkick_gives_energy_and_draw_only_on_a_vulnerable_target() {
    for (name, dmg) in [("Dropkick", 5), ("Dropkick+", 8)] {
        let mut s = cultist(&[name], true);
        s.set_draw(Pile::from_cards(&[card("Strike")]));
        play(&mut s, name, Some(0));
        assert_eq!((100 - s.monsters[0].hp, s.player.energy, s.hand.len()), (dmg, 2, 0));

        let mut s = cultist(&[name], true);
        s.set_draw(Pile::from_cards(&[card("Strike")]));
        s.monsters[0].powers.add(Power::Vulnerable, 1);
        play(&mut s, name, Some(0));
        assert_eq!(100 - s.monsters[0].hp, dmg * 3 / 2);
        assert_eq!(s.player.energy, 3, "1 spent, 1 gained");
        assert_eq!(s.hand.count(card("Strike")), 1);
    }
}

#[test]
fn go_for_the_eyes_applies_weak_only_against_an_attack_intent() {
    for (name, dmg, weak) in [("Go for the Eyes", 3, 1), ("Go for the Eyes+", 4, 2)] {
        let mut s = cultist(&[name], true);
        play(&mut s, name, Some(0));
        assert_eq!((100 - s.monsters[0].hp, s.player.energy), (dmg, 3));
        assert_eq!(s.monsters[0].powers.get(Power::Weak), weak);
        let mut s = cultist(&[name], false);
        play(&mut s, name, Some(0));
        assert_eq!(100 - s.monsters[0].hp, dmg);
        assert_eq!(s.monsters[0].powers.get(Power::Weak), 0);
    }
}

#[test]
fn ftl_draws_only_while_fewer_than_3_or_4_cards_were_played_before_it() {
    for (name, dmg, limit) in [("FTL", 5, 3), ("FTL+", 6, 4)] {
        for before in 0..=limit {
            let mut hand = vec!["Slice"; before];
            hand.push(name);
            let mut s = cultist(&hand, true);
            s.set_draw(Pile::from_cards(&[card("Strike")]));
            for _ in 0..before {
                play(&mut s, "Slice", Some(0));
            }
            assert_eq!(s.cards_played_this_turn, before as u8);
            let hp = s.monsters[0].hp;
            play(&mut s, name, Some(0));
            assert_eq!(hp - s.monsters[0].hp, dmg);
            assert_eq!(s.cards_played_this_turn, before as u8 + 1);
            let drew = s.hand.count(card("Strike")) == 1;
            assert_eq!(drew, before < limit, "{name} after {before} cards");
        }
    }
}

#[test]
fn cards_played_this_turn_resets_at_turn_start() {
    let mut s = cultist(&["Strike", "Defend"], false);
    s.monsters[0].hp = 100;
    play(&mut s, "Strike", Some(0));
    play(&mut s, "Defend", None);
    assert_eq!(s.cards_played_this_turn, 2);
    end_turn(&mut s);
    assert_eq!(s.cards_played_this_turn, 0);
}

#[test]
fn a_failed_row_is_skipped_but_later_effects_and_the_card_finish() {
    // Dropkick on a non-Vulnerable target still discards and leaves no pending event.
    let mut s = cultist(&["Dropkick"], true);
    s.set_draw(Pile::from_cards(&[card("Strike"), card("Defend")]));
    play(&mut s, "Dropkick", Some(0));
    assert!(s.awaiting_action());
    assert_eq!(s.discard().count(card("Dropkick")), 1);
}

#[test]
fn pools_training_and_held_out() {
    let ironclad: Vec<&str> = deck_cards().map(|c| c.name()).collect();
    for n in ["Spot Weakness", "Spot Weakness+", "Dropkick", "Dropkick+"] {
        assert!(ironclad.contains(&n), "{n} joins the training pool");
    }
    let held: Vec<&str> = held_out_cards().map(|c| c.name()).collect();
    for n in ["Go for the Eyes", "Go for the Eyes+", "FTL", "FTL+"] {
        assert!(held.contains(&n));
        assert!(!ironclad.contains(&n), "{n} never enters deck_cards()");
    }
    assert!(class_cards(CardClass::Silent).all(|c| !held_out_cards().any(|h| h == c)));
    assert_eq!(class_cards(CardClass::Silent).count(), 30, "Silent pool unchanged");
}
