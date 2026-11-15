//! `threshold::threshold` agrees with the rules (docs/specs/threshold-and-held-rows.md):
//! losing `hp_to_go - 1` HP doesn't switch the monster's move, losing
//! `hp_to_go` does, and its effects are what the switch does.

mod common;
use common::*;
use sts_engine::effects::Effect;
use sts_engine::monsters::{guardian, MonsterKind as K};
use sts_engine::threshold::{guardian_shift, threshold};
use sts_engine::*;

/// A fresh `kind` in slot 0 with `to_go` HP left before its threshold, and
/// a hand of one Strike (6 damage, no block in the way).
fn at(kind: K, to_go: i16) -> CombatState {
    let mut s = vs(&[kind], &["Strike"], None);
    let m = &mut s.monsters[0];
    if kind == K::TheGuardian {
        m.powers.add(Power::ModeShift, to_go - m.powers.get(Power::ModeShift));
    } else {
        m.hp = m.max_hp / 2 + to_go;
    }
    m.block = 0;
    s
}

#[test]
fn threshold_matches_rules() {
    for kind in [K::TheGuardian, K::AcidSlimeL, K::SpikeSlimeL, K::SlimeBoss] {
        let switch_to = if kind == K::TheGuardian { guardian::CLOSE_UP } else { kind.def().split_move };
        for to_go in [6, 7, 20] {
            let mut s = at(kind, to_go);
            assert_eq!(threshold(&s, 0).map(|t| t.hp_to_go), Some(to_go), "{kind:?} {to_go}");
            let before = s.monsters[0];
            play(&mut s, "Strike", Some(0));
            let m = s.monsters[0];
            assert_eq!(before.hp - m.hp, 6, "{kind:?}: Strike loses 6 HP");
            assert_eq!(m.intent() == switch_to, to_go <= 6, "{kind:?} {to_go}: switch iff 6 >= hp_to_go");
            match threshold(&s, 0) {
                None => assert!(to_go <= 6, "{kind:?} {to_go}: no threshold left only once it fired"),
                Some(t) => assert_eq!(t.hp_to_go, to_go - 6, "{kind:?} {to_go}"),
            }
            if kind == K::TheGuardian && to_go <= 6 {
                assert_eq!(m.block, guardian::DEFENSIVE_BLOCK, "Defensive mode's block after the card");
            }
        }
    }
}

#[test]
fn threshold_effects_are_the_switch() {
    let s = at(K::TheGuardian, 30);
    let close_up = K::TheGuardian.def().moves[guardian::CLOSE_UP as usize].effects;
    let shift = guardian_shift(K::TheGuardian.def());
    assert_eq!(shift[0], Effect::Block(guardian::DEFENSIVE_BLOCK));
    assert_eq!(&shift[1..], close_up);
    assert_eq!(threshold(&s, 0).unwrap().effects, shift);
    let s = at(K::AcidSlimeL, 10);
    assert_eq!(threshold(&s, 0).unwrap().effects, &[Effect::Split]);
}

#[test]
fn no_threshold_elsewhere() {
    assert_eq!(threshold(&vs(&[K::Cultist], &[], None), 0), None);
    assert_eq!(threshold(&vs(&[K::AcidSlimeM], &[], None), 0), None, "medium slimes don't split");
    let mut s = at(K::AcidSlimeL, 10);
    s.monsters[0].hp = s.monsters[0].max_hp / 2;
    assert_eq!(threshold(&s, 0), None, "at half HP or below");
    let mut s = at(K::TheGuardian, 30);
    s.monsters[0].powers.clear(Power::ModeShift);
    assert_eq!(threshold(&s, 0), None, "Defensive mode");
    assert_eq!(threshold(&s, 1), None, "empty slot");
}
