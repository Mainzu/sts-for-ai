//! Golden trajectories: 300 seeded random-agent games per encounter, both
//! characters, must play out exactly as they did when `data/golden.txt` was
//! recorded (before hook powers). Each game is a canonical text dump of the
//! state after every step, by name, so adding cards or powers doesn't change
//! it; the file keeps one FNV-1a hash per game.
//!
//! - Check: `cargo test --test golden` (all 9000 games, a few seconds).
//! - Re-record (only on unchanged behaviour): `GOLDEN_RECORD=1 cargo test --test golden`.
//! - Print one game's dump to diff against older code:
//!   `GOLDEN_DUMP=silent:cultist:17 cargo test --test golden dump -- --nocapture`
//!   (a cover game by its key: `GOLDEN_DUMP=cover-guardian:ironclad:the_guardian:2`).
//!
//! The cover games (`COVER`, keys `cover-<name>:...`, in `golden.txt` after
//! the rest so the rules version tracks them) play pack cards, relics and
//! potions, and also dump each chance state on the way to the next
//! decision, so rules that act between decisions (End Turn's stages) show.
//! `cover_games_reach_their_mechanics` checks each reaches what it covers;
//! `GOLDEN_COVER_SEARCH=<name> cargo test --test golden cover_search -- --nocapture`
//! lists seeds that do, for a game a rule change moved off its mechanics.

use std::collections::HashMap;
use std::fmt::Write;
use sts_engine::agent::{incoming_damage, random_action};
use sts_engine::cards::CardType;
use sts_engine::monsters::lagavulin;
use sts_engine::powers::Powers;
use sts_engine::monsters::EncounterGroup;
use sts_engine::state::MAX_MONSTERS;
use sts_engine::registry::{bind, load_pack, monster_kinds, potions_named, relics_named, Binding};
use sts_engine::*;

const GAMES: u64 = 300;
const DATA: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/data/golden.txt");
/// The proving sets' games, in a file of their own: `golden.txt`'s hash is
/// the registry's rules version (`scripts/registry.py`), which new content
/// must not move.
const PROVING_DATA: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/data/golden_proving.txt");

/// Today's deck-pool cards, by name, so later content can't change the decks.
const IRONCLAD_POOL: &[&str] = &[
    "Strike", "Defend", "Bash", "Shrug It Off", "Anger", "Body Slam", "Clash", "Cleave", "Clothesline",
    "Iron Wave", "Pommel Strike", "Thunderclap", "Twin Strike", "Wild Strike", "Heavy Blade",
    "Perfected Strike", "Sword Boomerang", "Bloodletting", "Hemokinesis", "Pummel", "Uppercut", "Inflame",
    "Flex", "Carnage",
];
const SILENT_POOL: &[&str] = &[
    "Silent Strike", "Silent Defend", "Neutralize", "Sucker Punch", "Leg Sweep", "Quick Slash", "Backflip",
    "Deflect", "Slice", "Dagger Spray", "Blade Dance", "Cloak and Dagger", "Deadly Poison", "Poisoned Stab",
    "Bouncing Flask",
];

/// Rules-engine proving content, one fixed set per spec: (name, character,
/// cards added to the starter). Each gets `PROVING_GAMES` games per
/// encounter under keys `proving-<name>:...`, so new content never changes
/// an earlier set.
const PROVING: &[(&str, Character, &[&str])] = &[
    ("whirlwind", Character::Ironclad, &["Whirlwind", "Whirlwind+", "Inflame"]),
    ("accuracy", Character::Silent, &["Accuracy", "Accuracy+", "Blade Dance", "Cloak and Dagger+"]),
    ("wraith", Character::Silent, &["Wraith Form", "Wraith Form+", "Caltrops", "Caltrops+"]),
    ("survivor", Character::Silent, &["Survivor", "Survivor+", "Burst", "Burst+", "Deflect"]),
    ("hologram", Character::Ironclad, &["Hologram", "Hologram+", "Shrug It Off"]),
    ("headbutt", Character::Ironclad, &["Headbutt", "Headbutt+", "Wild Strike", "Pommel Strike", "Shrug It Off"]),
    ("rampage", Character::Ironclad, &["Rampage", "Rampage", "Rampage+", "Protect", "Protect+"]),
];
const PROVING_GAMES: u64 = 40;

const IRONCLAD_PACK: &str = include_str!("../../content/packs/act1-ironclad.json");
const RELICS_PACK: &str = include_str!("../../content/packs/act1-relics.json");
const POTIONS_PACK: &str = include_str!("../../content/packs/act1-potions.json");
const COLORLESS_PACK: &str = include_str!("../../content/packs/act1-colorless.json");
const MONSTERS_PACK: &str = include_str!("../../content/packs/act1-monsters.json");

