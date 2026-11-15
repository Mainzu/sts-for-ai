//! Where a two-turn decision's time goes, by phase. Rebuilds `search`'s tree
//! (same rules as `search::Tree`, heuristic leaves) with a timer around each
//! step, on states from heuristic play of elite and boss fights.
//! `cargo run --release --example two_turn_phases [states] [--check <file>]`
//! `--check` writes each search's result (nodes, leaves, cuts, action, option
//! values' bits; two-turn, then one-turn) to `<file>`, for comparing two
//! builds. `--parts` splits the heuristic leaf time into `damage_rate`,
//! `hook_rates` and a state clone. `--census` counts what the searched
//! states hold (distinct card ids per pile, non-zero powers per creature),
//! the sizes a sparse state (runtime-registry stage 5) would need.

use std::collections::HashMap;
use std::time::Instant;

use sts_engine::agent::SearchAgent;
use sts_engine::chance::ChanceOutcomes;
use sts_engine::monsters::EncounterGroup;
use sts_engine::runner::{group_specs, play};
use sts_engine::search::{sample_rng, search, Evaluator, Heuristic, SearchConfig};
use sts_engine::{Action, CombatState};

/// Scores every leaf 1.0: times the tree alone.
struct Flat;

impl Evaluator for Flat {
    fn evaluate(&mut self, states: &[CombatState]) -> Vec<f32> {
        vec![1.0; states.len()]
    }
}

#[derive(Default)]
struct Clock {
    memo: f64,
    clone: f64,
    legal: f64,
    apply: f64,
    chance: f64,
    resolve: f64,
    leaf: f64,
    memo_insert: f64,
    eval: f64,
    nodes: usize,
    leaves: usize,
    actions: usize,
}

struct Tree<'a> {
    cfg: &'a SearchConfig,
    nodes: usize,
    memo: Vec<HashMap<CombatState, usize>>,
    leaves: Vec<CombatState>,
    leaf_index: HashMap<CombatState, usize>,
    c: Clock,
}

fn secs(t: Instant) -> f64 {
    t.elapsed().as_secs_f64()
}

impl Tree<'_> {
    fn leaf(&mut self, s: CombatState) -> usize {
        let t = Instant::now();
        if !s.is_over() && !self.leaf_index.contains_key(&s) {
            self.leaves.push(s.clone());
            self.leaf_index.insert(s, self.leaves.len() - 1);
        }
        self.c.leaf += secs(t);
        self.nodes += 1;
        self.nodes
    }

    fn child(&mut self, a: Action, after: CombatState, turns: u8, ord: u32) -> usize {
        if a != Action::EndTurn {
            self.expand(after, turns, ord)
        } else if turns > 1 && self.cfg.sample_k > 0 {
            self.expand(after, turns - 1, 0)
        } else {
            self.leaf(after)
        }
    }

    fn expand(&mut self, s: CombatState, turns: u8, ord: u32) -> usize {
        let t = Instant::now();
        let hit = self.memo[turns as usize].get(&s).copied();
        self.c.memo += secs(t);
        if let Some(id) = hit {
            return id;
        }
        let id = if s.is_over() || self.nodes >= self.cfg.max_nodes {
            self.leaf(s.clone())
        } else if s.pending.is_some() {
            let t = Instant::now();
            let outcomes = s.chance_outcomes(self.cfg.limit);
            self.c.chance += secs(t);
            match outcomes {
                Some(ChanceOutcomes::Listed(v)) => {
                    for (_, t) in v {
                        self.expand(t, turns, ord);
                    }
                }
                _ if self.cfg.sample_k > 0 => {
                    for i in 0..self.cfg.sample_k {
                        let t0 = Instant::now();
                        let mut t = s.clone();
                        self.c.clone += secs(t0);
                        let t0 = Instant::now();
                        t.resolve_chance(&mut sample_rng(self.cfg.seed, turns, s.turn, ord, i));
                        self.c.resolve += secs(t0);
                        self.expand(t, turns, ord + 1);
                    }
                }
                _ => {
                    self.leaf(s.clone());
                }
            }
            self.nodes += 1;
            self.nodes
        } else {
            let t = Instant::now();
            let acts = s.legal_actions();
            self.c.legal += secs(t);
            for a in acts {
                self.c.actions += 1;
                let t0 = Instant::now();
                let mut t = s.clone();
                self.c.clone += secs(t0);
                let t0 = Instant::now();
                t.apply_action(a).expect("legal action applies");
                self.c.apply += secs(t0);
                self.child(a, t, turns, ord);
            }
            self.nodes += 1;
            self.nodes
        };
        let t = Instant::now();
        self.memo[turns as usize].insert(s, id);
        self.c.memo_insert += secs(t);
        id
    }
}

