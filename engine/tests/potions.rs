//! Potions held in a fight (docs/specs/potions.md, step 2): the list the
//! player holds, its codec section, the entry format and its guard.

use sts_engine::potions::{PotionId, POTION_CAP, POTION_KEYS};
use sts_engine::registry::{load_pack, potion, potions_named, Binding};
use sts_engine::*;

/// Test potions (names of their own: the registry is shared by the
/// binary's tests). `pl-weak` applies a pack power, so a fight holding it
/// binds that power.
const PACK: &str = r#"{"version": 2, "powers": [
{"id": "PlTestFade", "hooks": [{"trigger": "OwnerTurnEnd", "condition": "Always", "effects": ["RemoveSelf"]}]}
], "potions": [
{"id": "pl-fire", "rarity": "common", "potency": 20, "effects": [{"Damage": {"amount": 20, "target": "Opponent"}}]},
{"id": "pl-swift", "rarity": "common", "potency": 3, "effects": [{"Draw": 3}]},
{"id": "pl-block", "rarity": "common", "potency": 12, "effects": [{"Block": 12}]},
{"id": "pl-rows", "rarity": "uncommon", "effects": [{"Block": 1}], "rows": [{"condition": "OwnerHpAtMostHalf", "effects": [{"Draw": 1}]}]},
{"id": "pl-weak", "rarity": "rare", "potency": 1, "effects": [{"Apply": {"power": "PlTestFade", "amount": 1, "target": "Me"}}]}
]}"#;

fn load() {
    load_pack(PACK).unwrap();
}

fn fight() -> CombatState {
    CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &Binding::default(), 50, 80, Encounter::JawWorm, &[], &mut Rng::new(3))
}

fn holding(names: &[&str]) -> CombatState {
    let mut s = fight();
    s.give_potions(&potions_named(names).unwrap()).unwrap();
    s
}

fn held(s: &CombatState) -> Vec<&'static str> {
    s.player.potions.iter().map(PotionId::name).collect()
}

#[test]
fn potion_list() {
    load();
    // No potion given: an empty list, and the state is the potion-free one.
    assert!(fight().player.potions.is_empty());
    assert_eq!(holding(&[]), fight());

    // Kept sorted by name: the order given doesn't matter.
    let a = holding(&["gen:pl-swift", "gen:pl-fire"]);
    let b = holding(&["gen:pl-fire", "gen:pl-swift"]);
    assert_eq!(a, b);
    assert_eq!(held(&a), ["gen:pl-fire", "gen:pl-swift"]);

    // Copies are kept; 5 hold, a 6th is an error naming it.
    let five = ["gen:pl-fire", "gen:pl-fire", "gen:pl-swift", "gen:pl-block", "gen:pl-rows"];
    assert_eq!(POTION_CAP, 5);
    assert_eq!(held(&holding(&five)), ["gen:pl-block", "gen:pl-fire", "gen:pl-fire", "gen:pl-rows", "gen:pl-swift"]);
    let six = [&five[..], &["gen:pl-swift"]].concat();
    let e = potions_named(&six).unwrap_err();
    assert!(e.contains("gen:pl-swift") && e.contains("POTION_CAP"), "{e}");
    // Given in two goes, the cap holds too, and the state stays as it was.
    let mut s = holding(&five);
    let e = s.give_potions(&potions_named(&["gen:pl-block"]).unwrap()).unwrap_err();
    assert!(e.contains("gen:pl-block") && e.contains("POTION_CAP"), "{e}");
    assert_eq!(s, holding(&five));

    // Unknown names are errors naming them.
    assert!(potions_named(&["gen:pl-nope"]).unwrap_err().contains("gen:pl-nope"));
    assert!(potions_named(&["Nope Potion"]).unwrap_err().contains("Nope Potion"));

    // Removing one keeps the order.
    let mut p = holding(&five).player.potions;
    assert_eq!(p.remove(1).name(), "gen:pl-fire");
    assert_eq!(p.iter().map(PotionId::name).collect::<Vec<_>>(), ["gen:pl-block", "gen:pl-fire", "gen:pl-rows", "gen:pl-swift"]);

    // Monsters hold none; the potions don't change the fight otherwise.
    let s = holding(&["gen:pl-fire"]);
    let mut bare = s.clone();
    bare.player.potions = Default::default();
    assert_eq!(bare, fight());
    // Beyond their own uses (step 3), the same actions.
    let no_uses: Vec<Action> = s.legal_actions().into_iter().filter(|a| !matches!(a, Action::UsePotion { .. })).collect();
    assert_eq!(no_uses, fight().legal_actions());
}