/// A cover game: one seeded random-agent game with pack content, made to
/// reach the rules named in `checks` (`reaches`). Its cards are added to
/// the starter by name (`gen:` for pack cards); relics and potions by pack
/// name, without `gen:`.
#[derive(Clone, Copy)]
struct Cover {
    name: &'static str,
    character: Character,
    cards: &'static [&'static str],
    relics: &'static [&'static str],
    potions: &'static [&'static str],
    enc: Encounter,
    /// A burning elite's buff on the fight's monsters.
    elite_buff: Option<EliteBuff>,
    /// Pack monsters by name (without `gen:`) fought instead of `enc`'s
    /// roll, in slot order (a hallway fight); empty for `enc`.
    monsters: &'static [&'static str],
    seed: u64,
    checks: &'static [&'static str],
}

/// Rules fixed outside golden on 2026-11-14
/// (docs/research/golden-gap-impact-2026-11-14.md), Duplication's
/// round-end timing and Lagavulin waking with a burning elite's extra
/// Metallicize. A new game goes at the end, so the earlier ones keep
/// their lines.
const COVER: &[Cover] = &[
    Cover {
        name: "turn-end-hp",
        character: Character::Ironclad,
        cards: &["Burn", "Burn", "Combust", "Combust"],
        relics: &[],
        potions: &["Regen Potion"],
        enc: Encounter::Cultist,
        elite_buff: None,
        monsters: &[],
        seed: 21,
        checks: &["burn-regen", "regen-combust", "burn-combust"],
    },
    Cover {
        name: "turn-end-block",
        character: Character::Ironclad,
        cards: &["Burn", "Burn", "Burn", "Metallicize", "Metallicize"],
        relics: &[],
        potions: &["Essence of Steel"],
        enc: Encounter::Lagavulin,
        elite_buff: None,
        monsters: &[],
        seed: 4,
        checks: &["metallicize-burn", "plated-burn"],
    },
    Cover {
        name: "rupture-duplication",
        character: Character::Ironclad,
        cards: &["Dazed", "Dazed", "Dazed", "Burn", "Burn", "Rupture", "Rupture", "Hemokinesis"],
        relics: &["Dead Branch", "Tungsten Rod"],
        potions: &["Duplication Potion"],
        enc: Encounter::Cultist,
        elite_buff: None,
        monsters: &[],
        seed: 13,
        checks: &["rupture-burn", "tungsten-hemokinesis", "duplication-round"],
    },
    Cover {
        name: "guardian",
        character: Character::Ironclad,
        cards: &["Combust", "Combust", "gen:Blood for Blood", "gen:Blood for Blood", "Bloodletting", "Burn", "Burn"],
        relics: &["Orichalcum"],
        potions: &[],
        enc: Encounter::TheGuardian,
        elite_buff: None,
        monsters: &[],
        seed: 2,
        checks: &["guardian-shift-turn-end", "bfb-per-copy", "bfb-limbo", "orichalcum-burn"],
    },
    Cover {
        name: "feed",
        character: Character::Ironclad,
        cards: &["gen:Feed", "gen:Feed", "gen:Havoc", "gen:Havoc", "Perfected Strike", "Perfected Strike", "Flex", "Flex"],
        relics: &[],
        potions: &["Ancient Potion"],
        enc: Encounter::Cultist,
        elite_buff: None,
        monsters: &[],
        seed: 147,
        checks: &["feed-kill", "perfected-strike-havoc", "flex-artifact"],
    },
    Cover {
        name: "lagavulin-burning",
        character: Character::Ironclad,
        cards: &[],
        relics: &[],
        potions: &[],
        enc: Encounter::Lagavulin,
        elite_buff: Some(EliteBuff::Metallicize),
        monsters: &[],
        seed: 1,
        checks: &["lagavulin-wake-hit"],
    },
    Cover {
        name: "pocketwatch",
        character: Character::Ironclad,
        cards: &["Anger", "Anger", "Flex", "gen:Double Tap", "gen:Havoc"],
        relics: &["Pocketwatch"],
        potions: &[],
        enc: Encounter::JawWorm,
        elite_buff: None,
        monsters: &[],
        seed: 2,
        checks: &["pocketwatch-draw", "pocketwatch-no-draw", "pocketwatch-copy-counts"],
    },
    Cover {
        name: "fire-breathing-curse",
        character: Character::Ironclad,
        cards: &["gen:Fire Breathing", "gen:Fire Breathing", "gen:Ascender's Bane", "gen:Clumsy", "Dazed"],
        relics: &[],
        potions: &[],
        enc: Encounter::ThreeSentries,
        elite_buff: Some(EliteBuff::Metallicize),
        monsters: &[],
        seed: 0,
        checks: &["fire-breathing-curse"],
    },
    Cover {
        name: "spore-cloud-held",
        character: Character::Silent,
        cards: &["Deadly Poison", "Deadly Poison", "Deadly Poison"],
        relics: &["Bronze Scales"],
        potions: &[],
        enc: Encounter::TwoFungiBeasts,
        elite_buff: None,
        monsters: &[],
        seed: 0,
        checks: &["spore-cloud-held"],
    },
    Cover {
        name: "gremlin-protect",
        character: Character::Ironclad,
        cards: &["gen:Flame Barrier", "gen:Flame Barrier"],
        relics: &["Bronze Scales"],
        potions: &[],
        enc: Encounter::Cultist,
        elite_buff: None,
        monsters: &["Mad Gremlin", "Shield Gremlin", "Mad Gremlin", "Sneaky Gremlin"],
        seed: 0,
        checks: &["ally-block-before-later-attacker"],
    },
    Cover {
        name: "gremlin-allies-at-move",
        character: Character::Ironclad,
        cards: &["gen:Flame Barrier+", "gen:Flame Barrier+", "gen:Flame Barrier+", "gen:Flame Barrier+"],
        relics: &["Bronze Scales"],
        potions: &[],
        enc: Encounter::Cultist,
        elite_buff: None,
        monsters: &["Shield Gremlin", "Sneaky Gremlin"],
        seed: 0,
        checks: &["allies-at-move"],
    },
    Cover {
        name: "lone-shield-gremlin",
        character: Character::Ironclad,
        cards: &[],
        relics: &[],
        potions: &[],
        enc: Encounter::Cultist,
        elite_buff: None,
        monsters: &["Shield Gremlin"],
        seed: 0,
        checks: &["lone-protect-opening"],
    },
];

