//! Options: the distinct choices at a decision, each with what it leads to.
//!
//! Actions are already distinct (`legal_actions`); options also merge
//! actions whose afterstates are equal. The afterstate (paused or not)
//! fixes the whole outcome distribution, so equal afterstates are the same
//! option.

use crate::chance::ChanceOutcomes;
use crate::state::{Action, CombatState};

#[derive(Clone, Debug)]
pub enum Outcome {
    /// No random event before the next decision (or the end of combat).
    Deterministic(CombatState),
    /// Few enough outcomes to list, every event on the way resolved: each
    /// state is at a decision or over.
    Chance(Vec<(f64, CombatState)>),
    /// Too many outcomes: the state paused at the first random event.
    Divergent(CombatState),
}

#[derive(Clone, Debug)]
pub struct Opt {
    /// Every action leading to this option, in `legal_actions` order.
    pub actions: Vec<Action>,
    pub outcome: Outcome,
}

/// Exact distribution of the states reached by resolving every pending
/// event, or `None` once it has more than `limit` outcomes or meets an event
/// with more than `limit`.
pub fn resolve_all(s: &CombatState, limit: usize) -> Option<Vec<(f64, CombatState)>> {
    let mut done: Vec<(f64, CombatState)> = Vec::new();
    let mut todo = vec![(1.0, s.clone())];
    while let Some((p, t)) = todo.pop() {
        match t.chance_outcomes(limit) {
            None => match done.iter_mut().find(|(_, d)| *d == t) {
                Some((q, _)) => *q += p,
                None => done.push((p, t)),
            },
            Some(ChanceOutcomes::Large) => return None,
            Some(ChanceOutcomes::Listed(v)) => todo.extend(v.into_iter().map(|(q, u)| (p * q, u))),
        }
        if done.len() > limit {
            return None;
        }
    }
    Some(done)
}

impl CombatState {
    /// Each distinct option at this decision; empty if not awaiting an action.
    pub fn options(&self, limit: usize) -> Vec<Opt> {
        let mut out: Vec<(CombatState, Opt)> = Vec::new();
        for a in self.legal_actions() {
            let mut after = self.clone();
            after.apply_action(a).expect("legal action applies");
            if let Some((_, o)) = out.iter_mut().find(|(s, _)| *s == after) {
                o.actions.push(a);
                continue;
            }
            let outcome = if after.pending.is_none() {
                Outcome::Deterministic(after.clone())
            } else {
                match resolve_all(&after, limit) {
                    Some(v) => Outcome::Chance(v),
                    None => Outcome::Divergent(after.clone()),
                }
            };
            out.push((after, Opt { actions: vec![a], outcome }));
        }
        out.into_iter().map(|(_, o)| o).collect()
    }
}
