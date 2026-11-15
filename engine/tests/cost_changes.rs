//! Cost changes in combat (docs/specs/cost-changes.md, building block C5):
//! a card that costs less per HP loss (Blood for Blood) and a power that
//! sets a type's cost and exhausts it when played (Corruption), from
//! `content/packs/act1-ironclad.json`.

use sts_engine::agent::greedy_action;
use sts_engine::cards::CardType;
use sts_engine::codec::{decode, encode};
use sts_engine::registry::{bind, card_json, load_pack};
use sts_engine::*;

const PACK: &str = include_str!("../../content/packs/act1-ironclad.json");

/// Test-only cards: an X-cost Skill and an unplayable Skill.
const EXTRA: &str = r#"{"version": 1, "cards": [
{"id": "CcXSkill", "cost": 0, "type": "Skill", "x_cost": true, "effects": []},
{"id": "CcUnplayable", "cost": 1, "type": "Skill", "unplayable": true, "effects": []}
]}"#;

/// (name, cost, cost upgraded, type), from sts_lightspeed's `Cards.h` and
/// wiki.gg (inventory "Block C5").
const SOURCE: [(&str, i8, i8, CardType); 2] = [("Blood for Blood", 4, 3, CardType::Attack), ("Corruption", 3, 2, CardType::Power)];

fn gen(name: &str) -> String {
    format!("gen:{name}")
}

fn id(name: &str) -> CardId {
    CardId::from_name(name).unwrap()
}

/// A combat against a Jaw Worm at 100 HP with the pack cards `pack` and the
/// official cards `hand` in hand, 10 energy, empty piles. Returns the state
/// and the ids of `pack` then `hand` in order.
fn setup(pack: &[&str], hand: &[&str]) -> (CombatState, Vec<CardId>) {
    load_pack(PACK).unwrap();
    load_pack(EXTRA).unwrap();
    let gens: Vec<String> = pack.iter().map(|n| gen(n)).collect();
    let mut names: Vec<&str> = gens.iter().map(String::as_str).collect();
    names.extend_from_slice(hand);
    let (ids, b) = bind(&names).unwrap();
    let mut s = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &mut Rng::new(1));
    s.hand = Hand::from_cards(&ids);
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    s.set_exhaust(Pile::default());
    s.player.energy = 10;
    let m = &mut s.monsters[0];
    m.hp = 100;
    m.max_hp = 100;
    m.block = 0;
    m.powers = Default::default();
    (s, ids)
}

fn play(s: &mut CombatState, card: CardId) {
    let target = if s.binding.def(card).targeted() { Some(0) } else { None };
    s.apply_action(Action::Play { card, target }).unwrap();
}

fn legal(s: &CombatState, card: CardId) -> bool {
    let target = if s.binding.def(card).targeted() { Some(0) } else { None };
    s.is_legal(Action::Play { card, target })
}

#[test]
fn every_entry_loads_as_the_source() {
    load_pack(PACK).unwrap();
    for (name, cost, cost_up, ty) in SOURCE {
        for (n, c) in [(name.to_string(), cost), (format!("{name}+"), cost_up)] {
            let (ids, b) = bind(&[&gen(&n)]).unwrap();
            let d = b.def(ids[0]);
            assert_eq!((d.cost(), d.ty, d.exhaust, d.x_cost()), (c, ty, false, false), "{n}");
            assert_eq!(d.cost_less_per_hp_loss, name == "Blood for Blood", "{n}");
        }
    }
    for (n, dmg) in [("Blood for Blood", 18), ("Blood for Blood+", 22)] {
        let (ids, b) = bind(&[&gen(n)]).unwrap();
        assert_eq!(format!("{:?}", b.def(ids[0]).effects), format!("[Damage {{ amount: {dmg}, hits: 1, target: Opponent }}]"), "{n}");
    }
}

/// The card a changed copy grew from (`c` itself for a plain card).
fn base_of(c: CardId) -> CardId {
    registry::copy_of(c).map_or(c, |(b, _)| b)
}

/// The one copy of `card` (changed or not) in the hand, draw or discard pile.
fn the_copy(s: &CombatState, card: CardId) -> CardId {
    let mut found: Vec<CardId> = Vec::new();
    for (c, n) in s.hand.iter().chain(s.draw().iter()).chain(s.discard().iter()) {
        if base_of(c) == card {
            found.extend(std::iter::repeat(c).take(n as usize));
        }
    }
    assert_eq!(found.len(), 1, "{found:?}");
    found[0]
}

