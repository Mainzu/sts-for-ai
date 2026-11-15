//! The fickle enemy's building blocks (docs/specs/fickle-enemy.md): the
//! Heal atom, and a pack power whose hook applies another pack power (a
//! cycle that moves one step per trigger).

mod common;
use common::*;
use sts_engine::monsters::MonsterKind as K;
use sts_engine::registry::{bind_power, load_pack};
use sts_engine::*;

const CYCLE: &str = r#"{"version": 1, "powers": [
 {"id": "fx_to_heal", "hooks": [{"trigger": "OwnerTurnStart", "effects": [{"Apply": {"power": "fx_heal5", "amount": 1, "target": "Me"}}, "RemoveSelf"]}]},
 {"id": "fx_gift_heal", "hooks": [{"trigger": "OwnerTurnEnd", "effects": [{"Apply": {"power": "fx_heal5", "amount": 1, "target": "AllOpponents"}}]}]},
 {"id": "fx_heal5", "hooks": [{"trigger": "OwnerTurnStart", "effects": [{"Heal": 5}]}]},
 {"id": "fx_a", "hooks": [
   {"trigger": {"CardPlayed": {"by": "Opponent"}}, "condition": {"CardType": "Attack"}, "effects": [{"Apply": {"power": "Strength", "amount": 1, "target": "Me"}}]},
   {"trigger": "OwnerTurnStart", "effects": [{"LoseHp": 3}, {"Apply": {"power": "fx_p", "amount": 1, "target": "Me"}}, "RemoveSelf"]}]},
 {"id": "fx_p", "hooks": [
   {"trigger": "OwnerTurnStart", "effects": [{"Heal": 3}, {"Apply": {"power": "fx_s", "amount": 1, "target": "Me"}}, "RemoveSelf"]}]},
 {"id": "fx_s", "hooks": [
   {"trigger": "OwnerTurnStart", "effects": [{"LoseHp": 3}, {"Apply": {"power": "fx_a", "amount": 1, "target": "Me"}}, "RemoveSelf"]}]}
]}"#;

/// A Cultist fight with pack power `id` (1 stack) on the Cultist, the
/// player at 500 HP holding `hand`.
fn with_pack_power(id: &str, hand: &[&str]) -> CombatState {
    load_pack(CYCLE).unwrap();
    let mut s = vs(&[K::Cultist], hand, None);
    s.player.hp = 500;
    s.player.max_hp = 500;
    let (b, p) = bind_power(&s.binding, id).unwrap();
    s.binding = b;
    s.monsters[0].powers.add(p, 1);
    s
}

fn slot(s: &CombatState, id: &str) -> Power {
    bind_power(&s.binding, id).unwrap().1
}

#[test]
fn heal_atom_heals_up_to_max() {
    let mut s = with_pack_power("fx_heal5", &[]);
    let max = s.monsters[0].max_hp;
    s.monsters[0].hp = max - 10;
    end_turn(&mut s);
    assert_eq!(s.monsters[0].hp, max - 5);
    s.monsters[0].hp = max - 2;
    end_turn(&mut s);
    assert_eq!(s.monsters[0].hp, max, "never above max HP");
}

#[test]
fn pack_power_hook_applies_pack_power() {
    let mut s = with_pack_power("fx_a", &["Strike", "Defend"]);
    // Binding the first power binds the cycle (its hooks' applies, transitively).
    assert_eq!(bind_power(&s.binding, "fx_s").unwrap().0, s.binding, "fx_s already bound");
    play(&mut s, "Defend", None);
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 0);
    play(&mut s, "Strike", Some(0));
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 1, "an Attack on an Attack turn");
    let max = s.monsters[0].max_hp;
    s.monsters[0].hp = max - 20;
    let (a, p, sk) = (slot(&s, "fx_a"), slot(&s, "fx_p"), slot(&s, "fx_s"));
    // One step per monster turn start, never the whole cycle at once.
    for (holds, hp) in [(p, max - 23), (sk, max - 20), (a, max - 23), (p, max - 26)] {
        end_turn(&mut s);
        let held: Vec<Power> = [a, p, sk].into_iter().filter(|&x| s.monsters[0].powers.get(x) > 0).collect();
        assert_eq!(held, vec![holds]);
        assert_eq!(s.monsters[0].hp, hp);
    }
}

#[test]
fn a_hook_naming_an_unknown_pack_power_is_refused() {
    let pack = r#"{"version": 1, "powers": [{"id": "fx_bad", "hooks": [{"trigger": "OwnerTurnStart",
        "effects": [{"Apply": {"power": "fx_nowhere", "amount": 1, "target": "Me"}}]}]}]}"#;
    assert!(load_pack(pack).is_err());
}

#[test]
fn the_bound_sees_a_heal_reached_through_a_hook_apply() {
    // The player holds a power that turns into a healing one.
    load_pack(CYCLE).unwrap();
    let mut s = vs(&[K::Cultist], &[], None);
    s.player.hp = 50;
    s.player.max_hp = 80;
    assert!(!s.can_heal());
    let (b, p) = bind_power(&s.binding, "fx_to_heal").unwrap();
    s.binding = b;
    s.player.powers.add(p, 1);
    assert!(s.can_heal(), "fx_to_heal becomes fx_heal5");
    // A monster's power that puts a healing power on the player.
    let mut s = vs(&[K::Cultist], &[], None);
    s.player.hp = 50;
    s.player.max_hp = 80;
    let (b, p) = bind_power(&s.binding, "fx_gift_heal").unwrap();
    s.binding = b;
    s.monsters[0].powers.add(p, 1);
    assert!(s.can_heal(), "the Cultist gives the player fx_heal5");
}
