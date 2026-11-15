//! Exact solver: values to the end of combat, budget, determinism.

mod common;

use common::*;
use sts_engine::agent::greedy_action;
use sts_engine::search::{search, Heuristic, SearchConfig};
use sts_engine::solve::{solve, MemoryStore, Solved, SolvedStore, SolveConfig};
use sts_engine::*;

fn cfg(max_nodes: u64) -> SolveConfig {
    SolveConfig { max_nodes, ..SolveConfig::default() }
}

fn dist_cfg(max_nodes: u64) -> SolveConfig {
    SolveConfig { max_nodes, distribution: true, bounds: false }
}

/// Decision states of one greedy game, in play order.
fn game_decisions(enc: Encounter, seed: u64) -> Vec<CombatState> {
    let mut rng = Rng::new(seed);
    let mut s = CombatState::new(&starter_deck(), 80, 80, enc, &mut rng);
    let mut out = Vec::new();
    while s.awaiting_action() {
        out.push(s.clone());
        let a = greedy_action(&s);
        s.step(a, &mut rng).unwrap();
    }
    out
}

/// Up to `n` positions from games' tails that solve within `max_nodes`,
/// walking each game back from its last decision to the first unsolvable one.
fn tail_positions(n: usize, max_nodes: u64) -> Vec<CombatState> {
    let mut out = Vec::new();
    'games: for seed in 0..200u64 {
        let enc = Encounter::ALL[seed as usize % Encounter::ALL.len()];
        for s in game_decisions(enc, seed).into_iter().rev() {
            if s.legal_actions().len() < 2 {
                continue;
            }
            if solve(&s, &cfg(max_nodes), None).is_none() {
                continue 'games;
            }
            out.push(s);
            if out.len() == n {
                return out;
            }
        }
    }
    out
}

#[test]
fn solve_terminal() {
    // Jaw Worm opens with Chomp (11 damage), so ending the turn costs HP.
    let s = with_hand(Encounter::JawWorm, &["Strike", "Defend"], 6);
    let r = solve(&s, &cfg(1_000_000), None).expect("tiny position solves");
    let strike_id = card("Strike");
    let strike = r
        .options
        .iter()
        .find(|o| matches!(o.actions[0], Action::Play { card, .. } if card == strike_id))
        .expect("Strike is an option");
    let mut after = s.clone();
    after.apply_action(strike.actions[0]).unwrap();
    assert!(after.won());
    assert_eq!(strike.value, after.score());
    let end = r.options.iter().find(|o| o.actions.contains(&Action::EndTurn)).unwrap();
    assert!(end.value < strike.value, "EndTurn {} vs Strike {}", end.value, strike.value);
}

#[test]
fn solve_groups_root_like_search() {
    for s in tail_positions(10, 50_000) {
        let r = solve(&s, &cfg(50_000), None).unwrap();
        let sr = search(&s, &mut Heuristic, &SearchConfig::default());
        let a: Vec<_> = r.options.iter().map(|o| o.actions.clone()).collect();
        let b: Vec<_> = sr.options.iter().map(|o| o.actions.clone()).collect();
        assert_eq!(a, b);
    }
}

#[test]
fn solve_budget() {
    // An opening position is far too big for 1,000 nodes.
    let s = fresh(Encounter::JawWorm, 3);
    assert!(solve(&s, &cfg(1_000), None).is_none());

    // A small position solves in exactly n nodes: n is enough, n - 1 is not.
    let small = tail_positions(5, 20_000);
    assert!(!small.is_empty());
    for s in small {
        let r = solve(&s, &cfg(20_000), None).unwrap();
        assert!(r.nodes <= 20_000);
        let n = r.nodes;
        let again = solve(&s, &cfg(n), None).expect("solves within its own node count");
        assert_eq!(again.nodes, n);
        if n > 1 {
            assert!(solve(&s, &cfg(n - 1), None).is_none());
        }
    }
}

#[test]
fn solve_deterministic() {
    let positions = tail_positions(20, 50_000);
    assert_eq!(positions.len(), 20);
    for s in &positions {
        let a = solve(s, &cfg(50_000), None).unwrap();
        let b = solve(s, &cfg(50_000), None).unwrap();
        assert_eq!(a.nodes, b.nodes);
        assert_eq!(a.options.len(), b.options.len());
        for (x, y) in a.options.iter().zip(&b.options) {
            assert_eq!(x.actions, y.actions);
            assert_eq!(x.value.to_bits(), y.value.to_bits());
            assert!((0.0..=2.0).contains(&x.value));
        }
    }
}

