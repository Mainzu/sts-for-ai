//! Draw triggers (docs/specs/draw-triggers.md, building block C3): a
//! power's `CardDrawn` hooks, with Evolve and Fire Breathing from
//! `content/packs/act1-ironclad.json`.

use sts_engine::agent::greedy_action;
use sts_engine::chance::ChanceOutcomes;
use sts_engine::cards::CardType;
use sts_engine::codec::{decode, encode};
use sts_engine::registry::{bind, load_pack};
use sts_engine::*;

const PACK: &str = include_str!("../../content/packs/act1-ironclad.json");

/// Test-only cards: a plain draw, a draw then a pick (the card pauses after
/// its draw), a 0-cost card that exhausts itself, a card that gives the enemy a per-hit reaction (a pack
/// power gaining Strength each time its owner loses HP, as Angry does), and
/// an unplayable Curse (as Ascender's Bane).
const EXTRA: &str = r#"{"version": 1, "powers": [
{"id": "DtAngry", "hooks": [{"trigger": {"OwnerLostHp": {"from": "Any"}}, "condition": "Always", "effects": [{"Apply": {"power": "Strength", "amount": 1, "target": "Me"}}]}]}
], "cards": [
{"id": "DtDrawTwo", "cost": 0, "type": "Skill", "effects": [{"Draw": 2}]},
{"id": "DtDrawPick", "cost": 0, "type": "Skill", "effects": [{"Draw": 1}, {"Pick": {"kind": "DiscardFromHand", "n": 1, "exact": true}}]},
{"id": "DtExh", "cost": 0, "type": "Skill", "exhaust": true, "effects": []},
{"id": "DtAnger", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "DtAngry", "amount": 1, "target": "Opponent"}}]},
{"id": "DtCurse", "cost": -2, "type": "Curse", "effects": []}
]}"#;

/// (name, cost, cost upgraded), from
/// sts_lightspeed's `usePowerCard` and the wiki (inventory "Block C3").
const SOURCE: [(&str, i8, i8); 2] = [("Evolve", 1, 1), ("Fire Breathing", 1, 1)];

fn gen(name: &str) -> String {
    format!("gen:{name}")
}

fn id(name: &str) -> CardId {
    CardId::from_name(name).unwrap()
}

/// A combat against a Jaw Worm at 100 HP with the pack cards `pack` and the
/// official cards `hand` in hand, 10 energy, empty piles.
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
    (s, ids[..pack.len()].to_vec())
}

fn play(s: &mut CombatState, card: CardId) {
    let target = if s.binding.def(card).targeted() { Some(0) } else { None };
    s.apply_action(Action::Play { card, target }).unwrap();
}

/// Ends the turn and plays out the monsters' turn and the next draw.
fn next_turn(s: &mut CombatState, seed: u64) {
    s.hand = Hand::default();
    s.step(Action::EndTurn, &mut Rng::new(seed)).unwrap();
    assert_eq!(s.stage, Stage::PlayerTurn);
}

#[test]
fn every_entry_loads_as_the_source() {
    load_pack(PACK).unwrap();
    for (name, cost, cost_up) in SOURCE {
        for (n, c) in [(name.to_string(), cost), (format!("{name}+"), cost_up)] {
            let (ids, b) = bind(&[&gen(&n)]).unwrap();
            let d = b.def(ids[0]);
            assert_eq!((d.cost(), d.ty, d.exhaust), (c, CardType::Power, false), "{n}");
        }
    }
}

#[test]
fn evolve_draws_per_status() {
    for (name, per) in [("Evolve", 1u8), ("Evolve+", 2)] {
        let (mut s, ids) = setup(&[name], &[]);
        play(&mut s, ids[0]);
        // The turn's draw takes all five (2 Dazed, 3 Strikes); Evolve then
        // draws from the discard, which holds only Defends.
        s.set_draw(Pile::from_cards(&[id("Dazed"), id("Dazed"), id("Strike"), id("Strike"), id("Strike")]));
        s.set_discard(Pile::from_cards(&[id("Defend"); 6]));
        next_turn(&mut s, 3);
        assert_eq!((s.hand.count(id("Dazed")), s.hand.count(id("Strike")), s.hand.count(id("Defend"))), (2, 3, 2 * per), "{name}");
        assert_eq!(s.unfired_draws, 0);
    }
}

