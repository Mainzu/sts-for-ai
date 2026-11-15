//! A pack in the format before upgrades as data (separate `X` and `X+`
//! entries) still loads and binds (docs/specs/card-upgrades.md). Its own
//! process: the rewritten pack defines the same ids differently.

use sts_engine::registry::{bind, load_pack};
use sts_engine::*;

const OLD_PACK: &str = include_str!("data/act1_ironclad_before_upgrades.json");

#[test]
fn old_format_pack_binds_its_upgrades() {
    load_pack(OLD_PACK).unwrap();
    let (ids, b) = bind(&["gen:Searing Blow+", "Defend"]).unwrap();
    let mut s = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &mut Rng::new(1));
    s.hand = Hand::from_cards(&[ids[0]]);
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    s.player.energy = 3;
    let hp = s.monsters[0].hp;
    s.monsters[0].block = 0;
    s.apply_action(Action::Play { card: ids[0], target: Some(0) }).unwrap();
    assert_eq!(hp - s.monsters[0].hp, 16);
}