fn card(name: &str) -> CardId {
    CardId::from_name(name).unwrap_or_else(|| panic!("no card {name}"))
}

/// Even seeds: the starter deck. Odd: starter + 5 picks (base or upgraded).
fn deck_for(character: Character, seed: u64, rng: &mut Rng) -> Vec<CardId> {
    let mut deck = character.starter_deck();
    if seed % 2 == 1 {
        let pool = match character {
            Character::Ironclad => IRONCLAD_POOL,
            Character::Silent => SILENT_POOL,
        };
        for _ in 0..5 {
            let i = rng.below(2 * pool.len() as u32) as usize;
            let name = pool[i / 2];
            deck.push(if i % 2 == 1 { card(&format!("{name}+")) } else { card(name) });
        }
    }
    deck
}

/// Nonzero powers sorted by name, so reordering `Power` doesn't matter;
/// a generated power by its binding's id. `*` marks `just_applied`.
fn dump_powers(out: &mut String, p: &Powers, b: &Binding) {
    let mut v: Vec<String> = Power::ALL
        .into_iter()
        .filter(|&pw| p.get(pw) != 0)
        .map(|pw| format!(" {pw:?}={}{}", p.get(pw), if p.just_applied(pw) { "*" } else { "" }))
        .collect();
    // Generated powers only when held, so existing games dump as before.
    for pw in Power::GEN.into_iter().filter(|&pw| p.get(pw) != 0) {
        let id = b.power_id(pw).expect("a held generated power is bound");
        v.push(format!(" {id}={}{}", p.get(pw), if p.just_applied(pw) { "*" } else { "" }));
    }
    v.sort();
    out.push_str(&v.concat());
}

/// Cards by their definition's name: an official card's own name, a
/// per-copy variant's override form.
fn dump_pile(out: &mut String, name: &str, p: PileRef<'_>, b: &Binding) {
    write!(out, " {name}[").unwrap();
    for (c, n) in p.iter() {
        write!(out, "{}x{n},", b.def(c).name).unwrap();
    }
    out.push(']');
}

fn card_name(c: CardId, b: &Binding) -> &'static str {
    b.def(c).name
}

