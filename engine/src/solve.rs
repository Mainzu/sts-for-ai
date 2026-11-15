//! Exact solver: each root option's expected final score under the best
//! play, to the end of combat.
//!
//! Every random event is listed in full, every decision takes its best
//! option, and there is no turn limit and no evaluator. Equal states share
//! one value (transpositions). A node budget bounds the work: past it the
//! solve reports unsolvable rather than an approximate value. Expanding a
//! state lists all its children (every outcome of a random event), so the
//! children listed are bounded too, at `TOUCHES_PER_NODE` per node of the
//! budget: one draw can have tens of thousands of outcomes.
//!
//! The tree is walked depth-first with an explicit stack, so deep trees
//! can't overflow the call stack.

use std::collections::hash_map::DefaultHasher;
use std::collections::HashMap;
use std::hash::BuildHasherDefault;

use crate::chance::ChanceOutcomes;
use crate::codec::{decode, encode};
use crate::state::{Action, CombatState};

/// Children listed per node of the budget (`Solution::touches`).
/// Measured 2026-10-28 over 400 bench puzzles solved cold at 1M nodes: at
/// most 4.4 per node (median 2.1).
pub const TOUCHES_PER_NODE: u64 = 16;

#[derive(Clone, Debug)]
pub struct SolveConfig {
    /// Most new states expanded (store hits count too) before giving up.
    pub max_nodes: u64,
    /// Also compute each option's outcome distribution.
    pub distribution: bool,
    /// Skip options that can't beat the best one (docs/specs/solver-bounds.md):
    /// at a decision, once the best option reaches the decision's
    /// `upper_bound`, or before opening an option whose `upper_bound` is at
    /// or below the best so far. Values stay exact; a skipped root or stored
    /// option is `bounded`. Ignored in a distribution solve.
    pub bounds: bool,
}

impl Default for SolveConfig {
    fn default() -> SolveConfig {
        SolveConfig { max_nodes: 1_000_000, distribution: false, bounds: false }
    }
}

/// The exact distribution of a combat's outcome under the best play.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Distribution {
    /// P(loss).
    pub loss: f64,
    /// (HP lost, P(win with that HP lost)), HP lost ascending, each once.
    /// HP lost is counted as the score counts it: after the end-of-combat
    /// heal, floored at 0.
    pub wins: Vec<(u16, f64)>,
}

impl Distribution {
    fn terminal(s: &CombatState) -> Distribution {
        if s.won() {
            Distribution { loss: 0.0, wins: vec![((s.start_hp - s.player.hp).max(0) as u16, 1.0)] }
        } else {
            Distribution { loss: 1.0, wins: Vec::new() }
        }
    }

    /// Adds `p` times `other`, in a fixed order.
    fn add_scaled(&mut self, other: &Distribution, p: f64) {
        self.loss += p * other.loss;
        for &(k, q) in &other.wins {
            match self.wins.binary_search_by_key(&k, |&(j, _)| j) {
                Ok(i) => self.wins[i].1 += p * q,
                Err(i) => self.wins.insert(i, (k, p * q)),
            }
        }
    }
}

/// What the solver knows about a solved state.
#[derive(Clone, Debug, PartialEq)]
pub struct Solved {
    /// Exact expected final score (`CombatState::score` scale, 0..=2).
    pub value: f64,
    /// A lower bound on the expansions a cold solve of it takes: the larger
    /// of the expansions its subtree took and one more than its costliest
    /// child's cost (a hit's stored cost included). Hits' subtrees overlap,
    /// so their costs aren't summed.
    pub cost: u64,
    /// The most turns the combat can still last under the best play: the
    /// best option's at decisions, the longest outcome's at chance nodes; 0
    /// when it ends this turn.
    pub turns_left: u16,
    /// Its outcome distribution, from a distribution solve.
    pub dist: Option<Distribution>,
    /// At a decision offered to a store, every option grouped as at a root,
    /// with its exact value (and distribution), or an upper bound when it
    /// was skipped (`bounded`): a stored decision answers a later solve of
    /// it as a root. `None` inside a solve.
    pub options: Option<Vec<SolvedOption>>,
}

/// Solved states kept across solves. The solver asks it about every newly
/// reached state, and offers it every state it finished when a solve ends.
pub trait SolvedStore {
    fn lookup(&mut self, s: &CombatState) -> Option<Solved>;
    /// Whether `insert` would keep this entry (by cost, for one); the solver
    /// offers only entries the store keeps, decisions with their options.
    fn keeps(&self, _solved: &Solved) -> bool {
        true
    }
    /// The store decides what to keep.
    fn insert(&mut self, s: &CombatState, solved: &Solved);
    /// Called once a solve has offered everything (a database writes its
    /// batch here).
    fn end_solve(&mut self) {}
}

