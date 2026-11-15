//! Hand-written evaluator: estimates the final score of a combat from its
//! state. Reads cards and monster moves only through their effect
//! primitives, so new cards and monsters built from the same primitives need
//! no changes here.
//!
//! The estimate: how much damage the deck deals and blocks per turn, how
//! long each monster takes to kill (killing in the order that minimises
//! damage taken), how much the monsters deal meanwhile, and so the HP left
//! at the end. Win probability is a smooth function of that HP.

use std::cell::RefCell;
use std::collections::HashMap;

use crate::agent::{hook_rates, intent_known, HookRates};
use crate::cards::{CardType, Tag};
use crate::chance::ChanceEvent;
use crate::effects::{Effect, Quantity, Target};
use crate::fxhash::FxBuild;
use crate::monsters::{MonsterKind, MoveDef, MoveId, NO_MOVE};
use crate::powers::Power;
use crate::search::Evaluator;
use crate::state::{CombatState, Stage, Who, DRAW_PER_TURN, ENERGY_PER_TURN, MAX_MONSTERS};

/// The heuristic as an [`Evaluator`].
pub struct Heuristic;

impl Evaluator for Heuristic {
    fn evaluate(&mut self, states: &[CombatState]) -> Vec<f32> {
        states.iter().map(estimate).collect()
    }
}

/// Share of the deck's damage output assumed to go into attacking (the rest
/// of the energy goes into blocking).
const ATTACK_SHARE: f32 = 0.75;
/// Share of the deck's block assumed to be useful in later rounds.
const BLOCK_USE: f32 = 0.7;
/// Steepness of the win probability in (damage to come / HP).
const WIN_CURVE: f32 = 4.0;
const MAX_ROUNDS: f32 = 50.0;
/// Damage one stack of Poison applied is worth (it ticks down over a few
/// rounds; fights are short).
const POISON_VALUE: f32 = 2.0;
/// Other cards in hand when a card that counts them is played (Fiend Fire).
const HAND_CARDS_EST: f32 = 4.0;
/// Of them, non-Attacks (Second Wind).
const NON_ATTACKS_EST: f32 = 2.0;

/// Per-turn output of the deck (hand, draw and discard).
struct Deck {
    dmg: f32,
    block: f32,
    skills: f32,
}

