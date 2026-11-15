//! Exhaust triggers (docs/specs/exhaust-triggers.md, building block C2):
//! a power's `CardExhausted` hooks and a card's `exhausted` effects, with
//! Dark Embrace, Feel No Pain and Sentinel from
//! `content/packs/act1-ironclad.json`.

use sts_engine::agent::greedy_action;
use sts_engine::cards::CardType;
use sts_engine::codec::{decode, encode};
use sts_engine::registry::{bind, card_json, load_pack};
use sts_engine::*;

const PACK: &str = include_str!("../../content/packs/act1-ironclad.json");

/// (name, cost, cost upgraded, type), from sts_lightspeed's card table
/// (inventory "Block C2").
const SOURCE: [(&str, i8, i8, CardType); 3] = [
    ("Dark Embrace", 2, 1, CardType::Power),
    ("Feel No Pain", 1, 1, CardType::Power),
    ("Sentinel", 1, 1, CardType::Skill),
];

fn gen(name: &str) -> String {
    format!("gen:{name}")
}

fn id(name: &str) -> CardId {
    CardId::from_name(name).unwrap()
}

/// A combat against a Jaw Worm at 100 HP with the pack cards `pack` and the
/// official cards `hand` in hand, 10 energy, empty draw, discard and
/// exhaust piles. Returns the state and the pack cards' ids.
fn setup(pack: &[&str], hand: &[&str]) -> (CombatState, Vec<CardId>) {
    load_pack(PACK).unwrap();
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
    (s, ids[..pack.len()].to_vec())
}

fn play(s: &mut CombatState, card: CardId) {
    let target = if s.binding.def(card).targeted() { Some(0) } else { None };
    s.apply_action(Action::Play { card, target }).unwrap();
}

#[test]
fn every_entry_loads_as_the_source() {
    load_pack(PACK).unwrap();
    for (name, cost, cost_up, ty) in SOURCE {
        for (n, c) in [(name.to_string(), cost), (format!("{name}+"), cost_up)] {
            let (ids, b) = bind(&[&gen(&n)]).unwrap();
            let d = b.def(ids[0]);
            assert_eq!((d.cost(), d.ty, d.exhaust), (c, ty, false), "{n}");
        }
    }
}

#[test]
fn feel_no_pain_blocks_per_exhaust() {
    for (name, per) in [("Feel No Pain", 3), ("Feel No Pain+", 4)] {
        for dex in [0, 2] {
            let (mut s, ids) = setup(&[name, "Burning Pact"], &["Strike", "Defend", "Bash"]);
            s.set_draw(Pile::from_cards(&[id("Strike"); 6]));
            s.player.powers.add(Power::Dexterity, dex);
            play(&mut s, ids[0]);
            assert_eq!(s.player.block, 0);
            play(&mut s, ids[1]);
            s.apply_action(Action::Choose(id("Bash"))).unwrap();
            // Raw block: Dexterity doesn't apply.
            assert_eq!(s.player.block, per, "{name} dex {dex}");
        }
    }
    // Fiend Fire: four cards and itself.
    let (mut s, ids) = setup(&["Feel No Pain", "Fiend Fire"], &["Strike", "Defend", "Bash", "Wound"]);
    play(&mut s, ids[0]);
    play(&mut s, ids[1]);
    assert_eq!((s.player.block, s.exhaust().len()), (15, 5));
    // Two Feel No Pains stack: 3 + 4 per card.
    let (mut s, ids) = setup(&["Feel No Pain", "Feel No Pain+", "Burning Pact"], &["Strike"]);
    play(&mut s, ids[0]);
    play(&mut s, ids[1]);
    play(&mut s, ids[2]);
    s.apply_action(Action::Choose(id("Strike"))).unwrap();
    assert_eq!(s.player.block, 7);
}