#[test]
fn blood_for_blood_costs_less_per_loss() {
    let (mut s, ids) = setup(&["Blood for Blood"], &["Bloodletting", "Bloodletting", "Bloodletting", "Bloodletting", "Bloodletting", "Bloodletting"]);
    let (bfb, bl) = (ids[0], ids[1]);
    assert_eq!(s.cost_of(bfb), 4);
    play(&mut s, bl);
    let c = the_copy(&s, bfb);
    assert_eq!(s.cost_of(c), 3, "one HP loss (Bloodletting)");
    assert_eq!(s.binding.def(c).name, "gen:Blood for Blood{cost=3/combat}");
    // Playable at its effective cost and spends exactly it.
    s.player.energy = 3;
    assert!(legal(&s, c));
    play(&mut s, c);
    assert_eq!(s.player.energy, 0);
    // A monster hit fully blocked doesn't count.
    s.player.block = 99;
    let hp = s.player.hp;
    s.hand = Hand::default();
    s.step(Action::EndTurn, &mut Rng::new(5)).unwrap();
    assert_eq!(s.stage, Stage::PlayerTurn);
    assert_eq!(s.player.hp, hp, "the hit was blocked");
    assert_eq!(s.cost_of(the_copy(&s, bfb)), 3, "a blocked hit is no loss");
    // An unblocked monster hit counts (damage past block); Jaw Worm may
    // buff instead of attacking, so end turns until a hit lands.
    let mut seed = 6;
    while s.player.hp == hp {
        s.player.block = 0;
        s.step(Action::EndTurn, &mut Rng::new(seed)).unwrap();
        seed += 1;
        assert!(seed < 12, "Jaw Worm attacks within a few turns");
    }
    let c = the_copy(&s, bfb);
    assert_eq!(s.cost_of(c), 2, "one unblocked hit is one loss");
    // Never below 0, and playable with 0 energy at cost 0.
    s.hand = Hand::from_cards(&[c, bl, bl, bl, bl, bl]);
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    s.player.energy = 10;
    for _ in 0..5 {
        play(&mut s, bl);
    }
    let c = the_copy(&s, bfb);
    assert_eq!(s.cost_of(c), 0, "seven losses");
    s.player.energy = 0;
    assert!(legal(&s, c));
    play(&mut s, c);
    assert_eq!(s.player.energy, 0);
}

#[test]
fn counter_capped_and_off_without_card() {
    for (card, cap) in [("Blood for Blood", 4), ("Blood for Blood+", 3)] {
        let (mut s, ids) = setup(&[card], &["Bloodletting"; 7]);
        for k in 1..=7u8 {
            play(&mut s, ids[1]);
            assert_eq!(s.times_lost_hp, k.min(cap), "{card}: {k} losses");
        }
    }
    // Five and seven losses are the same state once the rest agrees.
    let (mut a, ids) = setup(&["Blood for Blood"], &["Bloodletting"; 7]);
    let mut b = a.clone();
    for _ in 0..5 {
        play(&mut a, ids[1]);
    }
    for _ in 0..7 {
        play(&mut b, ids[1]);
    }
    a.player.hp = b.player.hp;
    a.player.energy = b.player.energy;
    a.hand = b.hand;
    a.set_discard(b.discard());
    a.cards_played_this_turn = b.cards_played_this_turn;
    assert_eq!(a, b);
    // Official content: the counter never moves, the encoding is the old one.
    let mut s = CombatState::new(&starter_deck(), 80, 80, Encounter::JawWorm, &mut Rng::new(3));
    s.hand = Hand::from_cards(&[id("Bloodletting"), id("Bloodletting")]);
    s.player.energy = 3;
    for _ in 0..2 {
        s.apply_action(Action::Play { card: id("Bloodletting"), target: None }).unwrap();
    }
    assert_eq!(s.times_lost_hp, 0);
    assert_eq!(decode(&encode(&s)), s);
}