/// A store that records which states it answered and which it was offered.
struct Recording {
    inner: MemoryStore,
    hits: Vec<CombatState>,
    offered: Vec<(CombatState, u64)>,
}

impl Recording {
    fn new(min_nodes: u64) -> Recording {
        Recording { inner: MemoryStore::new(min_nodes), hits: Vec::new(), offered: Vec::new() }
    }
}

impl SolvedStore for Recording {
    fn lookup(&mut self, s: &CombatState) -> Option<Solved> {
        let r = self.inner.lookup(s);
        if r.is_some() {
            self.hits.push(s.clone());
        }
        r
    }

    fn insert(&mut self, s: &CombatState, solved: &Solved) {
        self.offered.push((s.clone(), solved.cost));
        self.inner.insert(s, solved);
    }
}

/// A game's decisions with at least 2 options, last first.
fn walk_back(enc: Encounter, seed: u64) -> Vec<CombatState> {
    game_decisions(enc, seed).into_iter().rev().filter(|s| s.legal_actions().len() >= 2).collect()
}

fn same_values(a: &solve::Solution, b: &solve::Solution) {
    assert_eq!(a.options.len(), b.options.len());
    for (x, y) in a.options.iter().zip(&b.options) {
        assert_eq!(x.actions, y.actions);
        assert_eq!(x.value.to_bits(), y.value.to_bits());
    }
}

#[test]
fn store_exact() {
    const BUDGET: u64 = 8_000;
    let (mut nodes_cold, mut nodes_store, mut both, mut hit_checks) = (0u64, 0u64, 0usize, 0usize);
    for seed in 0..20u64 {
        let enc = Encounter::ALL[seed as usize % Encounter::ALL.len()];
        let decisions = walk_back(enc, seed);
        let cold: Vec<_> = decisions.iter().map_while(|s| solve(s, &cfg(BUDGET), None)).collect();
        // min_nodes 0 keeps every solved state, so every later decision is
        // in the store; the default keeps fewer, and values must not change.
        for min_nodes in [0, 1_000] {
            let mut store = Recording::new(min_nodes);
            // The store reaches further back; one decision past the cold
            // walk is enough to see it.
            for (i, s) in decisions.iter().enumerate().take(cold.len() + 1) {
                let hits_before = store.hits.len();
                let Some(warm) = solve(s, &cfg(BUDGET), Some(&mut store)) else { break };
                if let Some(c) = cold.get(i) {
                    same_values(c, &warm);
                    if min_nodes == 0 {
                        nodes_cold += c.nodes;
                        nodes_store += warm.nodes;
                        both += 1;
                    }
                }
                if min_nodes == 0 && i > 0 {
                    assert!(
                        store.hits[hits_before..].contains(&decisions[i - 1]),
                        "seed {seed}: the later decision on the played path is not a hit"
                    );
                    hit_checks += 1;
                }
            }
        }
    }
    eprintln!("store_exact: {both} decisions, {hit_checks} hit checks, nodes {nodes_store} vs {nodes_cold}");
    assert!(both >= 30, "only {both} decisions solved both ways");
    assert!(hit_checks >= 20, "only {hit_checks} hit checks");
    assert!(nodes_store < nodes_cold, "store {nodes_store} vs cold {nodes_cold}");
}

#[test]
fn store_skips_fast() {
    let positions = tail_positions(10, 50_000);
    for min_nodes in [1_000, 0] {
        let mut store = Recording::new(min_nodes);
        for s in &positions {
            solve(s, &cfg(50_000), Some(&mut store)).unwrap();
        }
        assert!(store.inner.iter().all(|(_, e)| e.cost >= min_nodes));
        assert!(!store.inner.is_empty(), "nothing stored at min_nodes {min_nodes}");
        if min_nodes == 0 {
            // Each solve offers only its own new states, so every offer is
            // a distinct state, and all of them are kept.
            assert_eq!(store.inner.len(), store.offered.len());
        } else {
            let cheap = store.offered.iter().filter(|(_, c)| *c < min_nodes).count();
            assert!(cheap > 0, "every offered state was expensive; the filter is untested");
            assert_eq!(store.inner.len(), store.offered.len() - cheap);
        }
    }
}