#[test]
fn dark_embrace_draws_after_the_card() {
    // Burning Pact draws 2, then Dark Embrace 1.
    let (mut s, ids) = setup(&["Dark Embrace", "Burning Pact"], &["Strike", "Defend"]);
    s.set_draw(Pile::from_cards(&[id("Bash"); 6]));
    play(&mut s, ids[0]);
    play(&mut s, ids[1]);
    s.apply_action(Action::Choose(id("Strike"))).unwrap();
    assert_eq!((s.hand.len(), s.hand.count(id("Bash")), s.draw().len(), s.pending), (4, 3, 3, None));
    // Draw and discard empty: the True Grit+ just discarded is the card drawn.
    let (mut s, ids) = setup(&["Dark Embrace", "True Grit+"], &["Defend"]);
    play(&mut s, ids[0]);
    play(&mut s, ids[1]);
    s.apply_action(Action::Choose(id("Defend"))).unwrap();
    assert_eq!((s.hand.count(ids[1]), s.discard().len(), s.exhaust().count(id("Defend"))), (1, 0, 1));
    // A full hand: only Burning Pact's draws fit.
    let (mut s, ids) = setup(&["Dark Embrace", "Burning Pact"], &[]);
    s.set_draw(Pile::from_cards(&[id("Bash"); 6]));
    play(&mut s, ids[0]);
    let mut hand = vec![ids[1]];
    hand.extend([id("Strike"); 9]);
    s.hand = Hand::from_cards(&hand);
    play(&mut s, ids[1]);
    s.apply_action(Action::Choose(id("Strike"))).unwrap();
    assert_eq!((s.hand.len(), s.draw().len()), (10, 4));
    // Two Dark Embraces: 2 per card.
    let (mut s, ids) = setup(&["Dark Embrace", "Dark Embrace+", "Burning Pact"], &["Strike"]);
    s.set_draw(Pile::from_cards(&[id("Bash"); 6]));
    play(&mut s, ids[0]);
    play(&mut s, ids[1]);
    play(&mut s, ids[2]);
    s.apply_action(Action::Choose(id("Strike"))).unwrap();
    assert_eq!(s.hand.count(id("Bash")), 4);
}

#[test]
fn fiend_fire_count_unchanged() {
    let (mut s, ids) = setup(&["Dark Embrace", "Fiend Fire"], &["Strike", "Defend", "Bash", "Wound"]);
    s.set_draw(Pile::from_cards(&[id("Defend"); 10]));
    play(&mut s, ids[0]);
    play(&mut s, ids[1]);
    assert_eq!(s.monsters[0].hp, 100 - 4 * 7);
    assert_eq!((s.hand.len(), s.hand.count(id("Defend")), s.exhaust().len()), (5, 5, 5));
}

#[test]
fn ethereal_at_turn_end() {
    // (Feel No Pain held, Dark Embrace held) -> (HP after the Jaw Worm's
    // Chomp, cards in the next turn's hand).
    let run = |fnp: bool, de: bool| {
        let mut pack = vec![];
        if fnp {
            pack.push("Feel No Pain");
        }
        if de {
            pack.push("Dark Embrace");
        }
        let (mut s, ids) = setup(&pack, &["Dazed"]);
        s.set_draw(Pile::from_cards(&[id("Strike"); 10]));
        for c in ids {
            play(&mut s, c);
        }
        let hp = s.player.hp;
        s.step(Action::EndTurn, &mut Rng::new(5)).unwrap();
        assert_eq!((s.stage, s.exhaust().count(id("Dazed"))), (Stage::PlayerTurn, 1));
        assert_eq!((s.unfired_exhausts, s.owed_draw), (0, 0));
        (hp - s.player.hp, s.hand.len())
    };
    let (lost, hand) = run(false, false);
    assert_eq!((lost, hand), (11, 5));
    // Feel No Pain's 3 block lands before the monster attacks.
    assert_eq!(run(true, false), (8, 5));
    // Dark Embrace's draw is owed to the next turn.
    assert_eq!(run(false, true), (11, 6));
    assert_eq!(run(true, true), (8, 6));
}

