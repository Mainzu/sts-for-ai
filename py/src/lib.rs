//! Python module `sts`: the combat engine, its agents and state features.
//! See SPEC.md (Python API) and docs/python-api.md.

mod features;
mod net;
mod render;

#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;

use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};

use numpy::ndarray::{Array1, Array2, Array3};
use numpy::{IntoPyArray, PyReadonlyArray1, PyReadonlyArrayDyn, PyUntypedArrayMethods};
use pyo3::exceptions::{PyKeyError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList, PyTuple};

use sts_engine::agent::{greedy_action as engine_greedy, intent_damage, random_action as engine_random, Agent, GreedyAgent, RandomAgent, SearchAgent};
use sts_engine::cards::{class_cards, deck_cards, held_out_cards, CardId};
use sts_engine::character::Character;
use sts_engine::heuristic::{estimate, hp_loss_estimate, strength_hits_left, turns_left_estimate};
use sts_engine::monsters::{Encounter, EncounterGroup};
use sts_engine::options::Outcome;
use sts_engine::powers::Power;
use sts_engine::registry::{self, Binding};
use sts_engine::potions::PotionSpec;
use sts_engine::relics::RelicSpec;
use sts_engine::rng::Rng;
use sts_engine::runner::{default_threads, group_specs_as, play, play_from, play_many, play_many_luck, CombatResult, GameSpec, LuckConfig, PLAY_TURN_LIMIT};
use sts_engine::search::{end_hp_scale, search as engine_search, Evaluator, Heuristic, OptionScore, ScoreRule, SearchConfig, SearchResult};
use sts_engine::solve::{solve as engine_solve, Distribution, MemoryStore, SolveConfig, Solution, SolvedOption};
use sts_engine::state::{Action, CombatState, Stage, MAX_MONSTERS};

use features::{
    condition_names, default_trigger_names, has_lookahead, EXTRA_KINDS, has_rates, has_start_hp, is_hook_power, power_name, Batch, CardRepr, Encoder, Vocab, EFFECT_SCALARS, ENTITIES, MODIFIER_POWERS,
    PILES, PILE_PARENTS, ROW_KINDS,
};
use net::{Head, Net, Scratch, Tensor};

fn err(msg: impl Into<String>) -> PyErr {
    PyValueError::new_err(msg.into())
}

fn card(name: &str) -> PyResult<CardId> {
    CardId::from_name(name).ok_or_else(|| {
        if name.starts_with("gen:") {
            err(format!("generated card {name:?} only in a deck (Combat, run specs), not here"))
        } else {
            err(format!("unknown card {name:?}"))
        }
    })
}

/// A deck's names (official, or `gen:<id>` from a loaded content pack) as
/// card ids, with its generated content bound to the reserved slots.
fn bind_deck(names: &[String]) -> PyResult<(Vec<CardId>, Binding)> {
    let names: Vec<&str> = names.iter().map(String::as_str).collect();
    registry::bind(&names).map_err(err)
}

/// A relic as Python gives it: a name, or `(name, counter)` to start its
/// counter there instead of at its file's `counter` (relic-entity spec).
#[derive(FromPyObject, Clone)]
enum RelicArg {
    Name(String),
    WithCounter(String, i16),
}

impl RelicArg {
    fn name(&self) -> &str {
        match self {
            RelicArg::Name(n) | RelicArg::WithCounter(n, _) => n,
        }
    }
}

/// Relics by name (docs/specs/relics.md), each at its given counter, the
/// pack powers of those acting in a fight of `group` checked to fit
/// `binding`'s free slots.
fn relic_args(args: Option<Vec<RelicArg>>, binding: &Binding, group: EncounterGroup, character: Character) -> PyResult<Vec<(String, RelicSpec)>> {
    let args = args.unwrap_or_default();
    let names: Vec<&str> = args.iter().map(RelicArg::name).collect();
    let mut relics = registry::relics_named(&names).map_err(err)?;
    for (a, (_, r)) in args.iter().zip(relics.iter_mut()) {
        if let RelicArg::WithCounter(_, c) = a {
            r.counter = *c;
        }
    }
    registry::bind_relics(binding, relics.iter().filter(|(_, r)| r.acts_in(group)), character).map_err(err)?;
    Ok(relics)
}

/// Potions by name (docs/specs/potions.md), at most `POTION_CAP`.
fn potion_args(names: Option<Vec<String>>) -> PyResult<Vec<(String, PotionSpec)>> {
    let names = names.unwrap_or_default();
    registry::potions_named(&names.iter().map(String::as_str).collect::<Vec<_>>()).map_err(err)
}

/// A card's name: its official name, or `gen:<id>` through the binding.
fn card_name(c: CardId, b: &Binding) -> &'static str {
    if c.is_official() { c.name() } else { b.def(c).name }
}

fn encounter(name: &str) -> PyResult<Encounter> {
    Encounter::from_name(name).ok_or_else(|| err(format!("unknown encounter {name:?}")))
}

fn group(name: &str) -> PyResult<EncounterGroup> {
    match name {
        "hallway" => Ok(EncounterGroup::Hallway),
        "elite" => Ok(EncounterGroup::Elite),
        "boss" => Ok(EncounterGroup::Boss),
        _ => Err(err(format!("unknown group {name:?} (hallway, elite, boss)"))),
    }
}

fn character(name: &str) -> PyResult<Character> {
    Character::from_name(name).ok_or_else(|| err(format!("unknown character {name:?} (ironclad, silent)")))
}

/// `(hp, max_hp)` for a combat at ascension `a`: `hp` defaults to the HP
/// a run starts with at that level, max HP to the run's starting max HP
/// (`Character::run_start_hp`) and is at least `hp`.
fn hp_pair(c: Character, hp: Option<i16>, max_hp: Option<i16>, a: u8) -> (i16, i16) {
    let (start, max) = c.run_start_hp(a);
    let hp = hp.unwrap_or(start);
    (hp, max_hp.unwrap_or(hp.max(max)))
}

/// The pack card a run's deck gets from ascension 10 (the game's
/// `AscendersBane`, `content/game_ids.json`).
const ASCENDERS_BANE: &str = "gen:Ascender's Bane";
/// The level from which a run's deck holds `ASCENDERS_BANE`.
const ASCENDERS_BANE_FROM: u8 = 10;

/// A burning elite's buff by name (`EliteBuff::name`); `None` for none.
/// "regenerate" needs its pack power loaded (`content/packs/act1-monsters.json`).
fn elite_buff(b: Option<&str>) -> PyResult<Option<sts_engine::EliteBuff>> {
    b.map(|n| {
        let b = sts_engine::EliteBuff::from_name(n).ok_or_else(|| {
            err(format!("unknown elite_buff {n:?} (known: {:?})", sts_engine::EliteBuff::ALL.map(|b| b.name())))
        })?;
        b.bind(&Default::default()).map_err(err)?;
        Ok(b)
    })
    .transpose()
}

/// Checks an ascension level (0 to 20); from `ASCENDERS_BANE_FROM`, loads
/// `ASCENDERS_BANE`'s entry of its pack (once per process; the whole pack
/// needs the Ironclad pack's pools), so a deck naming it binds in any
/// process that builds such a fight.
fn ascension(a: u8) -> PyResult<sts_engine::monsters::Ascension> {
    if a > sts_engine::monsters::MAX_ASCENSION {
        return Err(err(format!("ascension {a} above {}", sts_engine::monsters::MAX_ASCENSION)));
    }
    if a >= ASCENDERS_BANE_FROM {
        static LOADED: std::sync::OnceLock<Result<u64, String>> = std::sync::OnceLock::new();
        LOADED
            .get_or_init(|| {
                const PACK: &str = include_str!("../../content/packs/act1-colorless.json");
                let id = format!("{{\"id\": {:?},", &ASCENDERS_BANE[4..]);
                let entry = PACK.lines().find(|l| l.starts_with(&id)).ok_or_else(|| "no Ascender's Bane in content/packs/act1-colorless.json".to_string())?;
                registry::load_pack(&format!("{{\"version\": 2, \"cards\": [{}]}}", entry.trim_end_matches(',')))
            })
            .clone()
            .map_err(err)?;
    }
    Ok(sts_engine::monsters::Ascension(a))
}

/// A net's column names per path (`player`, `monsters`, `cards`, `rows`).
type Columns = HashMap<String, Vec<String>>;

fn layout_columns(columns: Option<Columns>) -> PyResult<Option<[Vec<String>; 4]>> {
    let Some(mut c) = columns else { return Ok(None) };
    let mut take = |k: &str| c.remove(k).ok_or_else(|| err(format!("columns needs {k:?} (player, monsters, cards, rows)")));
    let out = [take("player")?, take("monsters")?, take("cards")?, take("rows")?];
    if let Some(k) = c.keys().next() {
        return Err(err(format!("columns has an unknown path {k:?} (player, monsters, cards, rows)")));
    }
    Ok(Some(out))
}

/// Checks every name against a vocabulary's full list.
fn names_in(kind: &str, names: Option<Vec<String>>, all: &[String]) -> PyResult<Option<Vec<String>>> {
    for n in names.iter().flatten() {
        if !all.contains(n) {
            return Err(err(format!("unknown {kind} {n:?}")));
        }
    }
    Ok(names)
}

fn power(name: &str) -> PyResult<Power> {
    Power::ALL.into_iter().find(|&p| power_name(p) == name).ok_or_else(|| err(format!("unknown power {name:?}")))
}

fn deck_names(deck: &[CardId], b: &Binding) -> Vec<&'static str> {
    deck.iter().map(|&c| card_name(c, b)).collect()
}

/// An action: play a card (with a monster slot for targeted cards) or end
/// the turn. `Action()` is EndTurn. A generated card's action carries its
/// name (`gen:<id>`): its card id is a slot that only means something in
/// its combat, so `step` checks the name against the combat's binding.
#[pyclass(module = "sts", name = "Action", frozen, eq, hash, from_py_object)]
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
struct PyAction(Action, Option<&'static str>);

/// `act`, an id `b` doesn't hold left unnamed instead of failing.
fn act_in(a: Action, b: &Binding) -> PyAction {
    match a {
        Action::Play { card, .. } | Action::Choose(card) if !b.is_bound(card) => PyAction(a, Some("<unbound>")),
        _ => act(a, b),
    }
}

/// `a` as a Python action, a generated card named through `b`.
fn act(a: Action, b: &Binding) -> PyAction {
    match a {
        Action::Play { card, .. } | Action::Choose(card) if !card.is_official() => PyAction(a, Some(card_name(card, b))),
        _ => PyAction(a, None),
    }
}

#[pymethods]
impl PyAction {
    #[new]
    #[pyo3(signature = (card=None, target=None))]
    fn new(card: Option<&str>, target: Option<u8>) -> PyResult<PyAction> {
        match card {
            None if target.is_some() => Err(err("EndTurn takes no target")),
            None => Ok(PyAction(Action::EndTurn, None)),
            Some(name) => Ok(PyAction(Action::Play { card: self::card(name)?, target }, None)),
        }
    }

    /// At a pick: take `card` (decision-points spec).
    #[staticmethod]
    fn choose(card: &str) -> PyResult<PyAction> {
        Ok(PyAction(Action::Choose(self::card(card)?), None))
    }

    /// At an "up to n" pick: stop picking.
    #[staticmethod]
    fn done() -> PyAction {
        PyAction(Action::Done, None)
    }

    /// Use the held potion in list position `slot`, at monster slot
    /// `target` for a targeted potion (docs/specs/potions.md).
    #[staticmethod]
    #[pyo3(signature = (slot, target=None))]
    fn potion(slot: u8, target: Option<u8>) -> PyAction {
        PyAction(Action::UsePotion { slot, target }, None)
    }

    /// A potion use's position in the held list; None for other actions.
    #[getter]
    fn slot(&self) -> Option<u8> {
        match self.0 {
            Action::UsePotion { slot, .. } => Some(slot),
            _ => None,
        }
    }

    /// "play", "end", "choose", "done" or "potion".
    #[getter]
    fn kind(&self) -> &'static str {
        match self.0 {
            Action::Play { .. } => "play",
            Action::EndTurn => "end",
            Action::Choose(_) => "choose",
            Action::Done => "done",
            Action::UsePotion { .. } => "potion",
        }
    }

    /// The played card, or the chosen one.
    #[getter]
    fn card(&self) -> Option<&'static str> {
        match self.0 {
            Action::Play { card, .. } | Action::Choose(card) => Some(self.1.unwrap_or_else(|| card.name())),
            Action::EndTurn | Action::Done | Action::UsePotion { .. } => None,
        }
    }

    #[getter]
    fn target(&self) -> Option<u8> {
        match self.0 {
            Action::Play { target, .. } | Action::UsePotion { target, .. } => target,
            Action::EndTurn | Action::Choose(_) | Action::Done => None,
        }
    }

    #[getter]
    fn is_end_turn(&self) -> bool {
        self.0 == Action::EndTurn
    }

    fn __repr__(&self) -> String {
        format!("Action({})", action_label(*self))
    }
}

/// An action's text, a generated card by its name.
fn action_label(a: PyAction) -> String {
    match (a.0, a.1) {
        (Action::Play { target: Some(t), .. }, Some(n)) => format!("{n} -> slot {t}"),
        (Action::Play { target: None, .. }, Some(n)) => n.to_string(),
        (Action::Choose(_), Some(n)) => format!("Choose {n}"),
        (a, _) => render::action_name(a),
    }
}

