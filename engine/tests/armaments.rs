//! Armaments (docs/specs/card-upgrades.md, building block C6): upgrade a
//! card in hand for the rest of combat; Armaments+ upgrades every card in
//! hand. Numbers from wiki.gg and sts_lightspeed (`Cards.h`,
//! `BattleContext.cpp`, `Actions.cpp`): cost 1, Skill, Block 5 at both
//! levels; cards that can't be upgraded (statuses, at their max level) are
//! never picked, one candidate is upgraded without a choice.

mod common;

use sts_engine::cards::CardType;
use sts_engine::registry::{bind, load_pack};
use sts_engine::*;

const PACK: &str = include_str!("../../content/packs/act1-ironclad.json");

/// A combat against a Jaw Worm at 200 HP holding `hand` (official names or
/// `gen:` pack names), 10 energy, empty piles. Returns the state and the
/// hand's ids in order.
fn setup(hand: &[&str]) -> (CombatState, Vec<CardId>) {
    load_pack(PACK).unwrap();
    let (ids, b) = bind(hand).unwrap();
    let mut s = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &mut Rng::new(1));
    s.hand = Hand::from_cards(&ids);
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    s.set_exhaust(Pile::default());
    s.player.energy = 10;
    let m = &mut s.monsters[0];
    m.hp = 200;
    m.max_hp = 200;
    m.block = 0;
    m.powers = Default::default();
    (s, ids)
}

fn play(s: &mut CombatState, c: CardId) {
    let target = if s.binding.def(c).targeted() { Some(0) } else { None };
    s.apply_action(Action::Play { card: c, target }).unwrap();
}

fn hand_names(s: &CombatState) -> Vec<String> {
    let mut v: Vec<String> = s.hand.iter().flat_map(|(c, n)| std::iter::repeat(s.binding.def(c).name.to_string()).take(n as usize)).collect();
    v.sort();
    v
}

fn choices(s: &CombatState) -> Vec<String> {
    let mut v: Vec<String> = s
        .legal_actions()
        .into_iter()
        .filter_map(|a| if let Action::Choose(c) = a { Some(s.binding.def(c).name.to_string()) } else { None })
        .collect();
    v.sort();
    v
}

#[test]
fn armaments_as_the_sources() {
    load_pack(PACK).unwrap();
    for n in ["gen:Armaments", "gen:Armaments+"] {
        let (ids, b) = bind(&[n]).unwrap();
        let d = b.def(ids[0]);
        assert_eq!((d.cost(), d.ty, d.effects[0]), (1, CardType::Skill, sts_engine::effects::Effect::Block(5)), "{n}");
    }
    // Armaments+ is its unique upgrade (a separate entry).
    let (ids, b) = bind(&["gen:Armaments+"]).unwrap();
    assert_eq!(b.def(ids[0]).name, "gen:Armaments+");
    assert_eq!(sts_engine::registry::upgrade_name("gen:Armaments").unwrap().as_deref(), Some("gen:Armaments+"));
}

#[test]
fn picks_only_what_can_be_upgraded() {
    let (mut s, ids) = setup(&["gen:Armaments", "Strike", "Bash+", "Wound", "gen:Searing Blow+"]);
    play(&mut s, ids[0]);
    assert_eq!(s.player.block, 5);
    assert_eq!(choices(&s), ["Strike", "gen:Searing Blow+"]);
    s.apply_action(Action::Choose(ids[4])).unwrap();
    assert!(s.pick().is_none());
    assert_eq!(hand_names(&s), ["Bash+", "Strike", "Wound", "gen:Searing Blow+2"]);
    let sb = s.hand.iter().map(|(c, _)| c).find(|&c| s.binding.def(c).name == "gen:Searing Blow+2").unwrap();
    assert_eq!(sts_engine::state::card_damage(s.binding.def(sb)), 21);
    let hp = s.monsters[0].hp;
    play(&mut s, sb);
    assert_eq!(hp - s.monsters[0].hp, 21);
}

