//! Counterfactual state price (docs/specs/counterfactual-state-price.md):
//! the HP worth of each persistent element of a state (a held power of the
//! player or of a living monster), found by playing the greedy policy one
//! window forward with the element and without it, scaled by the rounds the
//! heuristic expects the fight to last. Reads powers only through the
//! engine's own play, so it prices content nothing has seen.

use crate::agent::greedy_action;
use crate::heuristic::{hp_loss_estimate, turns_left_estimate};
use crate::powers::Power;
use crate::rng::Rng;
use crate::state::{Action, CombatState, Who};

/// Actions a greedy turn may take before the window gives up.
const MAX_ACTIONS: usize = 200;

/// Living enemies' HP.
pub fn enemy_hp(s: &CombatState) -> i32 {
    s.living_slots().map(|i| s.monsters[i].hp as i32).sum()
}

/// Chance up to the next decision or the end of combat.
fn to_decision(t: &mut CombatState, rng: &mut Rng) {
    t.advance(rng);
}

/// One greedy player turn through its `EndTurn` (chance sampled on the way),
/// then chance up to the next decision. Stops at the end of combat.
pub fn greedy_round(t: &mut CombatState, rng: &mut Rng) {
    for _ in 0..MAX_ACTIONS {
        if t.is_over() {
            return;
        }
        if t.pending.is_some() {
            t.resolve_chance(rng);
            continue;
        }
        if !t.awaiting_action() {
            break;
        }
        let a = greedy_action(t);
        if t.apply_action(a).is_err() {
            break;
        }
        if a == Action::EndTurn {
            break;
        }
    }
    to_decision(t, rng);
}

/// The window from `s` with seed `seed`: `[s, after part 0, after part 1,
/// after part 2]` (part 2: one more greedy round, for growing elements).
fn window(s: &CombatState, seed: u64) -> [CombatState; 4] {
    let mut rng = Rng::new(seed);
    let mut t = s.clone();
    to_decision(&mut t, &mut rng);
    let p0 = t.clone();
    greedy_round(&mut t, &mut rng);
    let p1 = t.clone();
    greedy_round(&mut t, &mut rng);
    [s.clone(), p0, p1, t]
}

fn strength(s: &CombatState, who: Who) -> i16 {
    match who {
        Who::Player => s.player.powers.get(Power::Strength),
        Who::Monster(i) => {
            let m = &s.monsters[i as usize];
            if m.alive() {
                m.powers.get(Power::Strength)
            } else {
                0
            }
        }
    }
}

fn cleared(s: &CombatState, who: Who, p: Power) -> CombatState {
    let mut t = s.clone();
    match who {
        Who::Player => t.player.powers.clear(p),
        Who::Monster(i) => t.monsters[i as usize].powers.clear(p),
    }
    t
}

/// Every held power of the player and of each living monster, with its amount.
pub fn elements(s: &CombatState) -> Vec<(Who, Power, i16)> {
    let mut v: Vec<(Who, Power, i16)> = s.player.powers.iter().map(|(p, n)| (Who::Player, p, n)).collect();
    for i in s.living_slots() {
        v.extend(s.monsters[i].powers.iter().map(|(p, n)| (Who::Monster(i as u8), p, n)));
    }
    v
}

/// (who, power, amount, price in HP) for each element of `s`, `k` sampled
/// windows each (seeds 0..k, shared by the lines with and without it).
pub fn cf_prices(s: &CombatState, k: u32) -> Vec<(Who, Power, i16, f32)> {
    if s.is_over() || k == 0 {
        return Vec::new();
    }
    let els = elements(s);
    if els.is_empty() {
        return Vec::new();
    }
    let ehp = enemy_hp(s);
    let q = if ehp > 0 { hp_loss_estimate(s) / ehp as f32 } else { 0.0 };
    let rounds = (turns_left_estimate(s) - 1.0).max(0.0);
    // (HP lost, enemy HP removed) from state a to state b.
    let part = |a: &CombatState, b: &CombatState| -> (f32, f32) { ((a.player.hp - b.player.hp) as f32, (enemy_hp(a) - enemy_hp(b)) as f32) };
    let with: Vec<_> = (0..k as u64).map(|i| window(s, i)).collect();
    els.into_iter()
        .map(|(who, p, n)| {
            let base = cleared(s, who, p);
            let gap_start = (strength(s, who) - strength(&base, who)).abs();
            let mut total = 0.0;
            for (i, w) in with.iter().enumerate() {
                let o = window(&base, i as u64);
                // Part j's worth: the line with the element against the one without.
                let d = |j: usize| (part(&o[j], &o[j + 1]).0 - part(&w[j], &w[j + 1]).0) + q * (part(&w[j], &w[j + 1]).1 - part(&o[j], &o[j + 1]).1);
                let (d0, d1) = (d(0), d(1));
                let mut f = if w[2].is_over() || o[2].is_over() { 0.0 } else { rounds };
                if p.is_duration_debuff() {
                    f = f.min((n - 1).max(0) as f32);
                }
                let grows = (strength(&w[2], who) - strength(&o[2], who)).abs() > gap_start;
                total += if grows {
                    // Growth: round r after part 0 is worth d1 + (r - 1) x u, u the
                    // gain a round (part 2 against part 1); part 2 is played, so
                    // f - 1 rounds remain after it.
                    let d2 = d(2);
                    let u = d2 - d1;
                    let g = if w[3].is_over() || o[3].is_over() { 0.0 } else { (f - 1.0).max(0.0) };
                    d0 + d1 + d2 + g * d2 + u * g * (g + 1.0) / 2.0
                } else {
                    d0 + d1 * (f + 1.0)
                };
            }
            (who, p, n, total / k as f32)
        })
        .collect()
}

/// The sum of `cf_prices`, in HP.
pub fn cf_price(s: &CombatState, k: u32) -> f32 {
    cf_prices(s, k).iter().map(|e| e.3).sum()
}
