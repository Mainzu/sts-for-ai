//! Search over the current turn: depth-limited expectimax.
//!
//! The tree is built first, then every leaf is scored in one evaluator call
//! (so a neural net can score them as a batch), then values are backed up:
//! the best option at decisions, the probability-weighted average at chance
//! nodes. Leaves are EndTurn results and options whose random events are too
//! large to list; finished combats score exactly. Equal states share a node
//! (transpositions), so the tree is a DAG.

use std::collections::HashMap;

use crate::chance::ChanceOutcomes;
use crate::fxhash::FxBuild;
use crate::rng::Rng;
use crate::state::{Action, CombatState, Stage};

pub use crate::heuristic::Heuristic;

/// Scores states on the final-score scale (`CombatState::score`, 0..=2).
pub trait Evaluator {
    /// One estimate per state, in order. Search calls this once per decision
    /// with every leaf it reached.
    fn evaluate(&mut self, states: &[CombatState]) -> Vec<f32>;
}

#[derive(Clone, Debug)]
pub struct SearchConfig {
    /// Random events with more distinct outcomes than this are not listed.
    pub limit: usize,
    /// 0: large events are leaves. k > 0: sample k outcomes there and keep
    /// searching, and look past EndTurn while `turns` allows.
    pub sample_k: u32,
    /// Turns to search, the current one included. More than 1 only takes
    /// effect with `sample_k > 0`.
    pub turns: u8,
    /// Past this many nodes, unexpanded states become leaves; a state at a
    /// pick is still expanded, along its first option only.
    pub max_nodes: usize,
    /// Seeds the sampling at large events (see [`sample_rng`]).
    pub seed: u64,
    /// How finished combats score; it must match the evaluator's scale.
    pub rule: ScoreRule,
    /// The end-HP bonus c (0: off; docs/specs/end-hp-bonus.md): a finished
    /// combat also scores `c x 80 / max HP x clamp(score / 2) x (HP - start
    /// HP)`, HP after the end-of-combat heal, matching the evaluator's leaf
    /// price ([`end_hp_scale`]).
    pub end_hp_price: f32,
    /// The sampled-draw leaf (docs/specs/draw-leaf.md; 0: off). k > 0: a
    /// state after the last searched turn's EndTurn is played on to the
    /// next decision, sampling k outcomes at large events, and scored there.
    pub draw_k: u32,
    /// The turn-start leaf (docs/specs/turn-start-leaf.md; false: off): an
    /// end-of-turn leaf is scored after the player's turn-start hooks that
    /// need no chance (`CombatState::turn_start_leaf`).
    pub turn_start_leaf: bool,
    /// The leaf clear block (docs/specs/leaf-clear-block.md; false: off): an
    /// end-of-turn leaf (plain or turn-start, not the draw leaf) is scored
    /// with the player's block at 0, as the next StartTurn sets it.
    pub leaf_clear_block: bool,
    /// Projected leaf: once-a-turn Strength and Dexterity hooks applied this
    /// many more times at an end-of-turn leaf, after the turn-start leaf
    /// (`CombatState::projected_leaf`, docs/specs/projected-leaf.md); 0 is off.
    pub projected_ticks: u8,
    /// With `projected_ticks`: monsters' once-a-turn Weak, Frail and
    /// Vulnerable on the player are projected too
    /// (docs/specs/recurring-debuff-leaf.md; false: off).
    pub projected_debuffs: bool,
    /// The finish-faster tie break (docs/specs/finish-faster-tiebreak.md;
    /// false: off). Where values are exactly equal, pick the option that
    /// wins sooner inside the horizon, then the one leaving lower enemy HP.
    /// It never changes a value.
    pub tie_break: bool,
}

impl Default for SearchConfig {
    fn default() -> SearchConfig {
        SearchConfig { limit: 16, sample_k: 0, turns: 1, max_nodes: 50_000, seed: 0, rule: ScoreRule::Engine, end_hp_price: 0.0, draw_k: 0, turn_start_leaf: false, leaf_clear_block: false, projected_ticks: 0, projected_debuffs: false, tie_break: false }
    }
}

