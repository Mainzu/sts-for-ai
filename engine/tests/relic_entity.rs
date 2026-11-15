//! Relics as their own entity (docs/specs/relic-entity.md): the list the
//! player holds and its codec section.

use sts_engine::monsters::EncounterGroup;
use sts_engine::registry::{bind_relics, load_pack, relics_named, Binding};
use sts_engine::relics::RELIC_CAP;
use sts_engine::*;

const PACK: &str = include_str!("../../content/packs/act1-relics.json");

fn fight(relics: &[(String, sts_engine::relics::RelicSpec)]) -> CombatState {
    CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &Binding::default(), 50, 80, Encounter::JawWorm, relics, &mut Rng::new(3))
}

fn held(s: &CombatState) -> Vec<(&'static str, i16)> {
    s.player.relics.iter().map(|(id, c)| (id.name(), c)).collect()
}

#[test]
fn relic_list() {
    // No relic given: an empty list.
    assert!(fight(&[]).player.relics.is_empty());

    // 16 hold, in order, at the counter the caller gives.
    let mut sixteen = relics_named(&vec!["Burning Blood"; RELIC_CAP]).unwrap();
    sixteen[3].1.counter = 5;
    assert!(bind_relics(&Binding::default(), &sixteen, Character::Ironclad).is_ok());
    let s = fight(&sixteen);
    assert_eq!(s.player.relics.len(), RELIC_CAP);
    let mut want = vec![("Burning Blood", 0); RELIC_CAP];
    want[3].1 = 5;
    assert_eq!(held(&s), want);

    // A 17th is an error naming the relic.
    let seventeen = relics_named(&vec!["Burning Blood"; RELIC_CAP + 1]).unwrap();
    let e = bind_relics(&Binding::default(), &seventeen, Character::Ironclad).unwrap_err();
    assert!(e.contains("Burning Blood") && e.contains("RELIC_CAP"), "{e}");
    let panic = std::panic::catch_unwind(|| fight(&seventeen)).unwrap_err();
    let msg = panic.downcast_ref::<String>().cloned().unwrap_or_default();
    assert!(msg.contains("Burning Blood") && msg.contains("RELIC_CAP"), "{msg}");

    // Pack relics by name, in the given order; a relic that doesn't act in
    // this fight's kind isn't held.
    load_pack(PACK).unwrap();
    let r = relics_named(&["gen:Vajra", "gen:Anchor"]).unwrap();
    assert_eq!(held(&fight(&r)), [("gen:Vajra", 0), ("gen:Anchor", 0)]);
    let mut elite_only = relics_named(&["gen:Vajra"]).unwrap();
    assert!(elite_only[0].1.acts_in(EncounterGroup::Hallway));
    elite_only[0].1.fights = 0b010;
    assert!(fight(&elite_only).player.relics.is_empty());
}

#[test]
fn codec_relics() {
    load_pack(PACK).unwrap();
    // A relic-free fight writes no relic section (its bytes are pinned by
    // codec_golden); a held relic adds section 7 after every other.
    let mut r = relics_named(&["gen:Vajra", "Burning Blood"]).unwrap();
    r[1].1.counter = -3;
    let s = fight(&r);
    assert!(!s.has_generated());
    let bytes = codec::encode(&s);
    let back = codec::decode(&bytes);
    assert_eq!(back, s);
    assert_eq!(held(&back), [("gen:Vajra", 0), ("Burning Blood", -3)]);

    let mut bare = s;
    bare.player.relics = Default::default();
    let without = codec::encode(&bare);
    assert!(bytes.starts_with(&without) && bytes[without.len()] == 7, "the relic section comes last");
    assert_eq!(codec::decode(&without), bare);

    // An unknown relic name doesn't decode.
    let mut bad = bytes.clone();
    let at = bad.iter().rposition(|&b| b == b'V').unwrap();
    bad[at] = b'Q';
    assert!(codec::try_decode(&bad).is_none());
}

/// Loads a pack of test relics and powers (each test its own names: the
/// registry is shared by the binary's tests).
fn pack(powers: &str, relics: &str) {
    load_pack(&format!("{{\"version\": 2, \"powers\": [{powers}], \"relics\": [{relics}]}}")).unwrap();
}

fn fight_at(relics: &[&str], hp: i16) -> CombatState {
    let r = relics_named(relics).unwrap();
    let b = bind_relics(&Binding::default(), &r, Character::Ironclad).unwrap();
    CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &b, hp, 80, Encounter::JawWorm, &r, &mut Rng::new(3))
}

