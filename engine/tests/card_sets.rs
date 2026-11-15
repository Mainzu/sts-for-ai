//! Card pools as named sets (`configs/card-sets.json`, spec card-sets).

mod common;

use sts_engine::cards::{class_cards, deck_cards, held_out_cards, CardClass, CardId};
use sts_engine::registry::{official, parse_official, OFFICIAL_FILES};

const IRONCLAD: [&str; 58] = [
    "Strike", "Strike+", "Defend", "Defend+", "Bash", "Bash+", "Shrug It Off", "Shrug It Off+", "Anger", "Anger+", "Body Slam",
    "Body Slam+", "Clash", "Clash+", "Cleave", "Cleave+", "Clothesline", "Clothesline+", "Iron Wave", "Iron Wave+", "Pommel Strike",
    "Pommel Strike+", "Thunderclap", "Thunderclap+", "Twin Strike", "Twin Strike+", "Wild Strike", "Wild Strike+", "Heavy Blade",
    "Heavy Blade+", "Perfected Strike", "Perfected Strike+", "Sword Boomerang", "Sword Boomerang+", "Bloodletting", "Bloodletting+",
    "Hemokinesis", "Hemokinesis+", "Pummel", "Pummel+", "Uppercut", "Uppercut+", "Inflame", "Inflame+", "Flex", "Flex+", "Carnage",
    "Carnage+", "Spot Weakness", "Spot Weakness+", "Dropkick", "Dropkick+", "Combust", "Combust+", "Brutality", "Brutality+",
    "Rupture", "Rupture+",
];
const SILENT: [&str; 30] = [
    "Silent Strike", "Silent Strike+", "Silent Defend", "Silent Defend+", "Neutralize", "Neutralize+", "Sucker Punch",
    "Sucker Punch+", "Leg Sweep", "Leg Sweep+", "Quick Slash", "Quick Slash+", "Backflip", "Backflip+", "Deflect", "Deflect+",
    "Slice", "Slice+", "Dagger Spray", "Dagger Spray+", "Blade Dance", "Blade Dance+", "Cloak and Dagger", "Cloak and Dagger+",
    "Deadly Poison", "Deadly Poison+", "Poisoned Stab", "Poisoned Stab+", "Bouncing Flask", "Bouncing Flask+",
];
const CHECK9: [&str; 10] = [
    "Go for the Eyes", "Go for the Eyes+", "FTL", "FTL+", "Metallicize", "Metallicize+", "Demon Form", "Demon Form+", "Rage", "Rage+",
];
const PROVING: [&str; 20] = [
    "Whirlwind", "Whirlwind+", "Accuracy", "Accuracy+", "Wraith Form", "Wraith Form+", "Caltrops", "Caltrops+", "Survivor",
    "Survivor+", "Burst", "Burst+", "Hologram", "Hologram+", "Headbutt", "Headbutt+", "Rampage", "Rampage+", "Protect", "Protect+",
];

fn names(ids: impl Iterator<Item = CardId>) -> Vec<&'static str> {
    ids.map(|c| c.name()).collect()
}

#[test]
fn pools_pinned() {
    assert_eq!(names(deck_cards()), IRONCLAD);
    assert_eq!(names(class_cards(CardClass::Ironclad)), IRONCLAD);
    assert_eq!(names(class_cards(CardClass::Silent)), SILENT);
    assert_eq!(names(held_out_cards()), CHECK9);
    assert_eq!(names(sts_engine::card_sets::get("proving").unwrap().iter().copied()), PROVING);
}

#[test]
fn old_flags_load_and_are_ignored() {
    let [_, powers, monsters, encounters] = OFFICIAL_FILES;
    let old = include_str!("data/cards_old_flags.json").replace("\r\n", "\n");
    assert!(old.contains("\"held_out\": true") && old.contains("\"proving\": true"), "the fixture keeps the old flags");
    let o = parse_official([&old, powers, monsters, encounters]).expect("an old-format cards file loads");
    assert_eq!(o.cards.len(), official().cards.len());
    for (a, b) in o.cards.iter().zip(&official().cards) {
        // Played fields: an older file's upgrade is two entries, not a block.
        assert_eq!(common::card_dump(a), common::card_dump(b), "{}", b.name);
    }
}

use sts_engine::card_sets;

#[test]
fn sets_file_equals_the_pins() {
    assert_eq!(card_sets::names().collect::<Vec<_>>(), ["ironclad", "silent", "check9", "proving"]);
    let set = |n: &str| names(card_sets::get(n).unwrap_or_else(|| panic!("set {n}")).iter().copied());
    assert_eq!(set("ironclad"), IRONCLAD);
    assert_eq!(set("silent"), SILENT);
    assert_eq!(set("check9"), CHECK9);
    assert_eq!(set("proving"), PROVING);
    assert!(card_sets::get("colorless").is_none());
}

#[test]
fn sets_in_card_order_and_statuses_alone() {
    let s = card_sets::parse(r#"{"version": 1, "sets": {"a": ["Bash", "Wound", "Strike", "Burn"], "b": ["Bash"]}}"#).unwrap();
    let a: Vec<&str> = names(s[0].1.iter().copied());
    assert_eq!(a, ["Strike", "Strike+", "Bash", "Bash+", "Wound", "Burn", "Burn+"]);
    assert_eq!(s[1].0, "b");
}

#[test]
fn set_load_errors() {
    let e = |sets: &str| card_sets::parse(&format!(r#"{{"version": 1, "sets": {{{sets}}}}}"#)).unwrap_err();
    let x = e(r#""pool": ["Strike", "Strik"]"#);
    assert!(x.contains("\"pool\"") && x.contains("\"Strik\"") && x.contains("no official card"), "{x}");
    let x = e(r#""pool": ["Strike+"]"#);
    assert!(x.contains("\"pool\"") && x.contains("\"Strike+\"") && x.contains("upgrade"), "{x}");
    let x = e(r#""pool": ["Bash", "Strike", "Bash"]"#);
    assert!(x.contains("\"pool\"") && x.contains("\"Bash\"") && x.contains("twice"), "{x}");
    for v in [r#"{"sets": {}}"#, r#"{"version": 2, "sets": {}}"#] {
        let x = card_sets::parse(v).unwrap_err();
        assert!(x.contains("version"), "{x}");
    }
}
