//! Running many seeded combats for an agent, across threads.

use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Mutex;

use crate::agent::Agent;
use crate::cards::{deck_cards, CardId};
use crate::character::Character;
use crate::monsters::{Encounter, EncounterGroup};
use crate::registry::Binding;
use crate::potions::PotionSpec;
use crate::relics::RelicSpec;
use crate::chance::ChanceOutcomes;
use crate::rng::Rng;
use crate::search::{Evaluator, OptionScore};
use crate::state::{Action, CombatState};

pub const START_HP: i16 = 80;
/// A combat still running after this many turns ends as a loss: an agent
/// that blocks every hit and never attacks would otherwise play forever
/// (normal play has no turn limit).
pub const PLAY_TURN_LIMIT: u16 = 100;

/// One combat to play.
#[derive(Clone, Debug)]
pub struct GameSpec {
    pub character: Character,
    pub encounter: Encounter,
    pub deck: Vec<CardId>,
    pub seed: u64,
    pub hp: i16,
    pub max_hp: i16,
    /// Play in no-death mode (`CombatState::no_death`).
    pub no_death: bool,
    /// Generated content in `deck` (`registry::bind`); empty for official decks.
    pub binding: Binding,
    /// Relics held, by name (`registry::relics_named`; docs/specs/relics.md);
    /// their pack powers fit `binding`'s free slots (`registry::bind_relics`).
    pub relics: Vec<(String, RelicSpec)>,
    /// Potions held, by name (`registry::potions_named`;
    /// docs/specs/potions.md), given after the fight is built
    /// (`CombatState::give_potions`).
    pub potions: Vec<(String, PotionSpec)>,
    /// Turn 1 like every later turn (`CombatState::new_with_turn1`); off is
    /// the game's turn-1 order.
    pub turn1_pre_draw: bool,
    /// The game's ascension level (docs/specs/ascension.md); 0 for the
    /// engine's usual fight.
    pub ascension: crate::monsters::Ascension,
    /// A burning elite's buff (`CombatState::new_with_turn1`); `None` for
    /// every other fight.
    pub elite_buff: Option<crate::monsters::EliteBuff>,
}

#[derive(Clone, Debug)]
pub struct CombatResult {
    pub won: bool,
    /// HP at the end (Burning Blood's heal included), 0 on a loss (a
    /// combat stopped at `PLAY_TURN_LIMIT` included); in no-death mode the
    /// HP left (may be negative, no heal).
    pub hp_end: i16,
    /// HP the win gave inside `hp_end` (`CombatState::won_healed`: the
    /// `CombatWon` hooks and the win heal, as healed); 0 otherwise.
    pub healed: i16,
    pub hp_start: i16,
    pub turns: u16,
    pub score: f64,
    /// Every decision state and the action taken, when recording.
    pub trajectory: Vec<(CombatState, Action)>,
    /// Per recorded decision, the search's root options and values (empty
    /// for agents that don't search).
    pub option_values: Vec<Vec<OptionScore>>,
    /// Per decision, the luck drawn between its action and the next decision
    /// (`play_luck`; docs/specs/luck-corrected-labels.md); empty otherwise.
    pub luck: Vec<f64>,
}

impl CombatResult {
    pub fn hp_lost(&self) -> i16 {
        self.hp_start - self.hp_end
    }
}

/// `n` combats over `group`'s encounters in turn. Odd-numbered ones use the
/// starter deck plus `extra` random non-status cards. Seeds are
/// `seed * 1_000_003 + i`, so every agent faces the same specs.
pub fn group_specs(group: EncounterGroup, n: usize, extra: usize, seed: u64) -> Vec<GameSpec> {
    let pool: Vec<CardId> = deck_cards().collect();
    group_specs_from(group, n, extra, seed, &pool)
}

/// `group_specs` with the extra cards drawn from `pool`.
pub fn group_specs_from(group: EncounterGroup, n: usize, extra: usize, seed: u64, pool: &[CardId]) -> Vec<GameSpec> {
    group_specs_as(Character::Ironclad, group, n, extra, seed, pool)
}

/// `group_specs_from` for any character: its starter deck and starting HP.
pub fn group_specs_as(character: Character, group: EncounterGroup, n: usize, extra: usize, seed: u64, pool: &[CardId]) -> Vec<GameSpec> {
    let encounters: Vec<Encounter> = Encounter::ALL.into_iter().filter(|e| e.group() == group).collect();
    (0..n)
        .map(|i| {
            let seed = seed.wrapping_mul(1_000_003).wrapping_add(i as u64);
            let mut deck = character.starter_deck();
            if i % 2 == 1 && !pool.is_empty() {
                let mut rng = Rng::new(seed ^ 0xdec0_5eed);
                for _ in 0..extra {
                    deck.push(pool[rng.below(pool.len() as u32) as usize]);
                }
            }
            let hp = character.max_hp();
            GameSpec { character, encounter: encounters[i / 2 % encounters.len()], deck, seed, hp, max_hp: hp, no_death: false, binding: Binding::default(), relics: Vec::new(), potions: Vec::new(), turn1_pre_draw: false, ascension: Default::default(), elite_buff: None }
        })
        .collect()
}