/// One line per state, by name only. An ended fight writes only what
/// outlasts it (the result, HP, max HP): what else is left depends on how
/// the real game splits a fight-ending effect into actions (decisions.md,
/// "Golden games record an ended fight by what outlasts it").
fn dump_state(out: &mut String, s: &CombatState) {
    let p = &s.player;
    if let Stage::Over { won } = s.stage {
        writeln!(out, "over({won}) hp{}/{}", p.hp, p.max_hp).unwrap();
        return;
    }
    write!(out, "t{} hp{}/{} b{} e{}", s.turn, p.hp, p.max_hp, p.block, p.energy).unwrap();
    dump_powers(out, &p.powers, &s.binding);
    // Relics (with counters) and potions only when held, so existing games
    // dump as before.
    if !p.relics.is_empty() {
        out.push_str(" relics[");
        for (r, n) in p.relics.iter() {
            write!(out, "{}:{n},", r.name()).unwrap();
        }
        out.push(']');
    }
    if !p.potions.is_empty() {
        out.push_str(" potions[");
        for id in p.potions.iter() {
            write!(out, "{},", id.name()).unwrap();
        }
        out.push(']');
    }
    let stage = match s.stage {
        Stage::PlayerTurn => "player".to_string(),
        // X only when set, so existing games dump as before.
        Stage::PlayingCard { card, target, next, hit, x, more } => {
            let mut t = format!("playing({},{target:?},{next},{hit}", card_name(card, &s.binding));
            // New fields only when set, so existing games dump as before.
            if x != 0 {
                write!(t, ",x{x}").unwrap();
            }
            if more != Default::default() {
                write!(t, ",{more:?}").unwrap();
            }
            t + ")"
        }
        Stage::UsingPotion { potion, target, next, hit, pick } => format!("potion({},{target:?},{next},{hit},{pick:?})", potion.name()),
        Stage::RelicPick { relic, hook, next, hit, pick } => format!("relic-pick({relic},{hook},{next},{hit},{pick:?})"),
        Stage::RelicOffer { relic, hook, next, pick } => format!("relic-offer({relic},{hook},{next},{pick:?})"),
        Stage::MonsterRolls { next } => format!("rolls({next})"),
        Stage::EndingTurn { part } => format!("ending-turn({part})"),
        Stage::MonsterActing { slot, next } => format!("monster-acting({slot},{next})"),
        Stage::StartTurn => "start".to_string(),
        Stage::TurnStarted => "turn-started".to_string(),
        Stage::Over { won } => format!("over({won})"),
    };
    write!(out, " | {stage} pending={:?} created={} removed={} defer={:?}", s.pending, s.created, s.removed, s.deferred_block).unwrap();
    dump_pile(out, "hand", s.hand.view(), &s.binding);
    dump_pile(out, "draw", s.draw(), &s.binding);
    dump_pile(out, "disc", s.discard(), &s.binding);
    // The known top only when anything is known, so existing games dump as before.
    if !s.top.is_empty() {
        let known: Vec<&str> = s.top.known().map(|c| card_name(c, &s.binding)).collect();
        let floaters: Vec<(&str, u8)> = s.top.floaters().map(|(c, a)| (card_name(c, &s.binding), a)).collect();
        write!(out, " | top {known:?} floaters {floaters:?}").unwrap();
    }
    dump_pile(out, "exh", s.exhaust(), &s.binding);
    for m in s.monsters.iter().filter(|m| m.kind != MonsterKind::None) {
        let d = m.def();
        let mv = |id| d.moves.get(id as usize).map_or("-", |mv| mv.name);
        write!(out, " | {} hp{}/{} b{} mv{}<{} roll{} esc{}", d.name, m.hp, m.max_hp, m.block, mv(m.moves[0]), mv(m.moves[1]), m.rolled_damage, m.escaped).unwrap();
        dump_powers(out, &m.powers, &s.binding);
    }
    out.push('\n');
}

fn play_game(character: Character, enc: Encounter, seed: u64) -> String {
    let mut rng = Rng::new(seed);
    let deck = deck_for(character, seed, &mut rng);
    play_deck(character, enc, deck, rng)
}

fn play_proving(character: Character, extra: &[&str], enc: Encounter, seed: u64) -> String {
    let mut deck = character.starter_deck();
    deck.extend(extra.iter().map(|n| card(n)));
    play_deck(character, enc, deck, Rng::new(seed))
}

fn play_deck(character: Character, enc: Encounter, deck: Vec<CardId>, mut rng: Rng) -> String {
    let hp = character.max_hp();
    let mut s = CombatState::new_as(character, &deck, hp, hp, enc, &mut rng);
    let mut out = String::new();
    dump_state(&mut out, &s);
    while let Some(a) = random_action(&s, &mut rng) {
        dump_action(&mut out, &s, a);
        s.step(a, &mut rng).unwrap();
        dump_state(&mut out, &s);
    }
    out
}

fn dump_action(out: &mut String, s: &CombatState, a: Action) {
    match a {
        Action::Play { card, target } => writeln!(out, "> {} {target:?}", s.binding.def(card).name).unwrap(),
        Action::EndTurn => out.push_str("> end\n"),
        Action::Choose(card) => writeln!(out, "> choose {}", s.binding.def(card).name).unwrap(),
        Action::Done => out.push_str("> done\n"),
        Action::UsePotion { slot, target } => writeln!(out, "> potion {slot} {target:?}").unwrap(),
    }
}

/// The packs the cover games use, always in this order (card ids follow
/// load order, and the random agent's choices follow card ids).
fn load_packs() {
    load_pack(IRONCLAD_PACK).unwrap();
    load_pack(RELICS_PACK).unwrap();
    load_pack(POTIONS_PACK).unwrap();
    // Last, so the earlier packs' ids stay where they were (Curse cards for
    // `fire-breathing-curse`).
    load_pack(COLORLESS_PACK).unwrap();
    // Last too (pack monsters for the Protect cover games).
    load_pack(MONSTERS_PACK).unwrap();
}

/// One decision of a cover game: the state it was taken in, the action,
/// the chance states passed on the way (each with its event pending) and
/// the next decision's state.
struct Step {
    before: CombatState,
    action: Action,
    chance: Vec<CombatState>,
    after: CombatState,
}