#[test]
fn armaments_plus_upgrades_the_hand() {
    let (mut s, ids) = setup(&["gen:Armaments+", "Strike", "Strike", "Bash+", "Wound", "gen:Searing Blow+", "gen:Searing Blow"]);
    play(&mut s, ids[0]);
    assert_eq!(s.player.block, 5);
    assert_eq!(hand_names(&s), ["Bash+", "Strike+", "Strike+", "Wound", "gen:Searing Blow+", "gen:Searing Blow+2"]);
}

#[test]
fn no_pick_without_a_candidate_and_one_is_forced() {
    let (mut s, ids) = setup(&["gen:Armaments", "Bash+", "Wound"]);
    play(&mut s, ids[0]);
    assert!(s.pick().is_none(), "nothing to upgrade: no pick");
    assert_eq!(hand_names(&s), ["Bash+", "Wound"]);
    let (mut s, ids) = setup(&["gen:Armaments", "Bash+", "Defend", "Defend"]);
    play(&mut s, ids[0]);
    assert!(s.pick().is_none(), "one distinct candidate: upgraded at once");
    assert_eq!(hand_names(&s), ["Bash+", "Defend", "Defend+"]);
}

#[test]
fn upgraded_rampage_keeps_its_growth() {
    let (mut s, ids) = setup(&["Rampage", "gen:Armaments"]);
    play(&mut s, ids[0]);
    // The grown copy back in hand.
    s.hand = Hand::from_pile(s.discard());
    s.hand.add(ids[1], 1);
    s.set_discard(Pile::default());
    play(&mut s, ids[1]);
    let r = s.hand.iter().map(|(c, _)| c).next().unwrap();
    assert_eq!(s.binding.def(r).name, "Rampage+{damage=13/combat}");
    let hp = s.monsters[0].hp;
    play(&mut s, r);
    assert_eq!(hp - s.monsters[0].hp, 13);
    let r = s.discard().iter().map(|(c, _)| c).find(|&c| s.binding.def(c).name.starts_with("Rampage")).unwrap();
    assert_eq!(s.binding.def(r).name, "Rampage+{damage=21/combat}", "Rampage+ grows by 8");
}

#[test]
fn many_changed_copies_all_upgrade() {
    // Four changed copies held (once every variant slot), two of +2: the
    // +2 still upgrades (docs/specs/sparse-piles.md: no cap).
    let names = ["gen:Armaments", "gen:Searing Blow+2", "gen:Searing Blow+2", "gen:Searing Blow+4", "gen:Searing Blow+5", "gen:Searing Blow+6"];
    let (mut s, ids) = setup(&names);
    assert_eq!(sts_engine::codec::changed_ranks(&s).len(), 4);
    play(&mut s, ids[0]);
    s.apply_action(Action::Choose(ids[1])).unwrap();
    assert_eq!(hand_names(&s), ["gen:Searing Blow+2", "gen:Searing Blow+3", "gen:Searing Blow+4", "gen:Searing Blow+5", "gen:Searing Blow+6"]);
    let (mut s, ids) = setup(&names);
    play(&mut s, ids[0]);
    s.apply_action(Action::Choose(ids[5])).unwrap();
    assert_eq!(hand_names(&s), ["gen:Searing Blow+2", "gen:Searing Blow+2", "gen:Searing Blow+4", "gen:Searing Blow+5", "gen:Searing Blow+7"]);
}

#[test]
fn armaments_plus_upgrades_five_changed_copies() {
    let names = ["gen:Armaments+", "gen:Searing Blow+2", "gen:Searing Blow+3", "gen:Searing Blow+4", "gen:Searing Blow+5", "gen:Searing Blow+6"];
    let (mut s, ids) = setup(&names);
    play(&mut s, ids[0]);
    assert_eq!(hand_names(&s), ["gen:Searing Blow+3", "gen:Searing Blow+4", "gen:Searing Blow+5", "gen:Searing Blow+6", "gen:Searing Blow+7"]);
}
