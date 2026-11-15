//! The stages of the player's End Turn (`before_hand`, `Hook::before_hand`),
//! as the game runs them: the relics' `onPlayerEndTurn` and the powers'
//! `atEndOfTurnPreEndTurnCards` (Metallicize, Plated Armor), then the
//! hand's turn-end cards (Burn), then the powers' `atEndOfTurn` (Combust,
//! Regeneration). Each fight is a Jaw Worm's opening Chomp (11).

use sts_engine::registry::{bind, bind_power, load_pack, relics_named};
use sts_engine::*;

const IRONCLAD: &str = include_str!("../../content/packs/act1-ironclad.json");
const POTIONS: &str = include_str!("../../content/packs/act1-potions.json");
const RELICS: &str = include_str!("../../content/packs/act1-relics.json");

/// Test content: powers that gain 10 block in the `atEndOfTurn` pass when
/// the owner has exactly 1 or 0 block then (they show the block the pass
/// sees), and a relic whose turn-end hook acts after the hand.
const TEST: &str = r#"{"version": 2,
 "powers": [
  {"id": "tes-at1", "hooks": [{"trigger": "OwnerTurnEnd", "condition": {"OwnerBlockIs": 1}, "effects": [{"Block": 10}]}]},
  {"id": "tes-at0", "hooks": [{"trigger": "OwnerTurnEnd", "condition": {"OwnerBlockIs": 0}, "effects": [{"Block": 10}]}]}
 ],
 "relics": [{"id": "tes-late", "rarity": "common", "hooks": [{"trigger": "OwnerTurnEnd", "condition": {"OwnerBlockIs": 0}, "before_hand": false, "effects": [{"Block": 10}]}]}]}"#;

fn load() {
    load_pack(IRONCLAD).unwrap();
    load_pack(RELICS).unwrap();
    load_pack(POTIONS).unwrap();
    load_pack(TEST).unwrap();
}

/// A Jaw Worm fight at 80 of 80 with these pack relics, a hand of one
/// Burn and no block.
fn fight(relics: &[&str]) -> CombatState {
    load();
    let names: Vec<String> = relics.iter().map(|r| format!("gen:{r}")).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    let deck: Vec<&str> = starter_deck().iter().map(|&c| c.def().name).collect();
    let (ids, b) = bind(&deck).unwrap();
    let mut s = CombatState::new_bound_with(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &relics_named(&refs).unwrap(), &mut Rng::new(11));
    s.hand = Hand::from_cards(&[CardId::from_name("Burn").unwrap()]);
    s.player.block = 0;
    s
}

/// Adds `n` of the pack power `id` to the player.
fn give(s: &mut CombatState, id: &str, n: i16) -> Power {
    let (b, p) = bind_power(&s.binding, id).unwrap();
    s.binding = b;
    s.player.powers.add(p, n);
    p
}

/// Ends the turn with nothing played: the monsters act, then turn 2 starts.
fn next_turn(s: &mut CombatState) {
    let mut rng = Rng::new(12);
    s.step(Action::EndTurn, &mut rng).unwrap();
    s.advance(&mut rng);
    assert!(!s.is_over());
    assert_eq!(s.stage, Stage::PlayerTurn);
}

#[test]
fn burn_metallicize_combust_in_the_games_order() {
    // Metallicize 3 (before the hand): 3 block. Burn: 2 into it, 1 left.
    // Then the atEndOfTurn pass: Combust loses 1 HP (79) and deals 5 to
    // Jaw Worm; tes-at1 sees the 1 block and gains 10: 11, Chomp's 11 all
    // blocked. (Combust before Burn, as the engine had it, leaves tes-at1
    // seeing 3: Chomp then costs 10.)
    let mut s = fight(&[]);
    s.player.powers.add(Power::Metallicize, 3);
    s.player.powers.add(Power::Combust, 1);
    s.player.powers.add(Power::CombustDamage, 5);
    give(&mut s, "tes-at1", 1);
    let worm = s.monsters[0].hp;
    next_turn(&mut s);
    assert_eq!((s.player.hp, worm - s.monsters[0].hp), (79, 5));
}

#[test]
fn plated_armor_blocks_before_burn() {
    // Plated Armor 2 (before the hand): 2 block, Burn takes it all, and
    // the atEndOfTurn pass sees 0: tes-at0 gains 10, Chomp costs 1 (79).
    let mut s = fight(&[]);
    give(&mut s, "PlatedArmor", 2);
    give(&mut s, "tes-at0", 1);
    next_turn(&mut s);
    assert_eq!(s.player.hp, 79);
}

#[test]
fn regen_heals_after_burn() {
    // At 80 of 80, Burn takes 2 (78), then Regeneration 5 heals up to the
    // cap (80): Chomp leaves 69. Regeneration before Burn would heal
    // nothing (67).
    let mut s = fight(&[]);
    let regen = give(&mut s, "Regen", 5);
    next_turn(&mut s);
    assert_eq!((s.player.hp, s.player.powers.get(regen)), (69, 4));
}

#[test]
fn relic_turn_end_hooks_act_before_the_hand_unless_marked() {
    // Orichalcum (onPlayerEndTurn) sees no block before Burn: 6, Burn
    // leaves 4, Chomp costs 7 (73).
    let mut s = fight(&["Orichalcum"]);
    next_turn(&mut s);
    assert_eq!(s.player.hp, 73);
    // tes-late (before_hand false) acts after Burn (78): no block, so 10;
    // Chomp costs 1 (77).
    let mut s = fight(&["tes-late"]);
    next_turn(&mut s);
    assert_eq!(s.player.hp, 77);
}

#[test]
fn before_hand_only_on_turn_end_hooks() {
    let bad = r#"{"version": 2, "powers": [{"id": "tes-bad", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "before_hand": true, "effects": [{"Block": 1}]}]}]}"#;
    assert!(load_pack(bad).unwrap_err().contains("before_hand"));
}
