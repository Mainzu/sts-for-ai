//! A card's play condition (docs/specs/card-rules.md): `playable_if` with
//! the hook condition `HandAll`, replacing Clash's `only_attacks_in_hand`;
//! content-file versions 1 (the old field, mapped) and 2 (the new one).

mod common;

use common::*;
use sts_engine::cards::CardType;
use sts_engine::hooks::Condition;
use sts_engine::monsters::MonsterKind as K;
use sts_engine::registry::{bind, load_pack};
use sts_engine::*;

/// A Jaw Worm fight whose hand is `hand` (pack cards as `gen:<id>`), bound
/// as `bind` binds them, with 3 energy.
fn hand_of(hand: &[&str]) -> (CombatState, Vec<CardId>) {
    let (ids, b) = bind(hand).unwrap();
    let mut s = vs(&[K::JawWorm], &[], Some(50));
    s.binding = b;
    s.hand = Hand::from_cards(&ids);
    s.player.energy = 3;
    (s, ids)
}

#[test]
fn playable_if() {
    // Clash, from the official file: only with an all-Attack hand.
    assert_eq!(card("Clash").def().playable_if, Some(Condition::HandAll(CardType::Attack)));
    assert_eq!(card("Strike").def().playable_if, None);
    let (s, ids) = hand_of(&["Clash", "Strike"]);
    assert!(s.is_legal(Action::Play { card: ids[0], target: Some(0) }));
    let (s, ids) = hand_of(&["Clash", "Defend"]);
    assert!(!s.is_legal(Action::Play { card: ids[0], target: Some(0) }));

    // A pack card with another type.
    load_pack(
        r#"{"version": 2, "powers": [], "cards": [
{"id": "PiSkillsOnly", "cost": 0, "type": "Skill", "playable_if": {"HandAll": "Skill"}, "effects": [{"Block": 1}]}]}"#,
    )
    .unwrap();
    let (s, ids) = hand_of(&["gen:PiSkillsOnly", "Defend"]);
    assert!(s.is_legal(Action::Play { card: ids[0], target: None }));
    let (s, ids) = hand_of(&["gen:PiSkillsOnly", "Strike"]);
    assert!(!s.is_legal(Action::Play { card: ids[0], target: None }));
}

fn card_pack(version: u8, id: &str, extra: &str) -> String {
    format!(r#"{{"version": {version}, "powers": [], "cards": [{{"id": "{id}", "cost": 0, "type": "Attack"{extra}, "effects": [{{"Damage": {{"amount": 3, "hits": 1, "target": "Opponent"}}}}]}}]}}"#)
}

#[test]
fn card_versions() {
    // Version 1: the old field reads as the condition.
    load_pack(&card_pack(1, "CvOld", r#", "only_attacks_in_hand": true"#)).unwrap();
    load_pack(&card_pack(1, "CvOldOff", r#", "only_attacks_in_hand": false"#)).unwrap();
    let (ids, b) = bind(&["gen:CvOld", "gen:CvOldOff"]).unwrap();
    assert_eq!(b.def(ids[0]).playable_if, Some(Condition::HandAll(CardType::Attack)));
    assert_eq!(b.def(ids[1]).playable_if, None);
    // Version 2 refuses the old field, naming the new one.
    let e = load_pack(&card_pack(2, "CvOld2", r#", "only_attacks_in_hand": true"#)).unwrap_err();
    assert!(e.contains("playable_if"), "{e}");
    // Version 1 refuses the new field.
    let e = load_pack(&card_pack(1, "CvNew1", r#", "playable_if": {"HandAll": "Attack"}"#)).unwrap_err();
    assert!(e.contains("playable_if"), "{e}");
    // An unplayable card with a play condition.
    let e = load_pack(
        r#"{"version": 2, "powers": [], "cards": [{"id": "CvUnplayable", "cost": -2, "type": "Status", "playable_if": {"HandAll": "Attack"}, "effects": []}]}"#,
    )
    .unwrap_err();
    assert!(e.contains("unplayable"), "{e}");
    // An unknown card key.
    let e = load_pack(&card_pack(2, "CvUnknown", r#", "only_skills": true"#)).unwrap_err();
    assert!(e.contains("only_skills"), "{e}");
}