/// One option as returned to Python: `(actions, kind, [(prob, Combat)])`.
type PyOption = (Vec<PyAction>, &'static str, Vec<(f64, Combat)>);

/// One combat: the state plus the RNG its random events are sampled from.
/// `ascension` (0-20, docs/specs/ascension.md) is the game's level: the
/// monsters' numbers and rules at it, the potion slots, and the defaults of
/// `hp` and `max_hp` (the run's start at that level, `run_start`); a deck
/// that should hold Ascender's Bane names it (`run_start`'s `deck_adds`).
/// `elite_buff` ("strength", "max_hp", "metallicize", "regenerate") makes it the map's
/// burning elite, each monster buffed as Act 1's game does (`EliteBuff`).
#[pyclass(module = "sts")]
#[derive(Clone)]
struct Combat {
    s: CombatState,
    rng: Rng,
}

impl Combat {
    /// A copy of `s` with an RNG derived from this combat's, but not equal to
    /// it, so stepping an option's state doesn't replay the real future.
    fn child(&self, s: CombatState, k: u64) -> Combat {
        let seed = self.rng.clone().next_u64() ^ k.wrapping_mul(0x9e37_79b9_7f4a_7c15) ^ 0x0c41_1d00;
        Combat { s, rng: Rng::new(seed) }
    }

    fn need_action(&self) -> PyResult<()> {
        if self.s.awaiting_action() {
            Ok(())
        } else {
            Err(err("the combat is not awaiting an action"))
        }
    }
}

#[pymethods]
impl Combat {
    #[new]
    #[pyo3(signature = (deck, encounter, seed=0, hp=None, max_hp=None, character="ironclad", no_death=false, relics=None, turn1_pre_draw=false, potions=None, ascension=0, elite_buff=None))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        deck: Vec<String>,
        encounter: &str,
        seed: u64,
        hp: Option<i16>,
        max_hp: Option<i16>,
        character: &str,
        no_death: bool,
        relics: Option<Vec<RelicArg>>,
        turn1_pre_draw: bool,
        potions: Option<Vec<String>>,
        ascension: u8,
        elite_buff: Option<String>,
    ) -> PyResult<Combat> {
        let level = self::ascension(ascension)?;
        let elite_buff = self::elite_buff(elite_buff.as_deref())?;
        let potions = potion_args(potions)?;
        let (deck, binding) = bind_deck(&deck)?;
        let enc = self::encounter(encounter)?;
        let ch = self::character(character)?;
        let relics = relic_args(relics, &binding, enc.group(), ch)?;
        let (hp, max_hp) = hp_pair(ch, hp, max_hp, ascension);
        let mut rng = Rng::new(seed);
        let mut s = CombatState::new_bound_turn1(ch, &deck, &binding, hp, max_hp, enc, &relics, turn1_pre_draw, level, elite_buff, &mut rng);
        s.give_potions(&potions).map_err(err)?;
        s.no_death = no_death;
        Ok(Combat { s, rng })
    }

    /// A combat against these monsters by slot (an official monster by its
    /// game name, e.g. "Jaw Worm", or "gen:<id>" from a loaded content
    /// pack) instead of an encounter's roll. `relics` as for `Combat`; with
    /// no encounter, `group` (`"hallway"`, `"elite"`, `"boss"`) is the
    /// fight's kind for each relic's `fights`. `turn1_pre_draw` as for
    /// `Combat`.
    #[staticmethod]
    #[pyo3(signature = (deck, monsters, seed=0, hp=None, max_hp=None, character="ironclad", no_death=false, relics=None, group="hallway", turn1_pre_draw=false, potions=None, ascension=0, elite_buff=None))]
    #[allow(clippy::too_many_arguments)]
    fn versus(
        deck: Vec<String>,
        monsters: Vec<String>,
        seed: u64,
        hp: Option<i16>,
        max_hp: Option<i16>,
        character: &str,
        no_death: bool,
        relics: Option<Vec<RelicArg>>,
        group: &str,
        turn1_pre_draw: bool,
        potions: Option<Vec<String>>,
        ascension: u8,
        elite_buff: Option<String>,
    ) -> PyResult<Combat> {
        let level = self::ascension(ascension)?;
        let elite_buff = self::elite_buff(elite_buff.as_deref())?;
        let potions = potion_args(potions)?;
        let (deck, binding) = bind_deck(&deck)?;
        let names: Vec<&str> = monsters.iter().map(String::as_str).collect();
        let kinds = registry::monster_kinds(&names).map_err(err)?;
        // The monsters' pack powers must fit the slots the deck left, and
        // the acting relics' those the monsters left.
        let with_monsters = registry::bind_monsters(&binding, &kinds).map_err(err)?;
        let group = self::group(group)?;
        let ch = self::character(character)?;
        let relics = relic_args(relics, &with_monsters, group, ch)?;
        let (hp, max_hp) = hp_pair(ch, hp, max_hp, ascension);
        let mut rng = Rng::new(seed);
        let mut s = CombatState::new_with_turn1(ch, &deck, &binding, hp, max_hp, &kinds, group, &relics, turn1_pre_draw, level, elite_buff, &mut rng);
        s.give_potions(&potions).map_err(err)?;
        s.no_death = no_death;
        Ok(Combat { s, rng })
    }

    #[getter]
    fn character(&self) -> &'static str {
        self.s.character.name()
    }

    /// The game's ascension level the fight is played at (docs/specs/ascension.md).
    #[getter]
    fn ascension(&self) -> u8 {
        self.s.ascension.0
    }

    /// HP healed when this combat is won (`CombatState::win_heal`: the
    /// starter relic's, Black Blood's, ..., as Magic Flower scales it).
    #[getter]
    fn win_heal(&self) -> i16 {
        self.s.win_heal_scaled()
    }

    /// The relics the player holds, in order, as `(name, counter)`
    /// (relic-entity spec; the starter relic is the character's, not listed).
    #[getter]
    fn relics(&self) -> Vec<(&'static str, i16)> {
        self.s.player.relics.iter().map(|(id, c)| (id.name(), c)).collect()
    }

    /// The potions the player holds, by name, sorted (docs/specs/potions.md).
    #[getter]
    fn potions(&self) -> Vec<&'static str> {
        self.s.player.potions.iter().map(|p| p.name()).collect()
    }

    /// Each distinct legal action once (empty when not awaiting an action).
    fn legal_actions(&self) -> Vec<PyAction> {
        self.s.legal_actions().into_iter().map(|a| act(a, &self.s.binding)).collect()
    }

    /// Each distinct option: `(actions, kind, [(prob, Combat)])`, kind being
    /// "deterministic", "chance" or "divergent" (one paused state).
    #[pyo3(signature = (limit=16))]
    fn options(&self, limit: usize) -> Vec<PyOption> {
        let mut k = 0u64;
        let mut child = |s: CombatState| {
            k += 1;
            self.child(s, k)
        };
        self.s
            .options(limit)
            .into_iter()
            .map(|o| {
                let actions = o.actions.into_iter().map(|a| act(a, &self.s.binding)).collect();
                let (kind, outs) = match o.outcome {
                    Outcome::Deterministic(s) => ("deterministic", vec![(1.0, child(s))]),
                    Outcome::Chance(v) => ("chance", v.into_iter().map(|(p, s)| (p, child(s))).collect()),
                    Outcome::Divergent(s) => ("divergent", vec![(1.0, child(s))]),
                };
                (actions, kind, outs)
            })
            .collect()
    }

    /// Applies an action, sampling random events up to the next decision.
    fn step(&mut self, action: PyAction) -> PyResult<()> {
        if let (Action::Play { card, .. } | Action::Choose(card), Some(name)) = (action.0, action.1) {
            let b = &self.s.binding;
            if !b.is_bound(card) || b.def(card).name != name {
                return Err(err(format!("{name:?} is not in this combat's slot (take actions from this combat)")));
            }
        }
        self.s.step(action.0, &mut self.rng).map_err(|_| err(format!("illegal action {}", render::action_name(action.0))))
    }

    /// Samples any pending random events (a paused option state) up to the
    /// next decision.
    fn advance(&mut self) {
        self.s.advance(&mut self.rng);
    }

    fn is_over(&self) -> bool {
        self.s.is_over()
    }

    fn won(&self) -> bool {
        self.s.won()
    }

    /// The player escaped (Smoke Bomb; docs/specs/act1-singles.md): the
    /// fight is over and won, with the monsters' HP kept.
    #[getter]
    fn escaped(&self) -> bool {
        self.s.escaped
    }

    fn awaiting_action(&self) -> bool {
        self.s.awaiting_action()
    }

    fn player_hp(&self) -> i16 {
        self.s.player.hp
    }

    /// won × (2 − HP lost / 100), after end-of-combat healing; 0 while running or lost.
    fn score(&self) -> f64 {
        self.s.score()
    }

    /// The highest final score still possible (docs/specs/solver-bounds.md).
    fn upper_bound(&self) -> f64 {
        self.s.upper_bound()
    }

    /// Whether the player could still gain HP in this combat.
    fn can_heal(&self) -> bool {
        self.s.can_heal()
    }

    fn turn(&self) -> u16 {
        self.s.turn
    }

    /// The next turn's start draw as (min, max) (`CombatState::next_draw`).
    fn next_draw(&self) -> (u8, u8) {
        self.s.next_draw()
    }

    /// `{pile: {card name: count}}` for hand, draw, discard and exhaust.
    fn piles(&self) -> HashMap<&'static str, HashMap<&'static str, u8>> {
        let s = &self.s;
        [("hand", s.hand.view()), ("draw", s.draw()), ("discard", s.discard()), ("exhaust", s.exhaust())]
            .into_iter()
            .map(|(name, p)| (name, p.iter().map(|(c, n)| (card_name(c, &s.binding), n)).collect()))
            .collect()
    }

    /// Features of this one state (a batch of 1); see `Features`.
    #[pyo3(signature = (card_repr="effects", known_cards=None, known_powers=None, known_triggers=None, known_conditions=None, known_effects=None, columns=None, row_kinds=None, piles=None))]
    #[allow(clippy::too_many_arguments)]
    fn features<'py>(
        &self,
        py: Python<'py>,
        card_repr: &str,
        known_cards: Option<Vec<String>>,
        known_powers: Option<Vec<String>>,
        known_triggers: Option<Vec<String>>,
        known_conditions: Option<Vec<String>>,
        known_effects: Option<Vec<String>>,
        columns: Option<Columns>,
        row_kinds: Option<Vec<String>>,
        piles: Option<Vec<String>>,
    ) -> PyResult<Bound<'py, PyDict>> {
        let known = (known_cards, known_powers, known_triggers, known_conditions, known_effects);
        let enc = make_encoder(card_repr, known, (columns, row_kinds, piles), false, false, false, false, false)?;
        batch_dict(py, &enc, &enc.encode(&[&self.s]))
    }

    fn render(&self) -> String {
        render::render(&self.s)
    }

    /// The board as data (docs/specs/explorer-v2.md), from what `render`
    /// reads: turn, over/won, player {hp, max_hp, block, energy, powers,
    /// potions (names, in list order)},
    /// living monsters {slot, name, hp, max_hp, block, intent {name,
    /// damage, hits, known} or None, powers}, hand [{name, count, cost,
    /// upgraded}] in render's order, piles {draw, discard, exhaust:
    /// {count, cards: [(name, n)] sorted by name}} (draw never in order)
    /// with draw's `known_top` (the known cards, next drawn first), and
    /// the pending chance event in render's words or None.
    fn board<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let s = &self.s;
        let b = &s.binding;
        let powers = |p: &sts_engine::powers::Powers| -> PyResult<Bound<'py, PyList>> {
            let l = PyList::empty(py);
            for (name, amount) in render::power_list(p, b) {
                let d = PyDict::new(py);
                d.set_item("name", name)?;
                d.set_item("amount", amount)?;
                l.append(d)?;
            }
            Ok(l)
        };
        let out = PyDict::new(py);
        out.set_item("turn", s.turn)?;
        out.set_item("over", s.is_over())?;
        out.set_item("won", matches!(s.stage, Stage::Over { won: true }))?;
        let p = PyDict::new(py);
        p.set_item("hp", s.player.hp)?;
        p.set_item("max_hp", s.player.max_hp)?;
        p.set_item("block", s.player.block)?;
        p.set_item("energy", s.player.energy)?;
        p.set_item("powers", powers(&s.player.powers)?)?;
        // Held potions by name, in list order (a potion action's slot).
        p.set_item("potions", s.player.potions.iter().map(|q| q.name()).collect::<Vec<_>>())?;
        out.set_item("player", p)?;
        let monsters = PyList::empty(py);
        for slot in 0..MAX_MONSTERS {
            let m = &s.monsters[slot];
            if !m.alive() {
                continue;
            }
            let d = PyDict::new(py);
            d.set_item("slot", slot)?;
            d.set_item("name", m.def().name)?;
            d.set_item("hp", m.hp)?;
            d.set_item("max_hp", m.max_hp)?;
            d.set_item("block", m.block)?;
            // Runic Dome: a hidden move shows no name and its expected damage.
            match m.intent_def() {
                Some(_) if s.move_hidden(slot) => {
                    let i = PyDict::new(py);
                    i.set_item("name", py.None())?;
                    i.set_item("damage", intent_damage(s, slot))?;
                    i.set_item("hits", 0)?;
                    i.set_item("known", false)?;
                    d.set_item("intent", i)?;
                }
                Some(mv) => {
                    let hits: u32 = s.move_attacks(slot, mv, true).map(|(_, h)| h as u32).sum();
                    let i = PyDict::new(py);
                    i.set_item("name", mv.name)?;
                    i.set_item("damage", intent_damage(s, slot))?;
                    i.set_item("hits", hits)?;
                    i.set_item("known", sts_engine::agent::intent_known(s, slot))?;
                    d.set_item("intent", i)?;
                }
                None => d.set_item("intent", py.None())?,
            }
            d.set_item("powers", powers(&m.powers)?)?;
            monsters.append(d)?;
        }
        out.set_item("monsters", monsters)?;
        let hand = PyList::empty(py);
        for (c, n) in s.hand.iter() {
            let def = b.def(c);
            let d = PyDict::new(py);
            d.set_item("name", def.name)?;
            d.set_item("count", n)?;
            d.set_item("cost", def.cost())?;
            d.set_item("x_cost", def.x_cost())?;
            d.set_item("upgraded", def.name.ends_with('+') || def.level >= 2)?;
            hand.append(d)?;
        }
        out.set_item("hand", hand)?;
        let piles = PyDict::new(py);
        for (name, pile) in [("draw", s.draw()), ("discard", s.discard()), ("exhaust", s.exhaust())] {
            let mut cards: Vec<(&'static str, u8)> = pile.iter().map(|(c, n)| (card_name(c, b), n)).collect();
            cards.sort();
            let d = PyDict::new(py);
            d.set_item("count", pile.len())?;
            d.set_item("cards", cards)?;
            if name == "draw" {
                d.set_item("known_top", s.top.known().map(|c| card_name(c, b)).collect::<Vec<_>>())?;
            }
            piles.set_item(name, d)?;
        }
        out.set_item("piles", piles)?;
        out.set_item("pending", render::pending_text(s))?;
        Ok(out)
    }

    fn __repr__(&self) -> String {
        render::render(&self.s)
    }

    /// Equal when the engine states are equal (the afterstate); the RNG is
    /// left out, so the same state under another seed is equal. Works for
    /// states with generated content, which have no `encode`.
    fn __eq__(&self, other: &Bound<'_, PyAny>) -> bool {
        match other.cast::<Combat>() {
            Ok(o) => self.s == o.borrow().s,
            Err(_) => false,
        }
    }

    /// The engine state's hash (the RNG left out), consistent with `==`.
    fn __hash__(&self) -> u64 {
        use std::hash::{Hash, Hasher};
        let mut h = std::collections::hash_map::DefaultHasher::new();
        self.s.hash(&mut h);
        h.finish()
    }

    /// The plain end-of-turn leaf search scores (`search.rs` `child`):
    /// `EndTurn` applied up to the first chance event, or the next decision
    /// or the end when there is none (docs/specs/leaf-blind-numbers.md).
    fn after_end_turn(&self) -> PyResult<Combat> {
        self.need_action()?;
        let mut t = self.s.clone();
        t.apply_action(Action::EndTurn).map_err(|_| err("EndTurn is not legal here"))?;
        Ok(self.child(t, 0))
    }

    /// Where the state stands: "monster_rolls" (a monster's next move is
    /// being rolled, before `StartTurn` clears block), "draw" (the turn
    /// started, its draw pending), "decision", "over", or "other".
    #[getter]
    fn leaf_form(&self) -> &'static str {
        match (self.s.stage, self.s.pending.is_some()) {
            _ if self.s.is_over() => "over",
            (Stage::MonsterRolls { .. }, _) => "monster_rolls",
            (Stage::TurnStarted, true) => "draw",
            _ if self.s.awaiting_action() => "decision",
            _ => "other",
        }
    }

    /// `(block, energy)` of the player.
    #[getter]
    fn player_block_energy(&self) -> (i16, i16) {
        (self.s.player.block, self.s.player.energy)
    }

    /// Per monster slot `(alive, hp, block, intent damage, Strength, Weak,
    /// Vulnerable)`; intent damage as the features count it.
    fn monster_numbers(&self) -> Vec<(bool, i16, i16, i16, i16, i16, i16)> {
        (0..MAX_MONSTERS)
            .map(|i| {
                let m = &self.s.monsters[i];
                let p = |w| m.powers.get(w);
                (m.alive(), m.hp, m.block, intent_damage(&self.s, i), p(Power::Strength), p(Power::Weak), p(Power::Vulnerable))
            })
            .collect()
    }

    /// A copy with the player's block set to `block` (a probe's edit).
    fn with_player_block(&self, block: i16) -> Combat {
        let mut c = Clone::clone(self);
        c.s.player.block = block;
        c
    }

    /// A copy with `n` added to monster `slot`'s power `power` (a probe's
    /// edit): an official power by name, else a loaded pack power by id,
    /// bound into the copy's binding as a pack monster's start power is.
    fn with_monster_power(&self, slot: usize, power: &str, n: i16) -> PyResult<Combat> {
        if slot >= MAX_MONSTERS || !self.s.monsters[slot].alive() {
            return Err(err(format!("no living monster in slot {slot}")));
        }
        let mut c = Clone::clone(self);
        let p = match self::power(power) {
            Ok(p) => p,
            Err(_) => {
                let (b, p) = registry::bind_power(&self.s.binding, power).map_err(err)?;
                c.s.binding = b;
                p
            }
        };
        c.s.monsters[slot].powers.add(p, n);
        Ok(c)
    }

    /// A copy with the player's HP set to `hp` (a probe's edit): start HP
    /// and max HP stay.
    fn with_player_hp(&self, hp: i16) -> PyResult<Combat> {
        if hp < 1 || hp > self.s.player.max_hp {
            return Err(err(format!("hp {hp} must be in 1..={}", self.s.player.max_hp)));
        }
        let mut c = Clone::clone(self);
        c.s.player.hp = hp;
        Ok(c)
    }

    /// A copy with monster `slot`'s HP and max HP set (a probe's edit).
    fn with_monster_hp(&self, slot: usize, hp: i16, max_hp: i16) -> PyResult<Combat> {
        if slot >= MAX_MONSTERS || !self.s.monsters[slot].alive() {
            return Err(err(format!("no living monster in slot {slot}")));
        }
        if hp < 1 || hp > max_hp {
            return Err(err(format!("hp {hp} must be in 1..={max_hp}")));
        }
        let mut c = Clone::clone(self);
        c.s.monsters[slot].hp = hp;
        c.s.monsters[slot].max_hp = max_hp;
        Ok(c)
    }

    /// A copy with `n` added to the player's official power `power` (a
    /// probe's edit).
    fn with_player_power(&self, power: &str, n: i16) -> PyResult<Combat> {
        let mut c = Clone::clone(self);
        c.s.player.powers.add(self::power(power)?, n);
        Ok(c)
    }

    /// A copy whose RNG is seeded with `seed`, as `decode(bytes, seed)`
    /// seeds it (for states with pack content, which don't encode).
    fn with_seed(&self, seed: u64) -> Combat {
        Combat { s: self.s.clone(), rng: Rng::new(seed) }
    }

    /// The state as a view (docs/specs/real-game-bridge.md): what a player
    /// sees at the start of an action, as plain data that `from_view` turns
    /// back into an equal state. Only at the player's turn with nothing
    /// pending and official content only. `{turn, cards_played_this_turn,
    /// start_hp, times_lost_hp, player {hp, max_hp, block, energy, powers
    /// {name: n}, just_applied [name], relics [(name, counter)], potions
    /// [name]}, hand, draw, discard, exhaust {card: n}, monsters [{name, hp,
    /// max_hp, block, powers, just_applied, moves [intent, previous] (move
    /// positions in the kind's moves, or None), rolled_damage, escaped}]}`;
    /// the monsters by slot, up to
    /// the last one used.
    fn view<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let s = &self.s;
        if s.stage != Stage::PlayerTurn || s.pending.is_some() || s.is_over() {
            return Err(err("a view is only of a running fight at the player's turn with nothing pending"));
        }
        let b = &s.binding;
        // Names as `board` writes them: a pack power by its bare id, a pack
        // card as `gen:<id>`.
        let pname = |pw: Power| b.power_id(pw).map_or_else(|| power_name(pw), str::to_string);
        let powers = |p: &sts_engine::powers::Powers| -> PyResult<(Bound<'py, PyDict>, Vec<String>)> {
            let d = PyDict::new(py);
            let mut just = Vec::new();
            for (pw, n) in p.iter() {
                d.set_item(pname(pw), n)?;
                if p.just_applied(pw) {
                    just.push(pname(pw));
                }
            }
            Ok((d, just))
        };
        let pile = |p: sts_engine::state::PileRef<'_>| -> PyResult<Bound<'py, PyDict>> {
            let d = PyDict::new(py);
            for (c, n) in p.iter() {
                d.set_item(card_name(c, b), n)?;
            }
            Ok(d)
        };
        let v = PyDict::new(py);
        v.set_item("turn", s.turn)?;
        v.set_item("cards_played_this_turn", s.cards_played_this_turn)?;
        v.set_item("start_hp", s.start_hp)?;
        v.set_item("times_lost_hp", s.times_lost_hp)?;
        // A boss fight's mark for a potion barred in one (Smoke Bomb), kept
        // once no slot holds the boss (Slime Boss's split).
        v.set_item("boss_fight", s.boss_fight)?;
        // The level, only above 0 (views from before levels read the same).
        if s.ascension.0 != 0 {
            v.set_item("ascension", s.ascension.0)?;
        }
        let pl = PyDict::new(py);
        pl.set_item("hp", s.player.hp)?;
        pl.set_item("max_hp", s.player.max_hp)?;
        pl.set_item("block", s.player.block)?;
        pl.set_item("energy", s.player.energy)?;
        let (pp, pj) = powers(&s.player.powers)?;
        pl.set_item("powers", pp)?;
        pl.set_item("just_applied", pj)?;
        pl.set_item("relics", s.player.relics.iter().map(|(id, c)| (id.name(), c)).collect::<Vec<_>>())?;
        pl.set_item("potions", s.player.potions.iter().map(|p| p.name()).collect::<Vec<_>>())?;
        v.set_item("player", pl)?;
        v.set_item("hand", pile(s.hand.view())?)?;
        let free = PyDict::new(py);
        for cid in s.free_in_hand.iter() {
            let n: u8 = free.get_item(card_name(cid, b))?.map_or(Ok(0), |x| x.extract())?;
            free.set_item(card_name(cid, b), n + 1)?;
        }
        v.set_item("free", free)?;
        // Cards that cost less than their cost, above 0, this turn (Enlightenment).
        if !s.turn_costs.is_empty() {
            v.set_item("turn_costs", s.turn_costs.iter().map(|(c, k)| (card_name(c, b), k)).collect::<Vec<_>>())?;
        }
        // What the player knows of the draw pile's order (Headbutt):
        // the known cards from the top, and floaters (card, cards above it).
        v.set_item("top", s.top.known().map(|c| card_name(c, b)).collect::<Vec<_>>())?;
        // Sorted by name: the engine keeps them in card-id order, and the ids
        // of changed copies depend on what the process met first.
        let mut floaters: Vec<(&str, u8)> = s.top.floaters().map(|(c, a)| (card_name(c, b), a)).collect();
        floaters.sort();
        v.set_item("top_floaters", floaters)?;
        v.set_item("draw", pile(s.draw())?)?;
        v.set_item("discard", pile(s.discard())?)?;
        v.set_item("exhaust", pile(s.exhaust())?)?;
        let used = s.monsters.iter().rposition(|m| m.kind != sts_engine::monsters::MonsterKind::None).map_or(0, |i| i + 1);
        let mut ms = Vec::new();
        for m in &s.monsters[..used] {
            let d = PyDict::new(py);
            let def = m.def();
            d.set_item("name", def.name)?;
            d.set_item("hp", m.hp)?;
            d.set_item("max_hp", m.max_hp)?;
            d.set_item("block", m.block)?;
            let (mp, mj) = powers(&m.powers)?;
            d.set_item("powers", mp)?;
            d.set_item("just_applied", mj)?;
            // By position in the kind's moves: names repeat (Hexaghost's Sears).
            let mv = |id: u8| (id != sts_engine::monsters::NO_MOVE).then_some(id);
            d.set_item("moves", (mv(m.moves[0]), mv(m.moves[1])))?;
            d.set_item("rolled_damage", m.rolled_damage)?;
            d.set_item("escaped", m.escaped)?;
            let slot = ms.len();
            if s.intent_hidden[slot] != 0 {
                d.set_item("intent_hidden", s.intent_hidden[slot])?;
            }
            ms.push(d);
        }
        v.set_item("monsters", ms)?;
        Ok(v)
    }

    /// A fight from a view (`view`'s form), its RNG seeded with `seed`;
    /// `group` (`"hallway"`, `"elite"`, `"boss"`) is the fight's kind for
    /// each relic's `fights`. Built as `versus` builds one from every card
    /// in the view's piles and its monsters, then set field by field to the
    /// view, at the player's turn with nothing pending. Missing keys take
    /// the fresh fight's value (`start_hp`: the player's HP; a monster's
    /// `moves` and `powers`: its rolled first move and start powers).
    /// `ascension` is the game's level (docs/specs/ascension.md): the
    /// monsters' later moves and the potion slots follow it; default the
    /// view's `ascension`, else 0.
    #[staticmethod]
    #[pyo3(signature = (view, seed=0, group="hallway", ascension=None))]
    fn from_view(view: &Bound<'_, PyDict>, seed: u64, group: &str, ascension: Option<u8>) -> PyResult<Combat> {
        fn get<'py, T>(d: &Bound<'py, PyDict>, k: &str) -> PyResult<Option<T>>
        where
            T: FromPyObjectOwned<'py>,
            for<'a> <T as FromPyObject<'a, 'py>>::Error: Into<PyErr>,
        {
            match d.get_item(k)? {
                Some(v) if !v.is_none() => match v.extract::<T>() {
                    Ok(x) => Ok(Some(x)),
                    Err(e) => {
                        let e: PyErr = e.into();
                        Err(err(format!("view key {k:?}: {e}")))
                    }
                },
                _ => Ok(None),
            }
        }
        // `[[a, b], ...]` (lists or tuples: a view that went through JSON).
        fn pairs<'py, A, B>(d: &Bound<'py, PyDict>, k: &str) -> PyResult<Vec<(A, B)>>
        where
            A: FromPyObjectOwned<'py>,
            B: FromPyObjectOwned<'py>,
            for<'a> <A as FromPyObject<'a, 'py>>::Error: Into<PyErr>,
            for<'a> <B as FromPyObject<'a, 'py>>::Error: Into<PyErr>,
        {
            let items: Vec<Bound<'py, PyAny>> = get(d, k)?.unwrap_or_default();
            let bad = |e: PyErr| err(format!("view key {k:?}: {e}"));
            items
                .iter()
                .map(|x| {
                    let a = x.get_item(0)?.extract::<A>().map_err(|e| bad(e.into()))?;
                    let b = x.get_item(1)?.extract::<B>().map_err(|e| bad(e.into()))?;
                    Ok((a, b))
                })
                .collect()
        }
        fn need<'py, T>(d: &Bound<'py, PyDict>, k: &str) -> PyResult<T>
        where
            T: FromPyObjectOwned<'py>,
            for<'a> <T as FromPyObject<'a, 'py>>::Error: Into<PyErr>,
        {
            get(d, k)?.ok_or_else(|| err(format!("view has no {k:?}")))
        }
        let piles: Vec<(&str, HashMap<String, u8>)> =
            ["hand", "draw", "discard", "exhaust"].iter().map(|&k| Ok((k, get(view, k)?.unwrap_or_default()))).collect::<PyResult<_>>()?;
        // A copy changed in this fight is named `<card>{cost=N/combat,damage=N/combat}`
        // (registry::changed_copy): bound as its card, then changed.
        fn split_marks(name: &str) -> PyResult<(&str, Option<i16>, Option<i8>)> {
            let Some((base, marks)) = name.strip_suffix('}').and_then(|n| n.split_once('{')) else {
                return Ok((name, None, None));
            };
            let (mut damage, mut cost) = (None, None);
            for m in marks.split(',') {
                let bad = || err(format!("card {name:?}: unknown mark {m:?}"));
                let (k, v) = m.strip_suffix("/combat").and_then(|m| m.split_once('=')).ok_or_else(bad)?;
                match k {
                    "damage" => damage = Some(v.parse().map_err(|_| bad())?),
                    "cost" => cost = Some(v.parse().map_err(|_| bad())?),
                    _ => return Err(bad()),
                }
            }
            Ok((base, damage, cost))
        }
        let mut deck = Vec::new();
        for (_, p) in &piles {
            for (name, &n) in p {
                for _ in 0..n {
                    deck.push(split_marks(name)?.0.to_string());
                }
            }
        }
        deck.sort();
        let player: Bound<'_, PyDict> = need(view, "player")?;
        let monsters: Vec<Bound<'_, PyDict>> = need(view, "monsters")?;
        let names: Vec<String> = monsters.iter().map(|m| need(m, "name")).collect::<PyResult<_>>()?;
        let relics: Vec<(String, i16)> = pairs(&player, "relics")?;
        let potions: Vec<String> = get(&player, "potions")?.unwrap_or_default();
        let hp: i16 = need(&player, "hp")?;
        let max_hp: i16 = need(&player, "max_hp")?;
        let relic_list = relics.iter().map(|(n, c)| RelicArg::WithCounter(n.clone(), *c)).collect();
        // The deck's card ids by name, bound as `versus` binds them.
        let (ids, binding) = bind_deck(&deck)?;
        let mut card_ids: HashMap<String, CardId> = deck.iter().cloned().zip(ids).collect();
        for (_, p) in &piles {
            for name in p.keys() {
                let (base, damage, cost) = split_marks(name)?;
                if damage.is_some() || cost.is_some() {
                    let b = card_ids[base];
                    let def = binding.def(b);
                    let o = registry::Overrides { damage, level: def.level, cost };
                    card_ids.insert(name.clone(), registry::changed_copy(b, def, o).map_err(err)?);
                }
            }
        }
        let ascension = match ascension {
            Some(a) => a,
            None => get(view, "ascension")?.unwrap_or(0),
        };
        let mut c = Combat::versus(deck, names, seed, Some(hp), Some(max_hp), "ironclad", false, Some(relic_list), group, false, Some(potions), ascension, None)?;
        let s = &mut c.s;
        // An official power by name, else a loaded pack power by id, bound
        // into the fight's binding (as `with_monster_power` binds one).
        let power_of = |s: &mut CombatState, name: &str| -> PyResult<Power> {
            match self::power(name) {
                Ok(p) => Ok(p),
                Err(_) => {
                    let (b, p) = registry::bind_power(&s.binding, name).map_err(err)?;
                    s.binding = b;
                    Ok(p)
                }
            }
        };
        let set_powers = |s: &mut CombatState, who: Option<usize>, d: &Bound<'_, PyDict>| -> PyResult<()> {
            let Some(amounts): Option<HashMap<String, i16>> = get(d, "powers")? else {
                return Ok(()); // no "powers": the fresh fight's
            };
            let just: Vec<String> = get(d, "just_applied")?.unwrap_or_default();
            let mut fresh = sts_engine::powers::Powers::default();
            for (name, n) in amounts {
                fresh.add(power_of(s, &name)?, n);
            }
            for name in just {
                fresh.set_just_applied(power_of(s, &name)?);
            }
            match who {
                None => s.player.powers = fresh,
                Some(slot) => s.monsters[slot].powers = fresh,
            }
            Ok(())
        };
        s.player.hp = hp;
        s.player.max_hp = max_hp;
        s.player.block = need(&player, "block")?;
        s.player.energy = need(&player, "energy")?;
        set_powers(s, None, &player)?;
        // By name: the fight keeps only the relics that act in its kind
        // (Pantograph only in boss fights), so positions differ from the view's.
        for i in 0..s.player.relics.len() {
            let name = s.player.relics.id(i).name();
            if let Some((_, ctr)) = relics.iter().find(|(n, _)| n == name) {
                s.player.relics.set_counter(i, *ctr);
            }
        }
        for (k, p) in &piles {
            let mut pile = sts_engine::state::Pile::default();
            for (name, &n) in p {
                pile.add(card_ids[name], n);
            }
            match *k {
                "hand" => {
                    s.hand.clear();
                    for (cid, n) in pile.iter() {
                        s.hand.add(cid, n);
                    }
                }
                "draw" => s.set_draw(pile),
                "discard" => s.piles.set(sts_engine::state::Run::Discard, pile),
                _ => s.piles.set(sts_engine::state::Run::Exhaust, pile),
            }
        }
        for (slot, m) in monsters.iter().enumerate() {
            set_powers(s, Some(slot), m)?;
            let mon = &mut s.monsters[slot];
            mon.hp = need(m, "hp")?;
            mon.max_hp = need(m, "max_hp")?;
            mon.block = need(m, "block")?;
            let def = mon.def();
            let id = |pos: Option<u8>| -> PyResult<u8> {
                match pos {
                    None => Ok(sts_engine::monsters::NO_MOVE),
                    Some(i) if (i as usize) < def.moves.len() => Ok(i),
                    Some(i) => Err(err(format!("{} has no move {i}", def.name))),
                }
            };
            // No "moves": the fresh fight's rolled first moves.
            if let Some(moves) = get::<Vec<Option<u8>>>(m, "moves")? {
                let [now, before] = moves[..] else {
                    return Err(err(format!("{}: moves is [intent, previous]", def.name)));
                };
                mon.moves = [id(now)?, id(before)?];
            }
            mon.rolled_damage = get(m, "rolled_damage")?.unwrap_or(mon.rolled_damage);
            mon.escaped = get(m, "escaped")?.unwrap_or(false);
        }
        // Runic Dome (docs/research/build-plans-2026-11-14/frozen-eye-runic-dome.md):
        // a hidden move ("move_hidden", "moves" then the history: the move
        // used last and the one before) rolls when the monster acts, with
        // "allies_at_roll" (default: another monster lives now); one that
        // can only be one move is set and shown. "rolled_hidden": a rolled
        // attack amount not seen yet. "intent_hidden" sets the bits as
        // `Combat.view` writes them.
        use sts_engine::state::{HIDDEN_ALLIES, HIDDEN_MOVE, HIDDEN_ROLLED};
        for (slot, m) in monsters.iter().enumerate() {
            let mut bits: u8 = get(m, "intent_hidden")?.unwrap_or(0);
            if get::<bool>(m, "move_hidden")?.unwrap_or(false) {
                let allies = get::<bool>(m, "allies_at_roll")?.unwrap_or_else(|| s.living_slots().any(|i| i != slot));
                bits |= HIDDEN_MOVE | if allies { HIDDEN_ALLIES } else { 0 };
            }
            if get::<bool>(m, "rolled_hidden")?.unwrap_or(false) {
                bits |= HIDDEN_ROLLED;
            }
            s.intent_hidden[slot] = bits;
            if bits & HIDDEN_MOVE != 0 {
                if let [(mv, _)] = s.intent_distribution(slot)[..] {
                    s.set_monster_move(slot, mv);
                }
            }
        }
        s.turn = get(view, "turn")?.unwrap_or(s.turn);
        s.cards_played_this_turn = get(view, "cards_played_this_turn")?.unwrap_or(0);
        s.start_hp = get(view, "start_hp")?.unwrap_or(hp);
        s.times_lost_hp = get(view, "times_lost_hp")?.unwrap_or(0);
        if let Some(b) = get::<bool>(view, "boss_fight")? {
            s.boss_fight = b;
        }
        s.stage = Stage::PlayerTurn;
        s.pending = None;
        s.free_in_hand = Default::default();
        let free: HashMap<String, u8> = get(view, "free")?.unwrap_or_default();
        for (name, n) in free {
            let c = *card_ids.get(&name).ok_or_else(|| err(format!("free card {name:?} not in the piles")))?;
            for _ in 0..n {
                s.free_in_hand.add(c);
            }
        }
        s.turn_costs = Default::default();
        let costs: Vec<(String, u8)> = pairs(view, "turn_costs")?;
        for (name, k) in costs {
            let c = *card_ids.get(&name).ok_or_else(|| err(format!("turn_costs card {name:?} not in the piles")))?;
            if !s.turn_costs.add(c, k) {
                return Err(err("turn_costs: a cost of 0 or more marks than a hand holds"));
            }
        }
        s.cost_rolls = Default::default();
        s.top_queue = Default::default();
        s.top = Default::default();
        let known: Vec<String> = get(view, "top")?.unwrap_or_default();
        let floaters: Vec<(String, u8)> = pairs(view, "top_floaters")?;
        if !known.is_empty() || !floaters.is_empty() {
            let id = |n: &String| card_ids.get(n).copied().ok_or_else(|| err(format!("top card {n:?} not in the piles")));
            let known: Vec<CardId> = known.iter().map(id).collect::<PyResult<_>>()?;
            let floaters: Vec<(CardId, u8)> = floaters.iter().map(|(n, a)| Ok((id(n)?, *a))).collect::<PyResult<_>>()?;
            s.top = sts_engine::state::Top::from_parts(&known, &floaters).ok_or_else(|| err("top: not a draw-pile knowledge"))?;
            if !s.top.within(s.draw()) {
                return Err(err("top: cards or cards above them the draw pile doesn't hold"));
            }
        }
        s.deferred_block = [0; MAX_MONSTERS];
        s.block_broken = [0; MAX_MONSTERS];
        s.card_hp_losses = 0;
        s.unfired_exhausts = 0;
        s.owed_draw = 0;
        s.unfired_draws = 0;
        s.unfired_curse_draws = 0;
        s.offer = Default::default();
        Ok(c)
    }

    /// The counterfactual state price (docs/specs/counterfactual-state-price.md):
    /// `[(who, power, amount, price in HP)]`, `who` "player" or the monster slot.
    #[pyo3(signature = (k=4))]
    fn cf_prices(&self, py: Python<'_>, k: u32) -> PyResult<Vec<(Py<PyAny>, String, i16, f32)>> {
        sts_engine::cf::cf_prices(&self.s, k)
            .into_iter()
            .map(|(who, p, n, v)| {
                let w = match who {
                    sts_engine::Who::Player => "player".into_pyobject(py)?.into_any().unbind(),
                    sts_engine::Who::Monster(i) => i.into_pyobject(py)?.into_any().unbind(),
                };
                Ok((w, power_name(p), n, v))
            })
            .collect()
    }

    /// The sum of `cf_prices`, in HP.
    #[pyo3(signature = (k=4))]
    fn cf_price(&self, k: u32) -> f32 {
        sts_engine::cf::cf_price(&self.s, k)
    }

    /// The greedy policy played on from here for at most `rounds` rounds
    /// (chance sampled with `Rng::new(seed)`): `(HP lost, enemy HP removed,
    /// over)`.
    fn greedy_rollout(&self, rounds: u32, seed: u64) -> (i32, i32, bool) {
        let mut rng = Rng::new(seed);
        let mut t = self.s.clone();
        t.advance(&mut rng);
        for _ in 0..rounds {
            if t.is_over() {
                break;
            }
            sts_engine::cf::greedy_round(&mut t, &mut rng);
        }
        ((self.s.player.hp - t.player.hp) as i32, sts_engine::cf::enemy_hp(&self.s) - sts_engine::cf::enemy_hp(&t), t.is_over())
    }

    /// The heuristic's `(estimated score, HP loss from here, rounds left)`.
    fn heuristic_parts(&self) -> (f32, f32, f32) {
        (estimate(&self.s), hp_loss_estimate(&self.s), turns_left_estimate(&self.s))
    }

    /// An exact copy, RNG included.
    fn clone(&self) -> Combat {
        Clone::clone(self)
    }

    /// The state as compact bytes (`decode` rebuilds it); the RNG is not
    /// included.
    fn encode<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyBytes>> {
        if self.s.has_generated() {
            return Err(err("a combat with generated content has no state encoding"));
        }
        Ok(PyBytes::new(py, &sts_engine::codec::encode(&self.s)))
    }

    /// A combat from `encode`'s bytes, its RNG seeded with `seed`.
    #[staticmethod]
    #[pyo3(signature = (data, seed=0))]
    fn decode(data: &[u8], seed: u64) -> PyResult<Combat> {
        let s = sts_engine::codec::try_decode(data).ok_or_else(|| err("not a state encoding of this codec version"))?;
        Ok(Combat { s, rng: Rng::new(seed) })
    }
}

