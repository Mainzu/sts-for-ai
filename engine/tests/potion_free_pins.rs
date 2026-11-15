//! Potion-free legal actions (docs/specs/potions.md, build step 1): in a
//! fight with no potions, every decision offers exactly the actions it
//! offered before potions existed, in the same order. Recorded on the code
//! before potions; potions must leave it unchanged.
//!
//! Each game is random play (`random_action`) from a fixed seed; a line per
//! decision lists the legal actions by name. The file keeps one FNV-1a hash
//! per game. Rewrite on purpose only:
//!   `POTION_FREE_RECORD=1 cargo test --release --test potion_free_pins`.
//! Print one game: `POTION_FREE_DUMP=ironclad:cultist:3 cargo test --release
//!   --test potion_free_pins dump -- --nocapture`.

use std::fmt::Write as _;
use sts_engine::agent::random_action;
use sts_engine::cards::class_cards;
use sts_engine::*;

const FILE: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/data/potion_free_legal.txt");
const GAMES: u64 = 20;

/// The starter, plus 6 random class cards on odd seeds (as codec.rs), so
/// picks and targeted cards come up.
fn deck(character: Character, seed: u64) -> Vec<CardId> {
    let mut d = character.starter_deck();
    if seed % 2 == 1 {
        let pool: Vec<CardId> = class_cards(character.class()).collect();
        let mut rng = Rng::new(seed ^ 0xdec0);
        for _ in 0..6 {
            d.push(pool[rng.below(pool.len() as u32) as usize]);
        }
    }
    d
}

fn act(s: &CombatState, a: Action) -> String {
    match a {
        Action::Play { card, target } => format!("{}@{target:?}", s.binding.def(card).name),
        Action::EndTurn => "end".to_string(),
        Action::Choose(c) => format!("choose {}", s.binding.def(c).name),
        Action::Done => "done".to_string(),
        Action::UsePotion { .. } => unreachable!("no potions in these fights"),
    }
}

fn play(character: Character, enc: Encounter, seed: u64) -> String {
    let mut rng = Rng::new(seed);
    let hp = character.max_hp();
    let mut s = CombatState::new_as(character, &deck(character, seed), hp, hp, enc, &mut rng);
    let mut out = String::new();
    while let Some(a) = random_action(&s, &mut rng) {
        let names: Vec<String> = s.legal_actions().into_iter().map(|b| act(&s, b)).collect();
        writeln!(out, "t{} [{}] > {}", s.turn, names.join(", "), act(&s, a)).unwrap();
        s.step(a, &mut rng).unwrap();
    }
    out
}

fn fnv1a(s: &str) -> u64 {
    s.bytes().fold(0xcbf29ce484222325, |h, b| (h ^ b as u64).wrapping_mul(0x100000001b3))
}

fn key(character: Character, enc: Encounter, seed: u64) -> String {
    format!("{}:{}:{seed}", character.name(), enc.name())
}

#[test]
fn potion_free_legal_actions() {
    let mut lines = String::new();
    for character in Character::ALL {
        for enc in Encounter::ALL {
            for seed in 0..GAMES {
                writeln!(lines, "{} {:016x}", key(character, enc, seed), fnv1a(&play(character, enc, seed))).unwrap();
            }
        }
    }
    if std::env::var("POTION_FREE_RECORD").is_ok() {
        std::fs::write(FILE, &lines).unwrap();
        return;
    }
    let want = std::fs::read_to_string(FILE).expect("record with POTION_FREE_RECORD=1").replace("\r\n", "\n");
    let differ: Vec<&str> = lines
        .lines()
        .zip(want.lines())
        .filter(|(a, b)| a != b)
        .map(|(a, _)| a.split(' ').next().unwrap())
        .collect();
    assert_eq!(lines.lines().count(), want.lines().count(), "game count changed");
    assert!(differ.is_empty(), "{} games' legal actions differ, first {}; print it with POTION_FREE_DUMP", differ.len(), differ[0]);
}

#[test]
fn dump() {
    let Ok(spec) = std::env::var("POTION_FREE_DUMP") else { return };
    let p: Vec<&str> = spec.split(':').collect();
    let character = Character::from_name(p[0]).expect("character");
    let enc = Encounter::from_name(p[1]).expect("encounter");
    print!("{}", play(character, enc, p[2].parse().expect("seed")));
}
