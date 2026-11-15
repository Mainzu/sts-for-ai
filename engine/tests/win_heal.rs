//! The fight's combat-end heal (docs/specs/relics.md, step 2): the state's
//! `win_heal`, raised by `WinHeal`, encoded only when it differs from the
//! character's, and counted as healing by the solver's bounds. (The exact
//! solver encodes states, and pack cards don't encode, so the bound is
//! checked against the value play reaches.)

use sts_engine::codec::{encode, try_decode};
use sts_engine::registry::{bind, load_pack};
use sts_engine::*;

const PACK: &str = r#"{"version": 1,
 "cards": [
  {"id": "wh_mend", "cost": 0, "type": "Skill", "effects": [{"WinHeal": 10}]},
  {"id": "wh_hit", "cost": 1, "type": "Attack", "effects": [{"Damage": {"amount": 6, "target": "Opponent"}}]}
 ]}"#;

const HAND: [&str; 2] = ["gen:wh_mend", "gen:wh_hit"];

/// A Jaw Worm at `monster_hp` (no block), the player at 50 of 80 HP (the
/// fight started at 80) with
/// `hand` (pack card names) in hand, 3 energy, empty other piles.
fn combat(hand: &[&str], monster_hp: i16) -> CombatState {
    load_pack(PACK).unwrap();
    let (ids, b) = bind(hand).unwrap();
    let mut s = CombatState::new_bound(Character::Ironclad, &ids, &b, 50, 80, Encounter::JawWorm, &mut Rng::new(1));
    s.hand = Hand::from_cards(&ids);
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    s.player.energy = 3;
    s.monsters[0].hp = monster_hp;
    s.monsters[0].max_hp = monster_hp;
    s.monsters[0].block = 0;
    s.start_hp = 80;
    s
}

/// Plays the hand card `i` of `hand` (as `combat` was given it).
fn play(s: &mut CombatState, hand: &[&str], i: usize, target: Option<u8>) {
    let card = bind(hand).unwrap().0[i];
    s.step(Action::Play { card, target }, &mut Rng::new(2)).unwrap();
}

#[test]
fn a_fight_starts_with_the_characters_heal() {
    let s = CombatState::new(&starter_deck(), 80, 80, Encounter::JawWorm, &mut Rng::new(1));
    assert_eq!(s.win_heal, 6);
    let s = CombatState::new_as(Character::Silent, &Character::Silent.starter_deck(), 70, 70, Encounter::JawWorm, &mut Rng::new(1));
    assert_eq!(s.win_heal, 0);
}

#[test]
fn a_win_heal_card_raises_the_heal_on_a_won_fight() {
    let mut s = combat(&HAND, 6);
    play(&mut s, &HAND, 0, None);
    assert_eq!(s.win_heal, 16);
    play(&mut s, &HAND, 1, Some(0));
    assert!(s.won());
    assert_eq!(s.player.hp, 66, "50 + Burning Blood's 6 + 10");
}

#[test]
fn win_heal_is_capped_at_max_hp_and_absent_in_no_death() {
    let mut s = combat(&HAND, 6);
    s.player.hp = 75;
    play(&mut s, &HAND, 0, None);
    play(&mut s, &HAND, 1, Some(0));
    assert_eq!(s.player.hp, 80);
    let mut s = combat(&HAND, 6);
    s.no_death = true;
    play(&mut s, &HAND, 0, None);
    play(&mut s, &HAND, 1, Some(0));
    assert!(s.won());
    assert_eq!(s.player.hp, 50);
}

#[test]
fn codec_win_heal_roundtrip() {
    let s = CombatState::new(&starter_deck(), 70, 80, Encounter::JawWorm, &mut Rng::new(3));
    let before = encode(&s);
    // The default heal adds nothing.
    let mut t = s.clone();
    t.win_heal = 6;
    assert_eq!(encode(&t), before);
    // A raised heal is a tag-6 trailer that decodes back.
    t.win_heal = 10;
    let bytes = encode(&t);
    assert_eq!(&bytes[..before.len()], &before[..]);
    assert_eq!(bytes[before.len()], 6);
    assert_eq!(try_decode(&bytes).unwrap(), t);
    // A tag 6 holding the default is not an encoding.
    let mut bad = before.clone();
    bad.extend([6, 12]); // zigzag 6
    assert_eq!(try_decode(&bad), None);
    // Nor is a negative heal.
    let mut neg = before;
    neg.extend([6, 1]); // zigzag -1
    assert_eq!(try_decode(&neg), None);
}

#[test]
fn bound_with_win_heal_card() {
    // Without a heal card the bound is today's: HP plus Burning Blood.
    let plain = combat(&["gen:wh_hit"], 6);
    assert_eq!(plain.upper_bound(), 2.0 - 24.0 / 100.0);
    // A WinHeal still to play could heal past it: the bound is full HP.
    let mut s = combat(&HAND, 6);
    assert_eq!(s.upper_bound(), 2.0);
    play(&mut s, &HAND, 0, None);
    // Played, it sits in the discard pile and could come round again.
    assert_eq!(s.upper_bound(), 2.0);
    // With no heal card left, the raised heal is the bound's.
    let mut t = plain.clone();
    t.win_heal = 16;
    assert_eq!(t.upper_bound(), 2.0 - 14.0 / 100.0);
    play(&mut s, &HAND, 1, Some(0));
    assert!((s.score() - 1.86).abs() < 1e-9, "{}", s.score());
}