fn deck_output(s: &CombatState, living: usize, hr: &HookRates) -> Deck {
    let p = &s.player.powers;
    // Strength that grows each turn counts as two turns' worth.
    let growth = hr.strength + hr.strength_per_self_loss * hr.self_losses;
    let strength = p.get(Power::Strength) as f32 + hr.strength_once + 2.0 * growth;
    let dex = p.get(Power::Dexterity) as f32;
    let strikes: f32 = [s.hand.view(), s.draw(), s.discard()]
        .iter()
        .flat_map(|pile| pile.iter())
        .filter(|(c, _)| s.binding.def(*c).is_strike())
        .map(|(_, n)| n as f32)
        .sum();
    let (mut n, mut dmg, mut block, mut cost, mut draw, mut energy, mut skills) = (0f32, 0f32, 0f32, 0f32, 0f32, 0f32, 0f32);
    for pile in [s.hand.view(), s.draw(), s.discard()] {
        for (card, k) in pile.iter() {
            let k = k as f32;
            let d = s.binding.def(card);
            n += k;
            if d.unplayable() {
                continue;
            }
            cost += k * d.cost() as f32;
            skills += k * (d.ty == CardType::Skill) as u8 as f32;
            // Conditional rows count as if their condition held.
            for e in d.all_effects() {
                let (dm, bl) = match *e {
                    Effect::Damage { amount, hits, target } => {
                        let targets = if target == Target::AllOpponents { living.max(1) as f32 } else { 1.0 };
                        ((amount as f32 + strength).max(0.0) * hits as f32 * targets, 0.0)
                    }
                    Effect::PlainDamage { amount, target } => {
                        let targets = if target == Target::AllOpponents { living.max(1) as f32 } else { 1.0 };
                        (amount as f32 * targets, 0.0)
                    }
                    Effect::RandomDamage { amount, hits } => ((amount as f32 + strength).max(0.0) * hits as f32, 0.0),
                    // The same sums the three primitives these replaced used, so
                    // estimates on that content are unchanged.
                    Effect::ScaledDamage { amount, hits, target } => match (amount.of, hits.of) {
                        // Strength counts k + 1 times (Heavy Blade).
                        (Some(Quantity::OwnStrength), None) => (amount.base as f32 + (amount.kf() + 1.0) * strength, 0.0),
                        (Some(Quantity::CardsTagged(Tag::Strike)), None) => {
                            (amount.base as f32 + amount.kf() * strikes + strength, 0.0)
                        }
                        // Worth roughly one block card's block.
                        (Some(Quantity::OwnBlock), None) => (6.0 + strength, 0.0),
                        // The draw pile now (Mind Blast).
                        (Some(Quantity::DrawPileSize), None) => ((s.resolve(Who::Player, amount) as f32 + strength).max(0.0), 0.0),
                        // X-cost hits: X taken as a turn's energy, plus Chemical X's bonus.
                        (None, Some(Quantity::EnergySpent)) => {
                            let targets = if target == Target::AllOpponents { living.max(1) as f32 } else { 1.0 };
                            let x = hits.at(ENERGY_PER_TURN as i16 + s.relic_x_bonus()) as f32;
                            ((amount.base as f32 + strength).max(0.0) * x * targets, 0.0)
                        }
                        // Hits per card in hand (Fiend Fire): about four other cards.
                        (None, Some(Quantity::HandCards { .. })) => ((amount.base as f32 + strength).max(0.0) * HAND_CARDS_EST * hits.kf(), 0.0),
                        _ => (0.0, 0.0),
                    },
                    Effect::Block(b) => (0.0, b as f32 + dex),
                    // The block it would gain now (raw: no Dexterity).
                    Effect::BlockOf(a) => (0.0, s.resolve(Who::Player, a).max(0) as f32),
                    // Block per card counted (Second Wind): about two non-Attacks in hand.
                    Effect::ScaledBlock { amount, times } => match times.of {
                        None => (0.0, (amount as f32 + dex) * times.base as f32),
                        Some(_) => (0.0, (amount as f32 + dex) * NON_ATTACKS_EST * times.kf()),
                    },
                    Effect::Draw(m) => {
                        draw += k * m as f32;
                        (0.0, 0.0)
                    }
                    Effect::Apply { power: Power::Poison, amount, .. } => (POISON_VALUE * amount as f32, 0.0),
                    // As `Apply` of its amount resolved now.
                    Effect::ApplyOf { power: Power::Poison, amount, .. } => (POISON_VALUE * s.resolve(Who::Player, amount) as f32, 0.0),
                    Effect::RandomApply { power: Power::Poison, amount, hits } => (POISON_VALUE * (amount * hits as i16) as f32, 0.0),
                    Effect::GainEnergy(m) => {
                        energy += k * m as f32;
                        (0.0, 0.0)
                    }
                    _ => (0.0, 0.0),
                };
                dmg += k * dm;
                block += k * bl.max(0.0);
            }
        }
    }
    if n == 0.0 {
        return Deck { dmg: 0.0, block: 0.0, skills: 0.0 };
    }
    let cards = DRAW_PER_TURN as f32 * (1.0 + (draw / n).min(1.0)) + hr.draw;
    let energy = ENERGY_PER_TURN as f32 + cards * energy / n;
    let wanted = cards * cost / n;
    let scale = if wanted > energy { energy / wanted } else { 1.0 };
    Deck { dmg: cards * dmg / n * scale, block: cards * block / n * scale, skills: cards * skills / n * scale }
}

/// Damage and hits a move deals to the player, with the monster's current
/// powers; `vulnerable` says whether the player's Vulnerable counts.
fn move_damage(s: &CombatState, slot: usize, mv: &MoveDef, vulnerable: bool) -> (f32, f32) {
    s.move_attacks(slot, mv, vulnerable).fold((0.0, 0.0), |(dmg, hits), (d, h)| (dmg + d as f32 * h as f32, hits + h as f32))
}

/// Moves averaged over for a monster's damage per round, so cycles like
/// Slime Boss's (0, 0, 35) count at their average, not their next step.
const RATE_MOVES: usize = 4;

/// The walk's terms (probability, move) over a monster's next `RATE_MOVES`
/// rolls, in walk order. A monster AI reads only its kind, slot and move
/// history (`monsters::Ai`), so the terms are a function of those.
fn rate_terms(s: &CombatState, slot: usize) -> Vec<(f32, MoveId)> {
    let mut t = s.clone();
    let mut dist: Vec<([MoveId; 2], f32)> = vec![(s.monsters[slot].moves, 1.0)];
    let mut terms = Vec::new();
    for _ in 0..RATE_MOVES {
        let mut next: Vec<([MoveId; 2], f32)> = Vec::new();
        for (hist, p) in dist {
            t.monsters[slot].moves = hist;
            for (mv, q) in t.move_distribution(slot) {
                let pq = p * q as f32;
                terms.push((pq, mv));
                let h = [mv, hist[0]];
                match next.iter_mut().find(|(x, _)| *x == h) {
                    Some((_, r)) => *r += pq,
                    None => next.push((h, pq)),
                }
            }
        }
        dist = next;
    }
    terms
}

