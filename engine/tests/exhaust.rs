//! Exhausting cards other than the one in play (docs/specs/exhaust-cards.md,
//! building block C1): the six Ironclad cards in
//! `content/packs/act1-ironclad.json` that use it, the new effects, picks
//! and chance event, their hook refusals and their round-trips.

use sts_engine::agent::greedy_action;
use sts_engine::cards::CardType;
use sts_engine::codec::{decode, encode};
use sts_engine::registry::{bind, card_json, load_pack};
use sts_engine::effects::PickKind;
use sts_engine::state::{InPlay, Pick};
use sts_engine::*;

const PACK: &str = include_str!("../../content/packs/act1-ironclad.json");

/// (name, cost, cost upgraded, Attack, exhaust), from the wiki's Ironclad
/// card list, checked against sts_lightspeed (inventory "C1 cards").
const WIKI: [(&str, i8, i8, bool, bool); 6] = [
    ("True Grit", 1, 1, false, false),
    ("Burning Pact", 1, 1, false, false),
    ("Second Wind", 1, 1, false, false),
    ("Sever Soul", 2, 2, true, false),
    ("Fiend Fire", 2, 2, true, true),
    ("Exhume", 1, 0, false, true),
];

fn gen(name: &str) -> String {
    format!("gen:{name}")
}

fn id(name: &str) -> CardId {
    CardId::from_name(name).unwrap()
}

/// A combat against a Jaw Worm at 100 HP with the pack card `card` and the
/// official cards `hand` in hand, 3 energy, empty draw and discard piles.
/// Returns the state and the pack card's id.
fn setup(card: &str, hand: &[&str]) -> (CombatState, CardId) {
    load_pack(PACK).unwrap();
    let g = gen(card);
    let mut names = vec![g.as_str()];
    names.extend_from_slice(hand);
    let (ids, b) = bind(&names).unwrap();
    let mut s = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &mut Rng::new(1));
    s.hand = Hand::from_cards(&ids);
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    s.set_exhaust(Pile::default());
    s.player.energy = 3;
    let m = &mut s.monsters[0];
    m.hp = 100;
    m.max_hp = 100;
    m.block = 0;
    m.powers = Default::default();
    (s, ids[0])
}

fn play(s: &mut CombatState, card: CardId) {
    let target = if s.binding.def(card).targeted() { Some(0) } else { None };
    s.apply_action(Action::Play { card, target }).unwrap();
}

#[test]
fn every_entry_loads_as_the_wiki() {
    load_pack(PACK).unwrap();
    for (name, cost, cost_up, attack, exhaust) in WIKI {
        for (n, c) in [(name.to_string(), cost), (format!("{name}+"), cost_up)] {
            let (ids, b) = bind(&[&gen(&n)]).unwrap();
            let d = b.def(ids[0]);
            assert_eq!((d.cost(), d.ty == CardType::Attack, d.exhaust), (c, attack, exhaust), "{n}");
        }
    }
}

#[test]
fn burning_pact_exhausts_pick_then_draws() {
    for (name, draws) in [("Burning Pact", 2), ("Burning Pact+", 3)] {
        let (mut s, bp) = setup(name, &["Strike", "Defend", "Bash"]);
        s.set_draw(Pile::from_cards(&[id("Strike"); 6]));
        play(&mut s, bp);
        assert_eq!(s.legal_actions(), [Action::Choose(id("Strike")), Action::Choose(id("Defend")), Action::Choose(id("Bash"))], "{name}");
        s.apply_action(Action::Choose(id("Bash"))).unwrap();
        assert_eq!((s.exhaust().count(id("Bash")), s.hand.len(), s.discard().count(bp)), (1, 2 + draws, 1), "{name}");
    }
    // An empty hand: no pick, the draw still comes.
    let (mut s, bp) = setup("Burning Pact", &[]);
    s.set_draw(Pile::from_cards(&[id("Strike"); 6]));
    play(&mut s, bp);
    assert!(s.pick().is_none());
    assert_eq!((s.hand.len(), s.exhaust().len()), (2, 0));
}