/// Fixed hasher, so iteration order (and with it every offer order) is the
/// same every run.
type StateMap<V> = HashMap<CombatState, V, BuildHasherDefault<DefaultHasher>>;

/// One game's solved states, in memory. States that cost under `min_nodes`
/// to solve are quick to solve again, so they aren't kept.
pub struct MemoryStore {
    pub min_nodes: u64,
    map: StateMap<Solved>,
}

impl MemoryStore {
    pub fn new(min_nodes: u64) -> MemoryStore {
        MemoryStore { min_nodes, map: StateMap::default() }
    }

    pub fn len(&self) -> usize {
        self.map.len()
    }

    pub fn is_empty(&self) -> bool {
        self.map.is_empty()
    }

    pub fn iter(&self) -> impl Iterator<Item = (&CombatState, &Solved)> {
        self.map.iter()
    }
}

impl Default for MemoryStore {
    fn default() -> MemoryStore {
        MemoryStore::new(1_000)
    }
}

impl SolvedStore for MemoryStore {
    fn lookup(&mut self, s: &CombatState) -> Option<Solved> {
        self.map.get(s).cloned()
    }

    fn keeps(&self, solved: &Solved) -> bool {
        solved.cost >= self.min_nodes
    }

    fn insert(&mut self, s: &CombatState, solved: &Solved) {
        if !self.keeps(solved) {
            return;
        }
        // Never replace a distribution with a value-only entry.
        if solved.dist.is_none() && self.map.get(s).is_some_and(|e| e.dist.is_some()) {
            return;
        }
        self.map.insert(s.clone(), solved.clone());
    }
}

/// One option at the root with its exact value.
#[derive(Clone, Debug, PartialEq)]
pub struct SolvedOption {
    /// Every action leading to this option, in `legal_actions` order.
    pub actions: Vec<Action>,
    /// Exact, or an upper bound when `bounded`.
    pub value: f64,
    /// Its outcome distribution, from a distribution solve.
    pub dist: Option<Distribution>,
    /// Skipped by a bounded solve: `value` is the option's `upper_bound`,
    /// at most the decision's value.
    pub bounded: bool,
}

#[derive(Clone, Debug)]
pub struct Solution {
    /// Every distinct option at the root, grouped and ordered as `search`
    /// groups them.
    pub options: Vec<SolvedOption>,
    /// States newly expanded.
    pub nodes: u64,
    /// States whose value came from the store.
    pub hits: u64,
    /// Children listed while expanding (decisions' afterstates, events'
    /// outcomes); at most `TOUCHES_PER_NODE` times the node budget.
    pub touches: u64,
    /// The root's `turns_left` (see `Solved`).
    pub turns_left: u16,
    /// The root's cost (see `Solved`).
    pub cost: u64,
    /// The root's distribution (its best option's), from a distribution solve.
    pub dist: Option<Distribution>,
}

/// The same solve fills the table, and offers it to the store, in the same
/// order every time. Keyed by the state's codec bytes (about 70 bytes, not
/// the state's ~800): equal bytes mean equal states, and the table is most
/// of a solve's memory.
type Table = HashMap<Vec<u8>, Entry, BuildHasherDefault<DefaultHasher>>;

struct Entry {
    solved: Solved,
    /// Came from the store, so it isn't offered back.
    hit: bool,
}

/// A state being solved: its children and what is folded in so far.
/// States are held as codec bytes: a stalling line (the player can block
/// forever) runs the stack as deep as the budget, and full states there
/// took several GB at 1M nodes.
struct Frame {
    /// The state's codec bytes, and its turn.
    key: Vec<u8>,
    turn: u16,
    /// Children not yet folded in (codec bytes), with their probabilities
    /// (1 at decisions), last first so they are taken in listed order.
    kids: Vec<(f64, Vec<u8>)>,
    chance: bool,
    /// Best child value so far at decisions, the weighted sum at chance.
    acc: f64,
    /// The same for distributions: the first best child's, or the weighted
    /// sum (only in a distribution solve).
    dist: Option<Distribution>,
    /// The first best child's turns left at decisions, the most at chance,
    /// counted from this frame's turn.
    turns: u16,
    /// This frame's probability in its parent's sum.
    weight: f64,
    /// `nodes` when it was opened, and the costliest child's cost so far,
    /// for its cost.
    nodes_start: u64,
    sub: u64,
    /// The state's `upper_bound` at a decision in a bounded solve (else
    /// infinite): once `acc` reaches it, the remaining children are skipped.
    bound: f64,
}

