//! Probe for draw-knowledge item 6a, the Purity play-last reduction
//! (docs/research/build-plans-2026-11-14/purity-play-last.md, Step 0), kept
//! as the cost probe for 6b: it re-measures kb `measurement/purity-search-cost`.
//!
//! On the kb hand (Purity+ and nine Ironclad cards against Jaw Worm, empty
//! piles, 3 energy) it walks the turn twice. Walk A expands every legal
//! action. Walk B applies the 6a rule as the plan's Design section defines
//! it (obligation set on a Play that stops at a pick, picks recorded sorted,
//! the replay check done with `apply_action`). The plan's verdict expects
//! |B states| == |A|, |B keys| >= |A| and B's applies plus check applies >=
//! A's applies. It also prints `search()` uncapped and at the default cap.
//! Writes nothing to disk. Run (debug is enough, about 40 s):
//! `cargo test -p sts-engine --test play_last_probe -- --ignored --nocapture`

use std::collections::{HashMap, HashSet};
use std::time::Instant;

use sts_engine::registry::{bind, load_pack};
use sts_engine::search::{search, Heuristic, SearchConfig};
use sts_engine::*;

const IRONCLAD: &str = include_str!("../../content/packs/act1-ironclad.json");
const RELICS: &str = include_str!("../../content/packs/act1-relics.json");
const POTIONS: &str = include_str!("../../content/packs/act1-potions.json");
const COLORLESS: &str = include_str!("../../content/packs/act1-colorless.json");

/// `colorless.rs`'s `setup_in`: the pack card `card` and the official cards
/// `hand` in hand, 3 energy, empty piles, monsters at 100 HP, no block or powers.
fn setup_in(enc: Encounter, card: &str, hand: &[&str]) -> CombatState {
    load_pack(IRONCLAD).unwrap();
    load_pack(RELICS).unwrap();
    load_pack(POTIONS).unwrap();
    load_pack(COLORLESS).unwrap();
    let g = format!("gen:{card}");
    let mut names = vec![g.as_str()];
    names.extend_from_slice(hand);
    let (ids, b) = bind(&names).unwrap();
    let mut s = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, enc, &mut Rng::new(1));
    s.hand = Hand::from_cards(&ids);
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    s.set_exhaust(Pile::default());
    s.player.energy = 3;
    for m in s.monsters.iter_mut().filter(|m| m.alive()) {
        m.hp = 100;
        m.max_hp = 100;
        m.block = 0;
        m.powers = Default::default();
    }
    s
}

/// Where both walks stop: End Turn's result, a chance event, a finished
/// combat (recorded, not expanded).
fn stops(a: Action, t: &CombatState) -> bool {
    a == Action::EndTurn || t.is_over() || !t.awaiting_action()
}

/// The 6a obligation: the pre-state Q (interned), the play P that stopped at
/// a pick, and P's picks so far, sorted.
#[derive(Clone, PartialEq, Eq, Hash)]
struct Obl {
    pre: u32,
    play: Action,
    picks: Vec<CardId>,
}

#[derive(Default)]
struct WalkB {
    pres: Vec<CombatState>,
    pre_ids: HashMap<CombatState, u32>,
    pre_after: HashMap<(u32, Action), Option<CombatState>>,
    check_applies: usize,
    checks: usize,
    skipped: usize,
}

impl WalkB {
    fn intern(&mut self, s: &CombatState) -> u32 {
        if let Some(&i) = self.pre_ids.get(s) {
            return i;
        }
        let i = self.pres.len() as u32;
        self.pres.push(s.clone());
        self.pre_ids.insert(s.clone(), i);
        i
    }

    /// The plan's `commutes`: Q·a·P(picks) (then Done if the pick is still
    /// open) lands exactly on `after` = N·a.
    fn commutes(&mut self, o: &Obl, a: Action, after: &CombatState) -> bool {
        self.checks += 1;
        if !self.pre_after.contains_key(&(o.pre, a)) {
            let mut r = self.pres[o.pre as usize].clone();
            self.check_applies += 1;
            let v = match r.apply_action(a) {
                Ok(()) if r.pick().is_none() && r.pending.is_none() && !r.is_over() => Some(r),
                _ => None,
            };
            self.pre_after.insert((o.pre, a), v);
        }
        let Some(qa) = &self.pre_after[&(o.pre, a)] else { return false };
        let mut r = qa.clone();
        self.check_applies += 1;
        if r.apply_action(o.play).is_err() {
            return false;
        }
        for &c in &o.picks {
            if r.pending.is_some() || r.pick().is_none() {
                return false;
            }
            self.check_applies += 1;
            if r.apply_action(Action::Choose(c)).is_err() {
                return false;
            }
        }
        if r.pending.is_some() {
            return false;
        }
        if r.pick().is_some() {
            self.check_applies += 1;
            if r.apply_action(Action::Done).is_err() {
                return false;
            }
        }
        r.pending.is_none() && r == *after
    }
}

