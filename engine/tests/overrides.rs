//! Per-copy overrides (docs/specs/per-copy-overrides.md), as changed
//! copies by value (docs/specs/sparse-piles.md): Rampage grows its own copy,
//! equal copies are one card id, the codec carries them, and Retain.

mod common;

use common::*;
use sts_engine::codec;
use sts_engine::monsters::MonsterKind as K;
use sts_engine::codec::changed_ranks;
use sts_engine::registry::{copy_of, VARIANT_BASE};
use sts_engine::state::card_damage;
use sts_engine::*;

fn worm(hand: &[&str]) -> CombatState {
    vs(&[K::JawWorm], hand, Some(200))
}

/// The changed copy of `base` at `damage` the state names, if any.
fn variant(s: &CombatState, base: &str, damage: i16) -> Option<CardId> {
    changed_ranks(s)
        .into_iter()
        .find(|&c| copy_of(c) == Some((card(base), sts_engine::registry::Overrides { damage: Some(damage), level: card(base).def().level, cost: None })))
}

/// How many changed copies the state names.
fn n_changed(s: &CombatState) -> usize {
    changed_ranks(s).len()
}

#[test]
fn rampage_grows_its_own_copy() {
    let mut s = worm(&["Rampage", "Rampage"]);
    play(&mut s, "Rampage", Some(0));
    assert_eq!(s.monsters[0].hp, 192);
    let v13 = variant(&s, "Rampage", 13).expect("a Rampage at 13");
    assert_eq!(s.discard().count(v13), 1);
    assert_eq!(s.hand.count(card("Rampage")), 1, "the other copy is still 8");
    let d = s.binding.def(v13);
    assert_eq!((d.name, card_damage(d)), ("Rampage{damage=13/combat}", 13));
    // Play the grown copy: 13, then it is 18 and the 13 variant is gone.
    s.hand.add(v13, 1);
    s.discard_mut().remove(v13, 1);
    s.player.energy = 3;
    s.apply_action(Action::Play { card: v13, target: Some(0) }).unwrap();
    assert_eq!(s.monsters[0].hp, 192 - 13);
    assert!(variant(&s, "Rampage", 13).is_none());
    let v18 = variant(&s, "Rampage", 18).expect("now 18");
    assert_eq!((s.discard().count(v18), n_changed(&s)), (1, 1));
}

#[test]
fn copies_at_the_same_damage_are_one_key() {
    let mut s = worm(&["Rampage", "Rampage"]);
    s.player.energy = 5;
    play(&mut s, "Rampage", Some(0));
    play(&mut s, "Rampage", Some(0));
    let v13 = variant(&s, "Rampage", 13).unwrap();
    assert_eq!((s.discard().count(v13), n_changed(&s)), (2, 1));
}

#[test]
fn variants_are_canonical() {
    // Rampage grows to 13, Rampage+ to 16, in either order: equal states.
    let run = |first: &str, second: &str| {
        let mut s = worm(&["Rampage", "Rampage+"]);
        s.player.energy = 5;
        play(&mut s, first, Some(0));
        play(&mut s, second, Some(0));
        s.monsters[0].hp = 100;
        s
    };
    let (a, b) = (run("Rampage", "Rampage+"), run("Rampage+", "Rampage"));
    assert_eq!(changed_ranks(&a), changed_ranks(&b));
    assert_eq!(a.discard(), b.discard());
}

#[test]
fn codec_round_trips_variants() {
    let mut s = worm(&["Rampage", "Rampage+", "Defend"]);
    s.player.energy = 5;
    play(&mut s, "Rampage", Some(0));
    play(&mut s, "Rampage+", Some(0));
    let b = codec::encode(&s);
    assert_eq!(codec::decode(&b), s);
    let mut out = Vec::new();
    let v = variant(&s, "Rampage", 13).unwrap();
    let ranks = changed_ranks(&s);
    codec::encode_action_in(&ranks, Action::Play { card: v, target: Some(0) }, &mut out);
    assert_eq!(out, [1, VARIANT_BASE as u8, 1], "the rank byte, as the variant id was");
    assert_eq!(codec::decode_action_in(&ranks, &out, &mut 0), Some(Action::Play { card: v, target: Some(0) }));
}