/// The final-score formula search scores finished combats with.
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub enum ScoreRule {
    /// `CombatState::score`: a win scores 2 - HP lost since the start / 100.
    #[default]
    Engine,
    /// A win scores `c + w x end HP / 100` (HP after the end-of-combat heal),
    /// a loss 0 (docs/specs/survival-score.md).
    Survive { c: f32, w: f32 },
}

impl SearchConfig {
    /// The score of a finished combat `s`: its rule's, plus the end-HP bonus.
    pub fn finished(&self, s: &CombatState) -> f32 {
        let v = self.rule.terminal(s);
        if self.end_hp_price == 0.0 {
            return v;
        }
        v + self.end_hp_price * end_hp_scale(s) * (v / 2.0).clamp(0.0, 1.0) * (s.player.hp - s.start_hp) as f32
    }
}

/// The max HP the end-HP bonus c is quoted at: c prices one HP at this max
/// HP, and one share of the HP bar (an HP of 80ths) at any other.
pub const END_HP_REF_MAX_HP: f32 = 80.0;

/// The end-HP bonus's scale for `s`: `END_HP_REF_MAX_HP / max HP`, so a win
/// stays worth the same share of a full HP bar whatever the max HP (ideas#75;
/// exactly 1 at 80 max HP, where scores are bit-identical to an unscaled c).
pub fn end_hp_scale(s: &CombatState) -> f32 {
    END_HP_REF_MAX_HP / s.player.max_hp.max(1) as f32
}

impl ScoreRule {
    /// The score of a finished combat `s` under this rule.
    pub fn terminal(&self, s: &CombatState) -> f32 {
        match *self {
            ScoreRule::Engine => s.score() as f32,
            ScoreRule::Survive { c, w } => {
                if s.won() {
                    c + w * s.player.hp as f32 / 100.0
                } else {
                    0.0
                }
            }
        }
    }
}

/// One option at the root with its backed-up value.
#[derive(Clone, Debug)]
pub struct OptionScore {
    /// Every action leading to this option, in `legal_actions` order.
    pub actions: Vec<Action>,
    pub value: f32,
}

#[derive(Clone, Debug)]
pub struct SearchResult {
    /// First action of the best option (the first best on ties).
    pub action: Action,
    /// Every distinct option at the root, in `options()` order.
    pub options: Vec<OptionScore>,
    pub nodes: usize,
    /// States passed to the evaluator.
    pub leaves: usize,
    /// States made leaves only because the tree reached `max_nodes`.
    pub cuts: usize,
    /// The principal line (docs/specs/line-step.md): `action`, then the
    /// first best child at each decision below it, up to and including
    /// `EndTurn` or up to the first chance node, cut leaf or scored leaf.
    pub line: Vec<Action>,
}

/// The RNG for sample `i` of the `ord`-th sampled event since the searched
/// turn began (`turns`: turns left to search, `turn`: the state's counter,
/// which monster rolls see before it moves on). Nothing else about the state
/// feeds it, so sibling options meeting the same event see the same luck
/// (common random numbers).
pub fn sample_rng(seed: u64, turns: u8, turn: u16, ord: u32, i: u32) -> Rng {
    let key = (turns as u64) << 56 | (turn as u64) << 40 | (ord as u64) << 20 | i as u64;
    Rng::new(seed.wrapping_mul(0x9e37_79b9_7f4a_7c15) ^ key)
}

/// SipHash over whole states was ~25% of a two-turn decision
/// (decisions "Fast search tables built"). Nothing reads the tables' order,
/// so the hasher can't change results.
fn state_hash(s: &CombatState) -> u64 {
    use std::hash::{BuildHasher, Hash, Hasher};
    let mut h = FxBuild::default().build_hasher();
    s.hash(&mut h);
    h.finish()
}

const NONE: u32 = u32::MAX;

/// Which stored states equal a given one: the states stay where their owner
/// keeps them (a `Vec`, appended to); the table holds only each state's hash
/// and a chain of indices with that hash, so no state is copied into hash
/// buckets or moved when the table grows (most of a two-turn search was
/// moving states into and out of `HashMap` buckets; decisions "Series speed
/// and search identity after specs 2-9").
#[derive(Default)]
struct Index {
    heads: HashMap<u64, u32, FxBuild>,
    next: Vec<u32>,
}

