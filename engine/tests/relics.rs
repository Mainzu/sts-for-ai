//! The relic kind (docs/specs/relics.md, step 3): relic entries in packs
//! and in the official `content/relics.json`, their load errors, and the
//! starter relic's heal read from data.

use sts_engine::monsters::EncounterGroup;
use sts_engine::registry::{load_pack, official_relics, pack_relic_names, relic, OFFICIAL_RELICS};
use sts_engine::relics::{parse_official_relics, Rarity};
use sts_engine::*;

fn pack(relics: &str) -> String {
    format!(
        r#"{{"version": 1, "powers": [{{"id": "rk_power", "hooks": [{{"trigger": "OwnerTurnStart", "condition": "Always", "effects": [{{"GainEnergy": 1}}, "RemoveSelf"]}}]}}], "relics": [{relics}]}}"#
    )
}

#[test]
fn relic_load_errors() {
    for (entry, want) in [
        (r#"{"rarity": "common"}"#, "relic without an id"),
        (r#"{"id": "rk_a"}"#, "\"rk_a\": no rarity"),
        (r#"{"id": "rk_b", "rarity": "legendary"}"#, "\"rk_b\": unknown rarity \"legendary\""),
        (r#"{"id": "rk_c", "rarity": "common", "fights": ["elite", "shop"]}"#, "\"rk_c\": unknown fight kind"),
        (r#"{"id": "rk_d", "rarity": "common", "fights": []}"#, "\"rk_d\": fights is empty"),
        (r#"{"id": "rk_d2", "rarity": "common", "fights": "elite"}"#, "\"rk_d2\": fights must be a list"),
        (r#"{"id": "rk_e", "rarity": "common", "powers": [{"power": "Nope", "amount": 1}]}"#, "\"rk_e\": power \"Nope\" is not official nor a loaded pack power"),
        (r#"{"id": "rk_f", "rarity": "common", "win_heal": -2}"#, "\"rk_f\": win_heal -2 is negative"),
        (r#"{"id": "rk_g", "rarity": "common", "colour": "red"}"#, "\"rk_g\": unknown key \"colour\""),
        (r#"{"id": "rk_h", "rarity": "common", "powers": [{"power": "Strength"}]}"#, "\"rk_h\": power \"Strength\": amount must be an integer"),
        (r#"{"id": "rk_i", "rarity": "common"}, {"id": "rk_i", "rarity": "rare"}"#, "relic \"rk_i\" twice in the pack"),
    ] {
        let e = load_pack(&pack(entry)).expect_err(entry);
        assert!(e.contains(want), "{entry}: {e}");
    }
    // Nothing from a refused pack is loaded.
    assert!(relic("gen:rk_i").is_none());
    // Redefinition across packs.
    load_pack(&pack(r#"{"id": "rk_j", "rarity": "common", "win_heal": 1}"#)).unwrap();
    load_pack(&pack(r#"{"id": "rk_j", "rarity": "common", "win_heal": 1}"#)).expect("the same definition again is skipped");
    let e = load_pack(&pack(r#"{"id": "rk_j", "rarity": "common", "win_heal": 2}"#)).unwrap_err();
    assert!(e.contains("pack relic \"rk_j\" redefined"), "{e}");
    // The official file names official powers only.
    let e = parse_official_relics(r#"{"version": 1, "relics": [{"id": "X", "rarity": "common", "powers": [{"power": "rk_power", "amount": 1}]}]}"#).unwrap_err();
    assert!(e.contains("\"X\": power \"rk_power\" is not an official power"), "{e}");
    let e = parse_official_relics(r#"{"version": 1, "relics": [{"id": "X", "rarity": "common"}, {"id": "X", "rarity": "rare"}]}"#).unwrap_err();
    assert!(e.contains("relic \"X\" twice in the file"), "{e}");
}

#[test]
fn a_pack_relic_loads_with_its_fields() {
    load_pack(&pack(
        r#"{"id": "rk_full", "rarity": "boss", "powers": [{"power": "Strength", "amount": 2}, {"power": "rk_power", "amount": 1}], "fights": ["elite", "boss"], "win_heal": 3}"#,
    ))
    .unwrap();
    let r = relic("gen:rk_full").expect("loaded");
    assert_eq!(r.rarity, Rarity::Boss);
    assert_eq!(r.powers, vec![(Power::Strength, 2)]);
    assert_eq!(r.gen_powers.len(), 1);
    assert_eq!(r.win_heal, 3);
    assert!(!r.acts_in(EncounterGroup::Hallway) && r.acts_in(EncounterGroup::Elite) && r.acts_in(EncounterGroup::Boss));
    assert!(pack_relic_names().contains(&"gen:rk_full".to_string()));
    // Without `fights`, every fight.
    load_pack(&pack(r#"{"id": "rk_all", "rarity": "common"}"#)).unwrap();
    let r = relic("gen:rk_all").unwrap();
    assert!([EncounterGroup::Hallway, EncounterGroup::Elite, EncounterGroup::Boss].into_iter().all(|g| r.acts_in(g)));
    assert!(relic("rk_all").is_none(), "pack relics are named gen:<id>");
}

#[test]
fn burning_blood_from_data() {
    // The heal half (step 3): Burning Blood is the Ironclad's starter relic,
    // its 6 comes from content/relics.json, and a won fight heals it.
    assert_eq!(Character::Ironclad.starter_relic(), Some("Burning Blood"));
    assert_eq!(Character::Silent.starter_relic(), None);
    let bb = relic("Burning Blood").expect("an official relic");
    assert_eq!((bb.rarity, bb.win_heal), (Rarity::Starter, 6));
    assert_eq!(official_relics().len(), 1);
    assert_eq!(Character::Ironclad.win_heal(), bb.win_heal);
    assert_eq!(Character::Silent.win_heal(), 0);
    // The number is the file's: the same file with another heal parses to it.
    let edited = parse_official_relics(&OFFICIAL_RELICS.replace("\"win_heal\": 6", "\"win_heal\": 9")).unwrap();
    assert_eq!(edited[0].1.win_heal, 9);
    // A won fight heals it: one more hit wins (a Jaw Worm at 1 HP, no block).
    let mut s = CombatState::new(&starter_deck(), 50, 80, Encounter::JawWorm, &mut Rng::new(1));
    s.monsters[0].hp = 1;
    s.monsters[0].block = 0;
    let strike = s.legal_actions().into_iter().find(|a| matches!(a, Action::Play { target: Some(_), .. })).expect("an attack in the opening hand");
    s.step(strike, &mut Rng::new(2)).unwrap();
    assert!(s.won());
    assert_eq!(s.player.hp, 56);
}

// ---- giving relics to a fight (step 4) ----

use sts_engine::monsters::MonsterKind as Kind;
use sts_engine::registry::{bind_relics, relics_named, Binding, POWER_SLOTS};

fn give(names: &[&str]) -> Vec<(String, sts_engine::relics::RelicSpec)> {
    relics_named(names).unwrap()
}

fn fight(enc: Encounter, relics: &[&str], seed: u64) -> CombatState {
    CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &Binding::default(), 50, 80, enc, &give(relics), &mut Rng::new(seed))
}

#[test]
fn burning_blood_twice_heals_twice() {
    // The two-copy half: the starter is always held, naming it adds its heal again.
    let mut s = fight(Encounter::JawWorm, &["Burning Blood"], 1);
    assert_eq!(s.win_heal, 12);
    s.monsters[0].hp = 1;
    s.monsters[0].block = 0;
    let strike = s.legal_actions().into_iter().find(|a| matches!(a, Action::Play { target: Some(_), .. })).unwrap();
    s.step(strike, &mut Rng::new(2)).unwrap();
    assert!(s.won());
    assert_eq!(s.player.hp, 62);
}

#[test]
fn no_relics_is_the_fight_today() {
    for (enc, seed) in [(Encounter::JawWorm, 3), (Encounter::GremlinNob, 4), (Encounter::ALL[0], 5)] {
        let plain = CombatState::new(&starter_deck(), 50, 80, enc, &mut Rng::new(seed));
        assert!(fight(enc, &[], seed) == plain);
        assert_eq!(codec::encode(&fight(enc, &[], seed)), codec::encode(&plain));
    }
}

#[test]
fn a_pack_relic_fight() {
    load_pack(
        r#"{"version": 1, "powers": [{"id": "rg_anchor", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "effects": [{"Block": 10}, "RemoveSelf"]}]}],
            "relics": [{"id": "rg_str", "rarity": "common", "powers": [{"power": "Strength", "amount": 2}]},
                       {"id": "rg_anchor", "rarity": "common", "powers": [{"power": "rg_anchor", "amount": 1}]}]}"#,
    )
    .unwrap();
    let mut s = fight(Encounter::JawWorm, &["gen:rg_str", "gen:rg_anchor"], 7);
    assert_eq!(s.player.powers.get(Power::Strength), 2);
    assert_eq!(s.player.block, 10, "turn 1's hook gives its block after the block reset");
    assert!(s.has_generated(), "a pack relic's power is bound");
    assert!(s.player.powers.iter().all(|(p, _)| !Power::GEN.contains(&p)), "the turn-1 power removed itself");
    assert_eq!(s.win_heal, 6);
    // Turn 2: Strength stays, the block doesn't come back.
    let end = s.legal_actions().into_iter().find(|a| matches!(a, Action::EndTurn)).unwrap();
    let mut rng = Rng::new(8);
    s.step(end, &mut rng).unwrap();
    s.advance(&mut rng);
    assert_eq!(s.turn, 2);
    assert_eq!(s.player.powers.get(Power::Strength), 2);
    assert_eq!(s.player.block, 0);
    // Only the Strength relic: an official power, so the fight encodes.
    let o = fight(Encounter::JawWorm, &["gen:rg_str"], 7);
    assert!(!o.has_generated());
    codec::encode(&o);
}

#[test]
fn the_fights_filter() {
    load_pack(
        r#"{"version": 1, "powers": [{"id": "rg_e_pow", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "effects": [{"GainEnergy": 1}]}]}],
            "relics": [{"id": "rg_elite", "rarity": "shop", "powers": [{"power": "Strength", "amount": 1}, {"power": "rg_e_pow", "amount": 1}], "fights": ["elite"], "win_heal": 2}]}"#,
    )
    .unwrap();
    // A hallway fight: the relic does nothing, not even a bound slot.
    let hall = fight(Encounter::JawWorm, &["gen:rg_elite"], 9);
    assert!(hall == fight(Encounter::JawWorm, &[], 9));
    // An elite fight: its powers and heal.
    let elite = fight(Encounter::GremlinNob, &["gen:rg_elite"], 9);
    assert_eq!(elite.player.powers.get(Power::Strength), 1);
    assert_eq!(elite.player.energy, 4);
    assert_eq!(elite.win_heal, 8);
    // Without an encounter, the caller names the kind.
    let vs = |g| {
        CombatState::new_with(Character::Ironclad, &starter_deck(), &Binding::default(), 50, 80, &[Kind::GremlinNob], g, &give(&["gen:rg_elite"]), &mut Rng::new(9))
    };
    assert_eq!(vs(EncounterGroup::Hallway).player.powers.get(Power::Strength), 0);
    assert_eq!(vs(EncounterGroup::Elite).player.powers.get(Power::Strength), 1);
}

#[test]
fn relic_errors_name_the_relic() {
    let e = relics_named(&["Vajra"]).unwrap_err();
    assert!(e.contains("unknown relic \"Vajra\""), "{e}");
    let e = relics_named(&["gen:rg_nope"]).unwrap_err();
    assert!(e.contains("unknown relic \"gen:rg_nope\""), "{e}");
    // More pack powers than the slots hold.
    let n = POWER_SLOTS + 1;
    let powers: Vec<String> = (0..n).map(|i| format!(r#"{{"id": "rg_many{i}", "hooks": [{{"trigger": "OwnerTurnEnd", "condition": "Always", "effects": [{{"Block": 1}}]}}]}}"#)).collect();
    let refs: Vec<String> = (0..n).map(|i| format!(r#"{{"power": "rg_many{i}", "amount": 1}}"#)).collect();
    load_pack(&format!(r#"{{"version": 1, "powers": [{}], "relics": [{{"id": "rg_many", "rarity": "rare", "powers": [{}]}}]}}"#, powers.join(","), refs.join(","))).unwrap();
    let e = bind_relics(&Binding::default(), &give(&["gen:rg_many"]), Character::Ironclad).unwrap_err();
    assert!(e.starts_with("relic \"gen:rg_many\": "), "{e}");
}
