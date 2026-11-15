//! The player's turn around the draw (docs/specs/turn-start-draw.md):
//! `OwnerTurnStart` hooks before the turn's draw, `OwnerTurnStartPostDraw`
//! hooks after it; turn 1 as the game plays it (opening draw, post-draw
//! hooks, turn-start hooks) unless the fight is built with
//! `turn1_pre_draw`; a pre-draw `Draw` merged into the turn's draw; a
//! pre-draw kill ends the fight with no draw; monsters run both triggers in
//! one pass. Each hook here is a version-2 pack relic's power, given by a
//! `CombatStartPreDraw` hook: held before turn 1's hooks in both orders.

use sts_engine::monsters::EncounterGroup;
use sts_engine::registry::{bind, load_pack, monster_kinds, relics_named};
use sts_engine::*;

const PACK: &str = r#"{"version": 2, "powers": [
{"id": "TsoPreWounds", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "effects": [{"AddCard": {"card": "Wound", "n": 6, "pile": "Hand"}}]}]},
{"id": "TsoPostWounds", "hooks": [{"trigger": "OwnerTurnStartPostDraw", "condition": "Always", "effects": [{"AddCard": {"card": "Wound", "n": 6, "pile": "Hand"}}]}]},
{"id": "TsoPreDraw", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "effects": [{"Draw": 1}]}]},
{"id": "TsoPreDamage", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "effects": [{"PlainDamage": {"amount": 3, "target": "AllOpponents"}}]}]},
{"id": "TsoPreEnergy", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "effects": [{"GainEnergy": 1}]}]},
{"id": "TsoMonPost", "hooks": [{"trigger": "OwnerTurnStartPostDraw", "condition": "Always", "effects": [{"Apply": {"power": "Strength", "amount": 2, "target": "Me"}}]}]},
{"id": "TsoMonPre", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "effects": [{"Apply": {"power": "Strength", "amount": 3, "target": "Me"}}]}]}
], "relics": [
{"id": "Tso Pre Wounds", "rarity": "common", "hooks": [{"trigger": "CombatStartPreDraw", "condition": "Always", "effects": [{"Apply": {"power": "TsoPreWounds", "amount": 1, "target": "Me"}}]}]},
{"id": "Tso Post Wounds", "rarity": "common", "hooks": [{"trigger": "CombatStartPreDraw", "condition": "Always", "effects": [{"Apply": {"power": "TsoPostWounds", "amount": 1, "target": "Me"}}]}]},
{"id": "Tso Pre Draw", "rarity": "common", "hooks": [{"trigger": "CombatStartPreDraw", "condition": "Always", "effects": [{"Apply": {"power": "TsoPreDraw", "amount": 1, "target": "Me"}}]}]},
{"id": "Tso Pre Damage", "rarity": "common", "hooks": [{"trigger": "CombatStartPreDraw", "condition": "Always", "effects": [{"Apply": {"power": "TsoPreDamage", "amount": 1, "target": "Me"}}]}]},
{"id": "Tso Pre Energy", "rarity": "common", "hooks": [{"trigger": "CombatStartPreDraw", "condition": "Always", "effects": [{"Apply": {"power": "TsoPreEnergy", "amount": 1, "target": "Me"}}]}]}
], "monsters": [
{"id": "TsoBoth", "hp": [40, 40], "start_block": 0, "moves": [{"name": "Hit", "effects": [{"Damage": {"amount": 5, "hits": 1, "target": "Opponent"}}]}],
 "pattern": [{"when": [], "then": {"Move": 0}}],
 "start_powers": [{"power": "TsoMonPost", "amount": 1}, {"power": "TsoMonPre", "amount": 1}]}
]}"#;

fn wound() -> CardId {
    CardId::from_name("Wound").unwrap()
}

/// A starter-deck fight against `kinds` holding the pack relic `relic`.
fn fight(kinds: &[MonsterKind], relic: &str, turn1_pre_draw: bool, seed: u64) -> CombatState {
    load_pack(PACK).unwrap();
    let names: Vec<String> = starter_deck().iter().map(|&c| c.def().name.to_string()).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    let (ids, b) = bind(&refs).unwrap();
    let relics = relics_named(&[&format!("gen:{relic}")]).unwrap();
    CombatState::new_with_turn1(Character::Ironclad, &ids, &b, 80, 80, kinds, EncounterGroup::Hallway, &relics, turn1_pre_draw, Default::default(), None, &mut Rng::new(seed))
}

/// Ends the turn and samples on to the next decision.
fn next_turn(s: &mut CombatState, seed: u64) {
    s.step(Action::EndTurn, &mut Rng::new(seed)).unwrap();
    assert_eq!(s.stage, Stage::PlayerTurn);
}

/// (deck cards in hand, Wounds in hand).
fn hand_split(s: &CombatState) -> (u8, u8) {
    let w = s.hand.count(wound());
    (s.hand.len() as u8 - w, w)
}