impl Index {
    /// The index of a stored state equal to `s` (hash `h`).
    fn find(&self, states: &[CombatState], s: &CombatState, h: u64) -> Option<usize> {
        let mut i = *self.heads.get(&h)?;
        while i != NONE {
            if states[i as usize] == *s {
                return Some(i as usize);
            }
            i = self.next[i as usize];
        }
        None
    }

    /// Records that `states[i]` (just appended, hash `h`) is stored.
    fn add(&mut self, i: usize, h: u64) {
        debug_assert_eq!(i, self.next.len());
        let prev = self.heads.insert(h, i as u32).unwrap_or(NONE);
        self.next.push(prev);
    }
}

/// Expanded states and their nodes, for one turns-left value.
#[derive(Default)]
struct Memo {
    states: Vec<CombatState>,
    ids: Vec<usize>,
    index: Index,
}

enum Node {
    Exact(f32),
    Leaf(usize),
    /// Children with the action that reached each (the first such action).
    Decision(Vec<(Action, usize)>),
    Chance(Vec<(f32, usize)>),
}

struct Tree<'a> {
    cfg: &'a SearchConfig,
    nodes: Vec<Node>,
    cuts: usize,
    /// Node of each expanded state, one table per turns-left value.
    memo: Vec<Memo>,
    leaves: Vec<CombatState>,
    leaf_index: Index,
    /// With `tie_break`: (node, keys) of each exact node, in creation order.
    exact_keys: Vec<(usize, Keys)>,
    /// The tie keys' finish value of a leaf or a loss: the turn after the horizon.
    horizon: f32,
}

/// Tie keys (docs/specs/finish-faster-tiebreak.md): the turn a won fight
/// ends (the horizon if it doesn't), then the living monsters' HP; lower
/// is better. Monster block never survives the end-of-turn reset
/// (`CombatState::end_turn` clears it), so HP alone is the second key.
#[derive(Clone, Copy, Default, PartialEq)]
struct Keys {
    finish: f32,
    enemy_hp: f32,
}

fn enemy_hp(s: &CombatState) -> f32 {
    s.monsters.iter().filter(|m| m.alive()).map(|m| m.hp.max(0) as f32).sum()
}

/// Whether (value `v`, keys `k`) beats the best so far (`bv`, `bk`): a
/// higher value, or with `tie` an equal value and lower keys in order.
fn better(v: f32, k: Keys, bv: f32, bk: Keys, tie: bool) -> bool {
    v > bv || (tie && v == bv && (k.finish < bk.finish || (k.finish == bk.finish && k.enemy_hp < bk.enemy_hp)))
}