/// A known value, with its distribution in a distribution solve, its turns
/// left and its cost.
type Known = (f64, Option<Distribution>, u16, u64);

/// Past the budget, or a line that leaves the state's representable range.
struct Unsolvable;

/// Most copies of one card in one pile, of cards played in a turn, and of
/// turns, that a state may hold before it is expanded. Stalling lines (cards
/// added every turn, no turn limit) grow piles without end, and the state's
/// counters would wrap and give a wrong value; under these bounds no merge
/// of piles or single action can reach their limits. A real game never comes
/// near them, so only endless lines are cut, and those are never solvable.
const PILE_COPIES: u8 = 60;
const PLAYS_PER_TURN: u8 = 200;
const TURNS: u16 = 60_000;

/// Equal options' values can differ by rounding (chance probabilities that
/// sum to 1 only within rounding). The value is the plain maximum, but the
/// distribution and turns left come from the first option within `TIE` of
/// the best so far, so rounding noise doesn't pick a different line.
const TIE: f64 = 1e-12;

fn representable(s: &CombatState) -> bool {
    let piles = s.all_piles();
    piles.iter().all(|p| p.iter().all(|(_, n)| n < PILE_COPIES))
        && s.cards_played_this_turn < PLAYS_PER_TURN
        && s.turn < TURNS
        && s.created < TURNS
        && s.removed < TURNS
}

struct Solver<'a> {
    max_nodes: u64,
    distribution: bool,
    /// `SolveConfig::bounds`, off in a distribution solve.
    bounds: bool,
    store: Option<&'a mut dyn SolvedStore>,
    table: Table,
    nodes: u64,
    hits: u64,
    /// Children listed so far.
    touches: u64,
}