#[test]
fn evolve_full_hand_draws_nothing_more() {
    let (mut s, ids) = setup(&["Evolve", "DtDrawTwo"], &[]);
    play(&mut s, ids[0]);
    // Hand: DtDrawTwo and 7 Strikes; it draws 2 Dazed (hand 9).
    let mut hand = vec![ids[1]];
    hand.extend([id("Strike"); 7]);
    s.hand = Hand::from_cards(&hand);
    s.set_draw(Pile::from_cards(&[id("Dazed"), id("Dazed")]));
    // Draw and discard empty: Evolve's first draw takes the DtDrawTwo just
    // discarded (the reaction waits for the card), the second finds no room.
    play(&mut s, ids[1]);
    assert_eq!((s.hand.len(), s.hand.count(ids[1]), s.unfired_draws, s.pending), (10, 1, 0, None));
}

#[test]
fn evolve_chains() {
    // Only Dazed and one Strike: Evolve keeps drawing until the Strike, the
    // hand limit or the piles run out.
    for seed in 0..20 {
        let (mut s, ids) = setup(&["Evolve"], &[]);
        play(&mut s, ids[0]);
        let mut draw = vec![id("Dazed"); 11];
        draw.push(id("Strike"));
        s.set_draw(Pile::from_cards(&draw));
        next_turn(&mut s, seed);
        assert_eq!(s.unfired_draws, 0, "seed {seed}");
        let dazed = s.hand.count(id("Dazed")) as usize;
        let strike = s.hand.count(id("Strike"));
        // Every Dazed drawn drew one more card, until the hand was full.
        assert!(strike == 1 || s.hand.len() == 10, "seed {seed}: {dazed} Dazed, {strike} Strike");
        if strike == 1 && s.hand.len() < 10 {
            // The turn's draw of 5 plus one draw per Dazed.
            assert_eq!(s.hand.len(), (5 + dazed).min(12), "seed {seed}");
        }
    }
}

#[test]
fn fire_breathing_hits_per_status() {
    for (name, per) in [("Fire Breathing", 6), ("Fire Breathing+", 10)] {
        let (mut s, ids) = setup(&[name, "DtDrawTwo"], &[]);
        s.set_draw(Pile::from_cards(&[id("Wound"), id("Wound")]));
        play(&mut s, ids[0]);
        play(&mut s, ids[1]);
        assert_eq!((s.monsters[0].hp, s.unfired_draws), (100 - 2 * per, 0), "{name}");
    }
    // Block absorbs it; Strength and Vulnerable don't change it.
    let (mut s, ids) = setup(&["Fire Breathing", "DtDrawTwo"], &[]);
    s.set_draw(Pile::from_cards(&[id("Wound"), id("Wound")]));
    s.player.powers.add(Power::Strength, 3);
    s.monsters[0].powers.add(Power::Vulnerable, 2);
    s.monsters[0].block = 5;
    play(&mut s, ids[0]);
    play(&mut s, ids[1]);
    assert_eq!((s.monsters[0].hp, s.monsters[0].block), (100 - 7, 0));
    // One hit per card: a per-hit reaction (Angry-like) sees two hits.
    let (mut s, ids) = setup(&["Fire Breathing", "DtAnger", "DtDrawTwo"], &[]);
    s.set_draw(Pile::from_cards(&[id("Wound"), id("Wound")]));
    for c in ids {
        play(&mut s, c);
    }
    assert_eq!((s.monsters[0].hp, s.monsters[0].powers.get(Power::Strength)), (88, 2));
    // Killing the last enemy ends the combat with the counter clear.
    let (mut s, ids) = setup(&["Fire Breathing", "DtDrawTwo"], &[]);
    s.set_draw(Pile::from_cards(&[id("Wound"), id("Wound")]));
    s.monsters[0].hp = 5;
    play(&mut s, ids[0]);
    play(&mut s, ids[1]);
    assert_eq!((s.stage, s.unfired_draws), (Stage::Over { won: true }, 0));
}