/// Plays a cover game: its dump (every decision's state and every chance
/// state between) and its steps.
fn play_cover(c: &Cover) -> (String, Vec<Step>) {
    load_packs();
    let mut names: Vec<&str> = c.character.starter_deck().iter().map(|&id| id.def().name).collect();
    names.extend_from_slice(c.cards);
    let (ids, b) = bind(&names).unwrap();
    let gen = |v: &[&str]| v.iter().map(|n| format!("gen:{n}")).collect::<Vec<String>>();
    let (relics, potions) = (gen(c.relics), gen(c.potions));
    let relics = relics_named(&relics.iter().map(String::as_str).collect::<Vec<_>>()).unwrap();
    let potions = potions_named(&potions.iter().map(String::as_str).collect::<Vec<_>>()).unwrap();
    let mut rng = Rng::new(c.seed);
    let hp = c.character.max_hp();
    let mut s = if c.monsters.is_empty() {
        CombatState::new_bound_turn1(c.character, &ids, &b, hp, hp, c.enc, &relics, false, Default::default(), c.elite_buff, &mut rng)
    } else {
        let names = gen(c.monsters);
        let kinds = monster_kinds(&names.iter().map(String::as_str).collect::<Vec<_>>()).unwrap();
        CombatState::new_with_turn1(c.character, &ids, &b, hp, hp, &kinds, EncounterGroup::Hallway, &relics, false, Default::default(), c.elite_buff, &mut rng)
    };
    s.give_potions(&potions).unwrap();
    assert!(s.pending.is_none());
    let mut out = String::new();
    let mut steps = Vec::new();
    dump_state(&mut out, &s);
    while let Some(a) = random_action(&s, &mut rng) {
        dump_action(&mut out, &s, a);
        let before = s.clone();
        s.apply_action(a).unwrap();
        let mut chance = Vec::new();
        // `advance`, one event at a time.
        while s.pending.is_some() {
            dump_state(&mut out, &s);
            chance.push(s.clone());
            s.resolve_chance(&mut rng);
        }
        dump_state(&mut out, &s);
        steps.push(Step { before, action: a, chance, after: s.clone() });
    }
    (out, steps)
}

fn cover_key(c: &Cover) -> String {
    if c.monsters.is_empty() {
        format!("cover-{}:{}", c.name, key(c.character, c.enc, c.seed))
    } else {
        format!("cover-{}:{}:pack:{}", c.name, c.character.name(), c.seed)
    }
}

fn fnv1a(s: &str) -> u64 {
    s.bytes().fold(0xcbf29ce484222325, |h, b| (h ^ b as u64).wrapping_mul(0x100000001b3))
}

fn key(character: Character, enc: Encounter, seed: u64) -> String {
    format!("{}:{}:{seed}", character.name(), enc.name())
}

fn load() -> HashMap<String, u64> {
    let mut text = std::fs::read_to_string(DATA).expect("tests/data/golden.txt missing; record with GOLDEN_RECORD=1");
    text.push_str(&std::fs::read_to_string(PROVING_DATA).expect("tests/data/golden_proving.txt missing; record with GOLDEN_RECORD=1"));
    text.lines()
        .map(|l| {
            let (k, h) = l.split_once(' ').expect("bad golden line");
            (k.to_string(), u64::from_str_radix(h, 16).expect("bad golden hash"))
        })
        .collect()
}

#[test]
fn golden_trajectories() {
    let record = std::env::var("GOLDEN_RECORD").is_ok();
    let golden = if record { HashMap::new() } else { load() };
    // Loaded first, so every game plays with them as the cover games do.
    load_packs();
    let mut lines = String::new();
    let mut failed = Vec::new();
    for character in Character::ALL {
        for enc in Encounter::ALL {
            for seed in 0..GAMES {
                let k = key(character, enc, seed);
                let h = fnv1a(&play_game(character, enc, seed));
                writeln!(lines, "{k} {h:016x}").unwrap();
                if !record && golden.get(&k) != Some(&h) {
                    failed.push(k);
                }
            }
        }
    }
    for c in COVER {
        let k = cover_key(c);
        let h = fnv1a(&play_cover(c).0);
        writeln!(lines, "{k} {h:016x}").unwrap();
        if !record && golden.get(&k) != Some(&h) {
            failed.push(k);
        }
    }
    let mut proving = String::new();
    for &(name, character, extra) in PROVING {
        for enc in Encounter::ALL {
            for seed in 0..PROVING_GAMES {
                let k = format!("proving-{name}:{}", key(character, enc, seed));
                let h = fnv1a(&play_proving(character, extra, enc, seed));
                writeln!(proving, "{k} {h:016x}").unwrap();
                if !record && golden.get(&k) != Some(&h) {
                    failed.push(k);
                }
            }
        }
    }
    if record {
        std::fs::write(DATA, lines).unwrap();
        std::fs::write(PROVING_DATA, proving).unwrap();
        println!("recorded {DATA} and {PROVING_DATA}");
        return;
    }
    assert!(
        failed.is_empty(),
        "{} games differ from the golden trajectories, first {}; print it with GOLDEN_DUMP={} and diff against the old code",
        failed.len(),
        failed[0],
        failed[0]
    );
}

/// Prints one game's dump: `GOLDEN_DUMP=<character>:<encounter>:<seed>`.
#[test]
fn dump() {
    let Ok(spec) = std::env::var("GOLDEN_DUMP") else { return };
    if let Some(c) = COVER.iter().find(|c| cover_key(c) == spec) {
        print!("{}", play_cover(c).0);
        return;
    }
    let parts: Vec<&str> = spec.split(':').collect();
    let character = Character::from_name(parts[0]).expect("character");
    let enc = Encounter::from_name(parts[1]).expect("encounter");
    let seed: u64 = parts[2].parse().expect("seed");
    print!("{}", play_game(character, enc, seed));
}

