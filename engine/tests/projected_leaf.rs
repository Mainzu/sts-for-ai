//! The projected leaf (docs/specs/projected-leaf.md): once-a-turn hooks that
//! apply Strength or Dexterity to their owner run k more times at an
//! end-of-turn leaf, for the player and each living monster.

mod common;

use common::*;
use sts_engine::monsters::MonsterKind as K;
use sts_engine::powers::Power;
use sts_engine::search::{search, Evaluator, Heuristic, SearchConfig};
use sts_engine::*;

struct Record(Vec<CombatState>);

impl Evaluator for Record {
    fn evaluate(&mut self, states: &[CombatState]) -> Vec<f32> {
        self.0.extend_from_slice(states);
        Heuristic.evaluate(states)
    }
}

fn base() -> CombatState {
    vs(&[K::Cultist], &["Defend", "Defend", "Strike", "Strike", "Strike"], Some(60))
}

#[test]
fn projects_demon_form() {
    let mut s = base();
    s.player.powers.add(Power::DemonForm, 2);
    s.player.powers.add(Power::Strength, 1);
    assert_eq!(s.projected_leaf(2).player.powers.get(Power::Strength), 5);
    assert_eq!(s.projected_leaf(0), s);
    // nothing else moves
    let mut p = s.projected_leaf(2);
    p.player.powers.add(Power::Strength, -4);
    assert_eq!(p, s);
}

#[test]
fn projects_ritual_on_monster_only_growth() {
    let mut s = base();
    s.monsters[0].powers.add(Power::Ritual, 3);
    s.player.powers.add(Power::LoseStrength, 2);
    s.player.powers.add(Power::Strength, 2);
    s.player.powers.add(Power::Metallicize, 3);
    let t = s.projected_leaf(3);
    assert_eq!(t.monsters[0].powers.get(Power::Strength), 9);
    assert_eq!(t.player.powers.get(Power::Strength), 2, "Lose Strength removes itself: not projected");
    assert_eq!(t.player.block, s.player.block, "Metallicize's block is not projected");
    // no hook at all: unchanged
    assert_eq!(base().projected_leaf(3), base());
}

#[test]
fn search_scores_projected_leaves() {
    let mut s = base();
    s.player.powers.add(Power::DemonForm, 1);
    let mut off = Record(Vec::new());
    let a = search(&s, &mut off, &SearchConfig::default());
    let mut zero = Record(Vec::new());
    let b = search(&s, &mut zero, &SearchConfig { projected_ticks: 0, ..SearchConfig::default() });
    assert_eq!(off.0, zero.0);
    assert_eq!(format!("{a:?}"), format!("{b:?}"));
    let mut on = Record(Vec::new());
    search(&s, &mut on, &SearchConfig { projected_ticks: 2, ..SearchConfig::default() });
    let ended: Vec<_> = off.0.iter().filter(|t| !t.is_over()).collect();
    assert!(!ended.is_empty());
    for t in on.0.iter().filter(|t| !t.is_over()) {
        assert!(t.player.powers.get(Power::Strength) >= 2, "every leaf carries two projected ticks");
    }
}