#[test]
fn store_partial() {
    let mut checked = 0;
    for s in tail_positions(10, 50_000) {
        let full = solve(&s, &cfg(50_000), None).unwrap();
        if full.nodes < 100 {
            continue;
        }
        let mut store = MemoryStore::new(0);
        assert!(solve(&s, &cfg(full.nodes / 2), Some(&mut store)).is_none());
        assert!(!store.is_empty(), "a budget-out solve kept nothing");
        // Every kept subtree is exact: it equals that state's cold value.
        for (t, e) in store.iter().take(20) {
            if t.awaiting_action() {
                let cold = solve(t, &cfg(50_000), None).unwrap();
                let best = cold.options.iter().map(|o| o.value).fold(f64::NEG_INFINITY, f64::max);
                assert_eq!(best.to_bits(), e.value.to_bits());
            }
        }
        let warm = solve(&s, &cfg(50_000), Some(&mut store)).unwrap();
        assert!(warm.hits > 0);
        same_values(&full, &warm);
        checked += 1;
    }
    assert!(checked >= 5, "only {checked} positions were big enough");
}

/// Each option's distribution sums to 1 and implies its value.
fn check_distributions(r: &solve::Solution) {
    for o in &r.options {
        let d = o.dist.as_ref().expect("distribution solve gives every option a distribution");
        let total = d.loss + d.wins.iter().map(|&(_, p)| p).sum::<f64>();
        assert!((total - 1.0).abs() < 1e-9, "sums to {total}");
        let implied: f64 = d.wins.iter().map(|&(k, p)| p * (2.0 - k as f64 / 100.0)).sum();
        assert!((implied - o.value).abs() < 1e-9, "implies {implied}, value {}", o.value);
        assert!(d.wins.windows(2).all(|w| w[0].0 < w[1].0), "HP lost in ascending order, each once");
        assert!(d.loss >= 0.0 && d.wins.iter().all(|&(_, p)| p > 0.0));
    }
}

#[test]
fn distribution_consistent() {
    let mut positions = tail_positions(20, 50_000);
    assert_eq!(positions.len(), 20);
    // Greedy tails rarely risk a loss, so add one that does: 5 HP against
    // Jaw Worm's 11-damage opener, with too little to kill it this turn.
    let mut risky = with_hand(Encounter::JawWorm, &["Strike", "Defend"], 30);
    risky.player.hp = 5;
    positions.push(risky);
    let mut lossy = 0;
    for s in &positions {
        let plain = solve(s, &cfg(50_000), None).unwrap();
        assert!(plain.options.iter().all(|o| o.dist.is_none()));
        let full = solve(s, &dist_cfg(50_000), None).unwrap();
        same_values(&plain, &full);
        check_distributions(&full);
        lossy += full.options.iter().filter(|o| o.dist.as_ref().unwrap().loss > 0.0).count();
    }
    assert!(lossy > 0, "no option risks a loss; the loss term is untested");

    // A value-only store entry is a miss for a distribution solve, which
    // upgrades it; values stay the same.
    let mut store = MemoryStore::new(0);
    for s in positions.iter().take(5) {
        solve(s, &cfg(50_000), Some(&mut store)).unwrap();
    }
    assert!(store.iter().all(|(_, e)| e.dist.is_none()));
    for s in positions.iter().take(5) {
        let warm = solve(s, &dist_cfg(50_000), Some(&mut store)).unwrap();
        let cold = solve(s, &dist_cfg(50_000), None).unwrap();
        same_values(&cold, &warm);
        check_distributions(&warm);
        for (x, y) in cold.options.iter().zip(&warm.options) {
            assert_eq!(x.dist, y.dist);
        }
    }
    assert!(store.iter().any(|(_, e)| e.dist.is_some()), "nothing was upgraded");
    // A value solve over upgraded entries still hits them.
    let again = solve(&positions[0], &cfg(50_000), Some(&mut store)).unwrap();
    same_values(&solve(&positions[0], &cfg(50_000), None).unwrap(), &again);
}

/// `turns_left`, the solver half of `db_turns_left`: 0 when the best line
/// ends the combat this turn, 1 when it needs one more EndTurn.
#[test]
fn solve_turns_left() {
    let lethal = with_hand(Encounter::JawWorm, &["Strike", "Defend"], 6);
    let r = solve(&lethal, &cfg(1_000_000), None).unwrap();
    assert_eq!(r.turns_left, 0);

    // Nothing in hand can kill; next turn's draw is five Strikes.
    let mut later = with_hand(Encounter::JawWorm, &["Defend"], 6);
    later.set_draw(Pile::from_cards(&[card("Strike"); 5]));
    let r = solve(&later, &cfg(1_000_000), None).unwrap();
    assert_eq!(r.turns_left, 1);
    assert!(r.options.iter().all(|o| o.value > 1.5), "the fight is won next turn");

    // Stored entries carry it too: the root's entry equals the solution's.
    let mut store = MemoryStore::new(0);
    let r = solve(&later, &cfg(1_000_000), Some(&mut store)).unwrap();
    let root = store.iter().find(|(s, _)| **s == later).map(|(_, e)| e.clone()).unwrap();
    assert_eq!(root.turns_left, r.turns_left);
}