/// `known_*` lists: cards, powers, triggers, conditions, effects.
type KnownLists = (Option<Vec<String>>, Option<Vec<String>>, Option<Vec<String>>, Option<Vec<String>>, Option<Vec<String>>);
/// A net's layout: `columns`, `row_kinds`, `piles`.
type Layout = (Option<Columns>, Option<Vec<String>>, Option<Vec<String>>);

/// An encoder for `card_repr` and the `known_*` lists, writing `layout`.
/// Lookahead columns are on when `lookahead` says so or the layout's monster
/// columns name any (a net trained with them); rate columns likewise with
/// `rates` and the layout's player columns, and the start-HP column with
/// `start_hp`.
#[allow(clippy::too_many_arguments)]
fn make_encoder(
    card_repr: &str,
    known: KnownLists,
    layout: Layout,
    test_inject: bool,
    lookahead: bool,
    rates: bool,
    start_hp: bool,
    extra_rows: bool,
) -> PyResult<Encoder> {
    let (known_cards, known_powers, known_triggers, known_conditions, known_effects) = known;
    let repr = match card_repr {
        "effects" => CardRepr::Effects,
        "ids" => CardRepr::Ids,
        _ => return Err(err(format!("card_repr must be \"effects\" or \"ids\", not {card_repr:?}"))),
    };
    let vocab = Vocab {
        cards: known_cards.map(|v| v.iter().map(|n| card(n)).collect::<PyResult<_>>()).transpose()?,
        powers: known_powers.map(|v| v.iter().map(|n| power(n)).collect::<PyResult<_>>()).transpose()?,
        triggers: names_in("trigger", known_triggers, &trigger_names())?,
        conditions: names_in("condition", known_conditions, &condition_names())?,
        effects: names_in("effect", known_effects, &effect_names())?,
    };
    let (columns, row_kinds, piles) = layout;
    let lookahead = lookahead || columns.as_ref().and_then(|c| c.get("monsters")).is_some_and(|m| has_lookahead(m));
    let rates = rates || columns.as_ref().and_then(|c| c.get("player")).is_some_and(|m| has_rates(m));
    let start_hp = start_hp || columns.as_ref().and_then(|c| c.get("player")).is_some_and(|m| has_start_hp(m));
    // The opt-in row kinds are on when asked for or when the layout lists one.
    let extra_rows = extra_rows || row_kinds.as_ref().is_some_and(|l| l.iter().any(|k| EXTRA_KINDS.contains(&k.as_str())));
    let mut enc = Encoder::new(repr, &vocab).with_lookahead(lookahead).with_rates(rates).with_start_hp(start_hp).with_extra_rows(extra_rows);
    if test_inject {
        enc.inject_test();
    }
    enc.set_layout(layout_columns(columns)?, row_kinds, piles).map_err(err)?;
    Ok(enc)
}

fn batch_dict<'py>(py: Python<'py>, enc: &Encoder, b: &Batch) -> PyResult<Bound<'py, PyDict>> {
    let shape = |e: numpy::ndarray::ShapeError| err(e.to_string());
    let [dp, dm, dc, dr] = enc.layout_dims();
    let n_cards = b.card_count.len();
    let d = PyDict::new(py);
    d.set_item("player", Array2::from_shape_vec((b.n, dp), b.player.clone()).map_err(shape)?.into_pyarray(py))?;
    d.set_item(
        "monsters",
        Array3::from_shape_vec((b.n, MAX_MONSTERS, dm), b.monsters.clone()).map_err(shape)?.into_pyarray(py),
    )?;
    d.set_item("cards", Array2::from_shape_vec((n_cards, dc), b.cards.clone()).map_err(shape)?.into_pyarray(py))?;
    d.set_item("card_count", Array1::from_vec(b.card_count.clone()).into_pyarray(py))?;
    d.set_item("card_pile", Array1::from_vec(b.card_pile.clone()).into_pyarray(py))?;
    d.set_item("card_state", Array1::from_vec(b.card_state.clone()).into_pyarray(py))?;
    let n_rows = b.row_card.len();
    d.set_item("rows", Array2::from_shape_vec((n_rows, dr), b.rows.clone()).map_err(shape)?.into_pyarray(py))?;
    d.set_item("row_card", Array1::from_vec(b.row_card.clone()).into_pyarray(py))?;
    d.set_item("row_entity", Array1::from_vec(b.row_entity.clone()).into_pyarray(py))?;
    d.set_item("row_state", Array1::from_vec(b.row_state.clone()).into_pyarray(py))?;
    Ok(d)
}