#[test]
fn fire_breathing_hits_per_curse() {
    // The game's FireBreathingPower.onCardDraw: a Status or a Curse.
    let (mut s, ids) = setup(&["Fire Breathing+", "DtDrawTwo", "DtCurse"], &[]);
    s.set_draw(Pile::from_cards(&[ids[2], id("Wound")]));
    play(&mut s, ids[0]);
    play(&mut s, ids[1]);
    assert_eq!((s.monsters[0].hp, s.unfired_draws, s.unfired_curse_draws), (80, 0, 0));
    // Block absorbs it (run 72: 4 block, 6 to HP).
    let (mut s, ids) = setup(&["Fire Breathing+", "DtDrawTwo", "DtCurse"], &[]);
    s.set_draw(Pile::from_cards(&[ids[2]]));
    s.monsters[0].block = 4;
    play(&mut s, ids[0]);
    play(&mut s, ids[1]);
    assert_eq!((s.monsters[0].hp, s.monsters[0].block, s.unfired_curse_draws), (94, 0, 0));
    // Evolve takes Status only: a Curse draw draws nothing, and isn't
    // counted while no held hook takes Curse.
    let (mut s, ids) = setup(&["Evolve", "DtDrawPick", "DtCurse"], &["Strike"]);
    s.set_draw(Pile::from_cards(&[ids[2]]));
    s.set_discard(Pile::from_cards(&[id("Defend")]));
    play(&mut s, ids[0]);
    play(&mut s, ids[1]);
    assert!(s.pick().is_some());
    assert_eq!((s.unfired_draws, s.unfired_curse_draws), (0, 0));
    s.apply_action(Action::Choose(id("Strike"))).unwrap();
    // The one set up in hand and the one drawn; no Defend drawn.
    assert_eq!((s.hand.count(ids[2]), s.hand.count(id("Defend"))), (2, 0));
}

#[test]
fn fire_breathing_curse_at_turn_start() {
    // Run 72's miss: the turn's draw takes a Curse against a monster whose
    // Metallicize blocked at its turn end. Same seed without the Curse
    // (a Strike in its place) gives the HP and block before the hit.
    let run = |curse: bool, seed: u64| {
        let (mut s, ids) = setup(&["Fire Breathing+", "DtCurse"], &[]);
        play(&mut s, ids[0]);
        s.monsters[0].powers.add(Power::Metallicize, 4);
        let first = if curse { ids[1] } else { id("Strike") };
        s.set_draw(Pile::from_cards(&[first, id("Strike"), id("Strike"), id("Defend"), id("Defend")]));
        next_turn(&mut s, seed);
        (s.monsters[0].hp, s.monsters[0].block, s.unfired_curse_draws)
    };
    for seed in 0..6 {
        let (hp, block, _) = run(false, seed);
        assert!(block >= 4, "seed {seed}");
        let hit = 10;
        assert_eq!(run(true, seed), (hp - (hit - block).max(0), (block - hit).max(0), 0), "seed {seed}");
    }
}

#[test]
fn no_trigger_without_draw() {
    // Power Through's Wounds go into the hand without a draw.
    let (mut s, ids) = setup(&["Fire Breathing", "Power Through"], &[]);
    play(&mut s, ids[0]);
    play(&mut s, ids[1]);
    assert_eq!((s.hand.count(id("Wound")), s.monsters[0].hp, s.unfired_draws), (2, 100, 0));
    // Drawing non-Status cards fires nothing.
    let (mut s, ids) = setup(&["Fire Breathing", "DtDrawTwo"], &[]);
    s.set_draw(Pile::from_cards(&[id("Strike"), id("Defend")]));
    play(&mut s, ids[0]);
    play(&mut s, ids[1]);
    assert_eq!((s.hand.len(), s.monsters[0].hp), (2, 100));
    // Without a CardDrawn power, a Status drawn isn't counted: seen at a
    // pause inside the card (after a whole card the turn drains the counter
    // either way).
    let (mut s, ids) = setup(&["DtDrawPick"], &["Strike"]);
    s.set_draw(Pile::from_cards(&[id("Wound")]));
    play(&mut s, ids[0]);
    assert!(s.pick().is_some());
    assert_eq!(s.unfired_draws, 0);
}

