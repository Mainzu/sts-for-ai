//! Max HP and the heal by an amount (docs/specs/fractional-amounts.md,
//! step 3): `Quantity::OwnMaxHp` and `Effect::HealOf`, as Blood Potion's
//! "heal 1/5 of your max HP". Test pack content only.

mod common;

use common::*;
use sts_engine::effects::{Amount, Effect, Quantity};
use sts_engine::monsters::MonsterKind as K;
use sts_engine::registry::{bind, bind_power, effect_json, load_pack};
use sts_engine::*;

const PACK: &str = r#"{"version": 2, "powers": [
{"id": "HoUnblood", "hooks": [
  {"trigger": "OwnerUnbloodied", "condition": "Always", "effects": [{"Apply": {"power": "Strength", "amount": 1, "target": "Me"}}]}]},
{"id": "HoMend", "hooks": [
  {"trigger": "OwnerTurnEnd", "condition": "Always", "effects": [{"HealOf": {"base": 0, "k": "1/5", "of": "OwnMaxHp"}}]}]}
], "cards": [
{"id": "HoFifth", "cost": 0, "type": "Skill", "effects": [{"HealOf": {"base": 0, "k": "1/5", "of": "OwnMaxHp"}}]},
{"id": "HoNone", "cost": 0, "type": "Skill", "effects": [{"HealOf": {"base": -3, "k": "1/100", "of": "OwnMaxHp"}}]}
]}"#;

const NAMES: [&str; 2] = ["gen:HoFifth", "gen:HoNone"];

/// A Jaw Worm fight with the player at `hp` of `max_hp`, both test cards in
/// hand several times and `HoUnblood` on the player.
fn fight(hp: i16, max_hp: i16) -> (CombatState, Vec<CardId>) {
    load_pack(PACK).unwrap();
    let (ids, b) = bind(&NAMES).unwrap();
    let (b, p) = bind_power(&b, "HoUnblood").unwrap();
    let mut s = vs(&[K::JawWorm], &[], Some(40));
    s.binding = b;
    s.player.hp = hp;
    s.player.max_hp = max_hp;
    let hand: Vec<CardId> = ids.iter().flat_map(|&c| [c, c, c]).collect();
    s.hand = Hand::from_cards(&hand);
    s.player.energy = 3;
    s.player.powers.add(p, 1);
    (s, ids)
}

fn play_id(s: &mut CombatState, c: CardId) {
    s.apply_action(Action::Play { card: c, target: None }).expect("legal play");
}

#[test]
fn heal_of_max_hp() {
    // Blood Potion's heal: 16 at 80 max HP, 15 at 75 (75 / 5 = 15).
    let (mut s, ids) = fight(40, 80);
    play_id(&mut s, ids[0]);
    assert_eq!(s.player.hp, 56);
    // 40 of 80 is at most half; 56 is above: OwnerUnbloodied once.
    assert_eq!(s.player.powers.get(Power::Strength), 1);
    let (mut s, ids) = fight(40, 75);
    play_id(&mut s, ids[0]);
    assert_eq!(s.player.hp, 55);
    // 77 / 5 is 15.4: truncated to 15.
    let (mut s, ids) = fight(10, 77);
    play_id(&mut s, ids[0]);
    assert_eq!(s.player.hp, 25);
    // Capped at max HP.
    let (mut s, ids) = fight(75, 80);
    play_id(&mut s, ids[0]);
    assert_eq!(s.player.hp, 80);
    // A resolved amount at or below 0 heals nothing (-3 + 80/100 = -3).
    let (mut s, ids) = fight(40, 80);
    play_id(&mut s, ids[1]);
    assert_eq!(s.player.hp, 40);
    assert_eq!(s.player.powers.get(Power::Strength), 0);
    // Nothing at 0 HP.
    let (mut s, ids) = fight(0, 80);
    let _ = s.apply_action(Action::Play { card: ids[0], target: None });
    assert_eq!(s.player.hp, 0);
    // A monster's reads its own max HP: the worm at 40 of 90 heals 18.
    let (mut s, _) = fight(40, 80);
    let (b, p) = bind_power(&s.binding, "HoMend").unwrap();
    s.binding = b;
    s.monsters[0].max_hp = 90;
    s.monsters[0].hp = 40;
    assert_eq!(s.quantity(Who::Monster(0), Quantity::OwnMaxHp), 90);
    assert_eq!(s.quantity(Who::Player, Quantity::OwnMaxHp), 80);
    s.monsters[0].powers.add(p, 1);
    end_turn(&mut s);
    assert_eq!(s.monsters[0].hp, 58);
    // Scaled by stacks like BlockOf: 2 stacks of 1/5 is 2/5.
    assert_eq!(Effect::HealOf(Amount::frac(0, 1, 5, Quantity::OwnMaxHp).unwrap()).scaled(2), Effect::HealOf(Amount::frac(0, 2, 5, Quantity::OwnMaxHp).unwrap()));
    // Written back as loaded.
    assert_eq!(
        effect_json(&Effect::HealOf(Amount::frac(0, 1, 5, Quantity::OwnMaxHp).unwrap())).unwrap(),
        r#"{"HealOf": {"base": 0, "k": "1/5", "of": "OwnMaxHp"}}"#
    );
}

/// The game heals `(int)(maxHealth * f)` with a float `f` (Blood Potion:
/// `potency / 100.0F`); exact truncation agrees for every max HP 1-999 at
/// the shares the content uses (20%, 30%, 50%: 1/5, 3/10, 1/2).
#[test]
fn float_parity() {
    let mut differ = vec![];
    // 2/5: Blood Potion under Sacred Bark (potency 40, docs/specs/potions.md).
    for (a, b, potency) in [(1i32, 5i32, 20.0f32), (3, 10, 30.0), (1, 2, 50.0), (2, 5, 40.0)] {
        for m in 1..=999i32 {
            let exact = m * a / b;
            // Blood Potion's form: maxHealth * (potency / 100.0F).
            let game = (m as f32 * (potency / 100.0f32)) as i32;
            // The rest site's form: maxHealth * 0.3F, a float constant.
            let constant = (m as f32 * (a as f32 / b as f32)) as i32;
            if exact != game || exact != constant {
                differ.push((a, b, m, exact, game, constant));
            }
        }
    }
    assert!(differ.is_empty(), "max HP where the game's float differs (a, b, m, exact, potency form, constant form): {differ:?}");
}

#[test]
fn heal_of_lifts_the_bound() {
    let (mut s, ids) = fight(50, 80);
    s.hand = Hand::from_cards(&[ids[0]]);
    s.player.powers = Default::default();
    assert!(s.can_heal(), "a held HealOf card can heal");
    s.hand = Hand::default();
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    assert!(!s.can_heal(), "nothing left that heals");
}