/// Adds `heuristic` [B]: the hand-written evaluator's estimate of each state
/// (search's leaf value with evaluator "heuristic"; exact score when over),
/// and the scalars learned play's HP-loss nets need: `heuristic_hp_loss`
/// (the HP it expects the player to lose from here), `hp`, `start_hp`,
/// `max_hp` and `win_heal` (end-of-combat healing).
fn set_heuristic(py: Python<'_>, d: &Bound<'_, PyDict>, states: &[&CombatState]) -> PyResult<()> {
    let col = |f: &dyn Fn(&CombatState) -> f32| Array1::from_vec(states.iter().map(|s| f(s)).collect());
    d.set_item("heuristic", col(&|s| estimate(s)).into_pyarray(py))?;
    d.set_item("heuristic_hp_loss", col(&|s| hp_loss_estimate(s)).into_pyarray(py))?;
    d.set_item("hp", col(&|s| s.player.hp as f32).into_pyarray(py))?;
    d.set_item("start_hp", col(&|s| s.start_hp as f32).into_pyarray(py))?;
    d.set_item("max_hp", col(&|s| s.player.max_hp as f32).into_pyarray(py))?;
    d.set_item("win_heal", col(&|s| s.win_heal_scaled() as f32).into_pyarray(py))
}

/// Turns combats into evaluator input. `card_repr` is "effects" (cards as
/// effect-primitive vectors) or "ids" (one-hot card id, with an unknown
/// slot for cards outside `known_cards`). Powers outside `known_powers`
/// land in each power block's `unknown` dimension; in effects mode hook
/// powers are `rows` instead (see `features.rs`). `known_triggers`,
/// `known_conditions` and `known_effects` fix the rows' trigger and condition
/// one-hots (others go to `unknown`) and the effect scalars (others are
/// dropped). Every list gives its names' dimension order; `None` means all,
/// in engine order. `vocab` returns the lists in use, for a net's meta.
///
/// A net's own layout (the contract with the net, docs/decisions.md "Contract as built"):
/// `columns` (`{"player", "monsters", "cards", "rows"}`: column names in
/// the net's order) writes each path's columns in that order, 0 for a name
/// the encoder lacks, leaving out the ones the net lacks; `row_kinds` writes
/// only rows of those kinds; `piles` gives `card_pile` as the index in that
/// list, a pile it lacks as its parent's (`PILE_PARENTS`). `None` keeps the
/// encoder's own. `test_inject` (tests only) adds a `test` row kind and
/// pile (see features.rs).
#[pyclass(module = "sts", name = "Features", frozen, from_py_object)]
#[derive(Clone)]
struct PyFeatures {
    enc: Arc<Encoder>,
}

#[pymethods]
impl PyFeatures {
    #[new]
    #[pyo3(signature = (card_repr="effects", known_cards=None, known_powers=None, known_triggers=None, known_conditions=None, known_effects=None, columns=None, row_kinds=None, piles=None, test_inject=false, lookahead=false, rates=false, start_hp=false, extra_rows=false, shown_numbers=false, exhaust_hidden=false))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        card_repr: &str,
        known_cards: Option<Vec<String>>,
        known_powers: Option<Vec<String>>,
        known_triggers: Option<Vec<String>>,
        known_conditions: Option<Vec<String>>,
        known_effects: Option<Vec<String>>,
        columns: Option<Columns>,
        row_kinds: Option<Vec<String>>,
        piles: Option<Vec<String>>,
        test_inject: bool,
        lookahead: bool,
        rates: bool,
        start_hp: bool,
        extra_rows: bool,
        shown_numbers: bool,
        exhaust_hidden: bool,
    ) -> PyResult<PyFeatures> {
        let known = (known_cards, known_powers, known_triggers, known_conditions, known_effects);
        let enc = make_encoder(card_repr, known, (columns, row_kinds, piles), test_inject, lookahead, rates, start_hp, extra_rows)?
            .with_shown_numbers(shown_numbers)
            .with_exhaust_hidden(exhaust_hidden);
        Ok(PyFeatures { enc: Arc::new(enc) })
    }

    /// Row kinds this encoder writes.
    #[getter]
    fn row_kinds(&self) -> Vec<&'static str> {
        self.enc.row_kinds()
    }

    /// Whether the opt-in row kinds (static, countdown, replacement,
    /// pattern) are written.
    #[getter]
    fn extra_rows(&self) -> bool {
        self.enc.extra_rows()
    }

    /// Whether the monster lookahead columns are on.
    #[getter]
    fn lookahead(&self) -> bool {
        self.enc.lookahead()
    }

    /// Whether the rate columns are on.
    #[getter]
    fn rates(&self) -> bool {
        self.enc.rates()
    }

    /// Whether the start-HP column is on.
    #[getter]
    fn start_hp(&self) -> bool {
        self.enc.start_hp()
    }

    /// Whether card damage and block are written as the game shows them.
    #[getter]
    fn shown_numbers(&self) -> bool {
        self.enc.shown_numbers()
    }

    /// Whether the exhaust pile's counts are written as 0.
    #[getter]
    fn exhaust_hidden(&self) -> bool {
        self.enc.exhaust_hidden()
    }

    /// Piles this encoder writes, before any `piles`.
    #[getter]
    fn piles(&self) -> Vec<&'static str> {
        self.enc.piles()
    }

    /// `{"cards", "powers", "triggers", "conditions", "effects"}`: the
    /// vocabularies in use, in dimension order.
    #[getter]
    fn vocab(&self) -> HashMap<&'static str, Vec<String>> {
        self.enc.vocab_names().into_iter().collect()
    }

    /// Batch dict: player [B,P], monsters [B,5,M], cards [N,C], card_count
    /// [N], card_pile [N] (index into PILES), card_state [N] (index into B),
    /// rows [R,D], row_card [R] (index into N or -1), row_entity [R]
    /// (B * ENTITIES + entity, or -1), row_state [R]. With `heuristic=True`
    /// also heuristic [B]: the hand-written evaluator's estimate (not a
    /// feature).
    #[pyo3(signature = (combats, heuristic=false))]
    fn encode<'py>(&self, py: Python<'py>, combats: Vec<PyRef<'py, Combat>>, heuristic: bool) -> PyResult<Bound<'py, PyDict>> {
        let states: Vec<&CombatState> = combats.iter().map(|c| &c.s).collect();
        let d = batch_dict(py, &self.enc, &self.enc.encode(&states))?;
        if heuristic {
            set_heuristic(py, &d, &states)?;
        }
        Ok(d)
    }

    #[getter]
    fn dims(&self) -> HashMap<&'static str, usize> {
        let [dp, dm, dc, dr] = self.enc.layout_dims();
        HashMap::from([
            ("player", dp),
            ("monster", dm),
            ("card", dc),
            ("row", dr),
            ("piles", self.enc.n_piles()),
            ("entities", ENTITIES),
        ])
    }

    #[getter]
    fn card_repr(&self) -> &'static str {
        match self.enc.repr {
            CardRepr::Effects => "effects",
            CardRepr::Ids => "ids",
        }
    }

    #[getter]
    fn player_names(&self) -> Vec<String> {
        let [v, ..] = self.enc.layout_names();
        v
    }

    #[getter]
    fn monster_names(&self) -> Vec<String> {
        let [_, v, ..] = self.enc.layout_names();
        v
    }

    #[getter]
    fn card_names(&self) -> Vec<String> {
        let [.., v, _] = self.enc.layout_names();
        v
    }

    #[getter]
    fn row_names(&self) -> Vec<String> {
        let [.., v] = self.enc.layout_names();
        v
    }
}

/// A trained `stsnet.ValueNet` scored in Rust (build with
/// `stsnet.rust_evaluator`): `weights` is its state dict as float32 arrays,
/// `norm` the normaliser's `{key: (mean, std)}`, and `config` the features
/// it was trained on (`card_repr`, `known_*` as for `Features`) plus its
/// head: `hp_loss` (bool) and, for an HP-loss net, `bin_rep` (the HP lost
/// each histogram bin stands for). Layer sizes come from the weights.
/// `hp_bonus` (c, default 0: off) adds `c x min(1, max(0, score / 2)) x
/// (HP - start HP)` to every score: the HP price nets trained without a
/// start-HP column lack (results doc "HP bonus at the leaves").
/// `score_rule` (an HP-loss net only; absent: the engine's score) is
/// `{"kind": "survive", "c": C, "w": W}`: a win scores C + W x end HP / 100
/// (docs/specs/survival-score.md); search then scores finished combats the
/// same way. It can't be combined with `hp_bonus`.
/// `enemy_strength_price` (k, default 0: off) subtracts `k x min(1, max(0,
/// score / 2)) x (living monsters' Strength)` from every score
/// (docs/specs/enemy-strength-price.md); also not with a survive rule.
/// `strength_hits_price` (k, default 0: off) subtracts `k x min(1, max(0,
/// score / 2)) x heuristic::strength_hits_left` (living monsters' Strength x
/// the hits it will still land; docs/specs/strength-hits-price.md); also
/// not with a survive rule.
/// `hp_end_bonus` (c, default 0: off) adds `c x 80 / max HP x min(1, max(0,
/// score / 2)) x (min(HP + win heal, max HP) - start HP)` to every score (c
/// prices one HP at 80 max HP, a share of the HP bar at any; ideas#75), and search
/// prices finished combats the same way (docs/specs/end-hp-bonus.md); not
/// with `hp_bonus` or a survive rule.
/// `draw_k` (k, default 0: off) makes search score end-of-turn leaves after
/// k sampled draws, at the next decision (docs/specs/draw-leaf.md).
/// `turn_start_leaf` (default false) makes search score end-of-turn leaves
/// after the player's turn-start hooks that need no chance
/// (docs/specs/turn-start-leaf.md).
/// `leaf_clear_block` (default false) makes search score end-of-turn leaves
/// with the player's block at 0 (docs/specs/leaf-clear-block.md).
/// `projected_ticks` (k, default 0: off) makes search score end-of-turn
/// leaves with once-a-turn Strength and Dexterity hooks applied k more
/// times (docs/specs/projected-leaf.md); with `projected_debuffs` (default
/// false) monsters' once-a-turn Weak, Frail and Vulnerable on the player too
/// (docs/specs/recurring-debuff-leaf.md).
/// `tie_break` (default false) makes search break exact value ties toward
/// the sooner win, then lower enemy HP (docs/specs/finish-faster-tiebreak.md).
/// `shown_numbers` and `exhaust_hidden` (default false) are encoder flags:
/// card damage and block as the game shows them, the exhaust pile's counts
/// as 0 (docs/specs/shown-card-numbers.md).
#[pyclass(module = "sts", name = "NetEvaluator", frozen, from_py_object)]
#[derive(Clone)]
struct PyNet {
    net: Arc<Net>,
    enc: Arc<Encoder>,
    prices: Prices,
}

/// Search-time prices a `NetEvaluator` adds to its net's scores (see `PyNet`).
#[derive(Clone, Copy, Debug, Default, PartialEq)]
struct Prices {
    hp_bonus: f32,
    enemy_strength: f32,
    hp_end: f32,
    strength_hits: f32,
    /// Not a price: the search's draw leaf (`SearchConfig::draw_k`).
    draw_k: u32,
    /// Not a price: the search's turn-start leaf (`SearchConfig::turn_start_leaf`).
    turn_start_leaf: bool,
    /// Not a price: the search's leaf clear block (`SearchConfig::leaf_clear_block`).
    leaf_clear_block: bool,
    /// Not a price: the search's projected leaf (`SearchConfig::projected_ticks`).
    projected_ticks: u8,
    /// Not a price: the search's projected debuffs (`SearchConfig::projected_debuffs`).
    projected_debuffs: bool,
    /// Not a price: the search's tie break (`SearchConfig::tie_break`).
    tie_break: bool,
    /// Caps an unfinished leaf's net value at the score of a win at the HP it
    /// can still reach (HP now + the win heal, at most max HP), so no leaf
    /// outscores or ties an immediate win at the same HP (`@wc1`; backlog 82).
    win_cap: bool,
}

/// A `NetEvaluator` config's `score_rule` (see `PyNet`): absent, None or
/// kind "engine" is the engine's score; kind "survive" takes `c` (default
/// 1.0) and `w` (default 2.0).
fn score_rule(v: Option<Bound<'_, PyAny>>) -> PyResult<ScoreRule> {
    let Some(v) = v.filter(|v| !v.is_none()) else { return Ok(ScoreRule::Engine) };
    let d = v.cast::<PyDict>().map_err(|_| err("score_rule must be a dict"))?;
    let kind: String = match d.get_item("kind")? {
        Some(k) => k.extract()?,
        None => "engine".to_string(),
    };
    let num = |k: &str, default: f32| -> PyResult<f32> {
        match d.get_item(k)? {
            Some(x) if !x.is_none() => x.extract(),
            _ => Ok(default),
        }
    };
    match kind.as_str() {
        "engine" => Ok(ScoreRule::Engine),
        "survive" => Ok(ScoreRule::Survive { c: num("c", 1.0)?, w: num("w", 2.0)? }),
        _ => Err(err(format!("unknown score rule kind {kind:?} (engine, survive)"))),
    }
}

/// Adds the `hp_bonus`, `enemy_strength_price` and `hp_end_bonus` terms to `scores` of
/// `states` (see `PyNet`); both off leaves the scores bit-identical.
fn add_prices(scores: &mut [f32], states: &[&CombatState], p: Prices) {
    if p == Prices::default() {
        return;
    }
    for (v, s) in scores.iter_mut().zip(states) {
        if p.win_cap {
            let reach = (s.player.hp + s.win_heal_scaled()).min(s.player.max_hp);
            // A margin of 0.1 HP below the win, so an unfinished leaf never ties it
            // (a tie falls to the first option, which was not the kill).
            *v = v.min(2.0 - (s.start_hp - reach).max(0) as f32 / 100.0 - 0.001);
        }
        let f = (*v / 2.0).clamp(0.0, 1.0);
        let strength: i32 = s.monsters.iter().filter(|m| m.alive()).map(|m| m.powers.get(Power::Strength) as i32).sum();
        *v += p.hp_bonus * f * (s.player.hp - s.start_hp) as f32 - p.enemy_strength * f * strength as f32;
        if p.strength_hits != 0.0 {
            *v -= p.strength_hits * f * strength_hits_left(s);
        }
        if p.hp_end != 0.0 {
            let end = (s.player.hp + s.win_heal_scaled()).min(s.player.max_hp);
            *v += p.hp_end * end_hp_scale(s) * f * (end - s.start_hp) as f32;
        }
    }
}

#[pymethods]
impl PyNet {
    #[new]
    fn new(weights: &Bound<'_, PyDict>, norm: HashMap<String, (Vec<f32>, Vec<f32>)>, config: &Bound<'_, PyDict>) -> PyResult<PyNet> {
        let mut state: HashMap<String, Tensor> = HashMap::new();
        for (k, v) in weights.iter() {
            let a: PyReadonlyArrayDyn<f32> = v.extract().map_err(|_| err(format!("weight {k} must be a float32 array")))?;
            state.insert(k.extract()?, (a.as_array().iter().copied().collect(), a.shape().to_vec()));
        }
        let get = |k: &str| config.get_item(k);
        let opt = |k: &str| -> PyResult<Option<Vec<String>>> {
            match get(k)? {
                Some(v) if !v.is_none() => Ok(Some(v.extract()?)),
                _ => Ok(None),
            }
        };
        let repr: String = match get("card_repr")? {
            Some(v) => v.extract()?,
            None => "effects".to_string(),
        };
        let columns: Option<Columns> = match get("columns")? {
            Some(v) if !v.is_none() => Some(v.extract()?),
            _ => None,
        };
        let known = (opt("known_cards")?, opt("known_powers")?, opt("known_triggers")?, opt("known_conditions")?, opt("known_effects")?);
        let lookahead = match get("lookahead")? {
            Some(v) => v.is_truthy()?,
            None => false,
        };
        let rates = match get("rates")? {
            Some(v) => v.is_truthy()?,
            None => false,
        };
        let start_hp = match get("start_hp")? {
            Some(v) => v.is_truthy()?,
            None => false,
        };
        let flag = |k: &str| -> PyResult<bool> {
            match get(k)? {
                Some(v) => v.is_truthy(),
                None => Ok(false),
            }
        };
        let enc = make_encoder(&repr, known, (columns, opt("row_kinds")?, opt("piles")?), false, lookahead, rates, start_hp, false)?
            .with_shown_numbers(flag("shown_numbers")?)
            .with_exhaust_hidden(flag("exhaust_hidden")?);
        let hp_loss = match get("hp_loss")? {
            Some(v) => v.is_truthy()?,
            None => false,
        };
        let price = |k: &str| -> PyResult<f32> {
            match get(k)? {
                Some(v) if !v.is_none() => v.extract(),
                _ => Ok(0.0),
            }
        };
        let prices = Prices { hp_bonus: price("hp_bonus")?, enemy_strength: price("enemy_strength_price")?, hp_end: price("hp_end_bonus")?,
                              strength_hits: price("strength_hits_price")?,
                              draw_k: match get("draw_k")? {
                                  Some(v) if !v.is_none() => v.extract()?,
                                  _ => 0,
                              },
                              turn_start_leaf: match get("turn_start_leaf")? {
                                  Some(v) => v.is_truthy()?,
                                  None => false,
                              },
                              leaf_clear_block: match get("leaf_clear_block")? {
                                  Some(v) => v.is_truthy()?,
                                  None => false,
                              },
                              projected_ticks: match get("projected_ticks")? {
                                  Some(v) if !v.is_none() => v.extract()?,
                                  _ => 0,
                              },
                              projected_debuffs: match get("projected_debuffs")? {
                                  Some(v) => v.is_truthy()?,
                                  None => false,
                              },
                              tie_break: match get("tie_break")? {
                                  Some(v) => v.is_truthy()?,
                                  None => false,
                              },
                              win_cap: match get("win_cap")? {
                                  Some(v) => v.is_truthy()?,
                                  None => false,
                              } };
        if prices.hp_bonus != 0.0 && prices.hp_end != 0.0 {
            return Err(err("hp_bonus can't be combined with hp_end_bonus (both price HP)"));
        }
        let rule = score_rule(get("score_rule")?)?;
        if rule != ScoreRule::Engine && !hp_loss {
            return Err(err("a survive score rule needs an HP-loss net"));
        }
        if rule != ScoreRule::Engine && prices.hp_bonus != 0.0 {
            return Err(err("hp_bonus can't be combined with a survive score rule (it would price HP twice)"));
        }
        if rule != ScoreRule::Engine && prices.hp_end != 0.0 {
            return Err(err("hp_end_bonus can't be combined with a survive score rule (it would price HP twice)"));
        }
        if rule != ScoreRule::Engine && prices.strength_hits != 0.0 {
            return Err(err("strength_hits_price can't be combined with a survive score rule (it would price future HP twice)"));
        }
        if rule != ScoreRule::Engine && prices.enemy_strength != 0.0 {
            return Err(err("enemy_strength_price can't be combined with a survive score rule (it would price future HP twice)"));
        }
        let head = if hp_loss {
            let bin_rep: Vec<f32> = get("bin_rep")?.ok_or_else(|| err("an HP-loss net needs bin_rep"))?.extract()?;
            if bin_rep.len() < 2 {
                return Err(err("bin_rep needs at least the two bins that never win"));
            }
            Head::Histogram { bin_rep, rule }
        } else {
            Head::Score
        };
        let slope: f32 = match get("leaky_slope")? {
            Some(v) if !v.is_none() => v.extract()?,
            _ => 0.0,
        };
        if !(0.0..1.0).contains(&slope) {
            return Err(err(format!("leaky_slope {slope} is outside [0, 1)")));
        }
        let net = Net::new(&state, norm, enc.layout_dims(), head, slope).map_err(err)?;
        if net.n_piles != enc.n_piles() {
            return Err(err(format!("the net's head has {} pile slots, its features {}", net.n_piles, enc.n_piles())));
        }
        Ok(PyNet { net: Arc::new(net), enc: Arc::new(enc), prices })
    }

