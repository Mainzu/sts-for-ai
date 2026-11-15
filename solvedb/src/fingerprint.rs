//! The rules fingerprint: which engine version a solved value belongs to.
//!
//! A hash of the engine's rule files with comments and whitespace stripped,
//! plus the name order of every content table the codec writes as a number
//! (cards, powers, monster kinds, moves), plus the codec version. A real
//! rules edit gives a new fingerprint; comment and formatting edits don't.

use std::fmt::Write;
use std::sync::OnceLock;

use sts_engine::cards::CardId;
use sts_engine::codec::{CODEC_VERSION, MONSTER_KINDS};
use sts_engine::Power;

use crate::fnv1a;

/// The rule files, read when this crate is built.
pub const RULE_FILES: [(&str, &str); 17] = [
    ("state", include_str!("../../engine/src/state.rs")),
    ("cards", include_str!("../../engine/src/cards.rs")),
    ("monsters", include_str!("../../engine/src/monsters.rs")),
    ("powers", include_str!("../../engine/src/powers.rs")),
    ("hooks", include_str!("../../engine/src/hooks.rs")),
    ("effects", include_str!("../../engine/src/effects.rs")),
    ("chance", include_str!("../../engine/src/chance.rs")),
    ("character", include_str!("../../engine/src/character.rs")),
    ("registry", include_str!("../../engine/src/registry.rs")),
    ("relics", include_str!("../../engine/src/relics.rs")),
    // Potions held in a fight (docs/specs/potions.md).
    ("potions", include_str!("../../engine/src/potions.rs")),
    // What an upgrade changes, used by cards.rs (docs/specs/card-upgrades.md).
    ("upgrade", include_str!("../../engine/src/upgrade.rs")),
    // The official content (runtime registry stage 4): JSON has no
    // comments, so stripping drops only whitespace outside strings.
    ("content/cards", include_str!("../../content/cards.json")),
    ("content/powers", include_str!("../../content/powers.json")),
    ("content/monsters", include_str!("../../content/monsters.json")),
    // The starter relic's combat-end heal (docs/specs/relics.md).
    ("content/relics", include_str!("../../content/relics.json")),
    ("content/potions", include_str!("../../content/potions.json")),
];

fn ident(c: char) -> bool {
    c.is_alphanumeric() || c == '_'
}

/// Rust source with comments removed and whitespace kept only where it
/// separates two identifier characters (as one space). String and char
/// literals are kept as they are.
pub fn strip_code(src: &str) -> String {
    let c: Vec<char> = src.chars().collect();
    let mut out = String::with_capacity(src.len());
    let mut gap = false;
    let mut i = 0;
    while i < c.len() {
        let next = c.get(i + 1).copied();
        if c[i].is_whitespace() {
            gap = true;
            i += 1;
            continue;
        }
        if c[i] == '/' && next == Some('/') {
            while i < c.len() && c[i] != '\n' {
                i += 1;
            }
            gap = true;
            continue;
        }
        if c[i] == '/' && next == Some('*') {
            let mut depth = 0;
            while i < c.len() {
                if c[i] == '/' && c.get(i + 1) == Some(&'*') {
                    depth += 1;
                    i += 2;
                } else if c[i] == '*' && c.get(i + 1) == Some(&'/') {
                    depth -= 1;
                    i += 2;
                    if depth == 0 {
                        break;
                    }
                } else {
                    i += 1;
                }
            }
            gap = true;
            continue;
        }
        if gap && out.chars().last().is_some_and(ident) && ident(c[i]) {
            out.push(' ');
        }
        gap = false;
        let start = i;
        let after_ident = out.chars().last().is_some_and(ident);
        if c[i] == 'r' && !after_ident && matches!(next, Some('"') | Some('#')) {
            // A raw string, if `#`s lead to a quote.
            let mut j = i + 1;
            while c.get(j) == Some(&'#') {
                j += 1;
            }
            if c.get(j) == Some(&'"') {
                let hashes = j - i - 1;
                j += 1;
                while j < c.len() && !(c[j] == '"' && c[j + 1..].iter().take(hashes).filter(|&&h| h == '#').count() == hashes) {
                    j += 1;
                }
                i = (j + 1 + hashes).min(c.len());
                out.extend(&c[start..i]);
                continue;
            }
        }
        if c[i] == '"' {
            i += 1;
            while i < c.len() && c[i] != '"' {
                i += if c[i] == '\\' { 2 } else { 1 };
            }
            i = (i + 1).min(c.len());
        } else if c[i] == '\'' && next == Some('\\') {
            // Quote, backslash and the escaped char, then on to the close.
            i += 3;
            while i < c.len() && c[i] != '\'' {
                i += 1;
            }
            i = (i + 1).min(c.len());
        } else if c[i] == '\'' && c.get(i + 2) == Some(&'\'') {
            i += 3;
        } else {
            i += 1;
        }
        out.extend(&c[start..i]);
    }
    out
}

/// The content tables' names in the order the codec numbers them.
pub fn content_tables() -> String {
    let mut s = String::new();
    s.push_str("cards:");
    for c in CardId::all() {
        write!(s, "{}|", c.name()).unwrap();
    }
    s.push_str("\npowers:");
    for p in Power::ALL {
        write!(s, "{p:?}|").unwrap();
    }
    s.push_str("\nmonsters:");
    for k in MONSTER_KINDS {
        let d = k.def();
        write!(s, "{}(", d.name).unwrap();
        for m in d.moves {
            write!(s, "{}|", m.name).unwrap();
        }
        s.push(')');
    }
    s
}

/// The fingerprint of these rule files and content tables, as 16 hex digits.
pub fn fingerprint_of(files: &[(&str, &str)], tables: &str, codec_version: u8) -> String {
    let mut text = String::new();
    for (name, src) in files {
        write!(text, "\n== {name}\n{}", strip_code(src)).unwrap();
    }
    write!(text, "\n== tables\n{tables}\n== codec {codec_version}").unwrap();
    format!("{:016x}", fnv1a(text.as_bytes()))
}

/// This build's rules fingerprint.
pub fn fingerprint() -> &'static str {
    static FP: OnceLock<String> = OnceLock::new();
    FP.get_or_init(|| fingerprint_of(&RULE_FILES, &content_tables(), CODEC_VERSION))
}