/// Plays one combat. The combat's random events come from the spec's seed;
/// the agent gets an RNG of its own.
pub fn play(spec: &GameSpec, agent: &mut dyn Agent, record: bool) -> CombatResult {
    let mut rng = Rng::new(spec.seed);
    let mut agent_rng = Rng::new(spec.seed ^ 0xa6e7_a6e7);
    let mut s = CombatState::new_bound_turn1(spec.character, &spec.deck, &spec.binding, spec.hp, spec.max_hp, spec.encounter, &spec.relics, spec.turn1_pre_draw, spec.ascension, spec.elite_buff, &mut rng);
    s.give_potions(&spec.potions).unwrap_or_else(|e| panic!("{e}"));
    // No HP is lost before the first decision, so switching here is exact.
    s.no_death = spec.no_death;
    play_from(s, &mut rng, &mut agent_rng, agent, record, spec.hp)
}

/// Plays on from `s` to the end of the combat: random events from `rng`,
/// the agent's own RNG `agent_rng`. A state with a chance event pending (a
/// divergent afterstate) is advanced with `rng` first. `hp_start` is the
/// result's `hp_start` (the score comes from the state's own start HP).
/// A combat past `PLAY_TURN_LIMIT` turns stops there, lost.
pub fn play_from(s: CombatState, rng: &mut Rng, agent_rng: &mut Rng, agent: &mut dyn Agent, record: bool, hp_start: i16) -> CombatResult {
    play_core(s, rng, agent_rng, agent, record, hp_start, None)
}

/// Luck logging's settings (docs/specs/luck-corrected-labels.md): an
/// event's mean is exact over at most `limit` listed outcomes, else the
/// mean of `samples` sampled ones.
#[derive(Clone, Copy, Debug)]
pub struct LuckConfig {
    pub limit: usize,
    pub samples: u32,
}

impl Default for LuckConfig {
    fn default() -> Self {
        LuckConfig { limit: 64, samples: 16 }
    }
}

/// Salt of the luck logger's own RNG (its sampled outcomes), so logging
/// never draws from the game's RNG.
const LUCK_SALT: u64 = 0x10c6_10c6_10c6_10c6;

/// V of each state: the engine's score when finished, else `ev`'s value.
pub fn luck_values(ev: &mut dyn Evaluator, states: &[CombatState]) -> Vec<f64> {
    let running: Vec<CombatState> = states.iter().filter(|s| !s.is_over()).cloned().collect();
    let mut vals = if running.is_empty() { Vec::new() } else { ev.evaluate(&running) }.into_iter();
    states.iter().map(|s| if s.is_over() { s.score() } else { vals.next().expect("one value per state") as f64 }).collect()
}

/// The mean of V over the pending event's outcomes: exact over the listed
/// ones, else over `cfg.samples` outcomes sampled with `aux`.
pub fn luck_mean(s: &CombatState, ev: &mut dyn Evaluator, cfg: &LuckConfig, aux: &mut Rng) -> f64 {
    match s.chance_outcomes(cfg.limit) {
        Some(ChanceOutcomes::Listed(v)) => {
            let (ps, states): (Vec<f64>, Vec<CombatState>) = v.into_iter().unzip();
            ps.iter().zip(luck_values(ev, &states)).map(|(p, x)| p * x).sum()
        }
        _ => {
            let states: Vec<CombatState> = (0..cfg.samples.max(1))
                .map(|_| {
                    let mut t = s.clone();
                    t.resolve_chance(aux);
                    t
                })
                .collect();
            luck_values(ev, &states).iter().sum::<f64>() / states.len() as f64
        }
    }
}

/// `play`, logging each decision's luck (`CombatResult::luck`) with `ev`
/// as V: per chance event after a decision, V(the outcome drawn) minus the
/// mean of V over its outcomes. The game plays exactly as `play`'s.
pub fn play_luck(spec: &GameSpec, agent: &mut dyn Agent, record: bool, ev: &mut dyn Evaluator, cfg: &LuckConfig) -> CombatResult {
    let mut rng = Rng::new(spec.seed);
    let mut agent_rng = Rng::new(spec.seed ^ 0xa6e7_a6e7);
    let mut s = CombatState::new_bound_turn1(spec.character, &spec.deck, &spec.binding, spec.hp, spec.max_hp, spec.encounter, &spec.relics, spec.turn1_pre_draw, spec.ascension, spec.elite_buff, &mut rng);
    s.give_potions(&spec.potions).unwrap_or_else(|e| panic!("{e}"));
    s.no_death = spec.no_death;
    let mut aux = Rng::new(spec.seed ^ LUCK_SALT);
    play_core(s, &mut rng, &mut agent_rng, agent, record, spec.hp, Some((ev, cfg, &mut aux)))
}