    /// Scores [B] of `combats` (what search sees), or with `raw=True` the
    /// head's outputs [B, out] before the score (for tests).
    #[pyo3(signature = (combats, raw=false))]
    fn score<'py>(&self, py: Python<'py>, combats: Vec<PyRef<'py, Combat>>, raw: bool) -> PyResult<Bound<'py, PyAny>> {
        let states: Vec<&CombatState> = combats.iter().map(|c| &c.s).collect();
        let y = self.net.forward(&self.enc.encode(&states), &mut Scratch::default());
        if raw {
            let n_out = if states.is_empty() { 0 } else { y.len() / states.len() };
            let a = Array2::from_shape_vec((states.len(), n_out), y).map_err(|e| err(e.to_string()))?;
            return Ok(a.into_pyarray(py).into_any());
        }
        let mut v = self.net.scores(&y, &states);
        add_prices(&mut v, &states, self.prices);
        Ok(Array1::from_vec(v).into_pyarray(py).into_any())
    }
}

/// A Python callable as a search evaluator: it gets one batch dict per
/// search and returns one score per state. Errors are kept and raised
/// after the search. A callable whose `wants_heuristic` attribute is true
/// also gets `heuristic` in its batch.
#[derive(Clone)]
struct PyEval {
    f: Arc<Py<PyAny>>,
    enc: Arc<Encoder>,
    err: Arc<Mutex<Option<PyErr>>>,
    heuristic: bool,
    /// The callable's `score_rule` attribute (`score_rule` format; absent: engine).
    rule: ScoreRule,
}

impl PyEval {
    fn call(&self, py: Python<'_>, states: &[CombatState]) -> PyResult<Vec<f32>> {
        let refs: Vec<&CombatState> = states.iter().collect();
        let batch = batch_dict(py, &self.enc, &self.enc.encode(&refs))?;
        if self.heuristic {
            set_heuristic(py, &batch, &refs)?;
        }
        let r = self.f.bind(py).call1((batch,))?;
        let np = py.import("numpy")?;
        let a = np.call_method1("asarray", (r, "float32"))?.call_method0("ravel")?;
        let a: PyReadonlyArray1<f32> = a.extract()?;
        let v = a.as_slice().map_err(|e| err(e.to_string()))?.to_vec();
        if v.len() != states.len() {
            return Err(err(format!("evaluator returned {} values for {} states", v.len(), states.len())));
        }
        Ok(v)
    }

    fn take_err(&self) -> PyResult<()> {
        match self.err.lock().unwrap().take() {
            Some(e) => Err(e),
            None => Ok(()),
        }
    }
}

impl Evaluator for PyEval {
    fn evaluate(&mut self, states: &[CombatState]) -> Vec<f32> {
        if states.is_empty() || self.err.lock().unwrap().is_some() {
            return vec![0.0; states.len()];
        }
        Python::attach(|py| match self.call(py, states) {
            Ok(v) => v,
            Err(e) => {
                *self.err.lock().unwrap() = Some(e);
                vec![0.0; states.len()]
            }
        })
    }
}

/// One or more `NetEvaluator`s inside search (several: an ensemble, scored
/// by the mean of the members' scores): each search thread gets its own
/// clone (own scratch buffers, shared weights) and never takes Python's lock.
#[derive(Clone)]
struct NetEval {
    members: Vec<(Arc<Net>, Arc<Encoder>, Prices)>,
    scratch: Scratch,
}

/// States `NetEval` encodes and scores at once. A big search reaches
/// hundreds of thousands of leaves; their features all at once took GBs.
const LEAF_CHUNK: usize = 4096;

impl Evaluator for NetEval {
    fn evaluate(&mut self, states: &[CombatState]) -> Vec<f32> {
        let (net, enc, c) = &self.members[0];
        let mut out = net_scores(net, enc, states, LEAF_CHUNK, &mut self.scratch);
        let refs: Vec<&CombatState> = states.iter().collect();
        add_prices(&mut out, &refs, *c);
        if self.members.len() > 1 {
            for (net, enc, c) in &self.members[1..] {
                let mut m = net_scores(net, enc, states, LEAF_CHUNK, &mut self.scratch);
                add_prices(&mut m, &refs, *c);
                for (o, v) in out.iter_mut().zip(m) {
                    *o += v;
                }
            }
            let n = self.members.len() as f32;
            out.iter_mut().for_each(|o| *o /= n);
        }
        out
    }
}

/// `net`'s scores of `states`, encoded and run `chunk` states at a time.
/// The same values as one batch: the forward pass computes each state from
/// its own rows only.
fn net_scores(net: &Net, enc: &Encoder, states: &[CombatState], chunk: usize, scratch: &mut Scratch) -> Vec<f32> {
    let mut out = Vec::with_capacity(states.len());
    for part in states.chunks(chunk.max(1)) {
        let refs: Vec<&CombatState> = part.iter().collect();
        let y = net.forward(&enc.encode(&refs), scratch);
        out.extend(net.scores(&y, &refs));
    }
    out
}

enum Eval {
    Heuristic,
    Py(PyEval),
    Net(NetEval),
}

impl Eval {
    /// The score rule of the evaluator's scale: a net's own, else the engine's.
    fn rule(&self) -> ScoreRule {
        match self {
            Eval::Net(e) => e.members[0].0.head_kind.rule(),
            Eval::Py(e) => e.rule,
            Eval::Heuristic => ScoreRule::Engine,
        }
    }

    /// `cfg` with this evaluator's score rule, end-HP price and draw leaf.
    fn config(&self, cfg: &SearchConfig) -> SearchConfig {
        let (end_hp_price, draw_k, turn_start_leaf, leaf_clear_block, projected_ticks, projected_debuffs, tie_break) = match self {
            Eval::Net(e) => {
                let p = &e.members[0].2;
                (p.hp_end, p.draw_k, p.turn_start_leaf, p.leaf_clear_block, p.projected_ticks, p.projected_debuffs, p.tie_break)
            }
            _ => (0.0, 0, false, false, 0, false, false),
        };
        SearchConfig { rule: self.rule(), end_hp_price, draw_k, turn_start_leaf, leaf_clear_block, projected_ticks, projected_debuffs, tie_break, ..cfg.clone() }
    }
}

fn make_eval(evaluator: Option<&Bound<'_, PyAny>>, features: Option<&PyFeatures>) -> PyResult<Eval> {
    let Some(e) = evaluator else { return Ok(Eval::Heuristic) };
    if let Ok(name) = e.extract::<String>() {
        return match name.as_str() {
            "heuristic" => Ok(Eval::Heuristic),
            _ => Err(err(format!("unknown evaluator {name:?} (\"heuristic\", a NetEvaluator, a list of them or a callable)"))),
        };
    }
    if let Ok(n) = e.extract::<PyNet>() {
        return Ok(Eval::Net(NetEval { members: vec![(n.net, n.enc, n.prices)], scratch: Scratch::default() }));
    }
    if e.is_instance_of::<PyList>() || e.is_instance_of::<PyTuple>() {
        let mut members = Vec::new();
        for m in e.try_iter()? {
            let m = m?;
            let n: PyNet = m.extract().map_err(|_| err(format!("an ensemble holds only NetEvaluators, not {m:?}")))?;
            members.push((n.net, n.enc, n.prices));
        }
        if members.is_empty() {
            return Err(err("an ensemble needs at least one NetEvaluator"));
        }
        let rule = members[0].0.head_kind.rule();
        if members.iter().any(|(n, _, _)| n.head_kind.rule() != rule) {
            return Err(err("ensemble members must share a score rule"));
        }
        if members.iter().any(|m| m.2.hp_end != members[0].2.hp_end) {
            return Err(err("ensemble members must share an hp_end_bonus"));
        }
        if members.iter().any(|m| m.2.draw_k != members[0].2.draw_k) {
            return Err(err("ensemble members must share a draw_k"));
        }
        if members.iter().any(|m| m.2.turn_start_leaf != members[0].2.turn_start_leaf) {
            return Err(err("ensemble members must share a turn_start_leaf"));
        }
        if members.iter().any(|m| m.2.leaf_clear_block != members[0].2.leaf_clear_block) {
            return Err(err("ensemble members must share a leaf_clear_block"));
        }
        if members.iter().any(|m| m.2.projected_ticks != members[0].2.projected_ticks) {
            return Err(err("ensemble members must share a projected_ticks"));
        }
        if members.iter().any(|m| m.2.projected_debuffs != members[0].2.projected_debuffs) {
            return Err(err("ensemble members must share a projected_debuffs"));
        }
        if members.iter().any(|m| m.2.tie_break != members[0].2.tie_break) {
            return Err(err("ensemble members must share a tie_break"));
        }
        return Ok(Eval::Net(NetEval { members, scratch: Scratch::default() }));
    }
    if !e.is_callable() {
        return Err(err("evaluator must be \"heuristic\", a NetEvaluator, a list of them or a callable"));
    }
    let enc = match features {
        Some(f) => f.enc.clone(),
        None => Arc::new(Encoder::new(CardRepr::Effects, &Vocab::default())),
    };
    let heuristic = e.getattr("wants_heuristic").and_then(|a| a.is_truthy()).unwrap_or(false);
    let rule = score_rule(e.getattr("score_rule").ok())?;
    Ok(Eval::Py(PyEval { f: Arc::new(e.clone().unbind()), enc, err: Arc::new(Mutex::new(None)), heuristic, rule }))
}

fn config(limit: usize, sample_k: u32, turns: u8, seed: u64, max_nodes: usize) -> SearchConfig {
    SearchConfig { limit, sample_k, turns, seed, max_nodes, rule: ScoreRule::Engine, end_hp_price: 0.0, draw_k: 0, turn_start_leaf: false, leaf_clear_block: false, projected_ticks: 0, projected_debuffs: false, tie_break: false }
}

fn run_search(c: &Combat, ev: Option<&Bound<'_, PyAny>>, features: Option<&PyFeatures>, cfg: &SearchConfig) -> PyResult<SearchResult> {
    c.need_action()?;
    let e = make_eval(ev, features)?;
    let cfg = &e.config(cfg);
    match e {
        Eval::Heuristic => Ok(engine_search(&c.s, &mut Heuristic, cfg)),
        Eval::Net(mut e) => Ok(engine_search(&c.s, &mut e, cfg)),
        Eval::Py(mut e) => {
            let r = engine_search(&c.s, &mut e, cfg);
            e.take_err()?;
            Ok(r)
        }
    }
}

/// Searches the current turn. `evaluator` is "heuristic" (default) or a
/// callable taking a batch dict (see `Features.encode`) and returning one
/// score per state (0..2, final-score scale), or a `NetEvaluator` or a list
/// of them (an ensemble: the mean of their scores; each scored in
/// Rust on its own features; `features` is ignored). Returns `{action,
/// options: [(actions, value)], nodes, leaves, cuts, line}`; `cuts` counts
/// states left unexpanded because the tree reached `max_nodes`; `line` is
/// the principal line, `action` first (docs/specs/line-step.md).
#[pyfunction]
#[pyo3(signature = (combat, evaluator=None, limit=16, sample_k=0, turns=1, seed=0, features=None, max_nodes=50_000))]
#[allow(clippy::too_many_arguments)]
fn search<'py>(
    py: Python<'py>,
    combat: PyRef<'py, Combat>,
    evaluator: Option<Bound<'py, PyAny>>,
    limit: usize,
    sample_k: u32,
    turns: u8,
    seed: u64,
    features: Option<PyRef<'py, PyFeatures>>,
    max_nodes: usize,
) -> PyResult<Bound<'py, PyDict>> {
    let r = run_search(&combat, evaluator.as_ref(), features.as_deref(), &config(limit, sample_k, turns, seed, max_nodes))?;
    let d = PyDict::new(py);
    let b = &combat.s.binding;
    d.set_item("action", act(r.action, b))?;
    let options: Vec<(Vec<PyAction>, f32)> =
        r.options.into_iter().map(|o| (o.actions.into_iter().map(|a| act(a, b)).collect(), o.value)).collect();
    d.set_item("options", options)?;
    d.set_item("nodes", r.nodes)?;
    d.set_item("leaves", r.leaves)?;
    d.set_item("cuts", r.cuts)?;
    let line: Vec<PyAction> = r.line.into_iter().map(|a| act(a, b)).collect();
    d.set_item("line", line)?;
    Ok(d)
}

/// The action `search` picks.
#[pyfunction]
#[pyo3(signature = (combat, evaluator=None, limit=16, sample_k=0, turns=1, seed=0, features=None, max_nodes=50_000))]
#[allow(clippy::too_many_arguments)]
fn search_action<'py>(
    combat: PyRef<'py, Combat>,
    evaluator: Option<Bound<'py, PyAny>>,
    limit: usize,
    sample_k: u32,
    turns: u8,
    seed: u64,
    features: Option<PyRef<'py, PyFeatures>>,
    max_nodes: usize,
) -> PyResult<PyAction> {
    let r = run_search(&combat, evaluator.as_ref(), features.as_deref(), &config(limit, sample_k, turns, seed, max_nodes))?;
    Ok(act(r.action, &combat.s.binding))
}

/// The solved-state database (`db/solved.sqlite` by default), opened under
/// this build's rules fingerprint. A run sees it as it was when opened.
#[pyclass(module = "sts", name = "SolvedDb", frozen)]
struct PySolvedDb(Arc<solvedb::SolvedDb>);

fn db_err(e: solvedb::db::Error) -> PyErr {
    err(format!("solved-state database: {e}"))
}

/// A state found by `SolvedDb.lookup`: its value and, at a decision, its
/// options' values and which of them are upper bounds (solver bounds).
type Found = (f64, Option<Vec<f64>>, Option<Vec<bool>>);
/// A row read by `SolvedDb.fetch`: state bytes, value, options.
type Fetched<'py> = (Bound<'py, PyBytes>, f64, Vec<Bound<'py, PyAny>>);

/// A distribution as `(P(loss), [(HP lost, P)])`.
fn dist_py(d: &Distribution) -> (f64, Vec<(u16, f64)>) {
    (d.loss, d.wins.clone())
}

/// Options as `[(actions, value[, distribution])]`, or with `flags` (rows
/// read back, never with distributions) `[(actions, value, bounded)]`.
/// `b`: the state's binding, which names its generated cards and variants.
fn options_py<'py>(py: Python<'py>, options: &[SolvedOption], flags: bool, b: &Binding) -> PyResult<Vec<Bound<'py, PyAny>>> {
    options
        .iter()
        .map(|o| {
            let actions: Vec<PyAction> = o.actions.iter().map(|&a| act(a, b)).collect();
            Ok(match &o.dist {
                _ if flags => (actions, o.value, o.bounded).into_pyobject(py)?.into_any(),
                Some(d) => (actions, o.value, dist_py(d)).into_pyobject(py)?.into_any(),
                None => (actions, o.value).into_pyobject(py)?.into_any(),
            })
        })
        .collect()
}

/// Per option, whether its value is an upper bound (solver bounds).
fn bounded_py(options: &[SolvedOption]) -> Vec<bool> {
    options.iter().map(|o| o.bounded).collect()
}

#[pymethods]
impl PySolvedDb {
    #[new]
    #[pyo3(signature = (path=solvedb::db::DEFAULT_PATH.to_string(), max_gb=solvedb::db::DEFAULT_MAX_GB))]
    fn new(py: Python<'_>, path: String, max_gb: f64) -> PyResult<PySolvedDb> {
        let db = py.detach(|| solvedb::SolvedDb::open(path, max_gb)).map_err(db_err)?;
        Ok(PySolvedDb(Arc::new(db)))
    }

    #[getter]
    fn fingerprint(&self) -> String {
        self.0.fingerprint().to_string()
    }

    /// Rows of the current rules version when it was opened (full and trivial).
    #[getter]
    fn rows(&self) -> usize {
        self.0.snapshot_rows()
    }

    /// `{bytes, file_bytes, positions, versions: [(id, fingerprint, rows,
    /// current, trivial rows)], tables: [(table, bytes)], cost_quantiles:
    /// [(q, cost)]}`.
    fn stats<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let st = py.detach(|| self.0.stats()).map_err(db_err)?;
        let d = PyDict::new(py);
        d.set_item("bytes", st.bytes)?;
        d.set_item("file_bytes", st.file_bytes)?;
        d.set_item("positions", st.positions)?;
        let versions: Vec<(i64, String, u64, bool, u64)> =
            st.versions.into_iter().map(|v| (v.id, v.fingerprint, v.rows, v.current, v.trivial)).collect();
        d.set_item("versions", versions)?;
        d.set_item("tables", st.tables)?;
        d.set_item("cost_quantiles", st.cost_quantiles)?;
        Ok(d)
    }

    /// Over `max_bytes` (default: the `max_gb` cap), deletes other rules
    /// versions' rows, then the cheapest, until under 90% of it, then
    /// compacts. `{bytes_before, bytes_after, other_versions, current}`.
    #[pyo3(signature = (max_bytes=None))]
    fn evict<'py>(&self, py: Python<'py>, max_bytes: Option<u64>) -> PyResult<Bound<'py, PyDict>> {
        let e = py
            .detach(|| match max_bytes {
                Some(b) => self.0.evict(b),
                None => self.0.enforce_cap(),
            })
            .map_err(db_err)?;
        let d = PyDict::new(py);
        d.set_item("bytes_before", e.bytes_before)?;
        d.set_item("bytes_after", e.bytes_after)?;
        d.set_item("other_versions", e.other_versions)?;
        d.set_item("current", e.current)?;
        Ok(d)
    }

    /// Moves trivial rows no position points at from `states` to `trivial`
    /// and compacts the file (exact-solver Amendment 1; once, by hand, with
    /// nothing else using the database). `{bytes_before, bytes_after, moved}`.
    fn compact<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let c = py.detach(|| self.0.compact()).map_err(db_err)?;
        let d = PyDict::new(py);
        d.set_item("bytes_before", c.bytes_before)?;
        d.set_item("bytes_after", c.bytes_after)?;
        d.set_item("moved", c.moved)?;
        Ok(d)
    }

    /// Rebuilds costs the old summing rule broke (over `max_cost`, or
    /// negative) from the rows' children (docs/decisions.md, "Solved-state
    /// cost"; once, by hand, with nothing else using the database).
    /// `{states, trivial, clamped}`.
    fn repair_costs<'py>(&self, py: Python<'py>, max_cost: u64) -> PyResult<Bound<'py, PyDict>> {
        let r = py.detach(|| self.0.repair_costs(max_cost)).map_err(db_err)?;
        let d = PyDict::new(py);
        d.set_item("states", r.states)?;
        d.set_item("trivial", r.trivial)?;
        d.set_item("clamped", r.clamped)?;
        Ok(d)
    }

    /// Read-only (training labels): per state (codec bytes), `None`, or its
    /// exact value and, at a decision, each option's (`[value]`, in the
    /// order `solve` groups them) and whether each is an upper bound
    /// (`[bool]`), else `None` twice. As the database was opened.
    fn lookup(&self, py: Python<'_>, states: Vec<Vec<u8>>) -> PyResult<Vec<Option<Found>>> {
        let rows = py.detach(|| self.0.lookup(&states)).map_err(db_err)?;
        Ok(rows
            .into_iter()
            .map(|r| {
                r.map(|s| {
                    let values = s.options.as_ref().map(|o| o.iter().map(|o| o.value).collect());
                    (s.value, values, s.options.as_deref().map(bounded_py))
                })
            })
            .collect())
    }

    /// Row ids of the current version's decision states (rows with
    /// options) as opened, ordered by the rows' content (key hash; int64
    /// array), so seeded samples don't depend on write order.
    fn decision_ids<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let ids = py.detach(|| self.0.decision_ids()).map_err(db_err)?;
        Ok(Array1::from(ids).into_pyarray(py).into_any())
    }

    /// The rows `ids` (from `decision_ids`) in the order given, as
    /// `(state bytes, value, options)`, options as `(actions, value,
    /// bounded)` (`bounded`: the value is an upper bound).
    fn fetch<'py>(&self, py: Python<'py>, ids: Vec<i64>) -> PyResult<Vec<Fetched<'py>>> {
        let rows = py.detach(|| self.0.fetch(&ids)).map_err(db_err)?;
        rows.into_iter()
            .map(|(b, s)| {
                let binding = sts_engine::codec::decode(&b).binding;
                Ok((PyBytes::new(py, &b), s.value, options_py(py, s.options.as_deref().unwrap_or(&[]), true, &binding)?))
            })
            .collect()
    }

    /// The positions recorded under `source` (current rules version), oldest
    /// first: `{state: bytes, spec, prefix, step, horizon, gap, options,
    /// bounded}`, options and `bounded` as `solve` returns them.
    fn positions<'py>(&self, py: Python<'py>, source: &str) -> PyResult<Vec<Bound<'py, PyDict>>> {
        let rows = py.detach(|| self.0.positions(source)).map_err(db_err)?;
        rows.into_iter()
            .map(|r| {
                let d = PyDict::new(py);
                d.set_item("state", PyBytes::new(py, &r.state))?;
                d.set_item("spec", r.spec)?;
                d.set_item("prefix", r.prefix)?;
                d.set_item("step", r.step)?;
                d.set_item("horizon", r.horizon)?;
                d.set_item("gap", r.gap)?;
                let binding = sts_engine::codec::decode(&r.state).binding;
                d.set_item("options", options_py(py, &r.options, false, &binding)?)?;
                d.set_item("bounded", bounded_py(&r.options))?;
                Ok(d)
            })
            .collect()
    }
}

