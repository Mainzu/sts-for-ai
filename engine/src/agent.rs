//! Agents: random, greedy (one card at a time, hand-written rules) and
//! search with an evaluator.

use crate::cards::CardType;
use crate::chance::ChanceEvent;
use crate::effects::{Effect, Target};
use crate::hooks::{Condition, HpLossFrom, Side, Trigger};
use crate::monsters::{MoveDef, MoveId, NO_MOVE};
use crate::powers::{Power, Powers};
use crate::registry::Binding;
use crate::rng::Rng;
use crate::search::{search, Evaluator, OptionScore, SearchConfig, SearchResult};
use crate::state::{Action, CombatState, Stage};

pub trait Agent {
    /// Picks an action for a state awaiting one.
    fn act(&mut self, s: &CombatState, rng: &mut Rng) -> Action;

    /// The root options and values behind the latest `act`, for agents that
    /// search.
    fn last_options(&self) -> Option<&[OptionScore]> {
        None
    }
}

/// A uniformly random legal action; `None` when not awaiting one.
pub fn random_action(s: &CombatState, rng: &mut Rng) -> Option<Action> {
    let actions = s.legal_actions();
    if actions.is_empty() {
        return None;
    }
    Some(actions[rng.below(actions.len() as u32) as usize])
}

pub struct RandomAgent;

impl Agent for RandomAgent {
    fn act(&mut self, s: &CombatState, rng: &mut Rng) -> Action {
        random_action(s, rng).expect("state awaits an action")
    }
}

/// Damage the living monsters will deal to the player this round, from
/// their intents.
pub fn incoming_damage(s: &CombatState) -> i16 {
    s.living_slots().map(|slot| intent_damage(s, slot)).sum()
}

/// Damage the monster in `slot` will deal to the player with its intent
/// (0 for a dead slot or a move without attacks).
pub fn intent_damage(s: &CombatState, slot: usize) -> i16 {
    let m = &s.monsters[slot];
    let Some(mv) = m.intent_def().filter(|_| m.alive()) else { return 0 };
    s.move_attacks(slot, mv, true).map(|(d, h)| d * h as i16).sum()
}

/// Whether a monster's intent is the move it uses next (not still to roll).
pub fn intent_known(s: &CombatState, slot: usize) -> bool {
    let m = &s.monsters[slot];
    if m.intent() == NO_MOVE {
        return false;
    }
    match (s.stage, s.pending) {
        (Stage::MonsterRolls { .. }, Some(ChanceEvent::MonsterMove { slot: k } | ChanceEvent::AllyBlock { slot: k })) => slot < k as usize,
        (Stage::MonsterRolls { next }, _) => slot < next as usize,
        // Paused in the monsters' turn: monsters up to `k` have used the
        // move on show; their next isn't rolled yet.
        (Stage::MonsterActing { slot: k, .. }, _) => slot > k as usize,
        _ => true,
    }
}

/// Moves the lookahead rolls forward (the heuristic's `RATE_MOVES`).
pub const LOOK_MOVES: usize = 4;

/// A monster's next moves, from its AI rolled forward over its move history
/// (docs/specs/monster-lookahead.md).
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Lookahead {
    /// Move distribution at the first roll after the current history (the
    /// pending roll when the shown intent is stale), then the one after.
    pub next1: Vec<(MoveId, f32)>,
    pub next2: Vec<(MoveId, f32)>,
    /// Expected damage and hits per round over the next `LOOK_MOVES` rolls,
    /// with the monster's Strength and Weak, before the player's Vulnerable.
    pub rate_damage: f32,
    pub rate_hits: f32,
}

/// Damage and hits of a move with the monster's current powers, before the
/// player's Vulnerable.
fn move_damage(s: &CombatState, slot: usize, mv: &MoveDef) -> (f32, f32) {
    s.move_attacks(slot, mv, false).fold((0.0, 0.0), |(dmg, hits), (d, h)| (dmg + d as f32 * h as f32, hits + h as f32))
}