#[test]
fn dark_embrace_draws_count() {
    // Dark Embrace's draw on an exhaust is a draw: the Wound it draws makes
    // Fire Breathing hit.
    let (mut s, ids) = setup(&["Dark Embrace", "Fire Breathing", "DtExh"], &[]);
    s.set_draw(Pile::from_cards(&[id("Wound")]));
    for &c in &ids {
        play(&mut s, c);
    }
    assert_eq!((s.hand.count(id("Wound")), s.monsters[0].hp, s.unfired_draws), (1, 94, 0));
}

/// Every listed outcome sums to 1, and no state awaiting the player's
/// action at its turn (or finished) holds unfired draws.
fn walk(s: &CombatState, depth: usize, leaves: &mut usize) {
    assert!(depth < 40, "no end to the chance events");
    if s.is_over() {
        assert_eq!(s.unfired_draws, 0);
        *leaves += 1;
        return;
    }
    match s.chance_outcomes(100_000) {
        Some(ChanceOutcomes::Listed(v)) => {
            let sum: f64 = v.iter().map(|(p, _)| p).sum();
            assert!((sum - 1.0).abs() < 1e-9, "{sum}");
            for (_, t) in &v {
                walk(t, depth + 1, leaves);
            }
        }
        Some(ChanceOutcomes::Large) => panic!("too many outcomes"),
        None => {
            assert!(s.awaiting_action());
            assert_eq!(s.unfired_draws, 0, "{s:?}");
            *leaves += 1;
        }
    }
}

#[test]
fn chance_outcomes_with_evolve() {
    for powers in [&["Evolve", "DtDrawTwo"][..], &["Evolve", "Fire Breathing", "DtDrawTwo"][..]] {
        let (mut s, ids) = setup(powers, &[]);
        s.set_draw(Pile::from_cards(&[id("Dazed"), id("Dazed"), id("Dazed"), id("Strike"), id("Defend"), id("Bash")]));
        s.set_discard(Pile::from_cards(&[id("Wound"), id("Strike")]));
        for &c in &ids[..ids.len() - 1] {
            play(&mut s, c);
        }
        s.apply_action(Action::Play { card: ids[ids.len() - 1], target: None }).unwrap();
        let mut leaves = 0;
        walk(&s, 0, &mut leaves);
        assert!(leaves > 1, "{leaves}");
        // Sampled the same way.
        for seed in 0..200 {
            let mut t = s.clone();
            let mut rng = Rng::new(seed);
            while t.pending.is_some() {
                t.resolve_chance(&mut rng);
            }
            assert!(t.is_over() || t.awaiting_action());
            assert_eq!(t.unfired_draws, 0);
        }
    }
}

#[test]
fn drawn_by_a_card_fires_after_it() {
    // The card pauses at its pick after drawing a Dazed: Fire Breathing
    // hasn't hit yet; it hits once the card is done.
    let (mut s, ids) = setup(&["Fire Breathing", "DtDrawPick"], &["Strike"]);
    s.set_draw(Pile::from_cards(&[id("Dazed")]));
    play(&mut s, ids[0]);
    play(&mut s, ids[1]);
    assert!(s.pick().is_some());
    assert_eq!((s.monsters[0].hp, s.unfired_draws), (100, 1));
    s.apply_action(Action::Choose(id("Strike"))).unwrap();
    assert_eq!((s.monsters[0].hp, s.unfired_draws, s.discard().count(ids[1])), (94, 0, 1));
    // Official Pommel Strike drawing a Dazed: 9 then 6.
    let (mut s, ids) = setup(&["Fire Breathing"], &["Pommel Strike"]);
    s.set_draw(Pile::from_cards(&[id("Dazed")]));
    play(&mut s, ids[0]);
    play(&mut s, id("Pommel Strike"));
    assert_eq!((s.monsters[0].hp, s.discard().count(id("Pommel Strike"))), (100 - 9 - 6, 1));
}