#[test]
fn true_grit_random_is_chance() {
    let (mut s, tg) = setup("True Grit", &["Strike", "Strike", "Defend"]);
    play(&mut s, tg);
    assert_eq!(s.pending, Some(ChanceEvent::RandomExhaust));
    assert_eq!(s.player.block, 7);
    let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(10) else { panic!("listed") };
    assert_eq!(v.len(), 2);
    for (p, o) in &v {
        let want = if o.exhaust().count(id("Strike")) == 1 { 2.0 / 3.0 } else { 1.0 / 3.0 };
        assert!((p - want).abs() < 1e-9, "{p}");
        assert_eq!((o.exhaust().len(), o.hand.len(), o.discard().count(tg)), (1, 2, 1));
    }
    // Sampled: one card exhausted, the same as one listed outcome.
    let mut t = s.clone();
    t.advance(&mut Rng::new(7));
    assert!(v.iter().any(|(_, o)| *o == t));
    // One distinct card in hand: resolved at once.
    let (mut s, tg) = setup("True Grit", &["Strike", "Strike"]);
    play(&mut s, tg);
    assert_eq!((s.pending, s.exhaust().count(id("Strike")), s.hand.count(id("Strike"))), (None, 1, 1));
    // An empty hand: nothing.
    let (mut s, tg) = setup("True Grit", &[]);
    play(&mut s, tg);
    assert_eq!((s.pending, s.exhaust().len(), s.player.block), (None, 0, 7));
    // Upgraded: a pick.
    let (mut s, tg) = setup("True Grit+", &["Strike", "Strike", "Defend"]);
    play(&mut s, tg);
    assert_eq!(s.player.block, 9);
    assert_eq!(s.legal_actions(), [Action::Choose(id("Strike")), Action::Choose(id("Defend"))]);
    s.apply_action(Action::Choose(id("Defend"))).unwrap();
    assert_eq!((s.exhaust().count(id("Defend")), s.hand.count(id("Strike"))), (1, 2));
}

#[test]
fn second_wind_counts_non_attacks() {
    for (name, per) in [("Second Wind", 5), ("Second Wind+", 7)] {
        for dex in [0, 2] {
            let (mut s, sw) = setup(name, &["Strike", "Defend", "Defend", "Wound"]);
            s.player.powers.add(Power::Dexterity, dex);
            play(&mut s, sw);
            assert_eq!(s.player.block, 3 * (per + dex), "{name} dex {dex}");
            assert_eq!((s.hand.count(id("Strike")), s.hand.len()), (1, 1), "{name}");
            assert_eq!((s.exhaust().count(id("Defend")), s.exhaust().count(id("Wound")), s.discard().count(sw)), (2, 1, 1), "{name}");
        }
    }
}

#[test]
fn sever_soul_and_fiend_fire() {
    for (name, dmg) in [("Sever Soul", 16), ("Sever Soul+", 22)] {
        let (mut s, ss) = setup(name, &["Strike", "Defend", "Wound"]);
        play(&mut s, ss);
        assert_eq!(s.monsters[0].hp, 100 - dmg, "{name}");
        assert_eq!((s.hand.count(id("Strike")), s.hand.len(), s.exhaust().len(), s.discard().count(ss)), (1, 1, 2, 1), "{name}");
    }
    for (name, per) in [("Fiend Fire", 7), ("Fiend Fire+", 10)] {
        for str_ in [0, 2] {
            let (mut s, ff) = setup(name, &["Strike", "Defend", "Bash", "Wound"]);
            s.player.powers.add(Power::Strength, str_);
            play(&mut s, ff);
            assert_eq!(s.monsters[0].hp, 100 - 4 * (per + str_), "{name} str {str_}");
            assert_eq!((s.hand.len(), s.exhaust().len(), s.exhaust().count(ff)), (0, 5, 1), "{name}");
        }
    }
    let (mut s, ff) = setup("Fiend Fire", &[]);
    play(&mut s, ff);
    assert_eq!((s.monsters[0].hp, s.exhaust().count(ff)), (100, 1));
}

