//! Pack powers on pack monsters (docs/specs/monster-pack-powers.md, block
//! M5): a pack monster's start powers may name a pack power; the fight's
//! binding gains it after the deck's powers, and its hooks act for the
//! monster. The Mad Gremlin (`content/packs/act1-monsters.json`) is the
//! first entry that needs it.

use sts_engine::agent::greedy_action;
use sts_engine::effects::{Effect, Target};
use sts_engine::registry::{bind, bind_monsters, bind_power, load_pack, monster_kinds, Binding};
use sts_engine::*;

const MONSTERS: &str = include_str!("../../content/packs/act1-monsters.json");

const HIT: &str = r#"{"name": "Hit", "effects": [{"Damage": {"amount": 5, "hits": 1, "target": "Opponent"}}]}"#;
const LAST: &str = r#"{"when": [], "then": {"Move": 0}}"#;

/// A test pack: `mp_angry` (the Angry hook), `mp_p0`..`mp_p24` (no rows),
/// a card applying each, the monster `mp_m` (start `mp_angry` 1), and a
/// splitter whose children both start with `mp_angry` 1.
fn pack() -> String {
    let angry = r#"{"id": "mp_angry", "hooks": [{"trigger": {"OwnerLostHp": {"from": "Attack"}}, "condition": "Always", "effects": [{"Apply": {"power": "Strength", "amount": 1, "target": "Me"}}]}]}"#;
    let mut powers = vec![angry.to_string()];
    let mut cards = vec![r#"{"id": "mp_angry_card", "cost": 1, "type": "Skill", "effects": [{"Apply": {"power": "mp_angry", "amount": 1, "target": "Me"}}]}"#.to_string()];
    for i in 0..25 {
        powers.push(format!(r#"{{"id": "mp_p{i}"}}"#));
        cards.push(format!(r#"{{"id": "mp_card{i}", "cost": 1, "type": "Skill", "effects": [{{"Apply": {{"power": "mp_p{i}", "amount": 1, "target": "Me"}}}}]}}"#));
    }
    let start = r#", "start_powers": [{"power": "mp_angry", "amount": 1}]"#;
    let m = format!(r#"{{"id": "mp_m", "hp": [50, 50]{start}, "moves": [{HIT}], "pattern": [{LAST}]}}"#);
    let child = format!(r#"{{"id": "mp_child", "hp": [10, 12]{start}, "moves": [{HIT}], "pattern": [{LAST}]}}"#);
    let splitter = format!(
        r#"{{"id": "mp_splitter", "hp": [40, 40], "split": {{"move": 1, "into": ["gen:mp_child", "gen:mp_child"]}}, "moves": [{HIT}, {{"name": "Split", "effects": ["Split"]}}], "pattern": [{LAST}]}}"#
    );
    format!(
        r#"{{"version": 1, "powers": [{}], "cards": [{}], "monsters": [{m}, {child}, {splitter}]}}"#,
        powers.join(", "),
        cards.join(", ")
    )
}

fn kind(id: &str) -> MonsterKind {
    load_pack(&pack()).unwrap();
    monster_kinds(&[&format!("gen:{id}")]).unwrap()[0]
}

fn strike() -> CardId {
    CardId::from_name("Strike").unwrap()
}

/// A fight against `kinds` with `deck` bound, then `hand` (official names)
/// in hand, 3 energy, empty piles, monster 0 at 100 HP with no block.
fn fight(deck: &[&str], kinds: &[MonsterKind], hand: &[&str]) -> CombatState {
    let (ids, b) = bind(deck).unwrap();
    let mut s = CombatState::new_vs(Character::Ironclad, &ids, &b, 80, 80, kinds, &mut Rng::new(1));
    s.hand = Hand::from_cards(&hand.iter().map(|n| CardId::from_name(n).unwrap()).collect::<Vec<_>>());
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    s.player.energy = 3;
    s.player.block = 0;
    let m = &mut s.monsters[0];
    m.hp = 100;
    m.max_hp = 100;
    m.block = 0;
    s
}

fn play_strike(s: &mut CombatState) {
    s.apply_action(Action::Play { card: strike(), target: Some(0) }).unwrap();
}

#[test]
fn pack_power_start() {
    let m = kind("mp_m");
    let s = fight(&["Strike"], &[m], &[]);
    assert_eq!(s.binding.power_id(Power::GEN[0]), Some("mp_angry"));
    assert_eq!(s.monsters[0].powers.get(Power::GEN[0]), 1);
    assert_eq!(s.player.powers.get(Power::GEN[0]), 0);
}

#[test]
fn angry_on_attack_hp_loss() {
    let m = kind("mp_m");
    let mut s = fight(&["Strike"], &[m], &["Strike", "Strike", "Strike"]);
    play_strike(&mut s);
    assert_eq!((s.monsters[0].hp, s.monsters[0].powers.get(Power::Strength)), (94, 1), "unblocked Strike");
    s.monsters[0].block = 20;
    play_strike(&mut s);
    assert_eq!((s.monsters[0].block, s.monsters[0].powers.get(Power::Strength)), (14, 1), "fully blocked Strike");
    // HP lost to Poison (not an attack) at the monster's turn start.
    s.monsters[0].block = 0;
    s.monsters[0].powers.add(Power::Poison, 3);
    let hp = s.monsters[0].hp;
    s.step(Action::EndTurn, &mut Rng::new(7)).unwrap();
    assert!(s.monsters[0].hp < hp, "the poison ticked");
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 1, "Poison HP loss");
}

#[test]
fn deck_slots_kept() {
    let m = kind("mp_m");
    let deck = ["gen:mp_card0", "gen:mp_card1", "Strike"];
    let (_, b) = bind(&deck).unwrap();
    let bm = bind_monsters(&b, &[m]).unwrap();
    let (sm, sb) = (bm.slot_set(), b.slot_set());
    assert_eq!((sm.powers[0], sm.powers[1]), (sb.powers[0], sb.powers[1]), "deck power slots");
    assert_eq!(sm.cards, sb.cards, "deck card slots");
    assert_eq!(bm.power_id(Power::GEN[2]), Some("mp_angry"));
    let s = fight(&deck, &[m], &[]);
    assert_eq!(s.binding, bm);
    assert_eq!(s.monsters[0].powers.get(Power::GEN[2]), 1);
    // A deck already holding the power: one slot, shared.
    let (_, b) = bind(&["gen:mp_card0", "gen:mp_angry_card"]).unwrap();
    let bm = bind_monsters(&b, &[m]).unwrap();
    assert_eq!(bm, b);
    let s = fight(&["gen:mp_card0", "gen:mp_angry_card"], &[m], &[]);
    assert_eq!(s.monsters[0].powers.get(Power::GEN[1]), 1);
    // Official monsters add nothing.
    assert_eq!(bind_monsters(&b, &[MonsterKind::JawWorm]).unwrap(), b);
    assert_eq!(bind_monsters(&Binding::default(), &[MonsterKind::JawWorm]).unwrap(), Binding::default());
}

#[test]
fn too_many_slots() {
    let m = kind("mp_m");
    let names: Vec<String> = (0..24).map(|i| format!("gen:mp_card{i}")).collect();
    let deck: Vec<&str> = names.iter().map(String::as_str).collect();
    let (_, b) = bind(&deck).unwrap();
    let e = bind_monsters(&b, &[m]).unwrap_err();
    assert!(e.contains("24"), "{e}");
    // 23 deck powers and the monster's fit.
    let (_, b) = bind(&deck[..23]).unwrap();
    assert_eq!(bind_monsters(&b, &[m]).unwrap().power_id(Power::GEN[23]), Some("mp_angry"));
}

#[test]
fn split_child_pack_power() {
    let k = kind("mp_splitter");
    let b = bind_monsters(&Binding::default(), &[k]).unwrap();
    assert_eq!(b.power_id(Power::GEN[0]), Some("mp_angry"), "split children bound up front");
    let deck = Character::Ironclad.starter_deck();
    let mut rng = Rng::new(3);
    let mut s = CombatState::new_vs(Character::Ironclad, &deck, &Binding::default(), 80, 80, &[k], &mut rng);
    assert_eq!(s.monsters[0].powers.get(Power::GEN[0]), 0, "the splitter holds none");
    for _ in 0..200 {
        if s.is_over() || s.monsters[1].kind != MonsterKind::None {
            break;
        }
        s.step(greedy_action(&s), &mut rng).unwrap();
    }
    let child = kind("mp_child");
    assert_eq!((s.monsters[0].kind, s.monsters[1].kind), (child, child));
    assert_eq!((s.monsters[0].powers.get(Power::GEN[0]), s.monsters[1].powers.get(Power::GEN[0])), (1, 1));
}

#[test]
fn unknown_pack_power() {
    let entry = format!(r#"{{"id": "mp_bad", "hp": [5, 5], "start_powers": [{{"power": "mp_nowhere", "amount": 1}}], "moves": [{HIT}], "pattern": [{LAST}]}}"#);
    let e = load_pack(&format!(r#"{{"version": 1, "monsters": [{entry}]}}"#)).unwrap_err();
    assert!(e.contains("mp_bad") && e.contains("mp_nowhere"), "{e}");
    assert!(monster_kinds(&["gen:mp_bad"]).is_err());
}

#[test]
fn mad_gremlin_from_file() {
    load_pack(MONSTERS).unwrap();
    let k = monster_kinds(&["gen:Mad Gremlin"]).unwrap()[0];
    let d = k.def();
    assert_eq!((d.hp_min, d.hp_max, d.start_block), (20, 24, 0));
    assert_eq!(d.moves.len(), 1);
    assert_eq!(d.moves[0].name, "Scratch");
    assert_eq!(d.moves[0].effects, &[Effect::Damage { amount: 4, hits: 1, target: Target::Opponent }]);
    assert!(d.start_powers.is_empty(), "Angry is a pack power, not an official one");
    let deck = Character::Ironclad.starter_deck();
    let mut s = CombatState::new_vs(Character::Ironclad, &deck, &Binding::default(), 80, 80, &[k], &mut Rng::new(2));
    assert_eq!(s.binding.power_id(Power::GEN[0]), Some("Angry"));
    assert_eq!(s.monsters[0].powers.get(Power::GEN[0]), 1);
    assert!((20..=24).contains(&s.monsters[0].hp));
    // Three Strikes (18 damage, under its least HP), then its Scratch.
    s.hand = Hand::from_cards(&[strike(), strike(), strike()]);
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    s.player.energy = 3;
    s.player.block = 0;
    for _ in 0..3 {
        play_strike(&mut s);
    }
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 3);
    let hp = s.player.hp;
    s.step(Action::EndTurn, &mut Rng::new(7)).unwrap();
    assert_eq!(hp - s.player.hp, 7, "Scratch 4 + Strength 3");
}

#[test]
fn bind_power_reuses_and_fills() {
    load_pack(&pack()).unwrap();
    // A power the deck already binds keeps its slot.
    let (_, b) = bind(&["gen:mp_card0", "gen:mp_angry_card"]).unwrap();
    assert_eq!(b.power_id(Power::GEN[1]), Some("mp_angry"));
    let (nb, p) = bind_power(&b, "mp_angry").unwrap();
    assert_eq!(p, Power::GEN[1]);
    assert_eq!(nb.powers_in_play().len(), b.powers_in_play().len());
    // A new one takes the next free slot; deck slots stay.
    let (_, b) = bind(&["gen:mp_card0"]).unwrap();
    let (nb, p) = bind_power(&b, "mp_angry").unwrap();
    assert_eq!(p, Power::GEN[1]);
    assert_eq!(nb.power_id(Power::GEN[0]), Some("mp_p0"));
    // Past the slots: an error; unknown: an error.
    let names: Vec<String> = (0..24).map(|i| format!("gen:mp_card{i}")).collect();
    let deck: Vec<&str> = names.iter().map(String::as_str).collect();
    let (_, b) = bind(&deck).unwrap();
    assert!(bind_power(&b, "mp_angry").unwrap_err().contains("24"));
    assert!(bind_power(&Binding::default(), "mp_nope").is_err());
}