/// Distribution of one count over the census states.
#[derive(Default)]
struct Dist(Vec<u32>);

impl Dist {
    fn line(&mut self, name: &str) {
        let v = &mut self.0;
        v.sort_unstable();
        let q = |f: f64| v[((v.len() - 1) as f64 * f) as usize];
        let mean = v.iter().map(|&x| x as f64).sum::<f64>() / v.len() as f64;
        println!("  {name:<34} mean {mean:>5.2}  p50 {:>3}  p99 {:>3}  p99.9 {:>3}  max {:>3}", q(0.5), q(0.99), q(0.999), q(1.0));
    }
}

/// What the searched states hold: per pile, distinct card ids; per
/// creature, non-zero powers.
#[derive(Default)]
struct Census {
    piles: [Dist; 4],
    all_ids: Dist,
    cards: Dist,
    player_pw: Dist,
    monster_pw: Dist,
    slots: Dist,
    all_pw: Dist,
}

impl Census {
    fn add(&mut self, s: &CombatState) {
        use sts_engine::powers::{Power, Powers};
        let ps = s.all_piles();
        for (d, p) in self.piles.iter_mut().zip(ps) {
            d.0.push(p.iter().count() as u32);
        }
        self.all_ids.0.push(ps.iter().map(|p| p.iter().count() as u32).sum());
        self.cards.0.push(ps.iter().map(|p| p.len() as u32).sum());
        let nz = |pw: &Powers| Power::ALL_WITH_SLOTS.iter().filter(|&&p| pw.get(p) != 0).count() as u32;
        let mut total = nz(&s.player.powers);
        self.player_pw.0.push(total);
        let used: Vec<_> = s.monsters.iter().filter(|m| m.max_hp > 0).collect();
        self.slots.0.push(used.len() as u32);
        for m in used {
            let n = nz(&m.powers);
            self.monster_pw.0.push(n);
            total += n;
        }
        self.all_pw.0.push(total);
    }