type LuckArgs<'a> = (&'a mut dyn Evaluator, &'a LuckConfig, &'a mut Rng);

fn play_core(mut s: CombatState, rng: &mut Rng, agent_rng: &mut Rng, agent: &mut dyn Agent, record: bool, hp_start: i16, mut luck: Option<LuckArgs>) -> CombatResult {
    s.advance(rng);
    let mut trajectory = Vec::new();
    let mut option_values = Vec::new();
    let mut lucks = Vec::new();
    while !s.is_over() && s.turn <= PLAY_TURN_LIMIT {
        let a = agent.act(&s, agent_rng);
        if record {
            trajectory.push((s.clone(), a));
            option_values.push(agent.last_options().map(<[OptionScore]>::to_vec).unwrap_or_default());
        }
        match luck.as_mut() {
            None => s.step(a, rng).expect("agent chose a legal action"),
            Some((ev, cfg, aux)) => {
                // `step`'s own order (apply, then resolve each event in
                // turn), each event's luck read off clones.
                s.apply_action(a).expect("agent chose a legal action");
                let mut sum = 0.0;
                while s.pending.is_some() {
                    let mean = luck_mean(&s, &mut **ev, cfg, aux);
                    s.resolve_chance(rng);
                    sum += luck_values(&mut **ev, std::slice::from_ref(&s))[0] - mean;
                }
                lucks.push(sum);
            }
        }
    }
    CombatResult {
        won: s.won(),
        hp_end: if s.won() || s.no_death { s.player.hp } else { 0 },
        healed: s.won_healed.0,
        hp_start,
        turns: s.turn,
        score: s.score(),
        trajectory,
        option_values,
        luck: lucks,
    }
}

/// Plays every spec on `threads` threads, one agent per thread from `make`.
/// Results are in spec order.
pub fn play_many<A: Agent, F: Fn() -> A + Sync>(specs: &[GameSpec], make: F, threads: usize, record: bool) -> Vec<CombatResult> {
    play_many_with(specs, threads, &make, |agent: &mut A, spec: &GameSpec| play(spec, agent, record))
}

/// `play_many` with each game's luck logged (`play_luck`), one evaluator
/// per thread from `make_ev`.
pub fn play_many_luck<A: Agent, E: Evaluator, F: Fn() -> A + Sync, G: Fn() -> E + Sync>(
    specs: &[GameSpec],
    make: F,
    make_ev: G,
    threads: usize,
    record: bool,
    cfg: &LuckConfig,
) -> Vec<CombatResult> {
    let make_both = || (make(), make_ev());
    play_many_with(specs, threads, &make_both, |w: &mut (A, E), spec: &GameSpec| play_luck(spec, &mut w.0, record, &mut w.1, cfg))
}

/// Plays every spec on `threads` threads with a worker state per thread
/// from `make`; results in spec order.
fn play_many_with<W, M: Fn() -> W + Sync, P: Fn(&mut W, &GameSpec) -> CombatResult + Sync>(specs: &[GameSpec], threads: usize, make: &M, one: P) -> Vec<CombatResult> {
    let next = AtomicUsize::new(0);
    let out: Mutex<Vec<Option<CombatResult>>> = Mutex::new(vec![None; specs.len()]);
    std::thread::scope(|scope| {
        for _ in 0..threads.max(1) {
            scope.spawn(|| {
                let mut w = make();
                loop {
                    let i = next.fetch_add(1, Ordering::Relaxed);
                    if i >= specs.len() {
                        break;
                    }
                    let r = one(&mut w, &specs[i]);
                    out.lock().unwrap()[i] = Some(r);
                }
            });
        }
    });
    out.into_inner().unwrap().into_iter().map(|r| r.expect("every spec played")).collect()
}

/// Win rate and mean HP lost.
pub fn summarize(results: &[CombatResult]) -> (f64, f64) {
    let n = results.len().max(1) as f64;
    let wins = results.iter().filter(|r| r.won).count() as f64;
    let lost: f64 = results.iter().map(|r| r.hp_lost() as f64).sum();
    (wins / n, lost / n)
}

/// Threads for a run that doesn't name a count: the job's cap
/// `STS_JOB_THREADS` (the job runner sets it), else every core. A cap of 0
/// or one that isn't a number is ignored.
pub fn default_threads() -> usize {
    std::env::var("STS_JOB_THREADS")
        .ok()
        .and_then(|v| v.trim().parse::<usize>().ok())
        .filter(|&n| n > 0)
        .unwrap_or_else(|| std::thread::available_parallelism().map_or(1, |n| n.get()))
}