#[test]
fn corruption_skills_cost_zero_and_exhaust() {
    let (mut s, ids) = setup(&["Corruption", "Feel No Pain", "Disarm"], &["Defend", "Strike"]);
    let (corr, fnp, disarm, defend, strike) = (ids[0], ids[1], ids[2], ids[3], ids[4]);
    play(&mut s, fnp);
    assert_eq!(s.cost_of(defend), 1, "before Corruption");
    play(&mut s, corr);
    assert_eq!((s.cost_of(defend), s.cost_of(disarm), s.cost_of(strike)), (0, 0, 1));
    s.player.energy = 0;
    s.player.block = 0;
    assert!(legal(&s, defend) && !legal(&s, strike));
    play(&mut s, defend);
    assert_eq!(s.player.energy, 0);
    assert_eq!((s.exhaust().count(defend), s.discard().count(defend)), (1, 0), "Defend exhausted");
    assert_eq!(s.player.block, 5 + 3, "Defend's block and Feel No Pain's");
    // A Skill that already exhausts exhausts once.
    play(&mut s, disarm);
    assert_eq!(s.exhaust().count(disarm), 1);
    assert_eq!(s.player.block, 5 + 3 + 3, "Feel No Pain once more");
    // An Attack still costs its cost and is discarded.
    s.player.energy = 1;
    play(&mut s, strike);
    assert_eq!(s.player.energy, 0);
    assert_eq!((s.discard().count(strike), s.exhaust().count(strike)), (1, 0));
}

#[test]
fn corruption_leaves_x_and_unplayable() {
    let (mut s, ids) = setup(&["Corruption", "CcXSkill", "CcUnplayable"], &[]);
    let (corr, x, unplayable) = (ids[0], ids[1], ids[2]);
    play(&mut s, corr);
    assert!(!legal(&s, unplayable), "unplayable stays unplayable");
    s.player.energy = 3;
    play(&mut s, x);
    assert_eq!(s.player.energy, 0, "X spends all energy");
}

#[test]
fn second_corruption_changes_nothing() {
    let (mut one, ids) = setup(&["Corruption", "Corruption"], &["Defend"]);
    let (corr, defend) = (ids[0], ids[2]);
    let mut two = one.clone();
    play(&mut one, corr);
    play(&mut two, corr);
    play(&mut two, corr);
    for s in [&mut one, &mut two] {
        assert_eq!(s.cost_of(defend), 0);
        s.player.energy = 0;
        play(s, defend);
        assert_eq!(s.exhaust().count(defend), 1);
    }
}

#[test]
fn load_refuses_bad_rules() {
    let power = |n: u32, rule: &str| format!("{{\"version\": 1, \"powers\": [{{\"id\": \"CcBad{n}\", {rule}}}], \"cards\": []}}");
    load_pack(&power(0, "\"sets_cost\": {\"type\": \"Attack\", \"cost\": 1}, \"exhausts_played\": \"Power\"")).unwrap();
    for (n, rule, field) in [
        (1, "\"sets_cost\": {\"type\": \"Card\", \"cost\": 0}", "sets_cost"),
        (2, "\"sets_cost\": {\"type\": \"Skill\", \"cost\": 10}", "sets_cost"),
        (3, "\"sets_cost\": {\"type\": \"Skill\", \"cost\": -1}", "sets_cost"),
        // Any card type loads (Blue Candle's Curse; blocked-relics step 6).
        (4, "\"exhausts_played\": \"Card\"", "exhausts_played"),
    ] {
        let e = load_pack(&power(n, rule)).unwrap_err();
        assert!(e.contains(field), "{rule}: {e}");
    }
}