#[test]
fn turn_start_order() {
    // Pre-draw: 6 Wounds take hand space before the draw from turn 2 on
    // (4 drawn), not on turn 1 (5 drawn, then 5 of the 6 Wounds fit).
    let mut s = fight(&[MonsterKind::Cultist], "Tso Pre Wounds", false, 1);
    assert_eq!(s.turn, 1);
    assert_eq!(hand_split(&s), (5, 5));
    assert_eq!(s.discard().count(wound()), 1, "the Wound past the hand limit");
    next_turn(&mut s, 2);
    assert_eq!(s.turn, 2);
    assert_eq!(hand_split(&s), (4, 6));

    // `turn1_pre_draw`: turn 1 like every other turn.
    let s = fight(&[MonsterKind::Cultist], "Tso Pre Wounds", true, 1);
    assert_eq!(hand_split(&s), (4, 6));

    // Post-draw: after the draw on every turn, with or without the option.
    for pre1 in [false, true] {
        let mut s = fight(&[MonsterKind::Cultist], "Tso Post Wounds", pre1, 1);
        assert_eq!(hand_split(&s), (5, 5));
        next_turn(&mut s, 2);
        assert_eq!(hand_split(&s), (5, 5));
    }
}

#[test]
fn pre_draw_draw_merges() {
    // Turn 1 (the game's order): the opening 5, then the hook's 1.
    let mut s = fight(&[MonsterKind::JawWorm], "Tso Pre Draw", false, 3);
    assert_eq!(s.hand.len(), 6);
    // Turn 2: one chance event of 6 cards (4 left in the draw pile, so the
    // draw shuffles the discard pile in and is uncertain).
    let mut rng = Rng::new(4);
    s.apply_action(Action::EndTurn).unwrap();
    let mut draws = Vec::new();
    while let Some(ev) = s.pending {
        if let ChanceEvent::Draw { n } = ev {
            draws.push(n);
        }
        s.resolve_chance(&mut rng);
    }
    assert_eq!(draws, vec![6]);
    assert_eq!((s.turn, s.stage, s.hand.len()), (2, Stage::PlayerTurn, 6));
    // With the option, turn 1's draw is merged the same way.
    let s = fight(&[MonsterKind::JawWorm], "Tso Pre Draw", true, 3);
    assert_eq!(s.hand.len(), 6);
}

#[test]
fn pre_draw_kill_ends_fight() {
    // Jaw Worm's first move is Chomp (no block). At 3 HP on turn 2 the
    // pre-draw 3 damage kills it: the fight is won and nothing is drawn.
    let mut s = fight(&[MonsterKind::JawWorm], "Tso Pre Damage", false, 5);
    s.monsters[0].hp = 3;
    let draw_pile = s.draw().len();
    s.step(Action::EndTurn, &mut Rng::new(6)).unwrap();
    assert!(s.won(), "{:?}", s.stage);
    assert_eq!(s.turn, 2);
    assert_eq!(s.hand.len(), 0, "no draw");
    assert_eq!(s.draw().len(), draw_pile);
    assert!(s.pending.is_none());
}

#[test]
fn monsters_one_pass() {
    // A monster holding both triggers runs both at its turn start, before it
    // acts: its first Hit deals 5 + 2 + 3.
    load_pack(PACK).unwrap();
    let kinds = monster_kinds(&["gen:TsoBoth"]).unwrap();
    let mut s = fight(&kinds, "Tso Pre Energy", false, 7);
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 0);
    let hp = s.player.hp;
    next_turn(&mut s, 8);
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 5);
    assert_eq!(hp - s.player.hp, 10);
}

#[test]
fn plain_leaf_holds_pre_draw_energy() {
    // The search's plain leaf is `EndTurn` applied up to the first chance
    // event (search.rs `child`). Cultist's moves after the first are fixed,
    // so nothing is rolled: the leaf stops at the turn's draw, after the
    // pre-draw hooks, and holds their energy (3 + 1). (Three more cards in
    // the draw pile make turn 2's draw uncertain, so it pauses.)
    let mut s = fight(&[MonsterKind::Cultist], "Tso Pre Energy", false, 9);
    assert_eq!(s.player.energy, 4, "turn 1: after the opening draw");
    s.draw_mut().add(CardId::from_name("Bash").unwrap(), 3);
    let mut leaf = s.clone();
    leaf.apply_action(Action::EndTurn).unwrap();
    assert_eq!(leaf.stage, Stage::TurnStarted);
    assert!(matches!(leaf.pending, Some(ChanceEvent::Draw { .. })));
    assert_eq!((leaf.player.energy, leaf.player.block), (4, 0));
    // @tsl1 at the draw projects post-draw hooks only: none held here.
    assert!(leaf.turn_start_leaf().is_none());

    // Jaw Worm rolls its next move: the plain leaf stops at that roll,
    // before the turn starts; @tsl1 there projects both triggers.
    let s = fight(&[MonsterKind::JawWorm], "Tso Pre Energy", false, 9);
    let mut leaf = s.clone();
    leaf.apply_action(Action::EndTurn).unwrap();
    assert!(matches!(leaf.stage, Stage::MonsterRolls { .. }), "{:?}", leaf.stage);
    assert_eq!(leaf.player.energy, 4, "this turn's energy, unspent");
    assert_eq!(leaf.turn_start_leaf().expect("pre-draw hook still to run").player.energy, 5);
}