enum StoreKind {
    Memory(MemoryStore),
    Db(solvedb::DbStore),
}

struct StoreInner {
    kind: StoreKind,
    /// The last solve's root (codec bytes) and result, for `add_position`.
    last: Option<(Vec<u8>, Solution)>,
}

/// One game's store of solved states: memory only, or memory in front of a
/// `SolvedDb`. States costing under `min_nodes` aren't kept.
#[pyclass(module = "sts", name = "SolveStore", frozen)]
struct PySolveStore {
    inner: Mutex<StoreInner>,
    min_nodes: u64,
}

#[pymethods]
impl PySolveStore {
    #[new]
    #[pyo3(signature = (min_nodes=1_000, db=None))]
    fn new(min_nodes: u64, db: Option<PyRef<'_, PySolvedDb>>) -> PyResult<PySolveStore> {
        let kind = match db {
            Some(db) => StoreKind::Db(db.0.store(min_nodes).map_err(db_err)?),
            None => StoreKind::Memory(MemoryStore::new(min_nodes)),
        };
        Ok(PySolveStore { inner: Mutex::new(StoreInner { kind, last: None }), min_nodes })
    }

    #[getter]
    fn min_nodes(&self) -> u64 {
        self.min_nodes
    }

    /// Lookups the database answered (0 for a memory-only store).
    #[getter]
    fn db_hits(&self) -> u64 {
        match &self.inner.lock().unwrap().kind {
            StoreKind::Memory(_) => 0,
            StoreKind::Db(d) => d.db_hits,
        }
    }

    /// Records the last solve's root as a played position (stores over a
    /// `SolvedDb` only): its state row, with its options, and a `positions`
    /// row. `combat` must be the state last solved with this store. Returns
    /// whether the position is new for `source`.
    #[allow(clippy::too_many_arguments)]
    fn add_position(&self, py: Python<'_>, combat: PyRef<'_, Combat>, source: &str, spec: &str, prefix: &str, step: u32, horizon: u32, gap: f64) -> PyResult<bool> {
        let s = combat.s.clone();
        let bytes = sts_engine::codec::encode(&s);
        let mut g = self.inner.lock().unwrap();
        let StoreInner { kind, last } = &mut *g;
        let sol = match last {
            Some((b, sol)) if *b == bytes => sol,
            _ => return Err(err("add_position needs the state last solved with this store")),
        };
        let StoreKind::Db(store) = kind else {
            return Err(err("add_position needs a store over a SolvedDb"));
        };
        let pos = solvedb::Position { source, spec, prefix, step, horizon, gap };
        py.detach(|| store.add_position(&s, sol, &pos)).map_err(db_err)
    }
}

/// Solves the combat exactly: each root option's expected final score under
/// the best play, every random event listed, to the end of combat, grouped
/// as `search` groups options. Returns `{options: [(actions, value[,
/// (P(loss), [(HP lost, P)])])], bounded, nodes, hits, turns_left, cost}`,
/// or `None` when it needs more than `max_nodes`. `bounds`: skip options
/// that can't beat the best one (docs/specs/solver-bounds.md); a skipped
/// option's value is its upper bound and `bounded` (per option) says so.
/// Releases Python's lock.
#[pyfunction]
#[pyo3(signature = (combat, max_nodes=1_000_000, distribution=false, store=None, bounds=false))]
fn solve<'py>(
    py: Python<'py>,
    combat: PyRef<'py, Combat>,
    max_nodes: u64,
    distribution: bool,
    store: Option<PyRef<'py, PySolveStore>>,
    bounds: bool,
) -> PyResult<Option<Bound<'py, PyDict>>> {
    combat.need_action()?;
    let s = combat.s.clone();
    let cfg = SolveConfig { max_nodes, distribution, bounds };
    let r = match &store {
        Some(st) => {
            let mut g = st.inner.lock().unwrap();
            let g = &mut *g;
            let r = py.detach(|| match &mut g.kind {
                StoreKind::Memory(m) => engine_solve(&s, &cfg, Some(m)),
                StoreKind::Db(d) => engine_solve(&s, &cfg, Some(d)),
            });
            g.last = r.as_ref().map(|r| (sts_engine::codec::encode(&s), r.clone()));
            r
        }
        None => py.detach(|| engine_solve(&s, &cfg, None)),
    };
    let Some(r) = r else { return Ok(None) };
    let d = PyDict::new(py);
    d.set_item("options", options_py(py, &r.options, false, &s.binding)?)?;
    d.set_item("bounded", bounded_py(&r.options))?;
    d.set_item("nodes", r.nodes)?;
    d.set_item("hits", r.hits)?;
    d.set_item("touches", r.touches)?;
    d.set_item("turns_left", r.turns_left)?;
    d.set_item("cost", r.cost)?;
    Ok(Some(d))
}

#[pyfunction]
fn greedy_action(combat: PyRef<'_, Combat>) -> PyResult<PyAction> {
    combat.need_action()?;
    Ok(act(engine_greedy(&combat.s), &combat.s.binding))
}

#[pyfunction]
#[pyo3(signature = (combat, seed=0))]
fn random_action(combat: PyRef<'_, Combat>, seed: u64) -> PyResult<PyAction> {
    combat.need_action()?;
    Ok(act(engine_random(&combat.s, &mut Rng::new(seed)).expect("awaiting an action"), &combat.s.binding))
}

#[pyfunction]
fn action_name(action: PyAction) -> String {
    action_label(action)
}

/// Content hashes of the packs this process has loaded, in load order.
static LOADED: Mutex<Vec<String>> = Mutex::new(Vec::new());

/// Loads a content pack (docs/specs/registry-lite.md): a path to a JSON
/// file, or the JSON text itself. Append-only: ids already loaded with the
/// same definition are skipped, a different definition is an error.
/// Returns the pack's content hash (16 hex digits), for dataset meta;
/// decks then name its cards `gen:<id>`.
#[pyfunction]
fn load_content(pack: &str) -> PyResult<String> {
    let text = if pack.trim_start().starts_with('{') {
        pack.to_string()
    } else {
        std::fs::read_to_string(pack).map_err(|e| err(format!("content pack {pack:?}: {e}")))?
    };
    let h = format!("{:016x}", registry::load_pack(&text).map_err(err)?);
    let mut loaded = LOADED.lock().unwrap();
    if !loaded.contains(&h) {
        loaded.push(h.clone());
    }
    Ok(h)
}

/// The content hashes `load_content` returned in this process, in load
/// order (empty: official content only).
#[pyfunction]
fn loaded_content() -> Vec<String> {
    LOADED.lock().unwrap().clone()
}

/// `n` combat specs `(encounter, deck, seed)` over a group's encounters in
/// turn, from `character`'s starter deck; odd-numbered ones add `extra`
/// random cards from `card_pool` (default: the character's cards).
#[pyfunction]
#[pyo3(signature = (group, n, extra=5, seed=1, card_pool=None, character="ironclad"))]
fn make_specs(
    group: &str,
    n: usize,
    extra: usize,
    seed: u64,
    card_pool: Option<Vec<String>>,
    character: &str,
) -> PyResult<Vec<(&'static str, Vec<&'static str>, u64)>> {
    let ch = self::character(character)?;
    let pool: Vec<CardId> = match card_pool {
        Some(names) => names.iter().map(|n| card(n)).collect::<PyResult<_>>()?,
        None => class_cards(ch.class()).collect(),
    };
    Ok(group_specs_as(ch, self::group(group)?, n, extra, seed, &pool)
        .into_iter()
        .map(|s| (s.encounter.name(), deck_names(&s.deck, &s.binding), s.seed))
        .collect())
}

fn result_dict<'py>(py: Python<'py>, spec: &GameSpec, r: CombatResult, record: bool, values: bool) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("encounter", spec.encounter.name())?;
    d.set_item("deck", deck_names(&spec.deck, &spec.binding))?;
    d.set_item("seed", spec.seed)?;
    d.set_item("won", r.won)?;
    d.set_item("hp_start", r.hp_start)?;
    d.set_item("hp_end", r.hp_end)?;
    d.set_item("turns", r.turns)?;
    d.set_item("healed", r.healed)?;
    d.set_item("stalled", r.turns > PLAY_TURN_LIMIT)?;
    d.set_item("score", r.score)?;
    if values {
        // Each decision's actions are named through that state's binding
        // (a grown Rampage is a variant only that combat holds); without a
        // recorded trajectory, through the spec's, unbound ids unnamed.
        let v: Vec<Vec<(Vec<PyAction>, f32)>> = r
            .option_values
            .iter()
            .enumerate()
            .map(|(i, opts)| {
                let b = r.trajectory.get(i).map_or(&spec.binding, |(s, _)| &s.binding);
                opts.iter().map(|o| (o.actions.iter().map(|&a| act_in(a, b)).collect(), o.value)).collect()
            })
            .collect();
        d.set_item("values", v)?;
    }
    if record {
        let (states, actions): (Vec<Combat>, Vec<PyAction>) = r
            .trajectory
            .into_iter()
            .enumerate()
            .map(|(i, (s, a))| {
                let pa = act(a, &s.binding);
                (Combat { s, rng: Rng::new(spec.seed ^ (i as u64 + 1).wrapping_mul(0x5851_f42d_4c95_7f2d)) }, pa)
            })
            .unzip();
        d.set_item("states", states)?;
        d.set_item("actions", actions)?;
    }
    Ok(d)
}

/// Plays a game's forced opening actions, then hands over to `inner`.
/// Forced decisions report no search options; an illegal forced action sets
/// `bad` and stops the forcing (the game goes on with the agent).
struct Forced<'a, A: Agent> {
    inner: &'a mut A,
    prefix: &'a [Action],
    k: usize,
    forced_last: bool,
    bad: &'a AtomicBool,
}

impl<A: Agent> Agent for Forced<'_, A> {
    fn act(&mut self, s: &CombatState, rng: &mut Rng) -> Action {
        self.forced_last = false;
        if let Some(&a) = self.prefix.get(self.k) {
            self.k += 1;
            if s.legal_actions().contains(&a) {
                self.forced_last = true;
                return a;
            }
            self.bad.store(true, Ordering::Relaxed);
            self.k = self.prefix.len();
        }
        self.inner.act(s, rng)
    }

    fn last_options(&self) -> Option<&[OptionScore]> {
        if self.forced_last {
            None
        } else {
            self.inner.last_options()
        }
    }
}

/// `play_many`, or with `forced` each game first plays its forced opening
/// actions (`Forced`); returns the results and whether a forced action was
/// illegal.
fn play_all<A: Agent, F: Fn() -> A + Sync>(specs: &[GameSpec], forced: Option<&[Vec<Action>]>, make: F, threads: usize, record: bool) -> (Vec<CombatResult>, bool) {
    let Some(forced) = forced else { return (play_many(specs, make, threads, record), false) };
    let next = AtomicUsize::new(0);
    let bad = AtomicBool::new(false);
    let out: Mutex<Vec<Option<CombatResult>>> = Mutex::new(vec![None; specs.len()]);
    std::thread::scope(|scope| {
        for _ in 0..threads.max(1) {
            scope.spawn(|| {
                let mut agent = make();
                loop {
                    let i = next.fetch_add(1, Ordering::Relaxed);
                    if i >= specs.len() {
                        break;
                    }
                    let mut f = Forced { inner: &mut agent, prefix: &forced[i], k: 0, forced_last: false, bad: &bad };
                    let r = play(&specs[i], &mut f, record);
                    out.lock().unwrap()[i] = Some(r);
                }
            });
        }
    });
    (out.into_inner().unwrap().into_iter().map(|r| r.expect("every spec played")).collect(), bad.into_inner())
}

/// A `run` spec: `(encounter, deck, seed)`, or with the game's starting HP,
/// or keyed: `{"encounter", "deck", "seed"[, "hp"]}` (docs/decisions.md "Contract as built";
/// later fields join with defaults, unknown keys are refused).
#[derive(FromPyObject)]
enum SpecArg<'py> {
    WithHp(String, Vec<String>, u64, i16),
    Plain(String, Vec<String>, u64),
    Keyed(Bound<'py, PyDict>),
}

const SPEC_KEYS: [&str; 9] = ["encounter", "deck", "seed", "hp", "relics", "turn1_pre_draw", "potions", "ascension", "elite_buff"];

type KeyedSpec = (String, Vec<String>, u64, Option<i16>, Option<Vec<RelicArg>>, bool, Option<Vec<String>>, u8, Option<String>);

/// A keyed spec's fields: encounter, deck, seed required; hp, relics
/// (names, docs/specs/relics.md), turn1_pre_draw (default false,
/// docs/specs/turn-start-draw.md), potions (names,
/// docs/specs/potions.md) and ascension (default 0,
/// docs/specs/ascension.md) and elite_buff (`Combat`'s) optional.
fn keyed_spec(d: &Bound<'_, PyDict>) -> PyResult<KeyedSpec> {
    for k in d.keys() {
        let k: String = k.extract()?;
        if !SPEC_KEYS.contains(&k.as_str()) {
            return Err(err(format!("unknown spec key {k:?} (known: {SPEC_KEYS:?})")));
        }
    }
    let need = |k: &str| d.get_item(k)?.ok_or_else(|| err(format!("spec needs {k:?}")));
    let hp = match d.get_item("hp")? {
        Some(h) if !h.is_none() => Some(h.extract()?),
        _ => None,
    };
    let relics = match d.get_item("relics")? {
        Some(r) if !r.is_none() => Some(r.extract()?),
        _ => None,
    };
    let turn1_pre_draw = match d.get_item("turn1_pre_draw")? {
        Some(v) if !v.is_none() => v.extract()?,
        _ => false,
    };
    let potions = match d.get_item("potions")? {
        Some(p) if !p.is_none() => Some(p.extract()?),
        _ => None,
    };
    let ascension = match d.get_item("ascension")? {
        Some(v) if !v.is_none() => v.extract()?,
        _ => 0,
    };
    let elite_buff = match d.get_item("elite_buff")? {
        Some(v) if !v.is_none() => Some(v.extract()?),
        _ => None,
    };
    Ok((need("encounter")?.extract()?, need("deck")?.extract()?, need("seed")?.extract()?, hp, relics, turn1_pre_draw, potions, ascension, elite_buff))
}

