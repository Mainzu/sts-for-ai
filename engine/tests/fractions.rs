//! Fractional amounts (docs/specs/fractional-amounts.md, step 2): an
//! amount's `k` as a fraction `a/b`, `base + trunc(k × quantity / per)`,
//! truncated toward zero as the game's `(int)` cast.

use sts_engine::effects::{Amount, Effect, Quantity};
use sts_engine::registry::{bind, effect_json, load_pack};
use sts_engine::upgrade::Upgrade;
use sts_engine::*;

fn pack(cards: &str) -> String {
    format!("{{\"version\": 1, \"cards\": [{cards}]}}")
}

/// A one-card pack whose card is `BlockOf` the amount `a` (JSON); the
/// card's first effect, or the load error.
fn load_block_of(id: &str, a: &str) -> Result<Effect, String> {
    load_pack(&pack(&format!(r#"{{"id": "{id}", "cost": 1, "type": "Skill", "effects": [{{"BlockOf": {a}}}]}}"#)))?;
    let (ids, b) = bind(&[&format!("gen:{id}")])?;
    Ok(b.def(ids[0]).effects[0])
}

fn block_of(base: i16, k: i16, per: i16) -> Effect {
    Effect::BlockOf(Amount { base, k, per, of: Some(Quantity::OwnBlock) })
}

#[test]
fn fraction_parse() {
    for (id, k, want) in [
        ("FpFifth", r#""1/5""#, block_of(0, 1, 5)),
        ("FpTwoTenths", r#""2/10""#, block_of(0, 1, 5)),
        ("FpNegHalf", r#""-1/2""#, block_of(0, -1, 2)),
        ("FpWhole", "3", block_of(0, 3, 1)),
        ("FpWholeString", r#""4/2""#, block_of(0, 2, 1)),
    ] {
        let e = load_block_of(id, &format!(r#"{{"base": 0, "k": {k}, "of": "OwnBlock"}}"#)).unwrap_or_else(|e| panic!("{id}: {e}"));
        assert_eq!(e, want, "{id}");
    }
    // A number with a fraction part (it loaded as 0 before), a zero bottom,
    // a string that isn't a fraction: errors naming the entry.
    for (id, k) in [("FpHalfNumber", "0.5"), ("FpZero", r#""1/0""#), ("FpWord", r#""x""#), ("FpBool", "true")] {
        let e = load_block_of(id, &format!(r#"{{"base": 0, "k": {k}, "of": "OwnBlock"}}"#)).expect_err(id);
        assert!(e.contains(id), "{id}: {e}");
    }
    // The writer gives the fraction back, and today's forms unchanged.
    assert_eq!(effect_json(&block_of(0, 1, 5)).unwrap(), r#"{"BlockOf": {"base": 0, "k": "1/5", "of": "OwnBlock"}}"#);
    assert_eq!(effect_json(&block_of(2, 3, 1)).unwrap(), r#"{"BlockOf": {"base": 2, "k": 3, "of": "OwnBlock"}}"#);
    // A written fraction loads back as itself.
    let back = effect_json(&block_of(1, -3, 7)).unwrap();
    let a = back.strip_prefix(r#"{"BlockOf": "#).and_then(|r| r.strip_suffix('}')).unwrap();
    assert_eq!(load_block_of("FpRoundTrip", a).unwrap(), block_of(1, -3, 7));
}

#[test]
fn fraction_resolve() {
    let mut s = CombatState::new(&starter_deck(), 80, 80, Encounter::JawWorm, &mut Rng::new(1));
    s.player.block = 25;
    let a = Amount::frac(0, 1, 12, Quantity::OwnBlock).unwrap();
    assert_eq!(s.resolve(Who::Player, a), 2);
    s.player.block = 5;
    // Toward zero, not down: -5/2 is -2.
    assert_eq!(s.resolve(Who::Player, Amount::frac(0, -1, 2, Quantity::OwnBlock).unwrap()), -2);
    // `at` in 32 bits: k × q past i16 still divides right.
    assert_eq!(Amount::frac(0, 300, 1000, Quantity::OwnBlock).unwrap().at(999), 299);
    // A power's stacks scale the top and keep the bottom.
    let t = Amount::frac(0, 1, 5, Quantity::OwnBlock).unwrap().times(3);
    assert_eq!((t.k, t.per), (3, 5));
    assert_eq!(block_of(0, 1, 5).scaled(3), block_of(0, 3, 5));
    // Whole amounts resolve as before.
    s.player.block = 7;
    assert_eq!(s.resolve(Who::Player, Amount::of(2, 3, Quantity::OwnBlock)), 23);
}

#[test]
fn fraction_upgrade() {
    // A bottom below 1 is refused, naming the card.
    let e = load_pack(&pack(
        r#"{"id": "FuBad", "cost": 1, "type": "Skill", "effects": [{"BlockOf": {"base": 0, "k": "1/2", "of": "OwnBlock"}}], "upgrade": {"effects.0.BlockOf.per": -2}}"#,
    ))
    .and_then(|_| bind(&["gen:FuBad+"]).map(|_| ()))
    .expect_err("per 0");
    assert!(e.contains("FuBad"), "{e}");
    load_pack(&pack(
        r#"{"id": "FuThird", "cost": 1, "type": "Skill", "effects": [{"BlockOf": {"base": 0, "k": "1/5", "of": "OwnBlock"}}], "upgrade": {"effects.0.BlockOf.per": -2}}"#,
    ))
    .unwrap();
    let def = |n: &str| {
        let (ids, b) = bind(&[n]).unwrap();
        b.def(ids[0])
    };
    let (d0, d1) = (def("gen:FuThird"), def("gen:FuThird+"));
    assert_eq!(d1.effects[0], block_of(0, 1, 3));
    // The diff between the two names the bottom.
    let up = Upgrade::between(&d0.parts(), &d1.parts()).expect("an upgrade");
    let paths: Vec<String> = up.changes.iter().map(|(p, _)| p.write()).collect();
    assert_eq!(paths, ["effects.0.BlockOf.per"]);
}