#[test]
fn relic_hooks_first() {
    // Turn 1's OwnerTurnStart (after the post-draw hooks): the relic's hook
    // runs before the power's, so only the second one sees the HP loss.
    pack(
        r#"{"id": "RhfLose", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "effects": [{"LoseHp": 1}]}]},
           {"id": "RhfGuard", "hooks": [{"trigger": "OwnerTurnStart", "condition": "OwnerHpAtMostHalf", "effects": [{"Block": 5}]}]}"#,
        r#"{"id": "rhf-guard-first", "rarity": "common", "powers": [{"power": "RhfLose", "amount": 1}],
            "hooks": [{"trigger": "OwnerTurnStart", "condition": "OwnerHpAtMostHalf", "effects": [{"Block": 7}]}]},
           {"id": "rhf-lose-first", "rarity": "common", "powers": [{"power": "RhfGuard", "amount": 1}],
            "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "effects": [{"LoseHp": 1}]}]}"#,
    );
    let s = fight_at(&["gen:rhf-guard-first"], 41);
    assert_eq!((s.player.hp, s.player.block), (40, 0), "the relic's guard ran before the power's HP loss");
    let s = fight_at(&["gen:rhf-lose-first"], 41);
    assert_eq!((s.player.hp, s.player.block), (40, 5), "the power's guard saw the relic's HP loss");

    // Two relics run in list order.
    pack(
        "",
        r#"{"id": "rhf-a", "rarity": "common", "hooks": [{"trigger": "OwnerTurnStart", "condition": "OwnerHpAtMostHalf", "effects": [{"Block": 3}]}]},
           {"id": "rhf-b", "rarity": "common", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "effects": [{"LoseHp": 1}]}]}"#,
    );
    assert_eq!(fight_at(&["gen:rhf-a", "gen:rhf-b"], 41).player.block, 0);
    assert_eq!(fight_at(&["gen:rhf-b", "gen:rhf-a"], 41).player.block, 3);
}

#[test]
fn combat_start_order() {
    // A counter chain: each step fires only after the one before it.
    pack(
        r#"{"id": "CsoWard", "hooks": [{"trigger": "CombatStart", "condition": "Always", "effects": [{"Block": 4}]}]}"#,
        r#"{"id": "cso-chain", "rarity": "common", "hooks": [
            {"trigger": "CombatStartPreDraw", "condition": "Always", "effects": [{"SetCounter": 1}, {"Draw": 2}, {"Apply": {"power": "CsoWard", "amount": 1, "target": "Me"}}]},
            {"trigger": "CombatStart", "condition": {"CounterIs": 1}, "effects": [{"SetCounter": 2}]},
            {"trigger": "OwnerTurnStartPostDraw", "condition": {"CounterIs": 2}, "effects": [{"SetCounter": 3}]},
            {"trigger": "OwnerTurnStart", "condition": {"CounterIs": 3}, "effects": [{"SetCounter": 4}]}]}"#,
    );
    let mut s = fight_at(&["gen:cso-chain"], 80);
    assert_eq!(s.player.relics.counter(0), 4, "pre-draw, combat start, post-draw, turn start, in that order");
    // The pre-draw Draw joins the opening draw: one draw of 7.
    assert_eq!(s.hand.len(), 7);
    // A power may use CombatStart too: one held by then (given before the
    // draw; a power a relic applies in a pass first fires on the next pass,
    // docs/specs/fight-vocabulary.md, so one the `powers` shorthand gives at
    // CombatStart misses that CombatStart, as in the game's queue).
    assert_eq!(s.player.block, 4);
    // Neither fires again on turn 2.
    let mut rng = Rng::new(9);
    s.step(Action::EndTurn, &mut rng).unwrap();
    assert_eq!((s.turn, s.player.relics.counter(0), s.player.block), (2, 4, 0));
}

