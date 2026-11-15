//! Trigger `OwnerApplied` and the condition `Applying`
//! (docs/specs/act1-singles.md section 6) beyond Champion Belt, whose game
//! cases are in `act1_relics.rs`. Its own file: the relics it loads stay
//! out of `act1_relics.rs`'s pack count.

use sts_engine::hooks::{hooks, Trigger};
use sts_engine::registry::{bind, load_pack, relics_named};
use sts_engine::*;

/// The `OwnerApplied` hook's own applications don't fire it again; the
/// `Applying` condition loads under `OwnerApplied` only; no official power
/// has an `OwnerApplied` hook (`apply_power` skips the pass for a player
/// with no relics or pack powers).
#[test]
fn owner_applied_rules() {
    assert!(!Power::ALL.into_iter().any(|p| hooks(p).iter().any(|h| h.trigger == Trigger::OwnerApplied)));
    // Weak -> Weak would loop if its own Apply fired it: it runs once.
    load_pack(
        r#"{"version": 2, "relics": [{"id": "oa-Echo", "rarity": "common", "hooks": [{"trigger": "OwnerApplied", "condition": {"Applying": "Weak"},
        "effects": [{"Apply": {"power": "Weak", "amount": 1, "target": "Opponent"}}]}]}]}"#,
    )
    .unwrap();
    let (ids, b) = bind(&starter_deck().iter().map(|&c| c.def().name).collect::<Vec<_>>()).unwrap();
    let mut s = CombatState::new_bound_with(Character::Ironclad, &ids, &b, 50, 80, Encounter::JawWorm, &relics_named(&["gen:oa-Echo"]).unwrap(), &mut Rng::new(11));
    let c = CardId::from_name("Clothesline").unwrap();
    s.hand.add(c, 1);
    s.player.energy = 3;
    s.step(Action::Play { card: c, target: Some(0) }, &mut Rng::new(13)).unwrap();
    assert_eq!(s.monsters[0].powers.get(Power::Weak), 3, "Clothesline's 2 and the hook's 1");
    let bad = |trigger: &str, cond: &str| {
        let r = format!(r#"{{"version": 2, "relics": [{{"id": "oa-bad", "rarity": "common", "hooks": [{{"trigger": {trigger}, "condition": {cond}, "effects": [{{"Block": 1}}]}}]}}]}}"#);
        load_pack(&r).unwrap_err()
    };
    assert!(bad(r#""OwnerTurnEnd""#, r#"{"Applying": "Vulnerable"}"#).contains("OwnerApplied hook's only"));
    assert!(bad(r#""OwnerTurnEnd""#, r#"["Always", {"Applying": "Vulnerable"}]"#).contains("OwnerApplied hook's only"));
    assert!(bad(r#""OwnerApplied""#, r#"{"Applying": "Nope"}"#).contains("not an official power"));
    let card = load_pack(r#"{"version": 2, "cards": [{"id": "oa-card", "cost": 0, "type": "Skill", "rows": [{"condition": {"Applying": "Weak"}, "effects": [{"Block": 1}]}]}]}"#);
    assert!(card.unwrap_err().contains("OwnerApplied hook's only"));
}
