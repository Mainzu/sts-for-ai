//! The counterfactual state price (docs/specs/counterfactual-state-price.md).

mod common;

use common::*;
use sts_engine::cf::{cf_price, cf_prices};
use sts_engine::monsters::MonsterKind as K;
use sts_engine::powers::Power;
use sts_engine::*;

/// Player turn against a Cultist one round in (Incantation used, its attack
/// shown), no powers.
fn base(hp: i16) -> CombatState {
    let mut s = vs(&[K::Cultist], &["Strike", "Strike", "Strike", "Strike", "Strike"], Some(hp));
    // Strikes only: no block absorbs a monster's Strength.
    // One round in: the Cultist has used Incantation and shows its attack.
    end_turn(&mut s);
    end_turn(&mut s);
    s.monsters[0].powers = Default::default();
    s.player.hp = 80;
    s
}

fn price(s: &CombatState, who: Who, p: Power) -> f32 {
    cf_prices(s, 4).into_iter().find(|e| e.0 == who && e.1 == p).expect("element priced").3
}

#[test]
fn no_elements_no_price() {
    let s = base(50);
    assert!(cf_prices(&s, 4).is_empty());
    assert_eq!(cf_price(&s, 4), 0.0);
}

#[test]
fn enemy_strength_costs() {
    let mut a = base(30);
    a.monsters[0].powers.add(Power::Strength, 3);
    let mut b = base(80);
    b.monsters[0].powers.add(Power::Strength, 3);
    let (pa, pb) = (price(&a, Who::Monster(0), Power::Strength), price(&b, Who::Monster(0), Power::Strength));
    assert!(pa < 0.0, "{pa}");
    assert!(pb < pa, "longer fight, bigger cost: {pb} vs {pa}");
}

#[test]
fn player_strength_pays() {
    let mut s = base(50);
    s.player.powers.add(Power::Strength, 2);
    assert!(price(&s, Who::Player, Power::Strength) > 0.0);
}

#[test]
fn weak_is_capped() {
    let mut one = base(80);
    one.monsters[0].powers.add(Power::Weak, 1);
    let mut three = base(80);
    three.monsters[0].powers.add(Power::Weak, 3);
    let (p1, p3) = (price(&one, Who::Monster(0), Power::Weak), price(&three, Who::Monster(0), Power::Weak));
    assert!(p1 > 0.0 && p1 <= p3, "{p1} {p3}");
}

#[test]
fn ritual_grows() {
    let mut r = base(80);
    r.monsters[0].powers.add(Power::Ritual, 3);
    let mut st = base(80);
    st.monsters[0].powers.add(Power::Strength, 3);
    let (pr, ps) = (price(&r, Who::Monster(0), Power::Ritual), price(&st, Who::Monster(0), Power::Strength));
    assert!(pr < ps, "Ritual 3 {pr} vs Strength 3 {ps}");
}

#[test]
fn deterministic() {
    let mut s = base(60);
    s.monsters[0].powers.add(Power::Strength, 2);
    s.player.powers.add(Power::DemonForm, 2);
    assert_eq!(cf_prices(&s, 4), cf_prices(&s, 4));
}