    fn report(mut self) {
        use std::mem::size_of;
        use sts_engine::{monsters::Monster, powers::Powers, state::Pile};
        println!("census over {} searched states ({} bytes each now)", self.cards.0.len(), size_of::<CombatState>());
        println!("  bytes now: 4 piles {}, 6 power blocks {}, one monster {}, card ids {}", 4 * size_of::<Pile>(), 6 * size_of::<Powers>(), size_of::<Monster>(), sts_engine::cards::NUM_CARDS);
        for (d, name) in self.piles.iter_mut().zip(["hand", "draw", "discard", "exhaust"]) {
            d.line(&format!("distinct ids in {name}"));
        }
        self.all_ids.line("distinct ids, 4 piles summed");
        self.cards.line("cards, 4 piles summed");
        self.player_pw.line("non-zero player powers");
        self.monster_pw.line("non-zero powers per used monster");
        self.slots.line("monster slots used");
        self.all_pw.line("non-zero powers, all creatures");
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let want: usize = args.get(1).and_then(|a| a.parse().ok()).unwrap_or(150);
    let check = args.iter().position(|a| a == "--check").map(|i| args[i + 1].clone());
    let mut dump = String::new();
    let cfg = SearchConfig { turns: 2, sample_k: 4, max_nodes: 400_000, ..SearchConfig::default() };
    // States from one-turn heuristic play: every 3rd decision of each fight.
    let mut states = Vec::new();
    for g in [EncounterGroup::Elite, EncounterGroup::Boss] {
        for spec in group_specs(g, 40, 5, 7) {
            let mut agent = SearchAgent::new(Heuristic, SearchConfig::default());
            let r = play(&spec, &mut agent, true);
            states.extend(r.trajectory.into_iter().step_by(3).map(|(s, _)| s));
        }
    }
    let step = (states.len() / want).max(1);
    let states: Vec<CombatState> = states.into_iter().step_by(step).take(want).collect();
    println!("{} states, {} bytes each", states.len(), std::mem::size_of::<CombatState>());

    let parts_flag = args.iter().any(|a| a == "--parts");
    let census_flag = args.iter().any(|a| a == "--census");
    let mut census = Census::default();
    let mut leaf_parts = [0f64; 3];
    let mut total = Clock::default();
    let (mut whole, mut real, mut flat) = (0.0, 0.0, 0.0);
    for (k, s) in states.iter().enumerate() {
        let cfg = SearchConfig { seed: k as u64, ..cfg.clone() };
        let t = Instant::now();
        let r = search(s, &mut Heuristic, &cfg);
        real += secs(t);
        let t = Instant::now();
        std::hint::black_box(search(s, &mut Flat, &cfg));
        flat += secs(t);
        let values: Vec<u32> = r.options.iter().map(|o| o.value.to_bits()).collect();
        dump += &format!("{k} {} {} {} {:?} {values:?}
", r.nodes, r.leaves, r.cuts, r.action);
        if check.is_some() {
            let one = search(s, &mut Heuristic, &SearchConfig { seed: k as u64, ..SearchConfig::default() });
            let values: Vec<u32> = one.options.iter().map(|o| o.value.to_bits()).collect();
            dump += &format!("{k} one {} {:?} {values:?}
", one.nodes, one.action);
        }
        let t = Instant::now();
        let mut tree = Tree { cfg: &cfg, nodes: 0, memo: (0..=2).map(|_| HashMap::new()).collect(), leaves: Vec::new(), leaf_index: HashMap::new(), c: Clock::default() };
        for a in s.legal_actions() {
            let mut after = s.clone();
            after.apply_action(a).unwrap();
            tree.child(a, after, 2, 0);
        }
        let t0 = Instant::now();
        let v = Heuristic.evaluate(&tree.leaves);
        tree.c.eval += secs(t0);
        std::hint::black_box(v);
        if parts_flag {
            let t0 = Instant::now();
            for l in &tree.leaves {
                for slot in l.living_slots() {
                    std::hint::black_box(sts_engine::heuristic::damage_rate(l, slot));
                }
            }
            leaf_parts[0] += secs(t0);
            let t0 = Instant::now();
            for l in &tree.leaves {
                std::hint::black_box(sts_engine::agent::hook_rates(&l.player.powers, &l.binding));
                for slot in l.living_slots() {
                    std::hint::black_box(sts_engine::agent::hook_rates(&l.monsters[slot].powers, &l.binding));
                }
            }
            leaf_parts[1] += secs(t0);
            let t0 = Instant::now();
            for l in &tree.leaves {
                std::hint::black_box(l.clone());
            }
            leaf_parts[2] += secs(t0);
        }
        if census_flag {
            tree.memo.iter().flat_map(|m| m.keys()).chain(&tree.leaves).for_each(|s| census.add(s));
        }
        let t0 = Instant::now();
        drop(tree.memo);
        drop(tree.leaf_index);
        let freed = secs(t0);
        whole += secs(t);
        let c = tree.c;
        total.memo += c.memo;
        total.clone += c.clone;
        total.legal += c.legal;
        total.apply += c.apply;
        total.chance += c.chance;
        total.resolve += c.resolve;
        total.leaf += c.leaf;
        total.memo_insert += c.memo_insert + freed;
        total.eval += c.eval;
        total.nodes += r.nodes;
        total.leaves += r.leaves;
        total.actions += c.actions;
    }
    let parts = [
        ("memo lookup (hash + compare)", total.memo),
        ("memo insert + free maps", total.memo_insert),
        ("state clone", total.clone),
        ("legal_actions", total.legal),
        ("apply_action", total.apply),
        ("chance_outcomes (listing)", total.chance),
        ("resolve_chance (sampling)", total.resolve),
        ("leaf store (hash + clone)", total.leaf),
        ("heuristic leaf eval", total.eval),
    ];
    if let Some(path) = check {
        std::fs::write(&path, &dump).expect("write the check file");
        println!("wrote {path}");
    }
    let sum: f64 = parts.iter().map(|p| p.1).sum();
    println!("tree alone (flat leaves) {flat:.2} s, {:.1} us per node", flat / total.nodes as f64 * 1e6);
    println!("real search {real:.2} s; instrumented {whole:.2} s, timed parts {sum:.2} s");
    println!("{} nodes, {} leaves, {} actions applied; {:.1} us per node (real)", total.nodes, total.leaves, total.actions, real / total.nodes as f64 * 1e6);
    for (name, t) in parts {
        println!("{:>5.1}%  {:>7.3} s  {name}", 100.0 * t / whole, t);
    }
    if census_flag {
        census.report();
    }
    if parts_flag {
        let e = total.eval;
        for (name, t) in [("damage_rate (all living)", leaf_parts[0]), ("hook_rates (player + living)", leaf_parts[1]), ("one state clone", leaf_parts[2])] {
            println!("  leaf eval part: {:>5.1}% of eval  {:>7.3} s  {name}", 100.0 * t / e, t);
        }
    }
}
