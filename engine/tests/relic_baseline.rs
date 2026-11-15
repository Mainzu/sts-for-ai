//! Relic baseline (docs/specs/relic-entity.md, build step 1): each of the
//! 23 relics' fights as relics-as-powers plays them, recorded on the code
//! before relics became their own entity. Step 4 moves the relics off
//! helper powers and diffs against this file: every changed line is
//! explained by a line of the game's relic code (or comes from a helper
//! power's name leaving the power list), then the file is re-recorded.
//!
//! Each fight is greedy play (`greedy_action`) from a fixed seed; a line per
//! decision names the state in words (powers by name, piles by card), so a
//! diff reads directly. Rewrite on purpose only:
//!   `RELIC_BASELINE_RECORD=1 cargo test --release --test relic_baseline`.

use std::fmt::Write as _;
use sts_engine::agent::greedy_action;
use sts_engine::registry::{bind, load_pack, pack_relic_names, relics_named, Binding};
use sts_engine::powers::Powers;
use sts_engine::*;

const PACK: &str = include_str!("../../content/packs/act1-relics.json");
const FILE: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/data/relic_baseline.txt");
/// Decisions recorded per fight at most.
const CAP: usize = 30;
/// (encounter, HP of 80, seed): a hallway at half HP (Red Skull's start), an
/// elite at full, a boss in between (relics limited to some fight kinds).
const FIGHTS: [(Encounter, i16, u64); 3] = [(Encounter::JawWorm, 40, 1), (Encounter::GremlinNob, 80, 2), (Encounter::SlimeBoss, 55, 3)];
/// The starter deck and cards relics react to (Strikes, exhaust, Strength,
/// HP loss).
const EXTRA: [&str; 5] = ["Pommel Strike", "Shrug It Off", "Carnage", "Inflame", "Bloodletting"];

fn powers(s: &CombatState, p: &Powers) -> String {
    let names: Vec<String> = p
        .iter()
        .map(|(q, n)| {
            let name = s.binding.power_id(q).map(str::to_string).unwrap_or_else(|| format!("{q:?}"));
            format!("{name}={n}")
        })
        .collect();
    names.join(",")
}

/// Cards named through the fight's binding (a changed copy by its own name:
/// Snecko Eye's rolled costs).
fn pile(p: PileRef<'_>, b: &Binding) -> String {
    let names: Vec<String> = p.iter().map(|(c, n)| format!("{}x{n}", b.def(c).name)).collect();
    names.join(",")
}

fn act(a: Action, b: &Binding) -> String {
    match a {
        Action::Play { card, target } => match target {
            Some(t) => format!("{}@{t}", b.def(card).name),
            None => b.def(card).name.to_string(),
        },
        Action::Choose(c) => format!("choose {}", b.def(c).name),
        a => format!("{a:?}"),
    }
}

fn line(s: &CombatState) -> String {
    let p = &s.player;
    let mut out = format!(
        "t{} {:?} hp{} b{} e{} [{}] hand[{}] draw{} disc{} exh[{}] heal{}",
        s.turn,
        s.stage,
        p.hp,
        p.block,
        p.energy,
        powers(s, &p.powers),
        pile(s.hand.view(), &s.binding),
        s.draw().len(),
        s.discard().len(),
        pile(s.exhaust(), &s.binding),
        s.win_heal
    );
    for m in s.monsters.iter().filter(|m| m.max_hp > 0) {
        let _ = write!(out, " | {:?} hp{} b{} [{}]", m.kind, m.hp, m.block, powers(s, &m.powers));
    }
    out
}

/// The 55 relics: Burning Blood (official, the starter, named again) and
/// the pack's 54, then a fight with none as the control.
fn relics() -> Vec<String> {
    load_pack(PACK).unwrap();
    let mut out = vec!["Burning Blood".to_string()];
    // Sacred Bark acts only on potions (docs/specs/potions.md): this pin is
    // of potion-free fights, where `act1_potions.rs` checks it does nothing.
    let mut names: Vec<String> = pack_relic_names().into_iter().filter(|n| n != "gen:Sacred Bark").collect();
    names.sort();
    out.extend(names);
    out.push(String::new());
    out
}

fn record() -> String {
    let mut deck: Vec<String> = starter_deck().iter().map(|&c| c.def().name.to_string()).collect();
    deck.extend(EXTRA.iter().map(|s| s.to_string()));
    let refs: Vec<&str> = deck.iter().map(String::as_str).collect();
    let (ids, b) = bind(&refs).unwrap();
    let mut out = String::new();
    let all = relics();
    assert_eq!(all.len(), 81, "80 relics and the control");
    for r in &all {
        let given = if r.is_empty() { vec![] } else { relics_named(&[r.as_str()]).unwrap() };
        for (e, hp, seed) in FIGHTS {
            let mut rng = Rng::new(seed);
            let mut s = CombatState::new_bound_with(Character::Ironclad, &ids, &b, hp, 80, e, &given, &mut rng);
            let _ = writeln!(out, "## {} / {} hp{hp} seed{seed}", if r.is_empty() { "(none)" } else { r }, e.name());
            let mut n = 0;
            while !s.is_over() && n < CAP {
                let a = greedy_action(&s);
                let _ = writeln!(out, "{}  -> {}", line(&s), act(a, &s.binding));
                s.step(a, &mut rng).unwrap();
                s.advance(&mut rng);
                n += 1;
            }
            let _ = writeln!(out, "end over={} {}", s.is_over(), line(&s));
        }
    }
    out
}

#[test]
fn relic_baseline() {
    let got = record();
    if std::env::var("RELIC_BASELINE_RECORD").is_ok() {
        std::fs::write(FILE, &got).unwrap();
        return;
    }
    let want = std::fs::read_to_string(FILE).expect("record with RELIC_BASELINE_RECORD=1").replace("\r\n", "\n");
    if got != want {
        let (i, (g, w)) = got.lines().zip(want.lines()).enumerate().find(|(_, (g, w))| g != w).unwrap_or((0, ("", "")));
        panic!("relic baseline differs at line {}:\n got  {g}\n want {w}", i + 1);
    }
}
