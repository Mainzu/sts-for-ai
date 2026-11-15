//! Hooks that act first in a turn-end pass (`acts_first`, `Hook::first`):
//! the game's `addToTop` puts their work ahead of what the pass queued
//! before them. Regeneration (`RegenPower.atEndOfTurn`) and Orichalcum
//! (`Orichalcum.onPlayerEndTurn`) are the Act 1 ones.

use sts_engine::registry::{bind, bind_power, load_pack, potions_named, relics_named};
use sts_engine::*;

const IRONCLAD: &str = include_str!("../../content/packs/act1-ironclad.json");
const POTIONS: &str = include_str!("../../content/packs/act1-potions.json");
const RELICS: &str = include_str!("../../content/packs/act1-relics.json");

/// Test content: a relic that gains block at turn end in order (as Cloak
/// Clasp), and two powers that act first at the HP cap.
const TEST: &str = r#"{"version": 2,
 "powers": [
  {"id": "tef-lose", "hooks": [{"trigger": "OwnerTurnEnd", "condition": "Always", "acts_first": true, "effects": [{"LoseHp": 1}]}]},
  {"id": "tef-heal", "hooks": [{"trigger": "OwnerTurnEnd", "condition": "Always", "acts_first": true, "effects": [{"Heal": 1}]}]}
 ],
 "relics": [{"id": "tef-clasp", "rarity": "common", "hooks": [{"trigger": "OwnerTurnEnd", "condition": "Always", "effects": [{"Block": 1}]}]}]}"#;

fn load() {
    load_pack(IRONCLAD).unwrap();
    load_pack(RELICS).unwrap();
    load_pack(POTIONS).unwrap();
    load_pack(TEST).unwrap();
}

/// A Jaw Worm fight at `hp` of `max_hp` with these pack relics.
fn fight(hp: i16, max_hp: i16, relics: &[&str]) -> CombatState {
    load();
    let names: Vec<String> = relics.iter().map(|r| format!("gen:{r}")).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    let deck: Vec<&str> = starter_deck().iter().map(|&c| c.def().name).collect();
    let (ids, b) = bind(&deck).unwrap();
    CombatState::new_bound_with(Character::Ironclad, &ids, &b, hp, max_hp, Encounter::JawWorm, &relics_named(&refs).unwrap(), &mut Rng::new(11))
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
fn regen_heals_before_combusts_hp_loss() {
    // Live run 12 (Lagavulin): at 85 of 85 with Regeneration and Combust,
    // the game heals first (the cap cuts it off), then loses 1: 84.
    let mut s = fight(85, 85, &[]);
    s.give_potions(&potions_named(&["gen:Regen Potion"]).unwrap()).unwrap();
    let a = *s.legal_actions().iter().find(|a| matches!(a, Action::UsePotion { slot: 0, .. })).unwrap();
    s.step(a, &mut Rng::new(1)).unwrap();
    let regen = bind_power(&s.binding, "Regen").unwrap().1;
    s.player.powers.add(Power::Combust, 1);
    s.player.block = 100;
    next_turn(&mut s);
    assert_eq!((s.player.hp, s.player.powers.get(regen)), (84, 4));
}

#[test]
fn orichalcum_checks_before_earlier_relics_block() {
    // The game calls each relic's onPlayerEndTurn in turn: a relic before
    // Orichalcum queues its block at the bottom, so Orichalcum still sees
    // none and gains 6 on top: 7 block, and Chomp (11) costs 4.
    let mut s = fight(50, 80, &["tef-clasp", "Orichalcum"]);
    next_turn(&mut s);
    assert_eq!(s.player.hp, 46);
}

#[test]
fn hooks_that_act_first_run_last_called_first() {
    // tef-lose is called before tef-heal; both go on top, so the heal
    // (cut off at the cap) comes first, then the loss.
    let mut s = fight(80, 80, &[]);
    let (b, lose) = bind_power(&s.binding, "tef-lose").unwrap();
    let (b, heal) = bind_power(&b, "tef-heal").unwrap();
    s.binding = b;
    s.player.powers.add(lose, 1);
    s.player.powers.add(heal, 1);
    s.player.block = 100;
    next_turn(&mut s);
    assert_eq!(s.player.hp, 79);
}

#[test]
fn acts_first_only_on_queued_triggers() {
    let bad = r#"{"version": 2, "powers": [{"id": "tef-bad", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "acts_first": true, "effects": [{"Block": 1}]}]}]}"#;
    assert!(load_pack(bad).unwrap_err().contains("acts_first"));
}