type RateKey = (MonsterKind, crate::monsters::Ascension, usize, [MoveId; 2], bool);

thread_local! {
    /// `rate_terms` per (kind, level, slot, moves, allies bit); bounded by the static content.
    static RATE_TERMS: RefCell<HashMap<RateKey, Vec<(f32, MoveId)>, FxBuild>> = RefCell::new(HashMap::default());
}

/// Expected (damage, hits) per round over the monster's next `RATE_MOVES`
/// rolls, before the player's Vulnerable.
pub fn damage_rate(s: &CombatState, slot: usize) -> (f32, f32) {
    let m = &s.monsters[slot];
    let moves = m.def().moves;
    RATE_TERMS.with(|cache| {
        let mut cache = cache.borrow_mut();
        let terms = cache.entry((m.kind, m.ascension, slot, m.moves, crate::monsters::allies_bit(s, slot))).or_insert_with(|| rate_terms(s, slot));
        let (mut dmg, mut hits) = (0.0, 0.0);
        for &(pq, mv) in terms.iter() {
            if let Some(d) = moves.get(mv as usize) {
                let (a, b) = move_damage(s, slot, d, false);
                dmg += pq * a;
                hits += pq * b;
            }
        }
        (dmg / RATE_MOVES as f32, hits / RATE_MOVES as f32)
    })
}

/// HP to chew through, counting the children a slime will split into.
fn split_hp(kind: MonsterKind, hp: f32, max_hp: f32, splitting: bool) -> f32 {
    let d = kind.def();
    if d.split_move == NO_MOVE {
        return hp;
    }
    let [a, b] = d.split_into;
    if splitting || 2.0 * hp <= max_hp {
        split_hp(a, hp, hp, false) + split_hp(b, hp, hp, false)
    } else {
        let half = max_hp / 2.0;
        hp - half + split_hp(a, half, half, false) + split_hp(b, half, half, false)
    }
}

struct Foe {
    ehp: f32,
    /// Damage of the attack it makes this round (or next, when the monsters
    /// already acted).
    now: f32,
    /// Expected damage per later round (averaged over its move pattern),
    /// before the player's Vulnerable.
    later: f32,
    /// Extra damage per round per round (Ritual, Enrage).
    growth: f32,
    weak: f32,
    /// Its Strength times its hits per round (`strength_hits_left`).
    strength_hits: f32,
}

/// Estimated final score, 0..=2.
pub fn estimate(s: &CombatState) -> f32 {
    parts(s).0
}

/// The HP the player is expected to lose from here to the end of combat,
/// the damage estimate `estimate` scores (0 once the combat is over).
pub fn hp_loss_estimate(s: &CombatState) -> f32 {
    parts(s).1
}

/// Rounds the heuristic expects the combat to last from here: the time to
/// kill every monster in its kill order (0 once the combat is over).
pub fn turns_left_estimate(s: &CombatState) -> f32 {
    parts(s).2
}

/// Hits the living monsters' Strength will still land, summed as Strength x
/// hits per round x rounds it lands them: each monster until the round the
/// kill order expects it dead, or the player's death at the expected rate
/// if sooner (docs/specs/strength-hits-price.md; 0 once the combat is over).
pub fn strength_hits_left(s: &CombatState) -> f32 {
    parts(s).3
}

