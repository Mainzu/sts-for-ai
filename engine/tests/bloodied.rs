//! HP crossing half (docs/specs/red-skull-strength.md): `OwnerBloodied`
//! fires when HP loss takes the owner from above half its max HP to at most
//! half, `OwnerUnbloodied` when a heal takes it back above; once per
//! crossing, for the player and monsters, never on a killing hit; and the
//! hook condition `OwnerHpAtMostHalf`. Test pack content only.

mod common;

use common::*;
use sts_engine::monsters::MonsterKind as K;
use sts_engine::registry::{bind, bind_power, load_pack};
use sts_engine::*;

const PACK: &str = r#"{"version": 2, "powers": [
{"id": "BlBlood", "hooks": [
  {"trigger": "OwnerBloodied", "condition": "Always", "effects": [{"Apply": {"power": "Strength", "amount": 1, "target": "Me"}}]},
  {"trigger": "OwnerUnbloodied", "condition": "Always", "effects": [{"Apply": {"power": "Strength", "amount": -1, "target": "Me"}}]}]},
{"id": "BlHalfEnd", "hooks": [
  {"trigger": "OwnerTurnEnd", "condition": "OwnerHpAtMostHalf", "effects": [{"Apply": {"power": "Strength", "amount": 1, "target": "Me"}}]}]}
], "cards": [
{"id": "BlHurt", "cost": 0, "type": "Skill", "effects": [{"LoseHp": 10}]},
{"id": "BlHeal", "cost": 0, "type": "Skill", "effects": [{"Heal": 30}]},
{"id": "BlHit", "cost": 0, "type": "Attack", "effects": [{"Damage": {"amount": 6, "hits": 1, "target": "Opponent"}}]},
{"id": "BlBigHit", "cost": 0, "type": "Attack", "effects": [{"Damage": {"amount": 60, "hits": 1, "target": "Opponent"}}]}
]}"#;

/// A Jaw Worm fight (worm at 45 of 80 HP) with the player at `hp` of 80,
/// a hand of every test card several times, and `power` (3 stacks) on
/// `who`. Returns the state and the card ids by name.
fn fight(hp: i16, power: &str, on_player: bool) -> (CombatState, impl Fn(&str) -> CardId) {
    load_pack(PACK).unwrap();
    let names = ["gen:BlHurt", "gen:BlHeal", "gen:BlHit", "gen:BlBigHit"];
    let (ids, b) = bind(&names).unwrap();
    let (b, p) = bind_power(&b, power).unwrap();
    let mut s = vs(&[K::JawWorm], &[], Some(45));
    s.binding = b;
    s.monsters[0].max_hp = 80;
    s.player.hp = hp;
    s.player.max_hp = 80;
    let hand: Vec<CardId> = ids.iter().flat_map(|&c| [c, c, c, c, c]).collect();
    s.hand = Hand::from_cards(&hand);
    s.player.energy = 3;
    if on_player {
        s.player.powers.add(p, 3);
    } else {
        s.monsters[0].powers.add(p, 3);
    }
    let by = move |n: &str| ids[names.iter().position(|x| x.ends_with(n)).unwrap()];
    (s, by)
}

fn play_id(s: &mut CombatState, c: CardId, target: Option<u8>) {
    s.apply_action(Action::Play { card: c, target }).expect("legal play");
}

fn str_of(s: &CombatState) -> i16 {
    s.player.powers.get(Power::Strength)
}

#[test]
fn player_crossings() {
    let (mut s, id) = fight(50, "BlBlood", true);
    play_id(&mut s, id("BlHurt"), None); // 50 -> 40: at half, crossing
    assert_eq!((s.player.hp, str_of(&s)), (40, 3));
    play_id(&mut s, id("BlHurt"), None); // 40 -> 30: already at most half
    assert_eq!((s.player.hp, str_of(&s)), (30, 3));
    play_id(&mut s, id("BlHeal"), None); // 30 -> 60: above half again
    assert_eq!((s.player.hp, str_of(&s)), (60, 0));
    play_id(&mut s, id("BlHurt"), None); // 60 -> 50: still above
    assert_eq!((s.player.hp, str_of(&s)), (50, 0));
    play_id(&mut s, id("BlHurt"), None); // 50 -> 40: down again
    assert_eq!((s.player.hp, str_of(&s)), (40, 3));
    // A heal that stays at or below half: no crossing.
    let (mut s, id) = fight(5, "BlBlood", true);
    play_id(&mut s, id("BlHeal"), None); // 5 -> 35
    assert_eq!((s.player.hp, str_of(&s)), (35, 0));
}

#[test]
fn monster_crossings() {
    // Worm at 45 of 80: a 6 hit takes it to 39 (at most half).
    let (mut s, id) = fight(80, "BlBlood", false);
    play_id(&mut s, id("BlHit"), Some(0));
    assert_eq!((s.monsters[0].hp, s.monsters[0].powers.get(Power::Strength)), (39, 3));
    play_id(&mut s, id("BlHit"), Some(0)); // 39 -> 33: no second crossing
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 3);
    // A killing hit fires nothing.
    let (mut s, id) = fight(80, "BlBlood", false);
    play_id(&mut s, id("BlBigHit"), Some(0));
    assert!(s.is_over());
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 0);
}

#[test]
fn hp_at_most_half_condition() {
    for (hp, want) in [(40, 3), (41, 0)] {
        let (mut s, _) = fight(hp, "BlHalfEnd", true);
        s.hand = Hand::from_cards(&[]);
        let before = s.player.hp;
        s.apply_action(Action::EndTurn).expect("end turn");
        // The turn-end hooks ran before any monster acted.
        assert_eq!(str_of(&s), want, "hp {before}");
    }
}