impl Tree<'_> {
    fn push(&mut self, n: Node) -> usize {
        self.nodes.push(n);
        self.nodes.len() - 1
    }

    fn leaf(&mut self, s: CombatState) -> usize {
        if s.is_over() {
            let id = self.push(Node::Exact(self.cfg.finished(&s)));
            if self.cfg.tie_break {
                let finish = if s.won() { s.turn as f32 } else { self.horizon };
                self.exact_keys.push((id, Keys { finish, enemy_hp: enemy_hp(&s) }));
            }
            return id;
        }
        let h = state_hash(&s);
        let i = match self.leaf_index.find(&self.leaves, &s, h) {
            Some(i) => i,
            None => {
                self.leaves.push(s);
                self.leaf_index.add(self.leaves.len() - 1, h);
                self.leaves.len() - 1
            }
        };
        self.push(Node::Leaf(i))
    }

    /// The node after an action: EndTurn ends the search unless sampling
    /// may look into the next turn, or the draw leaf plays on to the next
    /// decision (turns left 0). `ord`: sampled events so far this turn.
    fn child(&mut self, a: Action, after: CombatState, turns: u8, ord: u32) -> usize {
        if a != Action::EndTurn {
            self.expand(after, turns, ord)
        } else if turns > 1 && self.cfg.sample_k > 0 {
            self.expand(after, turns - 1, 0)
        } else if self.cfg.draw_k > 0 {
            self.expand(after, 0, 0)
        } else {
            let mut after = after;
            // End Turn paused for owed random work (blocked-relics spec
            // step 5): sampled with this turn's luck until the monsters
            // have acted, so the leaf stands where it does without it.
            let mut i = 0;
            while matches!(after.stage, Stage::EndingTurn { .. } | Stage::MonsterActing { .. }) && after.pending.is_some() {
                after.resolve_chance(&mut sample_rng(self.cfg.seed, turns, after.turn, ord, u32::MAX - i));
                i += 1;
            }
            // The turn's reset clears it as the monster rolls finish; past
            // that (draw pending, or the next decision), the block is the
            // new turn's own (pre-draw hooks').
            if self.cfg.leaf_clear_block && !after.is_over() && !matches!(after.stage, Stage::StartTurn | Stage::TurnStarted | Stage::PlayerTurn | Stage::RelicPick { .. } | Stage::RelicOffer { .. } | Stage::EndingTurn { .. }) {
                after.player.block = after.block_after_turn_start();
            }
            let t = if self.cfg.turn_start_leaf { after.turn_start_leaf().unwrap_or(after) } else { after };
            if self.cfg.projected_ticks > 0 {
                let p = t.projected_leaf_with(self.cfg.projected_ticks, self.cfg.projected_debuffs);
                self.leaf(p)
            } else {
                self.leaf(t)
            }
        }
    }

    fn expand(&mut self, s: CombatState, turns: u8, ord: u32) -> usize {
        let h = state_hash(&s);
        let m = &self.memo[turns as usize];
        if let Some(i) = m.index.find(&m.states, &s, h) {
            return m.ids[i];
        }
        let id = if s.is_over() {
            self.leaf(s.clone())
        } else if self.nodes.len() >= self.cfg.max_nodes && s.pick().is_none() {
            // A pick is never a leaf; past the cap it is expanded along its
            // first option only (draw-knowledge item 4).
            self.cuts += 1;
            self.leaf(s.clone())
        } else if turns == 0 && s.awaiting_action() && s.pick().is_none() {
            self.leaf(s.clone())
        } else if s.pending.is_some() {
            let k = if turns == 0 { self.cfg.draw_k } else { self.cfg.sample_k };
            match s.chance_outcomes(self.cfg.limit) {
                Some(ChanceOutcomes::Listed(v)) => {
                    let ch = v.into_iter().map(|(p, t)| (p as f32, self.expand(t, turns, ord))).collect();
                    self.push(Node::Chance(ch))
                }
                _ if k > 0 => {
                    let ch = (0..k)
                        .map(|i| {
                            let mut t = s.clone();
                            t.resolve_chance(&mut sample_rng(self.cfg.seed, turns, s.turn, ord, i));
                            (1.0 / k as f32, self.expand(t, turns, ord + 1))
                        })
                        .collect();
                    self.push(Node::Chance(ch))
                }
                _ => self.leaf(s.clone()),
            }
        } else {
            let mut children: Vec<(Action, usize)> = Vec::new();
            // Past the cap only picks get here, and a pick always has an action.
            let past_cap = self.nodes.len() >= self.cfg.max_nodes;
            for a in s.legal_actions().into_iter().take(if past_cap { 1 } else { usize::MAX }) {
                let mut t = s.clone();
                t.apply_action(a).expect("legal action applies");
                let c = self.child(a, t, turns, ord);
                if !children.iter().any(|&(_, i)| i == c) {
                    children.push((a, c));
                }
            }
            self.push(Node::Decision(children))
        };
        let m = &mut self.memo[turns as usize];
        m.states.push(s);
        m.ids.push(id);
        m.index.add(m.states.len() - 1, h);
        id
    }
}