#[test]
fn protect_is_retained() {
    let mut s = worm(&["Protect", "Defend"]);
    s.set_draw(Pile::from_cards(&[card("Strike"); 10]));
    end_turn(&mut s);
    assert_eq!(s.hand.count(card("Protect")), 1);
    assert_eq!(s.hand.count(card("Defend")), 0);
    assert_eq!(s.hand.len(), 6, "the retained card plus the 5 drawn");
    play(&mut s, "Protect", None);
    assert_eq!(s.player.block, 12);
}

#[test]
fn slots_are_ordered_by_value() {
    // Rampage+ grows first (interned first), yet Rampage's variant takes
    // slot 0: the order is the cards' own, the same in every process.
    let mut s = worm(&["Rampage", "Rampage+"]);
    s.player.energy = 5;
    play(&mut s, "Rampage+", Some(0));
    play(&mut s, "Rampage", Some(0));
    let slot = |i: usize| copy_of(changed_ranks(&s)[i]).unwrap().0;
    assert_eq!((slot(0), slot(1)), (card("Rampage"), card("Rampage+")));
}

/// Moves `c` from the discard pile to hand and plays it on monster 0.
fn replay(s: &mut CombatState, c: CardId) -> CardId {
    s.discard_mut().remove(c, 1);
    s.hand.add(c, 1);
    s.player.energy = 3;
    s.apply_action(Action::Play { card: c, target: Some(0) }).unwrap();
    match s.discard().iter().find(|&(d, _)| copy_of(d).is_some_and(|(_, o)| o.damage > Some(card_damage(s.binding.def(c))))) {
        Some((d, _)) => d,
        None => c,
    }
}

#[test]
fn many_grown_copies_all_grow() {
    // Six Rampages at 13, 18, 23, 28, 33 and 38 (past the old 4 variants).
    let mut s = worm(&["Rampage"; 6]);
    s.monsters[0].hp = 999;
    s.monsters[0].max_hp = 999;
    let base = card("Rampage");
    for plays in 1..=6 {
        let mut c = base;
        for _ in 0..plays {
            if c == base {
                s.player.energy = 3;
                s.apply_action(Action::Play { card: base, target: Some(0) }).unwrap();
                c = variant(&s, "Rampage", 13).unwrap();
            } else {
                c = replay(&mut s, c);
            }
        }
    }
    assert_eq!(n_changed(&s), 6);
    for d in [13, 18, 23, 28, 33, 38] {
        assert_eq!(s.discard().count(variant(&s, "Rampage", d).unwrap()), 1, "a copy at {d}");
    }
    // The 38 copy grows to 43.
    let v38 = variant(&s, "Rampage", 38).unwrap();
    replay(&mut s, v38);
    assert!(variant(&s, "Rampage", 43).is_some() && variant(&s, "Rampage", 38).is_none());
    assert_eq!(n_changed(&s), 6);
}

#[test]
fn variant_state_bytes_are_pinned() {
    // Variant ids (VARIANT_BASE..) are written as raw bytes: widening the
    // generated slots (docs/specs/pack-slots.md) must not move them.
    let mut s = worm(&["Rampage", "Rampage+", "Defend"]);
    s.player.energy = 5;
    play(&mut s, "Rampage", Some(0));
    play(&mut s, "Rampage+", Some(0));
    assert_eq!(VARIANT_BASE, 144);
    let hex: String = codec::encode(&s).iter().map(|b| format!("{b:02x}")).collect();
    assert_eq!(hex, "010000a001a001000600000102f0029003000000ffff000001020100029001910100010000000000a001020002027c1a7d20");
}

#[test]
fn a_copy_at_its_own_damage_is_the_plain_card() {
    use sts_engine::registry::{changed_copy, Overrides};
    let r = card("Rampage");
    let own = card_damage(r.def());
    assert_eq!(changed_copy(r, r.def(), Overrides { damage: Some(own), level: r.def().level, cost: None }).unwrap(), r);
    assert_ne!(changed_copy(r, r.def(), Overrides { damage: Some(own + 5), level: r.def().level, cost: None }).unwrap(), r);
}