/// Rolls the monster in `slot` forward `LOOK_MOVES` moves from its current
/// move history, as the heuristic's damage rate does (state cloned, history
/// swapped per branch, branches merged by history). Only the history
/// changes, so HP, Strength or mode changes inside those moves aren't seen.
/// Empty for a dead or escaped monster.
pub fn lookahead(s: &CombatState, slot: usize) -> Lookahead {
    let m = &s.monsters[slot];
    if !m.alive() {
        return Lookahead::default();
    }
    let moves = m.def().moves;
    let mut t = s.clone();
    let mut dist: Vec<([MoveId; 2], f32)> = vec![(m.moves, 1.0)];
    let mut out = Lookahead::default();
    let (mut dmg, mut hits) = (0.0, 0.0);
    // Histories recur across steps; each one's distribution is rolled once.
    let mut seen: Vec<([MoveId; 2], Vec<(MoveId, f64)>)> = Vec::new();
    for step in 0..LOOK_MOVES {
        let mut next: Vec<([MoveId; 2], f32)> = Vec::new();
        let mut marginal: Vec<(MoveId, f32)> = Vec::new();
        for (hist, p) in dist {
            let i = match seen.iter().position(|(h, _)| *h == hist) {
                Some(i) => i,
                None => {
                    t.monsters[slot].moves = hist;
                    seen.push((hist, t.move_distribution(slot)));
                    seen.len() - 1
                }
            };
            let d = &seen[i].1;
            debug_assert!(!d.is_empty(), "{:?}: empty move distribution", m.kind);
            for &(mv, q) in d {
                let pq = p * q as f32;
                if let Some(d) = moves.get(mv as usize) {
                    let (a, b) = move_damage(s, slot, d);
                    dmg += pq * a;
                    hits += pq * b;
                }
                let h = [mv, hist[0]];
                match next.iter_mut().find(|(x, _)| *x == h) {
                    Some((_, r)) => *r += pq,
                    None => next.push((h, pq)),
                }
                if step < 2 {
                    match marginal.iter_mut().find(|(x, _)| *x == mv) {
                        Some((_, r)) => *r += pq,
                        None => marginal.push((mv, pq)),
                    }
                }
            }
        }
        debug_assert!((next.iter().map(|(_, p)| p).sum::<f32>() - 1.0).abs() < 1e-5, "{:?}: step {step} sums off 1", m.kind);
        match step {
            0 => out.next1 = marginal,
            1 => out.next2 = marginal,
            _ => {}
        }
        dist = next;
    }
    out.rate_damage = dmg / LOOK_MOVES as f32;
    out.rate_hits = hits / LOOK_MOVES as f32;
    out
}

/// What playing one card does, measured on a copy of the state.
struct PlayResult {
    action: Action,
    kills: usize,
    /// Monster HP + block removed.
    damage: i32,
    block: i16,
    cost: i8,
    hp_lost: i16,
    ty: CardType,
}

fn monster_total(s: &CombatState) -> i32 {
    s.living_slots().map(|i| (s.monsters[i].hp + s.monsters[i].block) as i32).sum()
}

/// One card at a time: kill if possible, else block incoming damage, else
/// the most damage per energy, else play any other card that doesn't cost
/// HP, else end the turn.
pub fn greedy_action(s: &CombatState) -> Action {
    // At a pick: the first option (cards in id order, then `Done`).
    if s.pick().is_some() {
        return s.legal_actions()[0];
    }
    let living = s.living_slots().count();
    let before = monster_total(s);
    let mut plays: Vec<PlayResult> = Vec::new();
    for a in s.legal_actions() {
        let Action::Play { card, .. } = a else { continue };
        let mut t = s.clone();
        // Random parts (draws, random targets) sampled with a fixed seed.
        t.step(a, &mut Rng::new(0)).expect("legal action applies");
        plays.push(PlayResult {
            action: a,
            kills: living - t.living_slots().count(),
            damage: before - monster_total(&t),
            block: t.player.block - s.player.block,
            cost: s.cost_of(card),
            hp_lost: s.player.hp - t.player.hp,
            ty: s.binding.def(card).ty,
        });
    }
    let per_energy = |x: f32, cost: i8| x / (cost.max(0) as f32).max(0.5);
    let best = |plays: &mut dyn Iterator<Item = &PlayResult>, key: &dyn Fn(&PlayResult) -> f32| {
        plays.max_by(|a, b| key(a).total_cmp(&key(b))).map(|p| p.action)
    };

    if let Some(a) = best(&mut plays.iter().filter(|p| p.kills > 0), &|p| p.kills as f32 * 100.0 - p.cost as f32) {
        return a;
    }
    let incoming = incoming_damage(s) - s.player.block;
    if incoming > 0 {
        if let Some(a) = best(&mut plays.iter().filter(|p| p.block > 0), &|p| per_energy(p.block as f32, p.cost)) {
            return a;
        }
    }
    if let Some(a) = best(&mut plays.iter().filter(|p| p.damage > 0), &|p| per_energy(p.damage as f32, p.cost)) {
        return a;
    }
    if let Some(p) = plays.iter().find(|p| p.hp_lost <= 0 && p.ty != CardType::Status) {
        return p.action;
    }
    Action::EndTurn
}

pub struct GreedyAgent;

impl Agent for GreedyAgent {
    fn act(&mut self, s: &CombatState, _: &mut Rng) -> Action {
        greedy_action(s)
    }
}

/// Index of an option picked by softmax over `values` at temperature
/// `temp`; at `temp` <= 0 the first best, without drawing from `rng`.
pub fn softmax_pick(values: &[f32], temp: f32, rng: &mut Rng) -> usize {
    let best = (0..values.len()).fold(0, |b, i| if values[i] > values[b] { i } else { b });
    if temp <= 0.0 {
        return best;
    }
    let w: Vec<f64> = values.iter().map(|&v| (((v - values[best]) / temp) as f64).exp()).collect();
    let mut u = rng.unit() * w.iter().sum::<f64>();
    for (i, &x) in w.iter().enumerate() {
        if u < x {
            return i;
        }
        u -= x;
    }
    best
}