/// Searches from a state awaiting an action.
pub fn search(root: &CombatState, eval: &mut dyn Evaluator, cfg: &SearchConfig) -> SearchResult {
    assert!(root.awaiting_action(), "search needs a state awaiting an action");
    let turns = cfg.turns.max(1);
    let mut tree = Tree {
        cfg,
        nodes: Vec::new(),
        cuts: 0,
        memo: (0..=turns).map(|_| Memo::default()).collect(),
        leaves: Vec::new(),
        leaf_index: Index::default(),
        exact_keys: Vec::new(),
        horizon: root.turn as f32 + turns as f32,
    };
    // Root options, merged by afterstate exactly as `options()` does.
    let mut root_opts: Vec<(CombatState, Vec<Action>, usize)> = Vec::new();
    for a in root.legal_actions() {
        let mut after = root.clone();
        after.apply_action(a).expect("legal action applies");
        if let Some((_, acts, _)) = root_opts.iter_mut().find(|(s, _, _)| *s == after) {
            acts.push(a);
            continue;
        }
        let c = tree.child(a, after.clone(), turns, 0);
        root_opts.push((after, vec![a], c));
    }

    let leaf_values = eval.evaluate(&tree.leaves);
    assert_eq!(leaf_values.len(), tree.leaves.len(), "evaluator returned the wrong number of values");
    // Children are pushed before their parents, so one pass in order works.
    let mut values = vec![0f32; tree.nodes.len()];
    let tie = cfg.tie_break;
    // Tie keys back up with the values; all default (equal) with it off.
    let mut keys = vec![Keys::default(); if tie { tree.nodes.len() } else { 0 }];
    let key = |keys: &[Keys], i: usize| if tie { keys[i] } else { Keys::default() };
    if tie {
        for &(i, k) in &tree.exact_keys {
            keys[i] = k;
        }
    }
    for (i, n) in tree.nodes.iter().enumerate() {
        values[i] = match n {
            Node::Exact(v) => *v,
            Node::Leaf(j) => leaf_values[*j],
            Node::Decision(ch) => ch.iter().map(|&(_, c)| values[c]).fold(f32::MIN, f32::max),
            Node::Chance(ch) => ch.iter().map(|&(p, c)| p * values[c]).sum(),
        };
        if tie {
            keys[i] = match n {
                Node::Exact(_) => keys[i],
                Node::Leaf(j) => Keys { finish: tree.horizon, enemy_hp: enemy_hp(&tree.leaves[*j]) },
                Node::Decision(ch) => {
                    let mut b = ch[0].1;
                    for &(_, c) in &ch[1..] {
                        if better(values[c], keys[c], values[b], keys[b], true) {
                            b = c;
                        }
                    }
                    keys[b]
                }
                Node::Chance(ch) => ch.iter().fold(Keys::default(), |a, &(p, c)| Keys {
                    finish: a.finish + p * keys[c].finish,
                    enemy_hp: a.enemy_hp + p * keys[c].enemy_hp,
                }),
            };
        }
    }

    let children: Vec<usize> = root_opts.iter().map(|&(_, _, c)| c).collect();
    let options: Vec<OptionScore> =
        root_opts.into_iter().map(|(_, actions, c)| OptionScore { actions, value: values[c] }).collect();
    let mut best = 0;
    for (i, o) in options.iter().enumerate() {
        if better(o.value, key(&keys, children[i]), options[best].value, key(&keys, children[best]), tie) {
            best = i;
        }
    }
    let best_child = children[best];
    // The principal line: the best root option's first action, then the
    // first best child at every decision below it; it stops after EndTurn
    // and at any node that is not a decision (chance, leaf, exact).
    let mut line = vec![options[best].actions[0]];
    let mut node = best_child;
    while line.last() != Some(&Action::EndTurn) {
        let Node::Decision(ch) = &tree.nodes[node] else { break };
        let mut pick = 0;
        for (i, &(_, c)) in ch.iter().enumerate() {
            if better(values[c], key(&keys, c), values[ch[pick].1], key(&keys, ch[pick].1), tie) {
                pick = i;
            }
        }
        line.push(ch[pick].0);
        node = ch[pick].1;
    }
    SearchResult { action: options[best].actions[0], options, nodes: tree.nodes.len(), leaves: tree.leaves.len(), cuts: tree.cuts, line }
}
