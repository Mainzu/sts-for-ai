//! Registry-lite (docs/specs/registry-lite.md): generated powers and power
//! cards loaded from a JSON pack and bound per combat to reserved slots.
//!
//! Written in step 1 against the API step 2 builds (switched on in step 2).
//!
//! API assumed (step 2 may rename; keep the checks):
//! - `registry::load_pack(&str) -> Result<u64, String>`: append-only; a
//!   second load of an identical definition is fine, a different one with
//!   the same id is an error.
//! - `registry::bind(&[&str]) -> Result<(Vec<CardId>, Binding), String>`:
//!   official names and `gen:<id>` names to card ids, generated ones bound
//!   to reserved slots in order of first appearance.
//! - `CombatState::new_bound(character, deck, &binding, hp, max_hp, encounter, rng)`.
//! - `Power::GEN`: the reserved power slots; slot 0 is the first generated
//!   power bound.
//! - `codec::encode` panics (message names "generated") on a bound state.

use sts_engine::agent::SearchAgent;
use sts_engine::codec;
use sts_engine::heuristic::Heuristic;
use sts_engine::registry::{self, Binding};
use sts_engine::runner::{play_from, CombatResult};
use sts_engine::search::SearchConfig;
use sts_engine::*;

/// A copy of Demon Form: the same hook, the same card.
const PACK: &str = r#"{
  "version": 1,
  "powers": [
    {"id": "gp_df", "debuff": false, "hooks": [
      {"trigger": "OwnerTurnStart", "condition": "Always",
       "effects": [{"Apply": {"power": "Strength", "amount": 1, "target": "Me"}}]}
    ]}
  ],
  "cards": [
    {"id": "gc_df", "cost": 3, "type": "Power", "exhaust": false, "ethereal": false,
     "effects": [{"Apply": {"power": "gp_df", "amount": 2, "target": "Me"}}]}
  ]
}"#;

fn load() {
    registry::load_pack(PACK).expect("pack loads");
}

fn card(name: &str) -> CardId {
    CardId::from_name(name).unwrap_or_else(|| panic!("no card {name}"))
}

/// Starter deck; `extra` goes straight into the hand (so the opening draw,
/// which samples by card id, is the same for the official card and its
/// copy), is played first, and then the heuristic plays the fight out.
fn play(enc: Encounter, seed: u64, extra: CardId, binding: &Binding) -> (CombatState, CombatResult) {
    let mut rng = Rng::new(seed);
    let mut s = CombatState::new_bound(Character::Ironclad, &starter_deck(), binding, 80, 80, enc, &mut rng);
    s.advance(&mut rng);
    s.hand.add(extra, 1);
    s.step(Action::Play { card: extra, target: None }, &mut rng).expect("Demon Form playable on turn 1");
    let after = s.clone();
    let mut agent = SearchAgent::new(Heuristic, SearchConfig::default());
    let r = play_from(s, &mut rng, &mut Rng::new(seed ^ 0x5eed), &mut agent, true, 80);
    (after, r)
}

#[test]
fn generated_demon_form_plays_like_demon_form() {
    load();
    let (ids, binding) = registry::bind(&["gen:gc_df"]).expect("binds");
    let copy = ids[0];
    for enc in [Encounter::Cultist, Encounter::GremlinNob, Encounter::Hexaghost] {
        for seed in 0..20 {
            let (a0, a) = play(enc, seed, card("Demon Form"), &Binding::default());
            let (b0, b) = play(enc, seed, copy, &binding);
            assert_eq!(a0.player.powers.get(Power::DemonForm), 2);
            assert_eq!(b0.player.powers.get(Power::GEN[0]), 2, "the copy's power sits in slot 0");
            assert_eq!(b0.player.powers.get(Power::DemonForm), 0);
            let ctx = format!("{enc:?} seed {seed}");
            assert_eq!((a.won, a.hp_end, a.turns), (b.won, b.hp_end, b.turns), "{ctx}");
            assert_eq!(a.score, b.score, "{ctx}");
            assert_eq!(a.trajectory.len(), b.trajectory.len(), "{ctx}");
            for (i, ((sa, xa), (sb, xb))) in a.trajectory.iter().zip(&b.trajectory).enumerate() {
                assert_eq!(xa, xb, "{ctx} step {i}: action");
                assert_eq!(sa.player.hp, sb.player.hp, "{ctx} step {i}");
                assert_eq!(sa.player.block, sb.player.block, "{ctx} step {i}");
                assert_eq!(sa.player.powers.get(Power::Strength), sb.player.powers.get(Power::Strength), "{ctx} step {i}");
                let hp = |s: &CombatState| s.monsters.iter().map(|m| m.hp).collect::<Vec<_>>();
                assert_eq!(hp(sa), hp(sb), "{ctx} step {i}");
            }
        }
    }
}