/// Search with an evaluator. Each decision's sampling seed comes from the
/// agent's RNG; `last` keeps the latest result (for replays). With
/// `explore` > 0 (self-play rounds) the option is picked by softmax over the
/// root option values at that temperature; 0 plays the best option.
pub struct SearchAgent<E: Evaluator> {
    pub eval: E,
    pub cfg: SearchConfig,
    pub last: Option<SearchResult>,
    pub explore: f32,
}

impl<E: Evaluator> SearchAgent<E> {
    pub fn new(eval: E, cfg: SearchConfig) -> SearchAgent<E> {
        SearchAgent { eval, cfg, last: None, explore: 0.0 }
    }
}

impl<E: Evaluator> Agent for SearchAgent<E> {
    fn act(&mut self, s: &CombatState, rng: &mut Rng) -> Action {
        let cfg = SearchConfig { seed: rng.next_u64(), ..self.cfg.clone() };
        let r = search(s, &mut self.eval, &cfg);
        let mut a = r.action;
        if self.explore > 0.0 && !r.options.is_empty() {
            let values: Vec<f32> = r.options.iter().map(|o| o.value).collect();
            a = r.options[softmax_pick(&values, self.explore, rng)].actions[0];
        }
        self.last = Some(r);
        a
    }

    fn last_options(&self) -> Option<&[OptionScore]> {
        self.last.as_ref().map(|r| r.options.as_slice())
    }
}

/// What a combatant's hook powers do, read from their hooks, in outcome
/// units per turn (the heuristic's reading; the encoder's `rates` columns).
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct HookRates {
    /// Block at each of its turns (Metallicize).
    pub block: f32,
    /// Block once, when it next loses HP (Curl Up).
    pub block_once: f32,
    /// Strength gained each turn (Ritual, Demon Form).
    pub strength: f32,
    /// Strength gained or lost once, at its turn's end (Flex).
    pub strength_once: f32,
    /// Strength per Skill its opponent plays (Enrage).
    pub strength_per_skill: f32,
    /// Strength per HP loss it causes itself (Rupture).
    pub strength_per_self_loss: f32,
    /// HP it loses to its own powers each turn (Combust, Brutality), and
    /// how many separate losses that is.
    pub self_loss: f32,
    pub self_losses: f32,
    /// HP still to lose to a countdown: n + (n-1) + ... + 1 (Poison).
    pub countdown_loss: f32,
    /// Non-attack damage to every enemy each turn (Combust).
    pub damage_all: f32,
    /// Extra cards drawn each turn (Brutality).
    pub draw: f32,
}

impl HookRates {
    /// Field names in declaration order (the encoder's `rate_*` columns).
    pub const NAMES: [&'static str; 11] = ["block", "block_once", "strength", "strength_once", "strength_per_skill", "strength_per_self_loss", "self_loss", "self_losses", "countdown_loss", "damage_all", "draw"];

    /// The fields in `NAMES` order.
    pub fn values(&self) -> [f32; 11] {
        [self.block, self.block_once, self.strength, self.strength_once, self.strength_per_skill, self.strength_per_self_loss, self.self_loss, self.self_losses, self.countdown_loss, self.damage_all, self.draw]
    }
}

pub fn hook_rates(pw: &Powers, binding: &Binding) -> HookRates {
    let mut r = HookRates::default();
    for &p in binding.powers_in_play() {
        let k = pw.get(p) as f32;
        let hs = binding.hooks(p);
        if k <= 0.0 || hs.is_empty() {
            continue;
        }
        let once = hs.iter().any(|h| h.effects.contains(&Effect::RemoveSelf));
        let countdown = hs.iter().any(|h| h.effects.iter().any(|e| matches!(e, Effect::ReduceSelf(_))));
        for h in hs {
            let turn = h.trigger.is_turn_start() || h.trigger == Trigger::OwnerTurnEnd;
            for e in h.effects {
                match (h.trigger, *e) {
                    (_, Effect::Block(n)) if turn => r.block += n as f32 * k,
                    (Trigger::OwnerLostHp { .. }, Effect::Block(n)) => r.block_once += n as f32 * k,
                    (_, Effect::Apply { power: Power::Strength, amount, target: Target::Me }) => {
                        let a = amount as f32 * k;
                        match h.trigger {
                            _ if turn && once => r.strength_once += a,
                            _ if turn => r.strength += a,
                            Trigger::CardPlayed { by: Side::Opponent } if h.condition == Condition::CardType(CardType::Skill) => {
                                r.strength_per_skill += a
                            }
                            Trigger::OwnerLostHp { from: HpLossFrom::Card } => r.strength_per_self_loss += a,
                            _ => {}
                        }
                    }
                    (_, Effect::LoseHp(_)) if turn && countdown => r.countdown_loss += k * (k + 1.0) / 2.0,
                    (_, Effect::LoseHp(n)) if turn => {
                        r.self_loss += n as f32 * k;
                        r.self_losses += 1.0;
                    }
                    (_, Effect::PlainDamage { amount, target: Target::AllOpponents }) if turn => r.damage_all += amount as f32 * k,
                    (_, Effect::Draw(n)) if turn => r.draw += n as f32 * k,
                    _ => {}
                }
            }
        }
    }
    r
}