/// A card's definition name without a changed copy's `{...}`.
fn base_name(s: &CombatState, c: CardId) -> &'static str {
    let n = s.binding.def(c).name;
    &n[..n.find('{').unwrap_or(n.len())]
}

fn count(s: &CombatState, p: PileRef<'_>, name: &str) -> u32 {
    p.iter().filter(|&(c, _)| base_name(s, c) == name).map(|(_, n)| n as u32).sum()
}

fn in_hand(s: &CombatState, name: &str) -> bool {
    count(s, s.hand.view(), name) > 0
}

/// Plain Burns in hand (2 each at turn end).
fn burns(s: &CombatState) -> u32 {
    count(s, s.hand.view(), "Burn")
}

/// A generated power's amount on the player (0 when not bound).
fn pack_power(s: &CombatState, id: &str) -> i16 {
    Power::GEN.into_iter().filter(|&p| s.player.powers.get(p) != 0).find(|&p| s.binding.power_id(p) == Some(id)).map_or(0, |p| s.player.powers.get(p))
}

fn has_relic(s: &CombatState, name: &str) -> bool {
    s.player.relics.iter().any(|(r, _)| r.name() == format!("gen:{name}"))
}

/// Pocketwatch's counter, when held.
fn pocketwatch(s: &CombatState) -> Option<i16> {
    s.player.relics.iter().find(|(r, _)| r.name() == "gen:Pocketwatch").map(|(_, n)| n)
}

/// The End Turn steps of a game with Pocketwatch that lead to the next
/// turn: (counter at End Turn, the Play actions of that turn, the hand
/// after the next turn's draw).
fn pocketwatch_turns(steps: &[Step]) -> Vec<(i16, usize, usize)> {
    let mut out = Vec::new();
    let mut plays = 0;
    for st in steps {
        if st.action != Action::EndTurn {
            plays += matches!(st.action, Action::Play { .. }) as usize;
            continue;
        }
        if let Some(n) = pocketwatch(&st.before) {
            if !st.after.is_over() && st.after.turn == st.before.turn + 1 {
                out.push((n, plays, st.after.hand.len()));
            }
        }
        plays = 0;
    }
    out
}

fn played(st: &Step) -> Option<&'static str> {
    match st.action {
        Action::Play { card, .. } => Some(base_name(&st.before, card)),
        _ => None,
    }
}