/// (estimated final score, expected HP lost from here, rounds left,
/// `strength_hits_left`).
fn parts(s: &CombatState) -> (f32, f32, f32, f32) {
    if s.is_over() {
        return (s.score() as f32, 0.0, 0.0, 0.0);
    }
    let living: Vec<usize> = s.living_slots().collect();
    let hr = hook_rates(&s.player.powers, &s.binding);
    let deck = deck_output(s, living.len(), &hr);
    let dpt = (deck.dmg * ATTACK_SHARE + hr.damage_all * living.len() as f32).max(1.0);
    let bpt = deck.block + hr.block;
    let bpe = bpt / ENERGY_PER_TURN as f32;
    let dpe = dpt / ENERGY_PER_TURN as f32;
    let p = &s.player;
    let pw = &p.powers;

    // Monsters already acted this round: the player's next turn comes fresh.
    // Paused inside their turn (`MonsterActing`), later monsters still act
    // on the player's block, so it isn't counted as acted.
    // Once it has started (`StartTurn`, `TurnStarted`), its block and energy
    // are the state's: the pre-draw hooks' are in them.
    let monsters_acted = matches!(s.stage, Stage::MonsterRolls { .. })
        || (s.stage == Stage::PlayerTurn && matches!(s.pending, Some(ChanceEvent::Draw { .. })));
    let (block_now, energy_now) =
        if monsters_acted { (0.0, ENERGY_PER_TURN as f32) } else { (p.block as f32, p.energy.max(0) as f32) };

    let mut foes: Vec<Foe> = Vec::with_capacity(MAX_MONSTERS);
    for &slot in &living {
        let m = &s.monsters[slot];
        let mp = &m.powers;
        let mr = hook_rates(mp, &s.binding);
        let splitting = m.def().split_move != NO_MOVE && m.intent() == m.def().split_move;
        let mut ehp = split_hp(m.kind, m.hp as f32, m.max_hp as f32, splitting)
            + m.block as f32
            + mr.block_once
            + 2.0 * mr.block;
        // Poison still to tick.
        ehp = (ehp - mr.countdown_loss).max(1.0);
        let vuln = mp.get(Power::Vulnerable) as f32;
        if vuln > 0.0 {
            ehp = (ehp / 1.5).max(ehp - 0.5 * dpt * vuln);
        }
        let (later, hits) = damage_rate(s, slot);
        let now = if intent_known(s, slot) {
            m.intent_def().map_or(0.0, |d| move_damage(s, slot, d, true).0)
        } else {
            later
        };
        let growth = (mr.strength + mr.strength_per_skill * deck.skills) * hits.max(1.0);
        let strength_hits = mp.get(Power::Strength) as f32 * hits.max(0.0);
        foes.push(Foe { ehp, now, later, growth, weak: mp.get(Power::Weak) as f32, strength_hits });
    }

    // This round: block what's coming with the energy left, attack with the rest.
    let now_in: f32 = foes.iter().map(|f| f.now).sum();
    let to_block = (now_in - block_now).max(0.0);
    let block_energy = if bpe > 0.0 { (to_block / bpe).min(energy_now) } else { 0.0 };
    let unblocked_now = (to_block - block_energy * bpe).max(0.0);
    let mut credit = (energy_now - block_energy) * dpe;

    // Kill order that minimises damage taken: least HP per damage first.
    foes.sort_by(|a, b| (a.ehp * b.later.max(0.1)).total_cmp(&(b.ehp * a.later.max(0.1))));
    let mut extra_ehp = 0.25 * dpt * pw.get(Power::Weak) as f32;
    let mut cum = 0.0;
    let mut later_dmg = 0.0;
    let mut rounds = 0f32;
    let mut lands: Vec<(f32, f32)> = Vec::with_capacity(foes.len());
    for f in &foes {
        let mut ehp = f.ehp + std::mem::take(&mut extra_ehp);
        let used = credit.min(ehp);
        ehp -= used;
        credit -= used;
        cum += ehp;
        let t = (cum / dpt).min(MAX_ROUNDS);
        rounds = rounds.max(t);
        lands.push((f.strength_hits, t));
        later_dmg += f.later * (t - 0.25 * f.weak.min(t)) + f.growth * t * t / 2.0;
    }
    let vuln_p = pw.get(Power::Vulnerable) as f32;
    if rounds > 0.0 {
        later_dmg *= 1.0 + 0.5 * vuln_p.min(rounds) / rounds;
    }
    let frail = pw.get(Power::Frail) as f32;
    let absorbed = (bpt * (rounds - 0.25 * frail.min(rounds))).min(later_dmg) * BLOCK_USE;

    let taken = unblocked_now + (later_dmg - absorbed).max(0.0) + hr.self_loss * rounds;
    let hp = (p.hp as f32).max(1.0);
    let t_player = if taken > hp { rounds * hp / taken } else { f32::INFINITY };
    let strength_hits: f32 = lands.iter().map(|&(sh, t)| sh * t.min(t_player)).sum();
    // Even when far behind, more HP or less damage to come must still score
    // higher, so this never flattens to 0: 1/2 when the expected damage
    // equals the HP, falling off as a power of their ratio.
    let win = 1.0 / (1.0 + (taken / hp).powf(WIN_CURVE));
    let max = p.max_hp as f32;
    let left = (hp - taken + s.win_heal_scaled() as f32).clamp(0.0, max);
    let lost = (s.start_hp as f32 - left).max(0.0);
    ((win * (2.0 - lost / 100.0)).clamp(0.0, 2.0), taken, rounds, strength_hits)
}