#[test]
fn generated_demon_form_has_demon_forms_rates() {
    use sts_engine::agent::hook_rates;
    use sts_engine::heuristic::turns_left_estimate;
    load();
    let (ids, binding) = registry::bind(&["gen:gc_df"]).expect("binds");
    for seed in 0..5 {
        let (a, _) = play(Encounter::Hexaghost, seed, card("Demon Form"), &Binding::default());
        let (b, _) = play(Encounter::Hexaghost, seed, ids[0], &binding);
        let ra = hook_rates(&a.player.powers, &a.binding);
        assert_eq!(ra.strength, 2.0, "Demon Form 2: +2 Strength a turn");
        assert_eq!(ra, hook_rates(&b.player.powers, &b.binding));
        assert_eq!(turns_left_estimate(&a), turns_left_estimate(&b));
        assert!(turns_left_estimate(&a) > 0.0);
    }
}

#[test]
fn binds_fifty_pack_cards() {
    // docs/specs/sparse-piles.md: no slot cap past 40 (32 until Entropic
    // Brew's pool needed 33, docs/specs/act1-singles.md section 5); slots
    // 40 and up take ids from NUM_CARD_IDS. A fight holds all 50 and plays.
    let cards: Vec<String> = (0..50)
        .map(|i| format!(r#"{{"id": "gc_c{i}", "cost": 1, "type": "Skill", "effects": [{{"Block": {}}}]}}"#, i + 1))
        .collect();
    registry::load_pack(&format!(r#"{{"version": 1, "cards": [{}]}}"#, cards.join(","))).expect("pack loads");
    let names: Vec<String> = (0..50).map(|i| format!("gen:gc_c{i}")).collect();
    let (ids, binding) = registry::bind(&names.iter().map(String::as_str).collect::<Vec<_>>()).expect("50 fit");
    let mut distinct = ids.clone();
    distinct.sort();
    distinct.dedup();
    assert_eq!(distinct.len(), 50);
    assert!(ids.iter().all(|&c| !registry::is_changed(c) && registry::card_slot(c).is_some()));
    assert_eq!(ids[40].0 as usize, registry::NUM_CARD_IDS);
    let mut rng = Rng::new(5);
    let mut s = CombatState::new_bound(Character::Ironclad, &ids, &binding, 80, 80, Encounter::ALL[0], &mut rng);
    s.advance(&mut rng);
    for _ in 0..30 {
        if s.is_over() {
            break;
        }
        let Some(a) = sts_engine::agent::random_action(&s, &mut rng) else { break };
        s.step(a, &mut rng).unwrap();
    }
    assert_eq!(s.all_piles().iter().map(|p| p.len()).sum::<usize>() + s.removed as usize, 50 + s.created as usize);
}

#[test]
fn binds_decks_past_the_inline_piles() {
    // The piles spill past PILES_INLINE entries (docs/specs/sparse-piles.md):
    // 41 distinct cards (past the old 40 a pile held) bind, and so does
    // every loaded card (past the old 52, 64 entries less MADE_ROOM).
    let cards: Vec<String> = (0..32)
        .map(|i| format!(r#"{{"id": "gq_c{i}", "cost": 1, "type": "Skill", "effects": [{{"Block": {}}}]}}"#, i + 1))
        .collect();
    registry::load_pack(&format!(r#"{{"version": 1, "cards": [{}]}}"#, cards.join(","))).expect("pack loads");
    let official = ["Strike", "Defend", "Bash", "Anger", "Cleave", "Clothesline", "Flex", "Strike+", "Headbutt"];
    let mut d: Vec<String> = (0..32).map(|i| format!("gen:gq_c{i}")).collect();
    d.extend(official.iter().map(|s| s.to_string()));
    registry::bind(&d.iter().map(String::as_str).collect::<Vec<_>>()).expect("41 distinct fit");
    registry::bind(&vec!["Strike"; 60]).expect("60 Strikes fit");
    let names: Vec<&str> = CardId::all().map(|c| c.name()).collect();
    assert!(names.len() > sts_engine::state::PILES_INLINE);
    registry::bind(&names).expect("every loaded card fits");
}

#[test]
fn slot_ids_round_trip() {
    for k in 0..registry::CARD_SLOTS {
        let c = registry::slot_card(k);
        assert_eq!(c.0 % 2, 0, "a slot's base id is even, its + the next");
        assert_eq!(registry::card_slot(c), Some(k));
        assert_eq!(registry::card_slot(CardId(c.0 + 1)), Some(k));
        assert!(!registry::is_changed(c));
    }
    // The 4 ids where the variants sat name no card.
    for i in 0..4 {
        assert_eq!(registry::card_slot(CardId((registry::VARIANT_BASE + i) as u16)), None);
    }
    for k in registry::CARD_SLOTS..registry::CARD_SLOTS + 50 {
        let c = registry::slot_card(k);
        assert_eq!((registry::card_slot(c), registry::card_slot(CardId(c.0 + 1))), (Some(k), Some(k)));
    }
    assert_eq!(registry::slot_card(registry::MAX_CARD_SLOTS - 1).0 + 1, registry::PARAM_BASE - 1);
    assert_eq!(registry::slot_card(0).0 as usize, sts_engine::cards::NUM_OFFICIAL_CARDS);
    assert_eq!(registry::slot_card(7).0, 142);
    assert_eq!(registry::slot_card(8).0, 148);
    // Slots 32-39 came after: 0-31 keep the ids they had.
    assert_eq!(registry::slot_card(31).0, 194);
    assert_eq!(registry::slot_card(39).0, 210);
    assert_eq!(sts_engine::cards::NUM_CARDS, 212);
}

#[test]
fn binds_twenty_four_pack_powers() {
    let mut powers = Vec::new();
    let mut cards = Vec::new();
    for i in 0..25 {
        powers.push(format!(
            r#"{{"id": "gp_n{i}", "debuff": false, "hooks": [{{"trigger": "OwnerTurnEnd", "condition": "Always", "effects": [{{"Block": {}}}]}}]}}"#,
            i + 1
        ));
        cards.push(format!(
            r#"{{"id": "gc_n{i}", "cost": 1, "type": "Power", "exhaust": false, "ethereal": false, "effects": [{{"Apply": {{"power": "gp_n{i}", "amount": 1, "target": "Me"}}}}]}}"#
        ));
    }
    let pack = format!(r#"{{"version": 1, "powers": [{}], "cards": [{}]}}"#, powers.join(","), cards.join(","));
    registry::load_pack(&pack).expect("pack loads");
    let fit: Vec<String> = (0..24).map(|i| format!("gen:gc_n{i}")).collect();
    let over: Vec<String> = (0..25).map(|i| format!("gen:gc_n{i}")).collect();
    fn refs(v: &[String]) -> Vec<&str> {
        v.iter().map(String::as_str).collect()
    }
    let (_, b) = registry::bind(&refs(&fit)).expect("24 fit");
    assert_eq!(b.power_id(Power::GEN[23]), Some("gp_n23"));
    let e = registry::bind(&refs(&over)).unwrap_err();
    assert!(e.contains("more than 24 generated powers"), "{e}");
}

#[test]
fn redefining_an_id_is_an_error() {
    load();
    load(); // the identical definition again is fine
    let changed = PACK.replace(r#""amount": 1"#, r#""amount": 2"#);
    assert!(registry::load_pack(&changed).is_err(), "gp_df redefined with another amount");
}

#[test]
fn unknown_generated_name_is_an_error() {
    assert!(registry::bind(&["gen:no_such_card"]).is_err());
}

#[test]
#[should_panic(expected = "generated")]
fn encoding_a_bound_state_panics() {
    load();
    let (_, binding) = registry::bind(&["gen:gc_df"]).expect("binds");
    let s = CombatState::new_bound(Character::Ironclad, &starter_deck(), &binding, 80, 80, Encounter::Cultist, &mut Rng::new(1));
    let _ = codec::encode(&s);
}

#[test]
fn unbound_state_encodes_as_before() {
    let mut rng = Rng::new(3);
    let a = CombatState::new(&starter_deck(), 80, 80, Encounter::JawWorm, &mut rng.clone());
    let b = CombatState::new_bound(Character::Ironclad, &starter_deck(), &Binding::default(), 80, 80, Encounter::JawWorm, &mut rng);
    assert_eq!(codec::encode(&a), codec::encode(&b));
}