#[test]
fn potion_entries() {
    load();
    let fire = potion("gen:pl-fire").unwrap();
    assert_eq!(fire.potency, 20);
    assert_eq!(fire.rarity.name(), "common");
    assert_eq!(fire.rows.len(), 1);
    let rows = potion("gen:pl-rows").unwrap();
    assert_eq!(rows.potency, 0, "potency defaults to 0");
    assert_eq!(rows.rows.len(), 2);
    // A potion applying a pack power binds it when held.
    let s = holding(&["gen:pl-weak"]);
    assert!(!s.binding.is_empty());
    assert!(fight().binding.is_empty());
    // A reload of the same pack is fine; a changed entry is an error.
    load();
    let e = load_pack(r#"{"version": 2, "potions": [{"id": "pl-fire", "rarity": "common", "potency": 21, "effects": [{"Damage": {"amount": 20, "target": "Opponent"}}]}]}"#).unwrap_err();
    assert!(e.contains("pl-fire") && e.contains("redefined"), "{e}");
}

#[test]
fn potion_keys_guard() {
    // A new potion key needs a read (and words under `potion_rule` when it
    // changes play).
    assert_eq!(POTION_KEYS, ["id", "rarity", "potency", "effects", "rows", "trigger", "fights"]);
    let words = registry::element_names().into_iter().find(|(f, _)| *f == "potion_rule").unwrap().1;
    assert!(words.contains(&"potency"), "potion_rule potency has no words");
    let bad = |entry: &str| load_pack(&format!(r#"{{"version": 2, "potions": [{entry}]}}"#)).unwrap_err();
    let e = bad(r#"{"id": "pkg", "rarity": "common", "charges": 1, "effects": [{"Block": 1}]}"#);
    assert!(e.contains("pkg") && e.contains("charges"), "{e}");
    let e = bad(r#"{"id": "pkg2", "rarity": "boss", "effects": [{"Block": 1}]}"#);
    assert!(e.contains("pkg2") && e.contains("boss"), "{e}");
    let e = bad(r#"{"id": "pkg3", "effects": [{"Block": 1}]}"#);
    assert!(e.contains("pkg3") && e.contains("rarity"), "{e}");
    let e = bad(r#"{"id": "pkg4", "rarity": "common", "potency": -1, "effects": [{"Block": 1}]}"#);
    assert!(e.contains("pkg4") && e.contains("potency"), "{e}");
    let e = bad(r#"{"id": "pkg5", "rarity": "common"}"#);
    assert!(e.contains("pkg5") && e.contains("no effects"), "{e}");
    let e = bad(r#"{"id": "pkg6", "rarity": "common", "effects": [{"Apply": {"power": "NoSuchPackPower", "amount": 1, "target": "Me"}}]}"#);
    assert!(e.contains("pkg6"), "{e}");
    let e = bad(r#"{"id": "pkg7", "rarity": "common", "effects": ["ReplayCard"]}"#);
    assert!(e.contains("pkg7"), "{e}");
    let e = bad(r#"{"id": "pkg9", "rarity": "common", "effects": [{"Block": 1}], "rows": [{"condition": {"CounterIs": 1}, "effects": [{"Block": 1}]}]}"#);
    assert!(e.contains("pkg9") && e.contains("CounterIs"), "{e}");
    // Two of one id in a pack.
    let e = bad(r#"{"id": "pkg8", "rarity": "common", "effects": [{"Block": 1}]}, {"id": "pkg8", "rarity": "common", "effects": [{"Block": 2}]}"#);
    assert!(e.contains("pkg8") && e.contains("twice"), "{e}");
    // Nothing from a refused pack is loaded.
    assert!(potion("gen:pkg").is_none() && potion("gen:pkg8").is_none());
    // The official file parses (empty until official potions are written).
    let _ = registry::official_potions();
}

#[test]
fn codec_potions() {
    load();
    // A potion-free fight writes no potion section (its bytes are pinned by
    // codec_golden); held potions add section 8 after every other.
    let s = holding(&["gen:pl-swift", "gen:pl-fire", "gen:pl-fire"]);
    assert!(!s.has_generated());
    let bytes = codec::encode(&s);
    let back = codec::decode(&bytes);
    assert_eq!(back, s);
    assert_eq!(held(&back), ["gen:pl-fire", "gen:pl-fire", "gen:pl-swift"]);

    let mut bare = s;
    bare.player.potions = Default::default();
    let without = codec::encode(&bare);
    assert!(bytes.starts_with(&without) && bytes[without.len()] == 8, "the potion section comes last");
    assert_eq!(codec::decode(&without), bare);
    assert_eq!(without, codec::encode(&fight()));

    // With relics too: section 7, then 8.
    let pack = include_str!("../../content/packs/act1-relics.json");
    load_pack(pack).unwrap();
    let relics = registry::relics_named(&["gen:Vajra"]).unwrap();
    let mut r = CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &Binding::default(), 50, 80, Encounter::JawWorm, &relics, &mut Rng::new(3));
    r.give_potions(&potions_named(&["gen:pl-block"]).unwrap()).unwrap();
    assert_eq!(codec::decode(&codec::encode(&r)), r);

    // An unknown potion name doesn't decode, nor an out-of-order list.
    let mut bad = bytes.clone();
    let at = bad.iter().rposition(|&b| b == b'w').unwrap();
    bad[at] = b'q';
    assert!(codec::try_decode(&bad).is_none());
    let name = |n: &str| [&[n.len() as u8][..], n.as_bytes()].concat();
    let mut swapped = without.clone();
    swapped.extend([8, 2]);
    swapped.extend(name("gen:pl-swift"));
    swapped.extend(name("gen:pl-fire"));
    assert!(codec::try_decode(&swapped).is_none());
    let mut empty = without.clone();
    empty.extend([8, 0]);
    assert!(codec::try_decode(&empty).is_none());
}