impl Solver<'_> {
    fn charge(&self) -> Result<(), Unsolvable> {
        if self.nodes + self.hits >= self.max_nodes {
            Err(Unsolvable)
        } else {
            Ok(())
        }
    }

    /// The value (and distribution, in a distribution solve) of `s` without
    /// expanding it, if it is known.
    fn known(&mut self, s: &CombatState, key: &[u8]) -> Result<Option<Known>, Unsolvable> {
        if s.is_over() {
            return Ok(Some((s.score(), self.distribution.then(|| Distribution::terminal(s)), 0, 0)));
        }
        if let Some(e) = self.table.get(key) {
            return Ok(Some((e.solved.value, e.solved.dist.clone(), e.solved.turns_left, e.solved.cost)));
        }
        let Some(store) = self.store.as_mut() else { return Ok(None) };
        let Some(solved) = store.lookup(s) else { return Ok(None) };
        // A value-only entry can't answer a distribution solve: the state is
        // solved again, and the store is offered the upgraded entry.
        if self.distribution && solved.dist.is_none() {
            return Ok(None);
        }
        self.charge()?;
        self.hits += 1;
        let known = (solved.value, solved.dist.clone(), solved.turns_left, solved.cost);
        // The table needs no options.
        let solved = Solved { options: None, ..solved };
        self.table.insert(key.to_vec(), Entry { solved, hit: true });
        Ok(Some(known))
    }

    fn open(&mut self, state: CombatState, key: Vec<u8>, weight: f64) -> Result<Frame, Unsolvable> {
        self.charge()?;
        if !representable(&state) {
            return Err(Unsolvable);
        }
        let nodes_start = self.nodes;
        self.nodes += 1;
        let room = self.max_nodes.saturating_mul(TOUCHES_PER_NODE).saturating_sub(self.touches);
        let (kids, chance) = if state.pending.is_some() {
            match state.chance_outcomes(usize::try_from(room).unwrap_or(usize::MAX)) {
                Some(ChanceOutcomes::Listed(v)) => (v, true),
                _ => return Err(Unsolvable),
            }
        } else {
            let mut kids: Vec<(f64, CombatState)> = Vec::new();
            for a in state.legal_actions() {
                let mut t = state.clone();
                t.apply_action(a).expect("legal action applies");
                if !kids.iter().any(|(_, k)| *k == t) {
                    kids.push((1.0, t));
                }
            }
            (kids, false)
        };
        if kids.len() as u64 > room {
            return Err(Unsolvable);
        }
        self.touches += kids.len() as u64;
        let bounded = self.bounds && !chance;
        let mut kids: Vec<(f64, Vec<u8>)> = if bounded {
            // Finished children first (they cost nothing and may reach the bound).
            let (over, rest): (Vec<_>, Vec<_>) = kids.into_iter().partition(|(_, k)| k.is_over());
            over.into_iter().chain(rest).map(|(p, k)| (p, encode(&k))).collect()
        } else {
            kids.into_iter().map(|(p, k)| (p, encode(&k))).collect()
        };
        kids.reverse();
        let bound = if bounded { state.upper_bound() } else { f64::INFINITY };
        let acc = if chance { 0.0 } else { f64::NEG_INFINITY };
        let dist = (chance && self.distribution).then(Distribution::default);
        Ok(Frame { key, turn: state.turn, kids, chance, acc, dist, turns: 0, weight, nodes_start, sub: 0, bound })
    }

    /// The exact value (and distribution) of `s`, solving whatever it needs.
    fn value(&mut self, s: CombatState) -> Result<Known, Unsolvable> {
        let key = encode(&s);
        if let Some(k) = self.known(&s, &key)? {
            return Ok(k);
        }
        let mut stack = vec![self.open(s, key, 1.0)?];
        loop {
            let top = stack.last_mut().unwrap();
            let (p, (v, d, tl, c), kid_turn) = if let Some((p, key)) = top.kids.pop() {
                let kid = decode(&key);
                match self.known(&kid, &key)? {
                    Some(k) => (p, k, kid.turn),
                    None => {
                        if self.bounds && !top.chance && kid.upper_bound() <= top.acc + TIE {
                            continue; // can't beat the best so far
                        }
                        let f = self.open(kid, key, p)?;
                        stack.push(f);
                        continue;
                    }
                }
            } else {
                let f = stack.pop().unwrap();
                let cost = (self.nodes - f.nodes_start).max(f.sub.saturating_add(1));
                let solved = Solved {
                    value: f.acc,
                    cost,
                    turns_left: f.turns,
                    dist: f.dist.clone(),
                    options: None,
                };
                let turn = f.turn;
                self.table.insert(f.key, Entry { solved, hit: false });
                if stack.is_empty() {
                    return Ok((f.acc, f.dist, f.turns, cost));
                }
                (f.weight, (f.acc, f.dist, f.turns, cost), turn)
            };
            let top = stack.last_mut().unwrap();
            top.sub = top.sub.max(c);
            let turns = tl + (kid_turn - top.turn);
            if top.chance {
                top.acc += p * v;
                if let (Some(acc), Some(d)) = (top.dist.as_mut(), d.as_ref()) {
                    acc.add_scaled(d, p);
                }
                top.turns = top.turns.max(turns);
            } else if v > top.acc + TIE {
                // Ties keep the first best, as search does.
                top.acc = v;
                top.dist = d;
                top.turns = turns;
            } else if v > top.acc {
                top.acc = v;
            }
            if !top.chance && top.acc >= top.bound - TIE {
                top.kids.clear(); // the best possible is reached
            }
        }
    }

    /// The options of a decision whose children are all solved.
    fn options(&self, s: &CombatState) -> Vec<SolvedOption> {
        group_options(s)
            .into_iter()
            .map(|(after, actions)| {
                if after.is_over() {
                    let dist = self.distribution.then(|| Distribution::terminal(&after));
                    return SolvedOption { actions, value: after.score(), dist, bounded: false };
                }
                match self.table.get(&encode(&after)) {
                    Some(e) => SolvedOption { actions, value: e.solved.value, dist: e.solved.dist.clone(), bounded: false },
                    // Skipped by a bounded solve.
                    None => SolvedOption { actions, value: after.upper_bound(), dist: None, bounded: true },
                }
            })
            .collect()
    }

    /// Offers every state solved here (not the store's own) to the store,
    /// decisions it keeps with their options.
    fn offer(&mut self) {
        if self.store.is_none() {
            return;
        }
        for (bytes, e) in &self.table {
            let store = self.store.as_mut().unwrap();
            // An entry the store won't keep isn't rebuilt to be offered.
            if e.hit || !store.keeps(&e.solved) {
                continue;
            }
            let s = decode(bytes);
            if s.awaiting_action() {
                let solved = Solved { options: Some(self.options(&s)), ..e.solved.clone() };
                self.store.as_mut().unwrap().insert(&s, &solved);
            } else {
                store.insert(&s, &e.solved);
            }
        }
        self.store.as_mut().unwrap().end_solve();
    }
}