#[test]
#[ignore = "cost probe for draw-knowledge 6a/6b; about 40 s in debug"]
fn purity_play_last_probe() {
    let hand = ["Strike", "Defend", "Bash", "Anger", "Clash", "Cleave", "Pommel Strike", "Twin Strike", "Flex"];
    let root = setup_in(Encounter::JawWorm, "Purity+", &hand);
    assert!(root.awaiting_action());

    // Walk A: every legal action, equal states merged.
    let t0 = Instant::now();
    let mut a_seen: HashSet<CombatState> = HashSet::new();
    let mut a_stops: HashSet<CombatState> = HashSet::new();
    let mut a_edges = 0usize;
    a_seen.insert(root.clone());
    let mut stack = vec![root.clone()];
    while let Some(s) = stack.pop() {
        for a in s.legal_actions() {
            let mut t = s.clone();
            t.apply_action(a).expect("legal action applies");
            a_edges += 1;
            if stops(a, &t) {
                a_stops.insert(t);
            } else if !a_seen.contains(&t) {
                a_seen.insert(t.clone());
                stack.push(t);
            }
        }
    }
    println!("walk A: |A| {} decision states, {} stop states, edges {} ({:.1?})", a_seen.len(), a_stops.len(), a_edges, t0.elapsed());

    // Walk B: the 6a rule. Key: (state, obligation). The root's children
    // never get an obligation (search() passes None there).
    let t0 = Instant::now();
    let mut w = WalkB::default();
    let mut b_keys: HashSet<(CombatState, Option<Obl>)> = HashSet::new();
    let mut b_stops: HashSet<CombatState> = HashSet::new();
    let (mut b_applies, mut b_followed) = (0usize, 0usize);
    b_keys.insert((root.clone(), None));
    let mut stack: Vec<(CombatState, Option<Obl>, bool)> = vec![(root.clone(), None, true)];
    while let Some((s, o, is_root)) = stack.pop() {
        let at_pick = s.pick().is_some();
        for a in s.legal_actions() {
            let mut t = s.clone();
            t.apply_action(a).expect("legal action applies");
            b_applies += 1;
            let child = if at_pick {
                // The parent's obligation carries on; Choose adds its card.
                o.clone().map(|mut o| {
                    if let Action::Choose(c) = a {
                        let i = o.picks.partition_point(|&x| x <= c);
                        o.picks.insert(i, c);
                    }
                    o
                })
            } else if let Some(o) = &o {
                if a != Action::EndTurn && w.commutes(o, a, &t) {
                    w.skipped += 1;
                    continue;
                }
                None
            } else if !is_root && a != Action::EndTurn && t.pick().is_some() && t.pending.is_none() {
                Some(Obl { pre: w.intern(&s), play: a, picks: Vec::new() })
            } else {
                None
            };
            b_followed += 1;
            if stops(a, &t) {
                b_stops.insert(t);
            } else {
                let key = (t, child);
                if !b_keys.contains(&key) {
                    b_keys.insert(key.clone());
                    stack.push((key.0, key.1, false));
                }
            }
        }
    }
    let b_states: HashSet<&CombatState> = b_keys.iter().map(|(s, _)| s).collect();
    let b_not_a = b_states.iter().filter(|s| !a_seen.contains(**s)).count();
    let a_not_b = a_seen.iter().filter(|s| !b_states.contains(s)).count();
    println!("walk B: |B states| {}, |B keys| {}, stop states {} ({:.1?})", b_states.len(), b_keys.len(), b_stops.len(), t0.elapsed());
    println!("walk B: applies {} (followed {}, skipped {}), checks {}, check applies {}, applies + check applies {}", b_applies, b_followed, w.skipped, w.checks, w.check_applies, b_applies + w.check_applies);
    println!("walk B: pre-states {}, pre_after cache {}; B states not in A {}, A states not in B {}; stops equal {}", w.pres.len(), w.pre_after.len(), b_not_a, a_not_b, a_stops == b_stops);
    drop(b_states);
    drop(b_keys);
    drop(a_seen);
    drop(w);

    for max_nodes in [usize::MAX, 50_000] {
        let t0 = Instant::now();
        let r = search(&root, &mut Heuristic, &SearchConfig { max_nodes, ..SearchConfig::default() });
        let cap = if max_nodes == usize::MAX { "uncapped".to_string() } else { max_nodes.to_string() };
        println!("search() {cap}: nodes {}, leaves {}, cuts {} ({:.1?})", r.nodes, r.leaves, r.cuts, t0.elapsed());
    }
}