#[cfg(test)]
mod luck_tests {
    use super::*;
    use crate::agent::SearchAgent;
    use crate::heuristic::Heuristic;
    use crate::search::SearchConfig;

    fn specs() -> Vec<GameSpec> {
        let mut v = group_specs(EncounterGroup::Elite, 6, 6, 7);
        v.extend(group_specs(EncounterGroup::Hallway, 6, 6, 9));
        v
    }

    #[test]
    fn luck_game_matches_plain() {
        let mut drawn = false;
        for spec in specs() {
            let plain = play(&spec, &mut SearchAgent::new(Heuristic, SearchConfig::default()), true);
            let logged = play_luck(&spec, &mut SearchAgent::new(Heuristic, SearchConfig::default()), true, &mut Heuristic, &LuckConfig::default());
            let acts = |r: &CombatResult| r.trajectory.iter().map(|(_, a)| *a).collect::<Vec<_>>();
            assert_eq!(acts(&plain), acts(&logged));
            assert_eq!((plain.score, plain.turns, plain.hp_end), (logged.score, logged.turns, logged.hp_end));
            assert_eq!(logged.luck.len(), logged.trajectory.len());
            assert!(plain.luck.is_empty());
            drawn |= logged.luck.iter().any(|&x| x.abs() > 1e-6);
        }
        assert!(drawn, "some luck is drawn");
    }

    /// States with a listed event pending, from the games' decisions.
    fn pending_states() -> Vec<CombatState> {
        let mut out = Vec::new();
        for spec in specs() {
            let r = play(&spec, &mut SearchAgent::new(Heuristic, SearchConfig::default()), true);
            for (s, a) in r.trajectory {
                let mut t = s.clone();
                t.apply_action(a).unwrap();
                if t.pending.is_some() && matches!(t.chance_outcomes(64), Some(ChanceOutcomes::Listed(_))) {
                    out.push(t);
                }
            }
        }
        assert!(out.len() > 20);
        out
    }

    #[test]
    fn luck_listed_event_has_zero_mean() {
        for s in pending_states() {
            let mean = luck_mean(&s, &mut Heuristic, &LuckConfig::default(), &mut Rng::new(1));
            let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(64) else { unreachable!() };
            let states: Vec<CombatState> = v.iter().map(|(_, t)| t.clone()).collect();
            let vals = luck_values(&mut Heuristic, &states);
            let zero: f64 = v.iter().zip(&vals).map(|((p, _), x)| p * (x - mean)).sum();
            assert!(zero.abs() < 1e-9, "{zero}");
            for seed in 0..5 {
                let mut t = s.clone();
                t.resolve_chance(&mut Rng::new(seed));
                assert!(states.contains(&t), "the drawn outcome is a listed one");
            }
        }
    }

    struct Const;
    impl Evaluator for Const {
        fn evaluate(&mut self, states: &[CombatState]) -> Vec<f32> {
            vec![1.0; states.len()]
        }
    }

    #[test]
    fn luck_constant_value_is_zero_while_running() {
        let mut sampled = 0;
        for s in pending_states() {
            let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(64) else { unreachable!() };
            if v.iter().all(|(_, t)| !t.is_over()) {
                let mean = luck_mean(&s, &mut Const, &LuckConfig::default(), &mut Rng::new(1));
                assert!((mean - 1.0).abs() < 1e-9);
                // A limit of 0 lists nothing: the sampled mean.
                let mean = luck_mean(&s, &mut Const, &LuckConfig { limit: 0, samples: 8 }, &mut Rng::new(3));
                assert!((mean - 1.0).abs() < 1e-9);
                sampled += 1;
            }
        }
        assert!(sampled > 0);
    }
}

#[cfg(test)]
mod tests {
    use super::default_threads;

    // One test for every case: the variable is process-wide, so cases in
    // parallel tests would race.
    #[test]
    fn default_threads_follows_the_job_cap() {
        const KEY: &str = "STS_JOB_THREADS";
        let saved = std::env::var_os(KEY);
        let all = std::thread::available_parallelism().map_or(1, |n| n.get());
        let with = |v: Option<&str>| {
            match v {
                Some(v) => std::env::set_var(KEY, v),
                None => std::env::remove_var(KEY),
            }
            default_threads()
        };
        let got = [with(Some("3")), with(Some(" 2 ")), with(Some("0")), with(Some("junk")), with(Some("")), with(None)];
        match saved {
            Some(v) => std::env::set_var(KEY, v),
            None => std::env::remove_var(KEY),
        }
        assert_eq!(got, [3, 2, all, all, all, all]);
    }
}