/// Solves a state awaiting an action. `None` when it needs more than
/// `cfg.max_nodes`. Every state finished before that is still offered to
/// the store, since those values are exact.
pub fn solve(root: &CombatState, cfg: &SolveConfig, mut store: Option<&mut dyn SolvedStore>) -> Option<Solution> {
    assert!(root.awaiting_action(), "solve needs a state awaiting an action");
    // A stored decision answers as a root, for one node of the budget.
    if let Some(e) = store.as_mut().and_then(|st| st.lookup(root)) {
        if let Some(options) = e.options {
            // An unbounded solve wants every option exact.
            let exact = cfg.bounds || options.iter().all(|o| !o.bounded);
            if cfg.max_nodes > 0 && exact && (!cfg.distribution || options.iter().all(|o| o.dist.is_some())) {
                return Some(Solution { options, nodes: 0, hits: 1, touches: 0, turns_left: e.turns_left, cost: e.cost, dist: e.dist });
            }
        }
    }
    let bounds = cfg.bounds && !cfg.distribution;
    let mut solver = Solver {
        max_nodes: cfg.max_nodes,
        distribution: cfg.distribution,
        bounds,
        store,
        table: Table::default(),
        nodes: 0,
        hits: 0,
        touches: 0,
    };
    let result = solve_root(&mut solver, root);
    solver.offer();
    let root = result.ok()?;
    Some(Solution {
        options: root.options.unwrap(),
        nodes: solver.nodes,
        hits: solver.hits,
        touches: solver.touches,
        turns_left: root.turns_left,
        cost: root.cost,
        dist: root.dist,
    })
}

/// Options at a decision: distinct afterstates in `legal_actions` order,
/// each with all its actions, exactly as `search` groups them.
pub fn group_options(s: &CombatState) -> Vec<(CombatState, Vec<Action>)> {
    let mut opts: Vec<(CombatState, Vec<Action>)> = Vec::new();
    for a in s.legal_actions() {
        let mut after = s.clone();
        after.apply_action(a).expect("legal action applies");
        match opts.iter_mut().find(|(t, _)| *t == after) {
            Some((_, acts)) => acts.push(a),
            None => opts.push((after, vec![a])),
        }
    }
    opts
}

/// The root's entry, with its options.
fn solve_root(solver: &mut Solver, root: &CombatState) -> Result<Solved, Unsolvable> {
    // The root counts as one expansion.
    solver.charge()?;
    if !representable(root) {
        return Err(Unsolvable);
    }
    solver.nodes += 1;
    let opts = group_options(root);
    let bound = if solver.bounds { root.upper_bound() } else { f64::INFINITY };
    let mut order: Vec<usize> = (0..opts.len()).collect();
    if solver.bounds {
        // Finished options first, as at every decision; reported in listed order.
        order.sort_by_key(|&i| !opts[i].0.is_over());
    }
    let mut slots: Vec<Option<SolvedOption>> = vec![None; opts.len()];
    let mut opts: Vec<Option<(CombatState, Vec<Action>)>> = opts.into_iter().map(Some).collect();
    let mut best = f64::NEG_INFINITY;
    let mut best_dist = None;
    let mut best_turns = 0;
    let mut sub = 0;
    for i in order {
        let (after, actions) = opts[i].take().expect("each option once");
        // A finished option's value is exact and costs nothing.
        if solver.bounds && !after.is_over() && (best >= bound - TIE || after.upper_bound() <= best + TIE) {
            let value = after.upper_bound();
            slots[i] = Some(SolvedOption { actions, value, dist: None, bounded: true });
            continue;
        }
        let turn = after.turn;
        let (value, dist, tl, c) = solver.value(after)?;
        sub = sub.max(c);
        if value > best + TIE {
            best = value;
            best_dist = dist.clone();
            best_turns = tl + (turn - root.turn);
        } else if value > best {
            best = value;
        }
        slots[i] = Some(SolvedOption { actions, value, dist, bounded: false });
    }
    let out: Vec<SolvedOption> = slots.into_iter().map(|o| o.expect("every option filled")).collect();
    let solved = Solved { value: best, cost: solver.nodes.max(sub.saturating_add(1)), turns_left: best_turns, dist: best_dist, options: None };
    solver.table.insert(encode(root), Entry { solved: solved.clone(), hit: false });
    Ok(Solved { options: Some(out), ..solved })
}
