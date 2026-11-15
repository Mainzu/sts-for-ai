//! The recurring debuff leaf (docs/specs/recurring-debuff-leaf.md): with
//! `projected_debuffs`, a living monster's once-a-turn Apply of Weak, Frail
//! or Vulnerable to the player runs k more times at the projected leaf.

use sts_engine::powers::Power;
use sts_engine::registry::{bind, load_pack, monster_kinds};
use sts_engine::search::{search, Heuristic, SearchConfig};
use sts_engine::*;

const HIT: &str = r#"{"name": "Hit", "effects": [{"Damage": {"amount": 5, "hits": 1, "target": "Opponent"}}]}"#;
const LAST: &str = r#"{"when": [], "then": {"Move": 0}}"#;

/// A monster starting with `rd_weak` 1 (OwnerTurnStart: Weak 1 to all
/// opponents) and `rd_frail` 1 (OwnerTurnEnd: Frail 1 to all opponents).
fn pack() -> String {
    let hook = |id: &str, trig: &str, p: &str| {
        format!(r#"{{"id": "{id}", "hooks": [{{"trigger": "{trig}", "condition": "Always", "effects": [{{"Apply": {{"power": "{p}", "amount": 1, "target": "AllOpponents"}}}}]}}]}}"#)
    };
    let start = r#", "start_powers": [{"power": "rd_weak", "amount": 1}, {"power": "rd_frail", "amount": 1}]"#;
    format!(
        r#"{{"version": 1, "powers": [{}, {}], "monsters": [{{"id": "rd_m", "hp": [50, 50]{start}, "moves": [{HIT}], "pattern": [{LAST}]}}]}}"#,
        hook("rd_weak", "OwnerTurnStart", "Weak"),
        hook("rd_frail", "OwnerTurnEnd", "Frail")
    )
}

fn fight() -> CombatState {
    load_pack(&pack()).unwrap();
    let kinds = monster_kinds(&["gen:rd_m"]).unwrap();
    let (ids, b) = bind(&["Strike", "Strike", "Defend", "Defend", "Bash"]).unwrap();
    let mut s = CombatState::new_vs(Character::Ironclad, &ids, &b, 80, 80, &kinds, &mut Rng::new(1));
    s.player.powers.add(Power::Weak, 1);
    s
}

#[test]
fn projects_recurring_weak_and_frail() {
    let s = fight();
    assert_eq!(s.projected_leaf_with(2, false), s.projected_leaf(2));
    assert_eq!(s.projected_leaf(2), s, "no Strength hook: @pl alone leaves it");
    let t = s.projected_leaf_with(2, true);
    assert_eq!(t.player.powers.get(Power::Weak), 3);
    assert_eq!(t.player.powers.get(Power::Frail), 2);
    assert_eq!(s.projected_leaf_with(0, true), s);
}

#[test]
fn artifact_cancels_a_projected_debuff() {
    let mut s = fight();
    s.player.powers.add(Power::Artifact, 1);
    let t = s.projected_leaf_with(2, true);
    // Weak runs first (one Apply of 2, cancelled by the one Artifact stack); Frail lands.
    assert_eq!(t.player.powers.get(Power::Artifact), 0);
    assert_eq!(t.player.powers.get(Power::Weak), 1);
    assert_eq!(t.player.powers.get(Power::Frail), 2);
}

#[test]
fn flag_without_ticks_is_off() {
    let s = fight();
    let mut h = Heuristic;
    let a = search(&s, &mut h, &SearchConfig::default());
    let b = search(&s, &mut h, &SearchConfig { projected_debuffs: true, ..SearchConfig::default() });
    assert_eq!(format!("{a:?}"), format!("{b:?}"));
}