#[test]
fn counter_effects() {
    // AddCounter then CounterIs, hooks in written order.
    pack(
        r#"{"id": "CeNever", "hooks": [{"trigger": "OwnerTurnStart", "condition": {"CounterIs": 0}, "effects": [{"Block": 50}]}]}"#,
        r#"{"id": "ce-count", "rarity": "common", "counter": 10, "powers": [{"power": "CeNever", "amount": 1}], "hooks": [
            {"trigger": "OwnerPlaysCard", "condition": "Always", "effects": [{"AddCounter": 1}]},
            {"trigger": "OwnerPlaysCard", "condition": {"CounterIs": 12}, "effects": [{"Block": 9}]}]}"#,
    );
    let mut s = fight_at(&["gen:ce-count"], 80);
    // CounterIs is false in a power's hook (its counter would be 0).
    assert_eq!((s.player.relics.counter(0), s.player.block), (10, 0), "the file's counter; no power counter");
    let mut rng = Rng::new(5);
    let mut play = |s: &mut CombatState| {
        let a = s.legal_actions().into_iter().find(|a| matches!(a, Action::Play { .. })).expect("a playable card");
        s.step(a, &mut rng).unwrap();
    };
    play(&mut s);
    assert_eq!((s.player.relics.counter(0), s.player.block >= 9), (11, false));
    let before = s.player.block;
    play(&mut s);
    assert_eq!(s.player.relics.counter(0), 12);
    assert!(s.player.block >= before + 9, "the relic's block at counter 12");

    // Counter effects only in a relic's hooks; stack effects never there.
    let pw = |e: &str| load_pack(&format!(r#"{{"version": 2, "powers": [{{"id": "CeBad", "hooks": [{{"trigger": "OwnerTurnEnd", "condition": "Always", "effects": [{e}]}}]}}]}}"#));
    assert!(pw(r#"{"SetCounter": 1}"#).unwrap_err().contains("only a relic's hook"));
    assert!(pw(r#"{"AddCounter": 1}"#).unwrap_err().contains("only a relic's hook"));
    let card = load_pack(r#"{"version": 2, "cards": [{"id": "ce-card", "cost": 1, "type": "Skill", "effects": [{"AddCounter": 1}]}]}"#);
    assert!(card.unwrap_err().contains("AddCounter"));
    let rl = |e: &str| load_pack(&format!(r#"{{"version": 2, "relics": [{{"id": "ce-bad", "rarity": "common", "hooks": [{{"trigger": "OwnerTurnEnd", "condition": "Always", "effects": [{e}]}}]}}]}}"#));
    let e = rl(r#""RemoveSelf""#).unwrap_err();
    assert!(e.contains("ce-bad") && e.contains("power's stacks"), "{e}");
    let e = load_pack(r#"{"version": 2, "relics": [{"id": "ce-bad2", "rarity": "common", "counter": 99999}]}"#).unwrap_err();
    assert!(e.contains("ce-bad2") && e.contains("counter"), "{e}");
}

#[test]
fn relic_keys_guard() {
    // A new relic key needs a read (and words under `relic_rule` when it
    // states a rule): update this list with them.
    assert_eq!(sts_engine::relics::RELIC_KEYS, ["id", "rarity", "powers", "fights", "win_heal", "hooks", "counter", "potion_potency", "potion_slots", "draw_per_turn", "x_bonus",
        "keeps_energy", "plays_per_turn", "keeps_hand", "heal_scale", "exhaust_save", "sees_draw_order", "hides_intents", "no_potions", "bottles"]);
    let words = sts_engine::registry::element_names().into_iter().find(|(f, _)| *f == "relic_rule").unwrap().1;
    for k in ["fights", "win_heal", "counter", "potion_potency", "potion_slots", "draw_per_turn", "x_bonus", "keeps_energy", "plays_per_turn", "keeps_hand", "heal_scale", "exhaust_save"] {
        assert!(words.contains(&k), "relic_rule {k} has no words");
    }
    let e = load_pack(r#"{"version": 2, "relics": [{"id": "rkg", "rarity": "common", "charges": 1}]}"#).unwrap_err();
    assert!(e.contains("rkg") && e.contains("charges") && e.contains("counter"), "{e}");
}

/// The fight after the player ends turn 1: the monsters' rolls pending,
/// the player's turn-start hooks still to run.
fn after_end_turn(relics: &[&str]) -> CombatState {
    let mut s = fight_at(relics, 80);
    s.apply_action(Action::EndTurn).unwrap();
    s
}

#[test]
fn turn_start_leaf_runs_relic_hooks() {
    // Mercury Hourglass's turn-start damage as a relic hook, and the same
    // hook on a power the player holds: the leaf runs both alike.
    load_pack(PACK).unwrap();
    pack(
        r#"{"id": "TslHourglass", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "effects": [{"PlainDamage": {"amount": 3, "target": "AllOpponents"}}]}]}"#,
        r#"{"id": "tsl-power", "rarity": "common", "hooks": [{"trigger": "CombatStartPreDraw", "condition": "Always", "effects": [{"Apply": {"power": "TslHourglass", "amount": 1, "target": "Me"}}]}]}"#,
    );
    let relic = after_end_turn(&["gen:Mercury Hourglass"]);
    let power = after_end_turn(&["gen:tsl-power"]);
    assert!(matches!(relic.stage, Stage::MonsterRolls { .. }), "{:?}", relic.stage);
    let p = power.turn_start_leaf().expect("the power's hook is due");
    let r = relic.turn_start_leaf().expect("the relic's hook is due");
    let hp = |s: &CombatState| s.monsters.iter().map(|m| m.hp).collect::<Vec<_>>();
    assert_eq!(hp(&r), hp(&p));
    assert_eq!(hp(&r)[0], hp(&relic)[0] - 3);

    // A relic's counter effects run in the leaf too (Lantern's once-only energy).
    pack(
        "",
        r#"{"id": "tsl-lantern", "rarity": "common", "counter": 1, "hooks": [{"trigger": "OwnerTurnStart", "condition": {"CounterIs": 1}, "effects": [{"GainEnergy": 1}, {"SetCounter": 2}]}]}"#,
    );
    let mut s = after_end_turn(&["gen:tsl-lantern"]);
    assert_eq!(s.player.relics.counter(0), 2, "turn 1's start set it");
    s.player.relics.set_counter(0, 1);
    let t = s.turn_start_leaf().expect("the relic's hook is due");
    assert_eq!((t.player.energy, t.player.relics.counter(0)), (s.player.energy + 1, 2));
}

#[test]
fn relic_heal_lifts_the_bound() {
    pack(
        "",
        r#"{"id": "rhb-heal", "rarity": "common", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "effects": [{"Heal": 5}]}]}"#,
    );
    let mut s = fight_at(&["gen:rhb-heal"], 50);
    s.player.hp = 30;
    assert!(s.can_heal(), "a relic's Heal hook can still heal");
    assert_eq!(s.upper_bound(), 2.0);
}
