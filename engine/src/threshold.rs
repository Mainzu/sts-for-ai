//! Read-only description of a monster's HP threshold, for features: "when
//! this monster has lost N more HP, these effects happen" (The Guardian's
//! Mode Shift, the large slimes' split). The rules themselves stay in
//! `CombatState::lost_hp`; this module is outside the rules fingerprint, and
//! `engine/tests/threshold.rs` checks it against the rules.

use std::sync::OnceLock;

use crate::effects::Effect;
use crate::monsters::{guardian, MonsterDef, MonsterKind, NO_MOVE};
use crate::powers::Power;
use crate::state::CombatState;

/// A threshold: HP still to lose before it fires, and what firing does.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Threshold {
    pub hp_to_go: i16,
    pub effects: &'static [Effect],
}

/// Mode Shift firing for The Guardian at definition `d` (one per
/// ascension level): Defensive mode's block, then its Close Up's effects.
pub fn guardian_shift(d: &'static MonsterDef) -> &'static [Effect] {
    static SHIFTS: OnceLock<Vec<(usize, &'static [Effect])>> = OnceLock::new();
    let all = SHIFTS.get_or_init(|| {
        let base = MonsterKind::TheGuardian.def();
        std::iter::once(base)
            .chain(base.levels.iter().map(|(_, l)| *l))
            .map(|l| {
                let mut v = vec![Effect::Block(guardian::DEFENSIVE_BLOCK)];
                v.extend_from_slice(l.moves[guardian::CLOSE_UP as usize].effects);
                (l as *const MonsterDef as usize, &*Box::leak(v.into_boxed_slice()))
            })
            .collect()
    });
    all.iter().find(|(p, _)| *p == d as *const MonsterDef as usize).expect("one of The Guardian's definitions").1
}

/// The threshold of the live monster in `slot`, if it has one.
pub fn threshold(s: &CombatState, slot: usize) -> Option<Threshold> {
    let m = &s.monsters[slot];
    if !m.alive() {
        return None;
    }
    let t = if m.kind == MonsterKind::TheGuardian && m.powers.get(Power::ModeShift) > 0 {
        Threshold { hp_to_go: m.powers.get(Power::ModeShift), effects: guardian_shift(m.def()) }
    } else {
        let split = m.def().split_move;
        if split == NO_MOVE || m.intent() == split || 2 * m.hp <= m.max_hp {
            return None;
        }
        Threshold { hp_to_go: m.hp - m.max_hp / 2, effects: m.def().moves[split as usize].effects }
    };
    debug_assert!(t.hp_to_go > 0, "threshold already reached: {t:?}");
    (t.hp_to_go > 0).then_some(t)
}