#[test]
fn entries_round_trip() {
    load_pack(PACK).unwrap();
    // Corruption's cards apply a pack power, which a card entry names by its
    // slot; the power is checked by reloading it below.
    for n in ["Blood for Blood", "Blood for Blood+"] {
        let (ids, b) = bind(&[&gen(n)]).unwrap();
        let d = b.def(ids[0]);
        let rt = format!("rt_cost_{}", n.replace(' ', "_").replace('+', "_up"));
        let entry = card_json(&rt, d).unwrap();
        load_pack(&format!("{{\"version\": 1, \"cards\": [{entry}]}}")).unwrap_or_else(|e| panic!("{n}: {e}\n{entry}"));
        let (ids2, b2) = bind(&[&gen(&rt)]).unwrap();
        let d2 = b2.def(ids2[0]);
        assert_eq!((d2.cost(), d2.cost_less_per_hp_loss, d2.effects), (d.cost(), d.cost_less_per_hp_loss, d.effects), "{n}");
    }
    // The power rules are part of the power's definition: the same entry
    // reloads, a changed rule under the same id is refused.
    load_pack(r#"{"version": 1, "powers": [{"id": "Corruption", "sets_cost": {"type": "Skill", "cost": 0}, "exhausts_played": "Skill"}]}"#).unwrap();
    let e = load_pack(r#"{"version": 1, "powers": [{"id": "Corruption", "sets_cost": {"type": "Skill", "cost": 0}, "exhausts_played": "Attack"}]}"#).unwrap_err();
    assert!(e.contains("redefined"), "{e}");
    let e = load_pack(r#"{"version": 1, "powers": [{"id": "Corruption", "sets_cost": {"type": "Skill", "cost": 1}, "exhausts_played": "Skill"}]}"#).unwrap_err();
    assert!(e.contains("redefined"), "{e}");
}

fn hash_of(s: &CombatState) -> u64 {
    use std::hash::{Hash, Hasher};
    let mut h = std::collections::hash_map::DefaultHasher::new();
    s.hash(&mut h);
    h.finish()
}

#[test]
fn the_counter_round_trips() {
    // On an official state (the codec holds official content only); with the
    // counter zero the encoding is the old one.
    let base = CombatState::new(&starter_deck(), 80, 80, Encounter::JawWorm, &mut Rng::new(3));
    let old = encode(&base);
    for u in [1, 4] {
        let mut s = base.clone();
        s.times_lost_hp = u;
        assert_ne!(s, base);
        let bytes = encode(&s);
        assert_ne!(bytes, old);
        assert_eq!(decode(&bytes), s, "{u}");
        assert_ne!(hash_of(&s), hash_of(&base), "the counter is part of the hash");
    }
    assert_eq!(decode(&old), base);
}

#[test]
fn greedy_plays_decks_of_them_to_an_end() {
    load_pack(PACK).unwrap();
    let pack = ["Blood for Blood", "Corruption", "Feel No Pain"];
    let mut names: Vec<&str> = Character::Ironclad.starter_deck().iter().map(|c| c.name()).collect();
    let gens: Vec<String> = pack.iter().map(|n| gen(n)).collect();
    names.extend(gens.iter().map(String::as_str));
    names.extend(["Bloodletting", "Shrug It Off"]);
    let (ids, b) = bind(&names).unwrap();
    let bfb = ids[names.iter().position(|n| *n == gens[0]).unwrap()];
    let corruption = s_power(&b);
    let (mut wins, mut bfb_played, mut bfb_cheap, mut corr_held, mut corr_exhausted) = (0, 0, 0, 0, 0);
    for seed in 0..40 {
        let mut rng = Rng::new(seed);
        let mut s = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &mut rng);
        let (mut n, mut played, mut cheap, mut held, mut exhausted) = (0, false, false, false, false);
        while !s.is_over() {
            // Greedy, except that a playable pack Power is played first
            // (greedy plays a Power only when nothing deals damage or blocks).
            let power = s.legal_actions().into_iter().find(|a| {
                matches!(a, Action::Play { card, .. } if s.binding.def(*card).ty == CardType::Power && s.binding.def(*card).name.starts_with("gen:"))
            });
            let a = power.unwrap_or_else(|| greedy_action(&s));
            let holds = s.player.powers.get(corruption) > 0;
            held |= holds;
            let ex = s.exhaust().len();
            if let Action::Play { card, .. } = a {
                if base_of(card) == bfb {
                    played = true;
                    cheap |= s.cost_of(card) < s.binding.def(bfb).cost();
                }
                let skill = s.binding.def(card).ty == CardType::Skill;
                s.step(a, &mut rng).unwrap();
                exhausted |= holds && skill && s.exhaust().len() > ex;
            } else {
                s.step(a, &mut rng).unwrap();
            }
            n += 1;
            assert!(n < 3000, "seed {seed}: no end");
        }
        wins += s.won() as u32;
        bfb_played += played as u32;
        bfb_cheap += cheap as u32;
        corr_held += held as u32;
        corr_exhausted += exhausted as u32;
    }
    println!(
        "greedy with the C5 cards vs Jaw Worm (powers first): {wins} of 40 won; Blood for Blood played in {bfb_played}, below base cost in {bfb_cheap}; Corruption held in {corr_held}, a Skill exhausted by it in {corr_exhausted}"
    );
    assert!(wins >= 20, "{wins}");
    assert!(bfb_cheap * 2 > bfb_played, "{bfb_cheap} of {bfb_played}");
    assert!(corr_exhausted * 2 > corr_held, "{corr_exhausted} of {corr_held}");
}

/// The bound slot of the pack power `Corruption`.
fn s_power(b: &registry::Binding) -> Power {
    b.powers_in_play().iter().copied().find(|&p| b.power_id(p) == Some("Corruption")).expect("Corruption bound")
}

#[test]
fn a_loss_drops_copies_in_hand_draw_and_discard_only() {
    // The game's `updateCardsOnDamage`: hand, discard and draw piles; the
    // exhaust pile keeps its copy's cost.
    let (mut s, ids) = setup(&["Blood for Blood"], &["Bloodletting", "Bloodletting"]);
    let (bfb, bl) = (ids[0], ids[1]);
    s.hand = Hand::from_cards(&[bfb, bl]);
    s.set_draw(Pile::from_cards(&[bfb, bfb]));
    s.set_discard(Pile::from_cards(&[bfb]));
    s.set_exhaust(Pile::from_cards(&[bfb]));
    play(&mut s, bl);
    let three = s.hand.iter().find(|&(c, _)| base_of(c) == bfb).unwrap().0;
    assert_eq!((s.cost_of(three), s.hand.count(bfb)), (3, 0), "the hand's copy");
    assert_eq!((s.draw().count(three), s.draw().count(bfb)), (2, 0), "the draw pile's copies");
    assert_eq!((s.discard().count(three), s.discard().count(bfb)), (1, 0), "the discard pile's copy");
    assert_eq!((s.exhaust().count(bfb), s.exhaust().count(three)), (1, 0), "the exhaust pile's copy keeps 4");
    // Copies at different costs each drop one: two losses on the hand's
    // copy, one on a copy that came in after the first loss.
    s.hand.add(bfb, 1);
    s.hand.add(bl, 1);
    play(&mut s, bl);
    let costs: std::collections::BTreeSet<i8> = s.hand.iter().filter(|&(c, _)| base_of(c) == bfb).map(|(c, _)| s.cost_of(c)).collect();
    assert_eq!(costs, [2, 3].into());
    assert_eq!(s.times_lost_hp, 2);
}

#[test]
fn the_copy_in_play_misses_a_loss_sharp_hide() {
    // Run 16: Blood for Blood+ played into The Guardian's Sharp Hide. The
    // thorns land while the card is in limbo, so its own cost stays; the
    // other copies drop.
    let (mut s, ids) = setup(&["Blood for Blood+"], &[]);
    let bfb = ids[0];
    s.hand = Hand::from_cards(&[bfb, bfb]);
    s.set_draw(Pile::from_cards(&[bfb]));
    s.monsters[0].powers.add(Power::SharpHide, 3);
    let hp = s.player.hp;
    play(&mut s, bfb);
    assert_eq!(s.player.hp, hp - 3, "Sharp Hide's 3");
    assert_eq!(s.times_lost_hp, 1);
    let two = s.hand.iter().next().unwrap().0;
    assert_eq!((s.hand.len(), base_of(two), s.cost_of(two)), (1, bfb, 2), "the copy in hand drops");
    assert_eq!(s.draw().iter().map(|(c, _)| s.cost_of(c)).collect::<Vec<_>>(), [2], "the draw pile's copy drops");
    assert_eq!(s.discard().count(bfb), 1, "the played copy kept cost 3");
    assert_eq!(s.cost_of(bfb), 3);
}

#[test]
fn an_upgrade_keeps_the_drops() {
    // BloodForBlood.upgrade: a cost below 4 becomes cost - 1 (floored at 0),
    // so a copy at 2 after two losses upgrades to 1, not to the base 3.
    let (mut s, ids) = setup(&["Blood for Blood"], &["Bloodletting", "Bloodletting"]);
    let (bfb, bl) = (ids[0], ids[1]);
    play(&mut s, bl);
    play(&mut s, bl);
    let c = the_copy(&s, bfb);
    assert_eq!(s.cost_of(c), 2);
    assert!(s.upgrade_in_hand(c));
    let up = s.hand.iter().next().unwrap().0;
    assert_eq!((s.binding.def(up).name, s.cost_of(up)), ("gen:Blood for Blood+{cost=1/combat}", 1));
    // An undropped copy upgrades to the plain upgraded card (4 -> 3).
    let (mut t, ids) = setup(&["Blood for Blood"], &[]);
    assert!(t.upgrade_in_hand(ids[0]));
    let up = t.hand.iter().next().unwrap().0;
    assert_eq!((t.binding.def(up).name, t.cost_of(up)), ("gen:Blood for Blood+", 3));
}

#[test]
fn equal_drops_are_equal_states() {
    // The same losses on the same copies give the same state, and a copy
    // dropped once is one card id wherever it lies.
    let (mut a, ids) = setup(&["Blood for Blood"], &["Bloodletting"]);
    let (bfb, bl) = (ids[0], ids[1]);
    a.set_discard(Pile::from_cards(&[bfb]));
    let mut b = a.clone();
    play(&mut a, bl);
    play(&mut b, bl);
    assert_eq!(a, b);
    let in_hand = a.hand.iter().find(|&(c, _)| base_of(c) == bfb).unwrap().0;
    assert_eq!(a.discard().count(in_hand), 1, "the discard's copy is the hand's card");
}
