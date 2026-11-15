//! The rules fingerprint follows code changes in the rule files and
//! ignores comment and whitespace changes.

use solvedb::fingerprint::{content_tables, fingerprint, fingerprint_of, strip_code, RULE_FILES};
use solvedb::fnv1a;
use sts_engine::codec::CODEC_VERSION;

#[test]
fn fingerprint_tracks_rules() {
    // Comments and formatting don't count.
    let a = "/// Doc.\npub fn hit(x: i16) -> i16 {\n    x + 1 // one more\n}\n";
    let b = "pub   fn hit( x : i16 )->i16{ /* block\n /* nested */ comment */ x+1 }";
    assert_eq!(strip_code(a), strip_code(b));
    assert_eq!(strip_code(a), "pub fn hit(x:i16)->i16{x+1}");
    // Code does.
    assert_ne!(strip_code(a), strip_code(&a.replace("x + 1", "x + 2")));
    assert_ne!(strip_code("pub fn a"), strip_code("pubfn a"));
    // Literals are kept whole, slashes and spaces included.
    assert_eq!(strip_code(r#"let s = "a // b";"#), r#"let s="a // b";"#);
    assert_eq!(strip_code(r##"r#"x " /* y"# + '"' + '\'' + 'a"##), r##"r#"x " /* y"#+'"'+'\''+'a"##);
    assert_eq!(strip_code("fn f<'a>(x: &'a str) {}"), "fn f<'a>(x:&'a str){}");

    // On the real rule files.
    let tables = content_tables();
    let base = fingerprint_of(&RULE_FILES, &tables, CODEC_VERSION);
    assert_eq!(base, fingerprint());
    assert_eq!(base.len(), 16);
    for i in 0..RULE_FILES.len() {
        let mut files = RULE_FILES;
        let commented = format!("// A new comment.\n{}\n/* and another */\n", files[i].1.replace("\n", "\n\n  "));
        files[i].1 = &commented;
        assert_eq!(fingerprint_of(&files, &tables, CODEC_VERSION), base, "{}: a comment changed it", files[i].0);
        let edited = format!("{}\nconst EXTRA: u8 = 1;\n", RULE_FILES[i].1);
        files[i].1 = &edited;
        assert_ne!(fingerprint_of(&files, &tables, CODEC_VERSION), base, "{}: a code edit didn't change it", files[i].0);
    }
    // A content table's order and the codec version count too.
    assert_ne!(fingerprint_of(&RULE_FILES, &tables.replacen("Strike|", "Strike2|", 1), CODEC_VERSION), base);
    assert_ne!(fingerprint_of(&RULE_FILES, &tables, CODEC_VERSION + 1), base);
    assert!(tables.contains("Bash|") && tables.contains("Strength|") && tables.contains("Jaw Worm(Chomp|"));
}

#[test]
fn fnv1a_known_values() {
    assert_eq!(fnv1a(b""), 0xcbf29ce484222325);
    assert_eq!(fnv1a(b"a"), 0xaf63dc4c8601ec8c);
}

/// The content tables (official names in codec order) are pinned: the
/// reserved registry-lite slots must stay out of them, so the fingerprint
/// moves only with rule-file code, never with generated content.
/// Re-pinned for Whirlwind (amount-expressions) and Accuracy / Red Skull
/// (static-modifiers), Wraith Form / Caltrops (replacement-hooks), Survivor /
/// Burst / Hologram (decision-points), Headbutt (known-top), Rampage / Protect
/// (per-copy-overrides), 2026-11-02; Damage Down / Weak on hit / Split Hits
/// (mutated-monsters-b), 2026-11-04.
#[test]
fn content_tables_pinned() {
    assert_eq!(fnv1a(content_tables().as_bytes()), 0x314cc2c2951a1c62, "content tables changed");
}

/// The official content files count as rules (runtime registry stage 4):
/// a changed number gives a new fingerprint, whitespace doesn't.
#[test]
fn fingerprint_tracks_content() {
    let tables = content_tables();
    let base = fingerprint_of(&RULE_FILES, &tables, CODEC_VERSION);
    for name in ["content/cards", "content/powers", "content/monsters", "content/relics", "content/potions"] {
        let i = RULE_FILES.iter().position(|(n, _)| *n == name).expect(name);
        let mut files = RULE_FILES;
        let spaced = RULE_FILES[i].1.replace(", ", ",   ").replace('\n', "\n\n");
        files[i].1 = &spaced;
        assert_eq!(fingerprint_of(&files, &tables, CODEC_VERSION), base, "{name}: whitespace changed it");
        // The file's version number: every official file has one.
        let changed = RULE_FILES[i].1.replacen("\"version\": 2", "\"version\": 3", 1);
        assert_ne!(changed, RULE_FILES[i].1, "{name}: no version number to change");
        files[i].1 = &changed;
        assert_ne!(fingerprint_of(&files, &tables, CODEC_VERSION), base, "{name}: a changed number didn't change it");
    }
}

/// Every engine module a rule file calls into is hashed too, or holds no
/// rules: an edit there would otherwise change play while the fingerprint,
/// and the solved rows under it, stay the same.
#[test]
fn rule_files_cover_the_modules_they_use() {
    // Machinery, like solve.rs (also unhashed): the sampler and the exact
    // enumerator (rng), a hash function (fxhash); the training pools
    // (card_sets, `configs/card-sets.json`: which cards decks draw from,
    // not how a combat plays; docs/specs/card-sets.md).
    const NOT_RULES: [&str; 3] = ["rng", "fxhash", "card_sets"];
    for (name, src) in RULE_FILES {
        let code = strip_code(src);
        for (at, _) in code.match_indices("crate::") {
            let m: String = code[at + "crate::".len()..].chars().take_while(|&c| c.is_alphanumeric() || c == '_').collect();
            assert!(
                RULE_FILES.iter().any(|(n, _)| *n == m) || NOT_RULES.contains(&m.as_str()),
                "{name}.rs uses crate::{m}, which the fingerprint doesn't hash"
            );
        }
    }
}

/// Content identity (docs/specs/runtime-registry.md stage 2): the codec refuses
/// states with generated content, so a loaded pack can't touch a solved
/// value and leaves the fingerprint and the content tables as they were.
#[test]
fn fingerprint_ignores_loaded_packs() {
    let before = fingerprint().to_string();
    sts_engine::registry::load_pack(
        r#"{"version": 1, "powers": [{"id": "fp_pw", "hooks": [{"trigger": "RoundEnd", "effects": [{"ReduceSelf": 1}]}]}],
            "cards": [{"id": "fp_card", "cost": 1, "type": "Skill", "effects": [{"Apply": {"power": "fp_pw", "amount": 2, "target": "Me"}}]}]}"#,
    )
    .unwrap();
    assert_eq!(fingerprint(), before);
    assert_eq!(fingerprint_of(&RULE_FILES, &content_tables(), CODEC_VERSION), before);
    assert_eq!(fnv1a(content_tables().as_bytes()), 0x314cc2c2951a1c62);
}
