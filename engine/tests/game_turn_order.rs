//! The game's turn order on the Act 1 packs (docs/specs/turn-start-draw.md,
//! "Outside assumptions"), each test against a line of the game's code
//! (decompiled `com/megacrit/cardcrawl/`, `Li-Binghui/MySlayTheSpire` and
//! `aeubanks/sts` agree): turn 1 in `rooms/AbstractRoom.java` `update`
//! (~255: the opening `DrawCardAction`, then `atBattleStart` relics, then
//! `atTurnStart` relics and `atStartOfTurn` powers), turn 2 on in
//! `actions/GameActionManager.java` (~446: `atTurnStart` relics and
//! `atStartOfTurn` powers, block loss, the turn's `DrawCardAction`, then
//! the post-draw relics and powers).

use sts_engine::monsters::EncounterGroup;
use sts_engine::registry::{bind, load_pack, relics_named};
use sts_engine::*;

const RELICS: &str = include_str!("../../content/packs/act1-relics.json");

/// A version-2 test relic whose pre-draw hook adds 6 Wounds to the hand.
const HAND_PACK: &str = r#"{"version": 2, "powers": [
{"id": "GtoPreWounds", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "effects": [{"AddCard": {"card": "Wound", "n": 6, "pile": "Hand"}}]}]}
], "relics": [
{"id": "Gto Pre Wounds", "rarity": "common", "powers": [{"power": "GtoPreWounds", "amount": 1}]}
]}"#;

fn wound() -> CardId {
    CardId::from_name("Wound").unwrap()
}

/// A starter-deck fight against `kinds` with these pack relics (game names).
fn fight(pack: &str, kinds: &[MonsterKind], relics: &[&str], turn1_pre_draw: bool, seed: u64) -> CombatState {
    load_pack(pack).unwrap();
    let names: Vec<String> = starter_deck().iter().map(|&c| c.def().name.to_string()).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    let (ids, b) = bind(&refs).unwrap();
    let rel: Vec<String> = relics.iter().map(|r| format!("gen:{r}")).collect();
    let rel: Vec<&str> = rel.iter().map(String::as_str).collect();
    let relics = relics_named(&rel).unwrap();
    CombatState::new_with_turn1(Character::Ironclad, &ids, &b, 80, 80, kinds, EncounterGroup::Hallway, &relics, turn1_pre_draw, Default::default(), None, &mut Rng::new(seed))
}

#[test]
fn bag_of_preparation_draws_after_the_opening_hand() {
    // AbstractRoom ~255: `BagOfPreparation.atBattleStart` queues its
    // `DrawCardAction(2)` after the opening draw: 7 cards on turn 1. It's
    // post-draw, so it holds with `turn1_pre_draw` too.
    for pre1 in [false, true] {
        let s = fight(RELICS, &[MonsterKind::JawWorm], &["Bag of Preparation"], pre1, 1);
        assert_eq!((s.turn, s.hand.len(), s.draw().len()), (1, 7, 3), "turn1_pre_draw {pre1}");
    }
}

#[test]
fn mark_of_pain_wounds_miss_the_opening_hand() {
    // AbstractRoom ~255: `MarkOfPain.atBattleStart` shuffles 2 Wounds into
    // the draw pile after the opening draw: none in the opening hand.
    for pre1 in [false, true] {
        let s = fight(RELICS, &[MonsterKind::JawWorm], &["Mark of Pain"], pre1, 2);
        assert_eq!(s.hand.len(), 5);
        assert_eq!(s.hand.count(wound()), 0, "turn1_pre_draw {pre1}");
        assert_eq!((s.draw().count(wound()), s.draw().len()), (2, 7));
    }
}

#[test]
fn pre_draw_hand_cards_take_draw_space_from_turn_2() {
    // GameActionManager ~446: from turn 2 an `atStartOfTurn` hook's cards
    // reach the hand before the turn's `DrawCardAction`: 6 Wounds leave room
    // for 4 of the 5. AbstractRoom ~255: on turn 1 it runs after the opening
    // draw, so all 5 are drawn and 5 of the 6 Wounds fit.
    let mut s = fight(HAND_PACK, &[MonsterKind::Cultist], &["Gto Pre Wounds"], false, 3);
    let deck_cards = |s: &CombatState| s.hand.len() - s.hand.count(wound()) as usize;
    assert_eq!((deck_cards(&s), s.hand.count(wound())), (5, 5));
    s.step(Action::EndTurn, &mut Rng::new(4)).unwrap();
    assert_eq!((s.turn, s.stage), (2, Stage::PlayerTurn));
    assert_eq!((deck_cards(&s), s.hand.count(wound())), (4, 6));
}

#[test]
fn mercury_hourglass_kill_on_turn_2_ends_the_fight_before_the_draw() {
    // GameActionManager ~446: `MercuryHourglass.atTurnStart` deals its 3
    // before the turn's `DrawCardAction`; a kill ends the fight with
    // nothing drawn.
    let mut s = fight(RELICS, &[MonsterKind::Cultist], &["Mercury Hourglass"], false, 5);
    s.monsters[0].hp = 3;
    s.monsters[0].block = 0;
    let draw_pile = s.draw().len();
    s.step(Action::EndTurn, &mut Rng::new(6)).unwrap();
    assert!(s.won(), "{:?}", s.stage);
    assert_eq!(s.turn, 2);
    assert_eq!(s.hand.len(), 0, "no draw");
    assert_eq!(s.draw().len(), draw_pile);
    assert!(s.pending.is_none());
}