/// Stored decisions carry each option's exact value, equal to a cold solve
/// of that decision, and answer a later solve of it as a root.
#[test]
fn store_options_match_cold() {
    let mut checked = 0;
    for s in tail_positions(5, 50_000) {
        let mut store = MemoryStore::new(0);
        solve(&s, &dist_cfg(50_000), Some(&mut store)).unwrap();
        let decisions: Vec<_> = store.iter().filter(|(t, _)| t.awaiting_action()).map(|(t, e)| (t.clone(), e.clone())).collect();
        assert!(store.iter().all(|(t, e)| e.options.is_some() == t.awaiting_action()));
        for (t, e) in decisions.iter().take(10) {
            let cold = solve(t, &dist_cfg(50_000), None).unwrap();
            assert_eq!(e.options.as_ref().unwrap(), &cold.options);
            let warm = solve(t, &dist_cfg(50_000), Some(&mut store)).unwrap();
            assert_eq!((warm.nodes, warm.hits), (0, 1));
            assert_eq!(warm.options, cold.options);
            assert_eq!((warm.turns_left, warm.dist.clone()), (cold.turns_left, cold.dist.clone()));
            checked += 1;
        }
    }
    assert!(checked >= 20, "only {checked} stored decisions");
}

#[test]
fn solve_touches_bounded() {
    // Listing a random event's outcomes is bounded with the nodes: a draw
    // of 5 from 16 kinds of card has thousands of outcomes, more than a
    // 100-node budget may list, so the solve gives up instead of listing
    // them all.
    use sts_engine::solve::TOUCHES_PER_NODE;
    let mut s = with_hand(Encounter::JawWorm, &["Defend"], 80);
    let kinds = ["Strike", "Defend", "Bash", "Cleave", "Anger", "Shrug It Off", "Pommel Strike", "Iron Wave",
                 "Clothesline", "Twin Strike", "Body Slam", "Thunderclap", "Inflame", "Flex", "Uppercut", "Dropkick"];
    let draw: Vec<_> = kinds.iter().flat_map(|n| [card(n), card(n)]).collect();
    s.set_draw(Pile::from_cards(&draw));
    assert!(solve(&s, &cfg(100), None).is_none());
    for p in tail_positions(10, 20_000) {
        let r = solve(&p, &cfg(20_000), None).expect("solved before");
        assert!(r.touches <= TOUCHES_PER_NODE * 20_000);
        assert!(r.touches >= r.nodes - 1, "every expanded state but the root was listed");
    }
}

/// A state's cost never exceeds what a cold solve of it expands, nor the
/// expansions a walk reusing hits has done in all, however far back it goes:
/// hits' subtrees overlap (transpositions), so summing their costs counted
/// shared states once per path and grew without bound.
#[test]
fn store_cost_bounded() {
    const BUDGET: u64 = 50_000;
    let (mut checked, mut cold_checked) = (0, 0);
    for seed in 0..20u64 {
        let enc = Encounter::ALL[seed as usize % Encounter::ALL.len()];
        let mut store = MemoryStore::new(0);
        let mut total = 0u64;
        for s in walk_back(enc, seed) {
            let Some(warm) = solve(&s, &cfg(BUDGET), Some(&mut store)) else { break };
            total += warm.nodes;
            assert!(warm.cost >= warm.nodes, "seed {seed}: cost {} below its own {} expansions", warm.cost, warm.nodes);
            let worst = store.iter().map(|(_, e)| e.cost).max().unwrap_or(0);
            assert!(worst <= total, "seed {seed}: a stored cost {worst} is above the walk's {total} expansions");
            if let Some(cold) = solve(&s, &cfg(BUDGET), None) {
                assert!(warm.cost <= cold.nodes, "seed {seed}: cost {} above a cold solve's {} nodes", warm.cost, cold.nodes);
                cold_checked += 1;
            }
            checked += 1;
        }
    }
    eprintln!("store_cost_bounded: {checked} decisions, {cold_checked} against cold solves");
    assert!(cold_checked >= 30, "only {cold_checked} decisions compared with cold solves");
}