#[test]
fn sentinel_energy_on_exhaust() {
    for (name, gain) in [("Sentinel", 2), ("Sentinel+", 3)] {
        let (mut s, ids) = setup(&[name, "Burning Pact"], &[]);
        s.player.energy = 3;
        play(&mut s, ids[1]);
        s.apply_action(Action::Choose(ids[0])).unwrap();
        assert_eq!((s.player.energy, s.exhaust().count(ids[0])), (2 + gain, 1), "{name}");
    }
    for (name, block) in [("Sentinel", 5), ("Sentinel+", 8)] {
        let (mut s, ids) = setup(&[name], &[]);
        s.player.energy = 3;
        play(&mut s, ids[0]);
        assert_eq!((s.player.block, s.player.energy, s.discard().count(ids[0])), (block, 2, 1), "{name}");
    }
    // Fiend Fire with two Sentinels.
    let (mut s, ids) = setup(&["Fiend Fire", "Sentinel"], &[]);
    s.hand.add(ids[1], 1);
    s.player.energy = 3;
    play(&mut s, ids[0]);
    assert_eq!((s.player.energy, s.exhaust().count(ids[1])), (5, 2));
}

#[test]
fn load_refuses_what_cant_fire_once_with_the_count() {
    let hook = |n: u32, cond: &str, effects: &str| {
        format!(
            "{{\"version\": 1, \"powers\": [{{\"id\": \"ExTrig{n}\", \"hooks\": [{{\"trigger\": \"CardExhausted\", \"condition\": {cond}, \"effects\": [{effects}]}}]}}], \"cards\": []}}"
        )
    };
    load_pack(&hook(0, "\"Always\"", "{\"Draw\": 1}, {\"Block\": 2}")).unwrap();
    let e = load_pack(&hook(1, "{\"CardType\": \"Skill\"}", "{\"Block\": 2}")).unwrap_err();
    assert!(e.contains("CardExhausted"), "{e}");
    let e = load_pack(&hook(2, "\"Always\"", "{\"ExhaustHand\": {}}")).unwrap_err();
    assert!(e.contains("CardExhausted"), "{e}");
    let e = load_pack(&hook(3, "\"Always\"", "{\"Pick\": {\"kind\": \"ExhaustFromHand\", \"n\": 1, \"exact\": true}}")).unwrap_err();
    assert!(e.contains("can't run in a hook"), "{e}");
    let card = |n: u32, effects: &str| {
        format!("{{\"version\": 1, \"cards\": [{{\"id\": \"ExCard{n}\", \"cost\": 1, \"type\": \"Skill\", \"effects\": [], \"exhausted\": [{effects}]}}]}}")
    };
    load_pack(&card(0, "{\"GainEnergy\": 1}, {\"Block\": 3}")).unwrap();
    let e = load_pack(&card(1, "{\"Damage\": {\"amount\": 5, \"hits\": 1, \"target\": \"Opponent\"}}")).unwrap_err();
    assert!(e.contains("exhausted"), "{e}");
    let e = load_pack(&card(2, "{\"Draw\": 1}")).unwrap_err();
    assert!(e.contains("exhausted"), "{e}");
}

#[test]
fn entries_and_states_round_trip() {
    load_pack(PACK).unwrap();
    // The writer names a generated power by its slot (`Gen0`), which a pack
    // can't load: the two power cards are checked by loading the pack.
    for name in ["Sentinel"] {
        for n in [name.to_string(), format!("{name}+")] {
            let (ids, b) = bind(&[&gen(&n)]).unwrap();
            let d = b.def(ids[0]);
            let rt = format!("rt_trig_{}", n.replace(' ', "_").replace('+', "_up"));
            let entry = card_json(&rt, d).unwrap();
            assert_eq!(entry.contains("\"exhausted\""), !d.exhausted.is_empty(), "{n}");
            load_pack(&format!("{{\"version\": 1, \"cards\": [{entry}]}}")).unwrap_or_else(|e| panic!("{n}: {e}\n{entry}"));
            let (ids2, b2) = bind(&[&gen(&rt)]).unwrap();
            let d2 = b2.def(ids2[0]);
            assert_eq!((d2.effects, d2.exhausted), (d.effects, d.exhausted), "{n}");
        }
    }
    // The counters, on an official state (the codec holds official content
    // only); with both zero the encoding is the old one.
    let base = CombatState::new(&starter_deck(), 80, 80, Encounter::JawWorm, &mut Rng::new(3));
    let old = encode(&base);
    for (u, o) in [(1, 0), (0, 2), (3, 1)] {
        let mut s = base.clone();
        s.unfired_exhausts = u;
        s.owed_draw = o;
        assert_ne!(s, base);
        let bytes = encode(&s);
        assert_ne!(bytes, old);
        assert_eq!(decode(&bytes), s, "{u} {o}");
    }
    assert_eq!(decode(&old), base);
}