/// Plays every spec `(encounter, deck, seed)` with an agent ("random",
/// "greedy" or "search") on `threads` threads (default: the job's cap
/// `STS_JOB_THREADS`, else all cores). The
/// combat's random events come from the spec's seed; `character` and `hp`
/// (default: its starting HP) apply to every spec, and a spec with a fourth
/// field `(encounter, deck, seed, hp)` starts at that HP instead (varied
/// self-play setups); a spec may also be a dict with those keys
/// (`encounter`, `deck`, `seed`, optional `hp`, `relics` (docs/specs/relics.md),
/// `turn1_pre_draw` (`Combat`'s) and `potions` (names, docs/specs/potions.md)). Returns one dict per
/// spec; with `record`, also the decision `states` and `actions`, and with
/// `values` as well, each decision's search `values`: `[(actions, value)]`
/// per root option, as `search` returns them.
/// `no_death` plays every combat in no-death mode (`Combat(no_death=True)`):
/// HP may go below 0, `hp_end` is the HP left, with no end-of-combat heal.
/// `explore` > 0 makes the search agent pick each option by softmax over its
/// root option values at that temperature (self-play rounds); 0 plays the
/// best option, unchanged.
/// `forced`, one action list per spec, makes each game play those actions
/// first (as decisions without search values) before the agent takes over:
/// a branch replays a game up to a point and then deviates.
/// `evaluator` and `features` are as for `search`; a `NetEvaluator` runs on
/// every thread without Python's lock, a Python callable takes turns on it.
/// `luck`, an unpriced `NetEvaluator` on the engine's score, logs each
/// game's luck (docs/specs/luck-corrected-labels.md): every result gets
/// `luck`, per decision the luck drawn after its action (`luck_limit`,
/// `luck_samples`: `runner::LuckConfig`); the games play as without it.
#[pyfunction]
#[pyo3(signature = (agent, specs, evaluator=None, features=None, limit=16, sample_k=0, turns=1, threads=None, record=false, hp=None, character="ironclad", values=false, no_death=false, explore=0.0, forced=None, max_nodes=50_000, luck=None, luck_limit=64, luck_samples=16))]
#[allow(clippy::too_many_arguments)]
fn run<'py>(
    py: Python<'py>,
    agent: &str,
    specs: Vec<SpecArg<'py>>,
    evaluator: Option<Bound<'py, PyAny>>,
    features: Option<PyRef<'py, PyFeatures>>,
    limit: usize,
    sample_k: u32,
    turns: u8,
    threads: Option<usize>,
    record: bool,
    hp: Option<i16>,
    character: &str,
    values: bool,
    no_death: bool,
    explore: f32,
    forced: Option<Vec<Vec<PyAction>>>,
    max_nodes: usize,
    luck: Option<PyRef<'py, PyNet>>,
    luck_limit: usize,
    luck_samples: u32,
) -> PyResult<Vec<Bound<'py, PyDict>>> {
    let luck_eval = match &luck {
        None => None,
        Some(l) => {
            if forced.is_some() {
                return Err(err("luck does not take forced openings".to_string()));
            }
            if l.prices != Prices::default() || l.net.head_kind.rule() != ScoreRule::Engine {
                return Err(err("luck needs an unpriced NetEvaluator on the engine's score".to_string()));
            }
            Some(NetEval { members: vec![(l.net.clone(), l.enc.clone(), l.prices)], scratch: Scratch::default() })
        }
    };
    let luck_cfg = LuckConfig { limit: luck_limit, samples: luck_samples };
    let lk = luck_eval.as_ref().map(|e| (e, &luck_cfg));
    if values && !record {
        return Err(err("values=True needs record=True".to_string()));
    }
    if forced.as_ref().is_some_and(|f| f.len() != specs.len()) {
        return Err(err("forced needs one action list per spec".to_string()));
    }
    let forced: Option<Vec<Vec<Action>>> = forced.map(|f| f.into_iter().map(|p| p.into_iter().map(|a| a.0).collect()).collect());
    let forced = forced.as_deref();
    let ch = self::character(character)?;
    let specs: Vec<GameSpec> = specs
        .iter()
        .map(|spec| {
            let (e, deck, seed, spec_hp, relics, turn1_pre_draw, potions, asc, buff) = match spec {
                SpecArg::WithHp(e, d, s, h) => (e.clone(), d.clone(), *s, Some(*h), None, false, None, 0, None),
                SpecArg::Plain(e, d, s) => (e.clone(), d.clone(), *s, hp, None, false, None, 0, None),
                SpecArg::Keyed(d) => {
                    let (e, deck, s, h, r, t, p, a, b) = keyed_spec(d)?;
                    (e, deck, s, h.or(hp), r, t, p, a, b)
                }
            };
            let ascension = self::ascension(asc)?;
            let elite_buff = self::elite_buff(buff.as_deref())?;
            let (hp, max_hp) = hp_pair(ch, spec_hp, None, asc);
            let (deck, binding) = bind_deck(&deck)?;
            let encounter = encounter(&e)?;
            let relics = relic_args(relics, &binding, encounter.group(), ch)?;
            let potions = potion_args(potions)?;
            // The potions' pack powers fit the slots the deck and relics left.
            let acting = registry::bind_relics(&binding, relics.iter().filter(|(_, r)| r.acts_in(encounter.group())), ch).map_err(err)?;
            registry::bind_potions(&acting, &potions).map_err(err)?;
            Ok(GameSpec { character: ch, encounter, deck, seed, hp, max_hp, no_death, binding, relics, potions, turn1_pre_draw, ascension, elite_buff })
        })
        .collect::<PyResult<_>>()?;
    let threads = threads.unwrap_or_else(default_threads);
    let cfg = config(limit, sample_k, turns, 0, max_nodes);
    let (results, bad) = match agent {
        "random" => py.detach(|| play_luck_or_all(&specs, forced, lk, || RandomAgent, threads, record)),
        "greedy" => py.detach(|| play_luck_or_all(&specs, forced, lk, || GreedyAgent, threads, record)),
        "search" => {
            let e = make_eval(evaluator.as_ref(), features.as_deref())?;
            let cfg = e.config(&cfg);
            match e {
                Eval::Heuristic => py.detach(|| play_luck_or_all(&specs, forced, lk, || SearchAgent { explore, ..SearchAgent::new(Heuristic, cfg.clone()) }, threads, record)),
                Eval::Net(e) => py.detach(|| play_luck_or_all(&specs, forced, lk, || SearchAgent { explore, ..SearchAgent::new(e.clone(), cfg.clone()) }, threads, record)),
                Eval::Py(e) => {
                    let r = py.detach(|| play_luck_or_all(&specs, forced, lk, || SearchAgent { explore, ..SearchAgent::new(e.clone(), cfg.clone()) }, threads, record));
                    e.take_err()?;
                    r
                }
            }
        }
        _ => return Err(err(format!("unknown agent {agent:?} (random, greedy, search)"))),
    };
    if bad {
        return Err(err("a forced action was not legal in its game".to_string()));
    }
    specs
        .iter()
        .zip(results)
        .map(|(s, mut r)| {
            let lucks = std::mem::take(&mut r.luck);
            let d = result_dict(py, s, r, record, values)?;
            if lk.is_some() {
                d.set_item("luck", lucks)?;
            }
            Ok(d)
        })
        .collect()
}

/// `play_all`, or with `luck` (an evaluator and its settings) every game's
/// luck logged (`runner::play_many_luck`; no forced openings).
fn play_luck_or_all<A: Agent, F: Fn() -> A + Sync>(
    specs: &[GameSpec],
    forced: Option<&[Vec<Action>]>,
    luck: Option<(&NetEval, &LuckConfig)>,
    make: F,
    threads: usize,
    record: bool,
) -> (Vec<CombatResult>, bool) {
    match luck {
        None => play_all(specs, forced, make, threads, record),
        Some((e, cfg)) => {
            let make_ev = || NetEval { members: e.members.clone(), scratch: Scratch::default() };
            (play_many_luck(specs, make, make_ev, threads, record, cfg), false)
        }
    }
}

/// Plays each start state on to the end (`play_from`) on `threads` threads,
/// one agent per thread; results in order. A start's RNG gives its random
/// events; the agent's RNG is derived from it.
fn play_starts<A: Agent, F: Fn() -> A + Sync>(starts: &[(CombatState, Rng)], make: F, threads: usize) -> Vec<CombatResult> {
    let next = AtomicUsize::new(0);
    let out: Mutex<Vec<Option<CombatResult>>> = Mutex::new(vec![None; starts.len()]);
    std::thread::scope(|scope| {
        for _ in 0..threads.max(1) {
            scope.spawn(|| {
                let mut agent = make();
                loop {
                    let i = next.fetch_add(1, Ordering::Relaxed);
                    if i >= starts.len() {
                        break;
                    }
                    let (s, rng) = &starts[i];
                    let mut rng = rng.clone();
                    let mut agent_rng = Rng::new(rng.clone().next_u64() ^ 0xa6e7_a6e7);
                    let hp = s.player.hp;
                    let r = play_from(s.clone(), &mut rng, &mut agent_rng, &mut agent, false, hp);
                    out.lock().unwrap()[i] = Some(r);
                }
            });
        }
    });
    out.into_inner().unwrap().into_iter().map(|r| r.expect("every start played")).collect()
}

/// Plays each combat on to the end with the search agent (rung 4's
/// play-outs, docs/specs/rung4-check.md): a position from
/// `Combat.decode(bytes, seed)`, whose seed gives the play-out's random
/// events; a combat with a chance event pending (a paused option state) is
/// advanced first. `evaluator`, `features` and the search settings are as
/// for `run`. Returns per combat `{won, score, hp_end, healed, turns, stalled}` (`healed`: HP the win gave inside `hp_end`; `stalled`: past `PLAY_TURN_LIMIT` turns, lost, `hp_end` 0), in order; a
/// finished combat returns its own result.
#[pyfunction]
#[pyo3(signature = (combats, evaluator=None, features=None, limit=16, sample_k=0, turns=1, threads=None, explore=0.0, max_nodes=50_000))]
#[allow(clippy::too_many_arguments)]
fn play_on<'py>(
    py: Python<'py>,
    combats: Vec<PyRef<'py, Combat>>,
    evaluator: Option<Bound<'py, PyAny>>,
    features: Option<PyRef<'py, PyFeatures>>,
    limit: usize,
    sample_k: u32,
    turns: u8,
    threads: Option<usize>,
    explore: f32,
    max_nodes: usize,
) -> PyResult<Vec<Bound<'py, PyDict>>> {
    let starts: Vec<(CombatState, Rng)> = combats.iter().map(|c| (c.s.clone(), c.rng.clone())).collect();
    let threads = threads.unwrap_or_else(default_threads);
    let e = make_eval(evaluator.as_ref(), features.as_deref())?;
    let cfg = e.config(&config(limit, sample_k, turns, 0, max_nodes));
    let results = match e {
        Eval::Heuristic => py.detach(|| play_starts(&starts, || SearchAgent { explore, ..SearchAgent::new(Heuristic, cfg.clone()) }, threads)),
        Eval::Net(e) => py.detach(|| play_starts(&starts, || SearchAgent { explore, ..SearchAgent::new(e.clone(), cfg.clone()) }, threads)),
        Eval::Py(e) => {
            let r = py.detach(|| play_starts(&starts, || SearchAgent { explore, ..SearchAgent::new(e.clone(), cfg.clone()) }, threads));
            e.take_err()?;
            r
        }
    };
    results
        .into_iter()
        .map(|r| {
            let d = PyDict::new(py);
            d.set_item("won", r.won)?;
            d.set_item("score", r.score)?;
            d.set_item("hp_end", r.hp_end)?;
            d.set_item("turns", r.turns)?;
            d.set_item("healed", r.healed)?;
            d.set_item("stalled", r.turns > PLAY_TURN_LIMIT)?;
            Ok(d)
        })
        .collect()
}

/// Every card name, status cards included (the ids of `card_repr="ids"`).
#[pyfunction]
fn all_card_names() -> Vec<&'static str> {
    CardId::all().map(|c| c.name()).collect()
}

/// The name one general upgrade (the rest site, Armaments) makes of card
/// `name` (official or `gen:`): `Bash` -> `Bash+`, `gen:Searing Blow+` ->
/// `gen:Searing Blow+2`; `None` for a status or a card at its max level.
#[pyfunction]
fn upgrade_name(name: &str) -> PyResult<Option<String>> {
    registry::upgrade_name(name).map_err(err)
}

/// A content file's card entry (JSON text; `version` its file's version,
/// `official` for `content/cards.json`) at upgrade level `level`, as the
/// engine resolves its `upgrade` block for play: an entry without the
/// block, named `X+` or `X+<n>`. `None` for an entry with no upgrade block
/// or a level past its max (registry::card_level_json).
#[pyfunction]
#[pyo3(signature = (entry, level=1, official=false, version=2))]
fn card_level(entry: &str, level: u8, official: bool, version: u8) -> PyResult<Option<String>> {
    registry::card_level_json(entry, level, official, version).map_err(err)
}

/// A card name without its level marks: `Bash+` -> `Bash`,
/// `gen:Searing Blow+12` -> `gen:Searing Blow`.
#[pyfunction]
fn base_name(name: &str) -> String {
    registry::base_name(name).to_string()
}

/// Card names Ironclad decks are built from (no status cards).
#[pyfunction]
fn deck_card_names() -> Vec<&'static str> {
    deck_cards().map(|c| c.name()).collect()
}

/// Card names a character's decks are built from (no statuses or Shivs).
#[pyfunction]
fn class_card_names(character: &str) -> PyResult<Vec<&'static str>> {
    Ok(class_cards(self::character(character)?.class()).map(|c| c.name()).collect())
}

#[pyfunction]
fn character_names() -> Vec<&'static str> {
    Character::ALL.iter().map(|c| c.name()).collect()
}

/// What a run starts with at ascension `ascension` (docs/specs/ascension.md),
/// for a fight built from scratch: `{"hp", "max_hp"}` (A14 lowers max HP,
/// A6 starts at 90% of it: `Character::run_start_hp`), `"potion_slots"`
/// (2 from A11) and `"deck_adds"`, the cards the run's deck gets (Ascender's
/// Bane from A10, its pack loaded in this process).
#[pyfunction]
#[pyo3(signature = (character="ironclad", ascension=0))]
fn run_start<'py>(py: Python<'py>, character: &str, ascension: u8) -> PyResult<Bound<'py, PyDict>> {
    self::ascension(ascension)?;
    let ch = self::character(character)?;
    let (hp, max_hp) = ch.run_start_hp(ascension);
    let d = PyDict::new(py);
    d.set_item("hp", hp)?;
    d.set_item("max_hp", max_hp)?;
    d.set_item("potion_slots", sts_engine::potions::BASE_POTION_SLOTS - (ascension >= sts_engine::potions::FEWER_SLOTS_FROM) as usize)?;
    d.set_item("deck_adds", if ascension >= ASCENDERS_BANE_FROM { vec![ASCENDERS_BANE] } else { vec![] })?;
    Ok(d)
}

/// A character's starter deck.
#[pyfunction]
#[pyo3(signature = (character, variant="default"))]
fn starter_deck(character: &str, variant: &str) -> PyResult<Vec<&'static str>> {
    // A named variant: "default" or "game" (the Silent's with Survivor).
    let deck = self::character(character)?.starter_deck_variant(variant).ok_or_else(|| err(format!("unknown starter variant {variant:?}")))?;
    Ok(deck_names(&deck, &Binding::default()))
}

/// "hallway", "elite" or "boss" for an official encounter or a loaded pack's
/// `gen:<id>`.
#[pyfunction]
fn encounter_group(name: &str) -> PyResult<&'static str> {
    Ok(match encounter(name)?.group() {
        EncounterGroup::Hallway => "hallway",
        EncounterGroup::Elite => "elite",
        EncounterGroup::Boss => "boss",
    })
}

/// (bound, capacity): distinct generated/pack slot sets this process has
/// bound, and the most it can.
#[pyfunction]
fn slot_sets() -> (usize, usize) {
    (sts_engine::registry::slot_sets_bound(), sts_engine::registry::SLOT_SET_CAPACITY)
}

#[pyfunction]
fn encounter_names() -> Vec<&'static str> {
    Encounter::ALL.iter().map(|e| e.name()).collect()
}

#[pyfunction]
fn power_names() -> Vec<String> {
    Power::ALL.iter().map(|&p| power_name(p)).collect()
}

/// Whether the engine's amount of a power can go below 0 (its row's
/// `can_go_negative`): an official power by name, else a loaded pack power
/// by id. Without it a negative application only reduces it. It speaks of
/// the engine's sign, not the game's: the game holds Wraith Form at -n and
/// the engine holds WraithForm at +n (no flag), so a reader of the game's
/// amounts negates Wraith Form's before it reaches the engine.
#[pyfunction]
fn power_can_go_negative(name: &str) -> PyResult<bool> {
    let (b, p) = match self::power(name) {
        Ok(p) => (registry::Binding::default(), p),
        Err(_) => registry::bind_power(&registry::Binding::default(), name).map_err(err)?,
    };
    Ok(b.rules(p).can_go_negative)
}

/// Powers with hooks (rows in effects mode).
#[pyfunction]
fn hook_power_names() -> Vec<String> {
    Power::ALL.iter().filter(|&&p| is_hook_power(p)).map(|&p| power_name(p)).collect()
}

/// Every hook trigger name (the `known_triggers` vocabulary).
#[pyfunction]
fn trigger_names() -> Vec<String> {
    default_trigger_names()
}

/// Every condition name (the `known_conditions` vocabulary).
#[pyfunction(name = "condition_names")]
fn py_condition_names() -> Vec<String> {
    condition_names()
}

/// Every effect scalar name (the `known_effects` vocabulary).
#[pyfunction]
fn effect_names() -> Vec<String> {
    EFFECT_SCALARS.iter().map(|s| s.to_string()).collect()
}

/// Card names held out of every training pool (check 9 only).
#[pyfunction]
fn held_out_card_names() -> Vec<&'static str> {
    held_out_cards().map(|c| c.name()).collect()
}

/// A named card set from `configs/card-sets.json`, base and upgraded names
/// in card order; an unknown name is a `KeyError` naming the known sets.
#[pyfunction]
fn card_set(name: &str) -> PyResult<Vec<&'static str>> {
    match sts_engine::card_sets::get(name) {
        Some(ids) => Ok(ids.iter().map(|c| c.name()).collect()),
        None => Err(PyKeyError::new_err(format!(
            "unknown card set {name:?} (known: {})",
            sts_engine::card_sets::names().collect::<Vec<_>>().join(", ")
        ))),
    }
}

/// The card sets' names, in file order.
#[pyfunction]
fn card_set_names() -> Vec<&'static str> {
    sts_engine::card_sets::names().collect()
}

