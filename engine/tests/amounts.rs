//! Amount expressions (docs/specs/amount-expressions.md): `base + k ×
//! quantity` attacks, card tags, the X-cost keyword and Whirlwind.

mod common;

use common::*;
use sts_engine::cards::{class_cards, held_out_cards, CardClass, Tag};
use sts_engine::codec;
use sts_engine::effects::{Effect, Quantity};
use sts_engine::monsters::MonsterKind as K;
use sts_engine::state::Stage;
use sts_engine::*;

fn worm(hand: &[&str]) -> CombatState {
    vs(&[K::JawWorm], hand, Some(100))
}

#[test]
fn body_slam_deals_block() {
    for name in ["Body Slam", "Body Slam+"] {
        let mut s = worm(&[name]);
        s.player.block = 13;
        play(&mut s, name, Some(0));
        assert_eq!(s.monsters[0].hp, 87, "{name}");
    }
}

#[test]
fn heavy_blade_counts_strength_three_times() {
    for (name, str_, dmg) in [("Heavy Blade", 2, 20), ("Heavy Blade", -1, 11), ("Heavy Blade+", 2, 24)] {
        let mut s = worm(&[name]);
        s.player.powers.add(Power::Strength, str_);
        play(&mut s, name, Some(0));
        assert_eq!(s.monsters[0].hp, 100 - dmg, "{name} at Strength {str_}");
    }
}

#[test]
fn strike_tag_is_the_strike_name() {
    for c in CardId::all() {
        let d = c.def();
        assert_eq!(d.has_tag(Tag::Strike), d.name.contains("Strike"), "{}", d.name);
    }
}

#[test]
fn whirlwind_spends_all_energy_hits_all_x_times() {
    for (name, per) in [("Whirlwind", 5), ("Whirlwind+", 8)] {
        let mut s = vs(&[K::JawWorm, K::Cultist], &[name], Some(40));
        assert!(!card(name).def().targeted());
        play(&mut s, name, None);
        assert_eq!(s.player.energy, 0);
        assert_eq!((s.monsters[0].hp, s.monsters[1].hp), (40 - 3 * per, 40 - 3 * per), "{name}");
    }
}

#[test]
fn whirlwind_at_zero_energy_is_legal_and_deals_nothing() {
    let mut s = worm(&["Whirlwind"]);
    s.player.energy = 0;
    assert!(s.legal_actions().contains(&Action::Play { card: card("Whirlwind"), target: None }));
    play(&mut s, "Whirlwind", None);
    assert_eq!(s.monsters[0].hp, 100);
    assert_eq!(s.discard().count(card("Whirlwind")), 1);
}

#[test]
fn whirlwind_x_uses_strength_and_vulnerable_per_hit() {
    let mut s = worm(&["Whirlwind"]);
    s.player.energy = 2;
    s.player.powers.add(Power::Strength, 1);
    s.monsters[0].powers.add(Power::Vulnerable, 2);
    play(&mut s, "Whirlwind", None);
    assert_eq!(s.monsters[0].hp, 100 - 2 * 9); // (5 + 1) × 1.5 = 9, twice
}

#[test]
fn x_survives_codec_round_trip() {
    let mut s = worm(&["Whirlwind"]);
    s.stage = Stage::PlayingCard { card: card("Whirlwind"), target: None, next: 0, hit: 0, x: 2, more: Default::default() };
    let bytes = codec::encode(&s);
    assert_eq!(codec::decode(&bytes), s);
    // X = 0 writes today's stage bytes.
    let mut t = s.clone();
    t.stage = Stage::PlayingCard { card: card("Whirlwind"), target: None, next: 0, hit: 0, x: 0, more: Default::default() };
    assert_eq!(codec::encode(&t).len() + 1, bytes.len());
    assert_eq!(codec::decode(&codec::encode(&t)), t);
}

#[test]
fn only_one_quantity_per_scaled_damage() {
    for c in CardId::all() {
        for e in c.def().all_effects() {
            if let Effect::ScaledDamage { amount, hits, .. } = *e {
                assert!(amount.of.is_none() || hits.of.is_none(), "{}", c.name());
                assert!(amount.of.is_some() || hits.of.is_some(), "{} reads nothing: use Damage", c.name());
            }
        }
    }
    let x_hits = |c: &str| {
        card(c).def().all_effects().any(|e| matches!(e, Effect::ScaledDamage { hits, .. } if hits.of == Some(Quantity::EnergySpent)))
    };
    assert!(x_hits("Whirlwind") && card("Whirlwind").def().x_cost());
}

#[test]
fn proving_cards_in_no_pool() {
    let set = card_sets::get("proving").expect("the proving set");
    let proving: Vec<&str> = set.iter().map(|c| c.name()).collect();
    // Each spec appends its own (Whirlwind first, spec 2).
    assert_eq!(proving[..2], ["Whirlwind", "Whirlwind+"]);
    assert!(proving.len() % 2 == 0);
    for class in [CardClass::Ironclad, CardClass::Silent, CardClass::Colorless] {
        assert!(class_cards(class).all(|c| !set.contains(&c)));
    }
    assert!(held_out_cards().all(|c| !set.contains(&c)));
}