#[test]
fn exhume_returns_not_exhume() {
    for name in ["Exhume", "Exhume+"] {
        let (mut s, ex) = setup(name, &[]);
        s.set_exhaust(Pile::from_cards(&[id("Bash"), ex]));
        play(&mut s, ex);
        assert_eq!(s.legal_actions(), [Action::Choose(id("Bash"))], "{name}");
        s.apply_action(Action::Choose(id("Bash"))).unwrap();
        assert_eq!((s.hand.count(id("Bash")), s.exhaust().count(ex), s.exhaust().len()), (1, 2, 2), "{name}");
    }
    // Only Exhume copies there: no pick.
    let (mut s, ex) = setup("Exhume", &["Strike"]);
    s.set_exhaust(Pile::from_cards(&[ex]));
    play(&mut s, ex);
    assert!(s.pick().is_none());
    assert_eq!((s.exhaust().count(ex), s.hand.len()), (2, 1));
}

#[test]
fn hooks_refuse_random_exhaust_and_picks() {
    let hook = |effects: &str| {
        format!(
            "{{\"version\": 1, \"powers\": [{{\"id\": \"ExhaustTest{}\", \"hooks\": [{{\"trigger\": \"OwnerTurnStart\", \"condition\": \"Always\", \"effects\": [{effects}]}}]}}], \"cards\": []}}",
            effects.len()
        )
    };
    load_pack(&hook("{\"ExhaustHand\": {}}")).unwrap();
    let e = load_pack(&hook("\"ExhaustRandom\"")).unwrap_err();
    assert!(e.contains("can't run in a hook"), "{e}");
    let e = load_pack(&hook("{\"Pick\": {\"kind\": \"ExhaustFromHand\", \"n\": 1, \"exact\": true}}")).unwrap_err();
    assert!(e.contains("can't run in a hook"), "{e}");
}

#[test]
fn entries_and_states_round_trip() {
    load_pack(PACK).unwrap();
    for (name, ..) in WIKI {
        for n in [name.to_string(), format!("{name}+")] {
            let (ids, b) = bind(&[&gen(&n)]).unwrap();
            let d = b.def(ids[0]);
            let rt = format!("rt_exhaust_{}", n.replace(' ', "_").replace('+', "_up"));
            let entry = card_json(&rt, d).unwrap();
            load_pack(&format!("{{\"version\": 1, \"cards\": [{entry}]}}")).unwrap_or_else(|e| panic!("{n}: {e}\n{entry}"));
            let (ids2, b2) = bind(&[&gen(&rt)]).unwrap();
            assert_eq!(b2.def(ids2[0]).effects, d.effects, "{n}");
        }
    }
    // The codec holds official content only, so the new pick kinds and the
    // chance event are checked on an official state set to each.
    let base = CombatState::new(&starter_deck(), 80, 80, Encounter::JawWorm, &mut Rng::new(3));
    for kind in [PickKind::ExhaustFromHand, PickKind::ReturnFromExhaust] {
        let mut s = base.clone();
        let pick = Some(Pick::new(kind, 1, true, false));
        s.stage = Stage::PlayingCard { card: id("Strike"), target: Some(0), next: 1, hit: 0, x: 0, more: InPlay { pick, ..InPlay::default() } };
        assert_eq!(decode(&encode(&s)), s, "{kind:?}");
    }
    let mut s = base.clone();
    s.stage = Stage::PlayingCard { card: id("Strike"), target: Some(0), next: 1, hit: 0, x: 0, more: InPlay::default() };
    s.pending = Some(ChanceEvent::RandomExhaust);
    assert_eq!(decode(&encode(&s)), s);
}

#[test]
fn greedy_plays_decks_of_them_to_an_end() {
    load_pack(PACK).unwrap();
    let all: Vec<String> = WIKI.iter().flat_map(|w| [gen(w.0), gen(&format!("{}+", w.0))]).collect();
    let mut wins = 0;
    for (g, group) in all.chunks(6).enumerate() {
        let mut names: Vec<&str> = Character::Ironclad.starter_deck().iter().map(|c| c.name()).collect();
        names.extend(group.iter().map(String::as_str));
        let (ids, b) = bind(&names).unwrap();
        for seed in 0..20 {
            let mut rng = Rng::new(seed);
            let mut s = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &mut rng);
            let mut n = 0;
            while !s.is_over() {
                s.step(greedy_action(&s), &mut rng).unwrap();
                n += 1;
                assert!(n < 2000, "group {g} seed {seed}: no end");
            }
            wins += s.won() as u32;
        }
    }
    println!("greedy with the C1 cards vs a Jaw Worm: {wins} of 40 won");
    assert_eq!(wins, 40);
}