#[pymodule]
fn sts(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Combat>()?;
    m.add_class::<PyAction>()?;
    m.add_class::<PyFeatures>()?;
    m.add_class::<PyNet>()?;
    m.add_class::<PySolvedDb>()?;
    m.add_class::<PySolveStore>()?;
    m.add("PILES", PILES.to_vec())?;
    m.add("PILE_PARENTS", PILE_PARENTS.iter().copied().collect::<HashMap<&str, &str>>())?;
    m.add("ROW_KINDS", ROW_KINDS.to_vec())?;
    // The rule keys a content power or card may set (docs/specs/card-rules.md).
    m.add("POWER_RULE_KEYS", registry::POWER_RULE_KEYS.to_vec())?;
    m.add("CARD_RULE_KEYS", registry::CARD_RULE_KEYS.to_vec())?;
    m.add("MODIFIER_POWERS", MODIFIER_POWERS.iter().map(|&p| power_name(p)).collect::<Vec<_>>())?;
    m.add_function(wrap_pyfunction!(hook_power_names, m)?)?;
    m.add_function(wrap_pyfunction!(search, m)?)?;
    m.add_function(wrap_pyfunction!(search_action, m)?)?;
    m.add_function(wrap_pyfunction!(solve, m)?)?;
    m.add_function(wrap_pyfunction!(greedy_action, m)?)?;
    m.add_function(wrap_pyfunction!(random_action, m)?)?;
    m.add_function(wrap_pyfunction!(action_name, m)?)?;
    m.add_function(wrap_pyfunction!(load_content, m)?)?;
    m.add_function(wrap_pyfunction!(loaded_content, m)?)?;
    m.add_function(wrap_pyfunction!(make_specs, m)?)?;
    m.add_function(wrap_pyfunction!(run, m)?)?;
    m.add_function(wrap_pyfunction!(play_on, m)?)?;
    m.add_function(wrap_pyfunction!(all_card_names, m)?)?;
    m.add_function(wrap_pyfunction!(deck_card_names, m)?)?;
    m.add_function(wrap_pyfunction!(upgrade_name, m)?)?;
    m.add_function(wrap_pyfunction!(card_level, m)?)?;
    m.add_function(wrap_pyfunction!(base_name, m)?)?;
    m.add_function(wrap_pyfunction!(class_card_names, m)?)?;
    m.add_function(wrap_pyfunction!(character_names, m)?)?;
    m.add_function(wrap_pyfunction!(starter_deck, m)?)?;
    m.add_function(wrap_pyfunction!(run_start, m)?)?;
    m.add_function(wrap_pyfunction!(encounter_names, m)?)?;
    m.add_function(wrap_pyfunction!(slot_sets, m)?)?;
    m.add_function(wrap_pyfunction!(encounter_group, m)?)?;
    m.add_function(wrap_pyfunction!(power_names, m)?)?;
    m.add_function(wrap_pyfunction!(power_can_go_negative, m)?)?;
    m.add_function(wrap_pyfunction!(trigger_names, m)?)?;
    m.add_function(wrap_pyfunction!(py_condition_names, m)?)?;
    m.add_function(wrap_pyfunction!(effect_names, m)?)?;
    m.add_function(wrap_pyfunction!(held_out_card_names, m)?)?;
    m.add_function(wrap_pyfunction!(card_set, m)?)?;
    m.add_function(wrap_pyfunction!(card_set_names, m)?)?;
    m.add("ENTITIES", ENTITIES)?;
    m.add("MAX_MONSTERS", MAX_MONSTERS)?;
    m.add("PLAY_TURN_LIMIT", PLAY_TURN_LIMIT)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use sts_engine::cards::starter_deck;
    use sts_engine::state::{Pile, Stage};

    /// Keeps every state search asks about.
    struct Record(Vec<CombatState>);

    impl Evaluator for Record {
        fn evaluate(&mut self, states: &[CombatState]) -> Vec<f32> {
            self.0.extend_from_slice(states);
            vec![1.0; states.len()]
        }
    }

    /// A small net with fixed pseudo-random weights fitting `enc`.
    fn tiny_net(enc: &Encoder) -> Net {
        tiny_net_seeded(enc, 7)
    }

    fn tiny_net_seeded(enc: &Encoder, seed: u64) -> Net {
        let (h, w) = (6, 4);
        let [dp, dm, dc, dr] = enc.layout_dims();
        let mut rng = Rng::new(seed);
        let mut state = HashMap::new();
        let mut lin = |name: &str, n_in: usize, n_out: usize| {
            let mut v = |n: usize| (0..n).map(|_| (rng.unit() as f32 - 0.5) * 0.4).collect::<Vec<f32>>();
            let (wt, b) = (v(n_in * n_out), v(n_out));
            state.insert(format!("{name}.weight"), (wt, vec![n_out, n_in]));
            state.insert(format!("{name}.bias"), (b, vec![n_out]));
        };
        lin("row.0", dr, h);
        lin("row.2", h, w);
        lin("card.0", dc + w, h);
        lin("card.2", h, w);
        lin("monster.0", dm + w, h);
        lin("monster.2", h, w);
        lin("player.0", dp + w, w);
        lin("head.0.0", (enc.n_piles() + 3) * w, h);
        lin("head.0.2", h, h);
        lin("head.1", h, 1);
        let norm = [("player", dp), ("monsters", dm), ("cards", dc), ("rows", dr)]
            .into_iter()
            .map(|(k, d)| (k.to_string(), (vec![0.0; d], vec![10.0; d])))
            .collect();
        Net::new(&state, norm, enc.layout_dims(), Head::Score, 0.0).unwrap()
    }

    /// Pummel 2x4 under Weak shows 4 (1 a hit), not the total's 6: shown
    /// numbers round each hit (`CombatState::shown_damage`).
    #[test]
    fn shown_numbers_round_each_hit() {
        let id = |n: &str| CardId::from_name(n).unwrap();
        let mut s = CombatState::new(&starter_deck(), 80, 80, Encounter::ALL[0], &mut Rng::new(1));
        s.hand = sts_engine::Hand::from_cards(&[id("Pummel")]);
        s.set_draw(Pile::default());
        s.set_discard(Pile::default());
        s.player.powers.add(Power::Weak, 1);
        let plain = Encoder::new(CardRepr::Effects, &Vocab::default());
        let names = plain.card_names();
        let col = |n: &str| names.iter().position(|x| x == n).unwrap();
        let (dc, d) = (plain.card_dim(), col("damage_single"));
        let dmg = |b: &Batch| b.cards.chunks(dc).zip(&b.card_pile).find(|(_, &p)| p == 0).unwrap().0[d];
        assert_eq!(dmg(&plain.encode(&[&s])), 8.0);
        assert_eq!(dmg(&plain.clone().with_shown_numbers(true).encode(&[&s])), 4.0);
        assert_eq!(s.shown_damage(2, 4), 4);
    }

    /// `with_shown_numbers` writes the game's shown numbers; `with_exhaust_hidden`
    /// zeroes the exhaust counts only; both off is today's batch
    /// (docs/specs/shown-card-numbers.md).
    #[test]
    fn shown_numbers_and_exhaust_hidden() {
        let id = |n: &str| CardId::from_name(n).unwrap();
        let mut s = CombatState::new(&starter_deck(), 80, 80, Encounter::ALL[0], &mut Rng::new(1));
        s.hand = sts_engine::Hand::from_cards(&[id("Twin Strike"), id("Defend")]);
        s.set_draw(Pile::default());
        s.set_discard(Pile::default());
        s.set_exhaust(Pile::from_cards(&[id("Strike")]));
        let plain = Encoder::new(CardRepr::Effects, &Vocab::default());
        let names = plain.card_names();
        let col = |n: &str| names.iter().position(|x| x == n).unwrap();
        let (dc, d, bl) = (plain.card_dim(), col("damage_single"), col("block"));
        // (Twin Strike's damage, Defend's block) of a batch's hand.
        let hand = |b: &Batch| {
            let rows: Vec<&[f32]> = b.cards.chunks(dc).zip(&b.card_pile).filter(|(_, &p)| p == 0).map(|(r, _)| r).collect();
            let ts = rows.iter().find(|r| r[col("type_attack")] > 0.0).unwrap()[d];
            let df = rows.iter().find(|r| r[col("type_skill")] > 0.0).unwrap()[bl];
            (ts, df)
        };
        let shown = plain.clone().with_shown_numbers(true);
        let hidden = plain.clone().with_exhaust_hidden(true);
        // Twin Strike 5x2 under Weak: 3 a hit, 6 (the game's number).
        let cases: [(&[(Power, i16)], (f32, f32)); 5] = [
            (&[], (10.0, 5.0)),
            (&[(Power::Weak, 1)], (6.0, 5.0)),
            (&[(Power::Strength, 2), (Power::Dexterity, 1)], (14.0, 6.0)),
            (&[(Power::Strength, 2), (Power::Weak, 1), (Power::Dexterity, 1), (Power::Frail, 2)], (10.0, 4.0)),
            (&[(Power::Strength, -9), (Power::Dexterity, -9)], (0.0, 0.0)),
        ];
        for (powers, want) in cases {
            let mut s = s.clone();
            for &(p, n) in powers {
                s.player.powers.add(p, n);
            }
            let base = plain.encode(&[&s]);
            assert_eq!(hand(&base), (10.0, 5.0), "plain numbers are printed ones");
            assert_eq!(hand(&shown.encode(&[&s])), want, "{powers:?}");
            let hb = hidden.encode(&[&s]);
            let ex: Vec<f32> = hb.card_count.iter().zip(&hb.card_pile).filter(|(_, &p)| p == 3).map(|(&c, _)| c).collect();
            assert_eq!(ex, vec![0.0]);
            let rest = |b: &Batch| b.card_count.iter().zip(&b.card_pile).filter(|(_, &p)| p != 3).map(|(&c, _)| c).collect::<Vec<_>>();
            assert_eq!(rest(&hb), rest(&base));
            assert_eq!(hb.cards, base.cards);
            let off = plain.clone().with_shown_numbers(false).with_exhaust_hidden(false).encode(&[&s]);
            assert_eq!((off.cards, off.card_count), (base.cards.clone(), base.card_count.clone()));
        }
    }

    #[test]
    fn chunked_leaf_scores_match_one_batch() {
        let mut leaves = Record(Vec::new());
        let cfg = config(16, 2, 2, 0, 3_000);
        let mut deck = starter_deck();
        deck.extend(deck_cards().step_by(25));
        for (k, &e) in Encounter::ALL.iter().take(4).enumerate() {
            let s = CombatState::new(&deck, 80, 80, e, &mut Rng::new(k as u64));
            engine_search(&s, &mut leaves, &cfg);
        }
        let states = leaves.0;
        // The full layout, and a lean one (every third column dropped,
        // threshold rows dropped) that encodes through the gather.
        let full = Encoder::new(CardRepr::Effects, &Vocab::default());
        let mut lean = full.clone();
        let cols = full.layout_names().map(|p| p.into_iter().enumerate().filter(|(i, _)| i % 3 != 1).map(|(_, n)| n).collect());
        lean.set_layout(Some(cols), Some(vec!["triggered".into(), "held".into()]), None).unwrap();
        for enc in [full, lean] {
            let net = tiny_net(&enc);
            let whole = net_scores(&net, &enc, &states, usize::MAX, &mut Scratch::default());
            let chunked = net_scores(&net, &enc, &states, 7, &mut Scratch::default());
            let distinct: std::collections::HashSet<u32> = whole.iter().map(|v| v.to_bits()).collect();
            assert!(states.len() > 100 && distinct.len() > 10, "{} states, {} distinct scores", states.len(), distinct.len());
            assert_eq!(whole.len(), states.len());
            assert_eq!(chunked.len(), states.len());
            assert!(whole.iter().zip(&chunked).all(|(a, b)| a.to_bits() == b.to_bits()), "chunked scores differ");
            assert!(net_scores(&net, &enc, &[], 7, &mut Scratch::default()).is_empty());
        }
    }

    #[test]
    fn ensemble_scores_are_the_members_mean() {
        let mut leaves = Record(Vec::new());
        let s = CombatState::new(&starter_deck(), 80, 80, Encounter::ALL[0], &mut Rng::new(3));
        engine_search(&s, &mut leaves, &config(16, 2, 2, 0, 2_000));
        let states = leaves.0;
        let enc = Arc::new(Encoder::new(CardRepr::Effects, &Vocab::default()));
        let (a, b) = (Arc::new(tiny_net_seeded(&enc, 7)), Arc::new(tiny_net_seeded(&enc, 8)));
        let sa = net_scores(&a, &enc, &states, LEAF_CHUNK, &mut Scratch::default());
        let sb = net_scores(&b, &enc, &states, LEAF_CHUNK, &mut Scratch::default());
        assert!(sa.iter().zip(&sb).any(|(x, y)| x != y), "the two nets should differ");
        let one = NetEval { members: vec![(a.clone(), enc.clone(), Prices::default())], scratch: Scratch::default() }.clone().evaluate(&states);
        assert!(one.iter().zip(&sa).all(|(x, y)| x.to_bits() == y.to_bits()), "one member must score like its net");
        let two = NetEval { members: vec![(a.clone(), enc.clone(), Prices::default()), (b, enc.clone(), Prices::default())], scratch: Scratch::default() }.evaluate(&states);
        assert_eq!(two.len(), states.len());
        for ((m, x), y) in two.iter().zip(&sa).zip(&sb) {
            assert!((m - (x + y) / 2.0).abs() < 1e-6, "{m} vs mean of {x} and {y}");
        }
        // hp_bonus: c x clamp(score / 2) x (HP - start HP) on top of the net's score.
        let hp_only = Prices { hp_bonus: 0.01, enemy_strength: 0.0, hp_end: 0.0, strength_hits: 0.0, draw_k: 0, turn_start_leaf: false, leaf_clear_block: false, projected_ticks: 0, projected_debuffs: false, tie_break: false, win_cap: false };
        let bonus = NetEval { members: vec![(a.clone(), enc.clone(), hp_only)], scratch: Scratch::default() }.evaluate(&states);
        for ((v, x), s) in bonus.iter().zip(&sa).zip(&states) {
            let want = x + 0.01 * (x / 2.0).clamp(0.0, 1.0) * (s.player.hp - s.start_hp) as f32;
            assert!((v - want).abs() < 1e-6, "{v} vs {want}");
        }
        assert!(states.iter().any(|s| s.player.hp != s.start_hp), "some leaf should have lost HP");
        // win_cap: no leaf scores above a win at the HP it can still reach (less 0.001),
        // and a leaf already below that keeps the net's score.
        let capped = Prices { win_cap: true, ..Prices::default() };
        let cap_scores = NetEval { members: vec![(a.clone(), enc.clone(), capped)], scratch: Scratch::default() }.evaluate(&states);
        for ((v, x), s) in cap_scores.iter().zip(&sa).zip(&states) {
            let reach = (s.player.hp + s.win_heal_scaled()).min(s.player.max_hp);
            let want = x.min(2.0 - (s.start_hp - reach).max(0) as f32 / 100.0 - 0.001);
            assert!((v - want).abs() < 1e-6, "{v} vs {want}");
        }
        // enemy_strength_price: k x clamp(score / 2) x living monsters' Strength off the score,
        // beside the HP term; a Nob with +3 Strength and a dead monster's Strength (ignored).
        let mut nob = CombatState::new(&starter_deck(), 70, 80, Encounter::GremlinNob, &mut Rng::new(5));
        nob.monsters[0].powers.add(Power::Strength, 3);
        let mut dead = nob.clone();
        dead.monsters[0].hp = 0;
        let mut more = states.clone();
        more.extend([nob, dead]);
        let base = net_scores(&a, &enc, &more, LEAF_CHUNK, &mut Scratch::default());
        let both = Prices { hp_bonus: 0.01, enemy_strength: 0.02, hp_end: 0.0, strength_hits: 0.0, draw_k: 0, turn_start_leaf: false, leaf_clear_block: false, projected_ticks: 0, projected_debuffs: false, tie_break: false, win_cap: false };
        let priced = NetEval { members: vec![(a.clone(), enc.clone(), both)], scratch: Scratch::default() }.evaluate(&more);
        for ((v, x), s) in priced.iter().zip(&base).zip(&more) {
            let f = (x / 2.0).clamp(0.0, 1.0);
            let st: i16 = s.monsters.iter().filter(|m| m.alive()).map(|m| m.powers.get(Power::Strength)).sum();
            let want = x + 0.01 * f * (s.player.hp - s.start_hp) as f32 - 0.02 * f * st as f32;
            assert!((v - want).abs() < 1e-6, "{v} vs {want}");
        }
        assert_eq!(more[more.len() - 2].monsters[0].powers.get(Power::Strength), 3);
        // hp_end_bonus: c x clamp(score / 2) x (min(HP + win heal, max HP) - start HP).
        // strength_hits_price: k x clamp(score / 2) x strength_hits_left off the score.
        let sh_only = Prices { strength_hits: 0.01, ..Prices::default() };
        let sh = NetEval { members: vec![(a.clone(), enc.clone(), sh_only)], scratch: Scratch::default() }.evaluate(&more);
        for ((v, x), s) in sh.iter().zip(&base).zip(&more) {
            let want = x - 0.01 * (x / 2.0).clamp(0.0, 1.0) * strength_hits_left(s);
            assert!((v - want).abs() < 1e-6, "{v} vs {want}");
        }
        assert!(strength_hits_left(&more[more.len() - 2]) > 0.0, "the Nob leaf has Strength to price");
        let end_only = Prices { hp_end: 0.01, ..Prices::default() };
        let ended = NetEval { members: vec![(a, enc, end_only)], scratch: Scratch::default() }.evaluate(&more);
        for ((v, x), s) in ended.iter().zip(&base).zip(&more) {
            let end = (s.player.hp + s.win_heal).min(s.player.max_hp);
            let want = x + 0.01 * (x / 2.0).clamp(0.0, 1.0) * (end - s.start_hp) as f32;
            assert!((v - want).abs() < 1e-6, "{v} vs {want}");
        }
        assert!(more.iter().any(|s| s.win_heal == 6 && s.player.hp + 6 < s.player.max_hp), "some leaf should get the whole heal");
    }

    /// A histogram with all its mass on bin `i` of `rep`.
    fn one_hot(rep: &[f32], i: usize) -> Vec<f32> {
        let mut p = vec![0.0; rep.len()];
        p[i] = 1.0;
        p
    }

    #[test]
    fn histogram_score_rules() {
        use crate::net::external_score;
        let rep = [0.0, 10.0, 60.0, 150.0, 150.0];
        let survive = ScoreRule::Survive { c: 1.0, w: 2.0 };
        let mut s = CombatState::new(&starter_deck(), 50, 80, Encounter::ALL[0], &mut Rng::new(1));
        assert_eq!(s.win_heal, 6);
        // hp 50, 10 lost, healed 6: end 46. Engine (start 50): 2 - 4 / 100; survive: 1 + 2 x 46 / 100.
        assert_eq!(external_score(&one_hot(&rep, 1), &rep, ScoreRule::Engine, &s), 2.0 - (50.0 - 46.0) / 100.0);
        assert!((external_score(&one_hot(&rep, 1), &rep, survive, &s) - 1.92).abs() < 1e-6);
        // HP lost at or above the current HP, and the last two bins, never win.
        for i in [2, 3, 4] {
            assert_eq!(external_score(&one_hot(&rep, i), &rep, survive, &s), 0.0);
        }
        // The heal is capped at max HP: hp 78, nothing lost, ends at 80.
        s.player.hp = 78;
        assert!((external_score(&one_hot(&rep, 0), &rep, survive, &s) - 2.6).abs() < 1e-6);
        // Mixed mass: the probability-weighted sum (at hp 78, 60 lost still wins).
        let p = [0.5, 0.25, 0.25, 0.0, 0.0];
        let want = 0.5 * 2.6 + 0.25 * (1.0 + 2.0 * 74.0 / 100.0) + 0.25 * (1.0 + 2.0 * 24.0 / 100.0);
        assert!((external_score(&p, &rep, survive, &s) - want).abs() < 1e-6);
    }

    #[test]
    fn terminal_rule_scores_finished_combats() {
        let survive = ScoreRule::Survive { c: 1.0, w: 2.0 };
        let mut s = CombatState::new(&starter_deck(), 40, 80, Encounter::ALL[0], &mut Rng::new(1));
        s.start_hp = 70;
        s.stage = Stage::Over { won: true };
        assert_eq!(survive.terminal(&s), 1.0 + 2.0 * 40.0 / 100.0);
        assert_eq!(ScoreRule::Engine.terminal(&s), s.score() as f32);
        assert_eq!(ScoreRule::Engine.terminal(&s), 2.0 - 0.3);
        s.stage = Stage::Over { won: false };
        assert_eq!(survive.terminal(&s), 0.0);
        assert_eq!(ScoreRule::Engine.terminal(&s), 0.0);
    }

    #[test]
    fn search_scores_a_kill_with_its_rule() {
        // One monster at 1 HP: every attack ends the combat, so those options
        // are finished states scored by the search's rule (heal 6, capped at 80).
        let mut s = CombatState::new(&starter_deck(), 74, 80, Encounter::ALL[0], &mut Rng::new(2));
        assert_eq!(s.living_slots().count(), 1, "Cultist is alone");
        s.monsters[0].hp = 1;
        s.monsters[0].block = 0;
        let engine = engine_search(&s, &mut Record(Vec::new()), &config(16, 0, 1, 0, 50_000));
        let cfg = SearchConfig { rule: ScoreRule::Survive { c: 1.0, w: 2.0 }, ..config(16, 0, 1, 0, 50_000) };
        let survive = engine_search(&s, &mut Record(Vec::new()), &cfg);
        let best = |r: &SearchResult| r.options.iter().map(|o| o.value).fold(f32::MIN, f32::max);
        assert_eq!(best(&engine), 2.0 - (74.0 - 80.0f32).max(0.0) / 100.0);
        assert!((best(&survive) - (1.0 + 2.0 * 80.0 / 100.0)).abs() < 1e-6, "{}", best(&survive));
        // Unfinished options are the evaluator's (1.0) under both rules.
        assert!(survive.options.iter().any(|o| o.value == 1.0));
        // The end-HP bonus prices the kill's HP after the heal (80 - 74 = +6);
        // off, the kill scores exactly the engine's score.
        let cfg = SearchConfig { end_hp_price: 0.01, ..config(16, 0, 1, 0, 50_000) };
        let priced = engine_search(&s, &mut Record(Vec::new()), &cfg);
        assert!((best(&priced) - (2.0 + 0.01 * 6.0)).abs() < 1e-6, "{}", best(&priced));
        assert!(priced.options.iter().any(|o| o.value == 1.0));
    }

    #[test]
    fn end_hp_price_on_finished_combats() {
        let mut s = CombatState::new(&starter_deck(), 40, 80, Encounter::ALL[0], &mut Rng::new(1));
        s.start_hp = 50;
        s.stage = Stage::Over { won: true };
        let off = config(16, 0, 1, 0, 50_000);
        let on = SearchConfig { end_hp_price: 0.02, ..off.clone() };
        assert_eq!(off.finished(&s).to_bits(), (s.score() as f32).to_bits());
        let v = s.score() as f32;
        assert!((on.finished(&s) - (v + 0.02 * (v / 2.0).clamp(0.0, 1.0) * -10.0)).abs() < 1e-6);
        s.stage = Stage::Over { won: false };
        assert_eq!(on.finished(&s), 0.0);
    }
}