/// Whether a cover game's steps reach `check`: the rule acts, in a state
/// where the rule it replaced would have played out differently.
fn reaches(check: &str, steps: &[Step]) -> bool {
    let ended = || steps.iter().filter(|st| st.action == Action::EndTurn);
    match check {
        // Rupture on the player's own Burn: Strength gained at End Turn,
        // with Rupture held, a Burn in hand and nothing else that moves
        // Strength then.
        "rupture-burn" => ended().any(|st| {
            let p = &st.before.player.powers;
            let others = [Power::LoseStrength, Power::DemonForm, Power::Brutality].iter().any(|&q| p.get(q) != 0);
            p.get(Power::Rupture) > 0 && !others && in_hand(&st.before, "Burn") && st.after.player.powers.get(Power::Strength) > p.get(Power::Strength)
        }),
        // Tungsten Rod on Hemokinesis' own 2: 1 lost.
        "tungsten-hemokinesis" => steps.iter().any(|st| {
            matches!(played(st), Some("Hemokinesis" | "Hemokinesis+")) && has_relic(&st.before, "Tungsten Rod") && st.before.player.hp - st.after.player.hp == 1
        }),
        // The turn-end stages: the relics' and the before-the-hand
        // powers' block, then the hand's Burn, then the powers'
        // `atEndOfTurn`. Each check holds where the order shows: no block
        // when End Turn starts and less damage coming than the block
        // gained (so the block before the hand takes the Burn, and
        // after it would not have), or HP near the cap (so a heal is cut
        // off).
        "orichalcum-burn" => ended().any(|st| {
            let s = &st.before;
            has_relic(s, "Orichalcum") && burns(s) > 0 && s.player.block == 0 && incoming_damage(s) < 6
        }),
        "metallicize-burn" => ended().any(|st| {
            let s = &st.before;
            let m = s.player.powers.get(Power::Metallicize);
            m > 0 && pack_power(s, "PlatedArmor") == 0 && burns(s) > 0 && s.player.block == 0 && incoming_damage(s) < m
        }),
        "plated-burn" => ended().any(|st| {
            let s = &st.before;
            let p = pack_power(s, "PlatedArmor");
            p > 0 && s.player.powers.get(Power::Metallicize) == 0 && burns(s) > 0 && s.player.block == 0 && incoming_damage(s) < p
        }),
        // Burn, then Regeneration's heal: less HP missing than the heal
        // (Regeneration before Burn would heal less).
        "burn-regen" => ended().any(|st| {
            let s = &st.before;
            let r = pack_power(s, "Regen");
            r > 0 && burns(s) > 0 && s.player.block == 0 && s.player.hp + r > s.player.max_hp
        }),
        // Regeneration acting first, ahead of Combust's loss: after the
        // Burns the heal reaches the cap.
        "regen-combust" => ended().any(|st| {
            let s = &st.before;
            let r = pack_power(s, "Regen");
            r > 0 && s.player.powers.get(Power::Combust) > 0 && s.player.block == 0 && s.player.hp - 2 * burns(s) as i16 + r > s.player.max_hp
        }),
        // Burn, then Combust's damage wins the fight (Combust first would
        // have ended it before the Burn).
        "burn-combust" => ended().any(|st| {
            let s = &st.before;
            s.player.powers.get(Power::Combust) > 0 && burns(s) > 0 && s.player.block == 0 && st.after.won()
        }),
        // Duplication still held at a chance state after the turn's
        // `atEndOfTurn` pass, before the round's end.
        "duplication-round" => ended().any(|st| st.chance.iter().any(|s| matches!(s.stage, Stage::EndingTurn { part: 2 | 4 }) && pack_power(s, "Duplication") > 0)),
        // The Guardian's Mode Shift broken at End Turn (Combust): it
        // starts the player's next turn with its 20 block.
        "guardian-shift-turn-end" => ended().any(|st| {
            let (b, a) = (&st.before.monsters[0], &st.after.monsters[0]);
            !st.after.is_over() && st.before.player.powers.get(Power::Combust) > 0 && b.powers.get(Power::ModeShift) > 0 && a.powers.get(Power::ModeShift) == 0 && a.block == 20
        }),
        // Blood for Blood's cost carried per copy: a cheaper copy in a pile.
        "bfb-per-copy" => steps.iter().any(|st| {
            let s = &st.after;
            s.hand.view().iter().chain(s.draw().iter()).chain(s.discard().iter()).any(|(c, _)| s.binding.def(c).name.starts_with("gen:Blood for Blood{"))
        }),
        // HP lost while a Blood for Blood is in play (Sharp Hide): the copy
        // in limbo keeps its cost.
        "bfb-limbo" => steps.iter().any(|st| played(st) == Some("gen:Blood for Blood") && st.after.player.hp < st.before.player.hp),
        // Feed killing: max HP up.
        "feed-kill" => steps.iter().any(|st| matches!(played(st), Some("gen:Feed" | "gen:Feed+")) && st.after.player.max_hp > st.before.player.max_hp),
        // Havoc playing Perfected Strike from limbo: it lands in the
        // exhaust pile, having dealt damage to a monster still standing.
        "perfected-strike-havoc" => steps.iter().any(|st| {
            let ps = |s: &CombatState| count(s, s.exhaust(), "Perfected Strike") + count(s, s.exhaust(), "Perfected Strike+");
            matches!(played(st), Some("gen:Havoc" | "gen:Havoc+"))
                && ps(&st.after) > ps(&st.before)
                && !st.after.is_over()
                && st.after.monsters[0].hp < st.before.monsters[0].hp
        }),
        // Artifact blocking Flex's LoseStrength.
        "flex-artifact" => steps.iter().any(|st| {
            matches!(played(st), Some("Flex" | "Flex+")) && st.before.player.powers.get(Power::Artifact) > 0 && st.after.player.powers.get(Power::LoseStrength) == 0
        }),
        // Lagavulin woken by HP loss (stunned) keeps the Metallicize above
        // the 8 waking takes off (a burning elite's +4); the old rule
        // cleared it all. (Its third Sleep turn always took off just 8.)
        "lagavulin-wake-hit" => steps.iter().any(|st| {
            let (b, a) = (&st.before.monsters[0], &st.after.monsters[0]);
            st.action != Action::EndTurn
                && b.kind == MonsterKind::Lagavulin
                && lagavulin::asleep(b)
                && a.alive()
                && a.intent() == lagavulin::STUNNED
                && a.powers.get(Power::Metallicize) > 0
                && a.powers.get(Power::Metallicize) == b.powers.get(Power::Metallicize) - lagavulin::OPEN_METALLICIZE
        }),
        // Pocketwatch (the game's count of cards played since the last
        // post-draw): at most 3 at End Turn, the next turn draws 5 + 3.
        "pocketwatch-draw" => pocketwatch_turns(steps).iter().any(|&(n, _, hand)| n <= 3 && hand == 8),
        // 4 or more: the next turn draws 5.
        "pocketwatch-no-draw" => pocketwatch_turns(steps).iter().any(|&(n, _, hand)| n >= 4 && hand == 5),
        // A Double Tap copy or Havoc's card counted: at most 3 Play actions
        // but 4 or more cards played, and no draw (a count of the player's
        // own plays would have drawn).
        "pocketwatch-copy-counts" => pocketwatch_turns(steps).iter().any(|&(n, plays, hand)| plays <= 3 && n >= 4 && hand == 5),
        // Fire Breathing on a Curse draw (the game's onCardDraw: Status or
        // Curse): an End Turn whose next draw took a Curse and no Status,
        // and the monsters lost HP through their Metallicize block.
        "fire-breathing-curse" => ended().any(|st| {
            let (b, a) = (&st.before, &st.after);
            let hp = |s: &CombatState| s.monsters.iter().map(|m| m.hp as i32).sum::<i32>();
            let held = |ty: CardType| a.hand.view().iter().any(|(c, _)| a.binding.def(c).ty == ty);
            !a.is_over() && pack_power(b, "FireBreathing") > 0 && held(CardType::Curse) && !held(CardType::Status) && hp(a) < hp(b)
        }),
        // A Fungi Beast killed in the monsters' turn (Poison, Thorns): its
        // Spore Cloud lands with the turn ended and is held through that
        // round's end (the game's turnHasEnded).
        "spore-cloud-held" => ended().any(|st| {
            let (b, a) = (&st.before, &st.after);
            let fungi = |s: &CombatState| s.monsters.iter().filter(|m| m.alive() && m.kind == MonsterKind::FungiBeast).count();
            !a.is_over() && fungi(a) < fungi(b) && b.player.powers.get(Power::Vulnerable) == 0 && a.player.powers.get(Power::Vulnerable) == 2
        }),
        // One killed by the player's card: it ticks at that round's end.
        "spore-cloud-ticks" => steps.windows(2).any(|w| {
            let (play, end) = (&w[0], &w[1]);
            let fungi = |s: &CombatState| s.monsters.iter().filter(|m| m.alive() && m.kind == MonsterKind::FungiBeast).count();
            play.action != Action::EndTurn
                && fungi(&play.after) < fungi(&play.before)
                && play.before.player.powers.get(Power::Vulnerable) == 0
                && play.after.player.powers.get(Power::Vulnerable) == 2
                && end.action == Action::EndTurn
                && !end.after.is_over()
                && end.after.player.powers.get(Power::Vulnerable) == 1
        }),
        // Protect paused the monsters' turn on its pick, and a monster
        // after the Shield Gremlin ends the turn with part of the 7 block
        // used: it was hit (Thorns, Flame Barrier) after the block landed.
        "ally-block-before-later-attacker" => ended().any(|st| {
            st.chance.iter().any(|c| match c.stage {
                Stage::MonsterActing { slot, .. } => (slot as usize + 1..MAX_MONSTERS).any(|i| {
                    let m = &st.after.monsters[i];
                    m.alive() && c.monsters[i].block == 0 && m.block > 0 && m.block < 7
                }),
                _ => false,
            })
        }),
        // The last ally died in the monsters' turn after the Shield
        // Gremlin's Protect: counted at the move, it protects again.
        "allies-at-move" => ended().any(|st| {
            let (b, a) = (&st.before, &st.after);
            let shield = |s: &CombatState| (0..MAX_MONSTERS).find(|&i| s.monsters[i].alive() && s.monsters[i].def().name.ends_with("Shield Gremlin"));
            match (shield(b), shield(a)) {
                (Some(i), Some(j)) if i == j => {
                    let others = |s: &CombatState| s.living_slots().filter(|&k| k != i).count();
                    !a.is_over() && others(b) > 0 && others(a) == 0 && b.monsters[i].intent_def().unwrap().name == "Protect" && a.monsters[i].intent_def().unwrap().name == "Protect"
                }
                _ => false,
            }
        }),
        // A Shield Gremlin alone opens with Protect on itself.
        "lone-protect-opening" => steps.first().is_some_and(|st| st.before.monsters[0].intent_def().unwrap().name == "Protect")
            && ended().next().is_some_and(|st| st.after.is_over() || st.after.monsters[0].block == 7),
        _ => panic!("no check {check}"),
    }
}

#[test]
fn cover_games_reach_their_mechanics() {
    let mut missed = Vec::new();
    for c in COVER {
        let (_, steps) = play_cover(c);
        for &check in c.checks {
            if !reaches(check, &steps) {
                missed.push(format!("{}: {check}", cover_key(c)));
            }
        }
    }
    assert!(missed.is_empty(), "cover games miss: {missed:?}");
}

/// Seeds whose game reaches all checks but at most one:
/// `GOLDEN_COVER_SEARCH=<name>`.
#[test]
fn cover_search() {
    let Ok(name) = std::env::var("GOLDEN_COVER_SEARCH") else { return };
    let base = COVER.iter().find(|c| c.name == name).expect("cover game");
    let mut tally: HashMap<&str, u32> = HashMap::new();
    for seed in 0..2000 {
        let c = Cover { seed, ..*base };
        let (_, steps) = play_cover(&c);
        let missing: Vec<&str> = c.checks.iter().copied().filter(|k| !reaches(k, &steps)).collect();
        for k in &missing {
            *tally.entry(*k).or_insert(0) += 1;
        }
        if missing.len() <= 1 {
            println!("seed {seed}: {} steps, missing {missing:?}", steps.len());
        }
    }
    println!("missed per check: {tally:?}");
}