#[test]
fn load_refuses_what_cant_fire_per_card() {
    let hook = |n: u32, cond: &str, effects: &str| {
        format!(
            "{{\"version\": 1, \"powers\": [{{\"id\": \"DrTrig{n}\", \"hooks\": [{{\"trigger\": \"CardDrawn\", \"condition\": {cond}, \"effects\": [{effects}]}}]}}], \"cards\": []}}"
        )
    };
    load_pack(&hook(0, "{\"CardType\": \"Status\"}", "{\"Draw\": 1}, {\"Block\": 2}")).unwrap();
    let e = load_pack(&hook(1, "\"Always\"", "{\"Draw\": 1}")).unwrap_err();
    assert!(e.contains("CardDrawn"), "{e}");
    let e = load_pack(&hook(2, "{\"CardType\": \"Skill\"}", "{\"Draw\": 1}")).unwrap_err();
    assert!(e.contains("CardDrawn"), "{e}");
    load_pack(&hook(5, "{\"CardType\": \"Curse\"}", "{\"Block\": 2}")).unwrap();
    let e = load_pack(&hook(3, "{\"CardType\": \"Status\"}", "{\"ExhaustHand\": {}}")).unwrap_err();
    assert!(e.contains("CardDrawn"), "{e}");
    let e = load_pack(&hook(4, "{\"CardType\": \"Status\"}", "{\"Pick\": {\"kind\": \"ExhaustFromHand\", \"n\": 1, \"exact\": true}}")).unwrap_err();
    assert!(e.contains("can't run in a hook"), "{e}");
}

#[test]
fn the_counter_round_trips() {
    // On an official state (the codec holds official content only); with the
    // counter zero the encoding is the old one.
    let base = CombatState::new(&starter_deck(), 80, 80, Encounter::JawWorm, &mut Rng::new(3));
    let old = encode(&base);
    for u in [1, 4] {
        let mut s = base.clone();
        s.unfired_draws = u;
        assert_ne!(s, base);
        let bytes = encode(&s);
        assert_ne!(bytes, old);
        assert_eq!(decode(&bytes), s, "{u}");
    }
    assert_eq!(decode(&old), base);
    // The Curse-draw counter, its own tag, beside the Status one.
    for (u, c) in [(0, 1), (2, 3)] {
        let mut s = base.clone();
        (s.unfired_draws, s.unfired_curse_draws) = (u, c);
        assert_ne!(s, base);
        assert_eq!(decode(&encode(&s)), s, "{u} {c}");
    }
}

#[test]
fn greedy_plays_decks_of_them_to_an_end() {
    load_pack(PACK).unwrap();
    let pack = ["Evolve", "Fire Breathing", "Reckless Charge", "Power Through"];
    let mut names: Vec<&str> = Character::Ironclad.starter_deck().iter().map(|c| c.name()).collect();
    let gens: Vec<String> = pack.iter().map(|n| gen(n)).collect();
    names.extend(gens.iter().map(String::as_str));
    names.push("Wild Strike");
    let (ids, b) = bind(&names).unwrap();
    let (mut wins, mut held, mut fired) = (0, 0, 0);
    for seed in 0..40 {
        let mut rng = Rng::new(seed);
        let mut s = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, Encounter::ThreeSentries, &mut rng);
        let (mut n, mut was_held, mut seen) = (0, false, false);
        while !s.is_over() {
            let holds = s.binding.powers_in_play().iter().any(|&p| s.binding.power_id(p).is_some() && s.player.powers.get(p) > 0);
            let before = (s.hand.len(), s.monsters.iter().map(|m| m.hp as i32).sum::<i32>());
            let statuses = |s: &CombatState| s.hand.iter().filter(|&(c, _)| s.binding.def(c).ty == CardType::Status).map(|(_, k)| k as usize).sum::<usize>();
            let st = statuses(&s);
            s.step(greedy_action(&s), &mut rng).unwrap();
            was_held |= holds;
            // A Status reached the hand by a draw while a trigger power was held.
            seen |= holds && statuses(&s) > st && s.hand.len() > before.0;
            n += 1;
            assert!(n < 3000, "seed {seed}: no end");
        }
        wins += s.won() as u32;
        held += was_held as u32;
        fired += seen as u32;
    }
    println!("greedy with the C3 cards vs Three Sentries: {wins} of 40 won, a trigger power held in {held}, a Status drawn with it held in {fired}");
    assert!(wins >= 20, "{wins}");
    assert!(fired >= 1, "{fired}");
}
