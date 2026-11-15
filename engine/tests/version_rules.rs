//! Content-file versions (docs/specs/turn-start-draw.md, "Pack versions"):
//! in a version-1 file `OwnerTurnStart` means today's after-the-draw hook
//! (`OwnerTurnStartPostDraw`) and `OwnerTurnStartPostDraw` is an error; in
//! version 2 both words mean what they say; any other version is an error.
//! The official files are version 2, Demon Form and Brutality post-draw.

use sts_engine::hooks::{hooks, Trigger};
use sts_engine::registry::{self, load_pack, parse_official, OFFICIAL_FILES};
use sts_engine::Power;

/// A pack with power `id` holding one hook of `trigger`, and a card `c<id>`
/// applying it, at `version`.
fn pack(version: u32, id: &str, trigger: &str) -> String {
    format!(
        r#"{{"version": {version}, "powers": [{{"id": "{id}", "hooks": [{{"trigger": "{trigger}", "condition": "Always", "effects": [{{"GainEnergy": 1}}]}}]}}],
 "cards": [{{"id": "c{id}", "cost": 1, "type": "Power", "effects": [{{"Apply": {{"power": "{id}", "amount": 1, "target": "Me"}}}}]}}]}}"#
    )
}

/// The trigger of the pack power `id`'s hook, once loaded and bound.
fn trigger_of(id: &str) -> Trigger {
    let (_, binding) = registry::bind(&[&format!("gen:c{id}")]).expect("binds");
    binding.hooks(Power::GEN[0])[0].trigger
}

#[test]
fn version_1_reads_turn_start_as_post_draw() {
    load_pack(&pack(1, "vr_v1", "OwnerTurnStart")).expect("version 1 loads");
    assert_eq!(trigger_of("vr_v1"), Trigger::OwnerTurnStartPostDraw);
}

#[test]
fn version_2_reads_both_words_as_written() {
    load_pack(&pack(2, "vr_v2_pre", "OwnerTurnStart")).expect("version 2 loads");
    assert_eq!(trigger_of("vr_v2_pre"), Trigger::OwnerTurnStart);
    load_pack(&pack(2, "vr_v2_post", "OwnerTurnStartPostDraw")).expect("version 2 loads");
    assert_eq!(trigger_of("vr_v2_post"), Trigger::OwnerTurnStartPostDraw);
}

#[test]
fn post_draw_word_in_version_1_is_an_error() {
    let e = load_pack(&pack(1, "vr_v1_post", "OwnerTurnStartPostDraw")).unwrap_err();
    assert!(e.contains("OwnerTurnStartPostDraw") && e.contains("version"), "{e}");
}

#[test]
fn other_versions_are_errors() {
    for v in [0, 3] {
        let e = load_pack(&pack(v, &format!("vr_bad{v}"), "OwnerTurnStart")).unwrap_err();
        assert!(e.contains("version"), "version {v}: {e}");
    }
    let e = load_pack(r#"{"powers": []}"#).unwrap_err();
    assert!(e.contains("version"), "no version: {e}");
}

#[test]
fn official_files_are_version_2() {
    for (name, text) in registry::official_files() {
        assert!(text.starts_with("{\"version\": 2,"), "content/{name}");
    }
    assert!(hooks(Power::DemonForm).iter().all(|h| h.trigger == Trigger::OwnerTurnStartPostDraw));
    assert!(hooks(Power::Brutality).iter().all(|h| h.trigger == Trigger::OwnerTurnStartPostDraw));
    assert!(hooks(Power::Poison).iter().all(|h| h.trigger == Trigger::OwnerTurnStart));
}

#[test]
fn official_powers_file_follows_its_version() {
    let [cards, powers, monsters, encounters] = OFFICIAL_FILES;
    // The same file as version 1 would mean Poison post-draw: it parses.
    let v1 = powers.replacen("\"version\": 2", "\"version\": 1", 1).replace("OwnerTurnStartPostDraw", "OwnerTurnStart");
    assert!(parse_official([cards, &v1, monsters, encounters]).is_ok());
    // Version 1 with the post-draw word, or version 3: refused.
    let bad = powers.replacen("\"version\": 2", "\"version\": 1", 1);
    assert!(parse_official([cards, &bad, monsters, encounters]).err().expect("refused").contains("version"));
    let v3 = powers.replacen("\"version\": 2", "\"version\": 3", 1);
    assert!(parse_official([cards, &v3, monsters, encounters]).err().expect("refused").contains("version"));
}