#[test]
fn greedy_plays_decks_of_them_to_an_end() {
    load_pack(PACK).unwrap();
    let pack = ["Dark Embrace", "Feel No Pain", "Sentinel", "Burning Pact", "True Grit", "Second Wind"];
    let mut names: Vec<&str> = Character::Ironclad.starter_deck().iter().map(|c| c.name()).collect();
    let gens: Vec<String> = pack.iter().map(|n| gen(n)).collect();
    names.extend(gens.iter().map(String::as_str));
    let (ids, b) = bind(&names).unwrap();
    let (mut wins, mut fired) = (0, 0);
    for seed in 0..40 {
        let mut rng = Rng::new(seed);
        let mut s = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &mut rng);
        let mut n = 0;
        let mut seen = false;
        while !s.is_over() {
            let held = |s: &CombatState| s.binding.powers_in_play().iter().any(|&p| s.binding.power_id(p).is_some() && s.player.powers.get(p) > 0);
            let before = s.exhaust().len();
            let had = held(&s);
            s.step(greedy_action(&s), &mut rng).unwrap();
            seen |= had && s.exhaust().len() > before;
            n += 1;
            assert!(n < 2000, "seed {seed}: no end");
        }
        wins += s.won() as u32;
        fired += seen as u32;
    }
    println!("greedy with the C2 cards vs a Jaw Worm: {wins} of 40 won, a trigger power held at an exhaust in {fired}");
    assert_eq!(wins, 40);
    // The heuristic gives the trigger powers no value, so greedy plays Dark
    // Embrace or Feel No Pain in 15 of the 40 games (seeds fixed); each of
    // those 15 saw an exhaust with the power held.
    assert!(fired >= 12, "{fired}");
}

#[test]
fn turn_start_exhausts_fire_after_the_turn_start_hooks() {
    // A pack power whose turn-start hook exhausts the hand, with Feel No
    // Pain held: the five cards drawn are exhausted, and the hooks fire
    // before the player's first decision (3 block each).
    load_pack(PACK).unwrap();
    load_pack(r#"{"version": 1, "powers": [{"id": "TsExh", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "effects": [{"ExhaustHand": {}}]}]}], "cards": [{"id": "TsExhCard", "cost": 0, "type": "Power", "effects": [{"Apply": {"power": "TsExh", "amount": 1, "target": "Me"}}]}]}"#).unwrap();
    let (mut s, ids) = setup(&["Feel No Pain", "TsExhCard"], &[]);
    s.set_draw(Pile::from_cards(&[id("Strike"); 10]));
    for c in ids {
        play(&mut s, c);
    }
    s.step(Action::EndTurn, &mut Rng::new(5)).unwrap();
    assert_eq!(s.stage, Stage::PlayerTurn);
    assert_eq!((s.hand.len(), s.exhaust().count(id("Strike")), s.player.block), (0, 5, 15));
    assert_eq!((s.unfired_exhausts, s.owed_draw), (0, 0));
}

#[test]
fn a_finished_combat_holds_no_unfired_exhausts() {
    // Official Pummel (it exhausts itself) kills the Jaw Worm: the combat
    // ends with the counters clear, so the state encodes as before C2.
    let (mut s, _) = setup(&[], &["Pummel"]);
    s.monsters[0].hp = 3;
    play(&mut s, id("Pummel"));
    assert_eq!(s.stage, Stage::Over { won: true });
    assert_eq!((s.exhaust().count(id("Pummel")), s.unfired_exhausts, s.owed_draw), (1, 0, 0));
}
