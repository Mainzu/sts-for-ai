//! The Ironclad cards the engine lacked, as pack data
//! (`content/packs/act1-ironclad.json`, lane act1-content step 3; values
//! in docs/research/act1-inventory.md "Step 3"): each entry loads with the
//! wiki's cost, type and keywords, and plays with the wiki's numbers.

use sts_engine::agent::greedy_action;
use sts_engine::cards::CardType;
use sts_engine::registry::{bind, load_pack};
use sts_engine::*;

mod common;
use common::{assert_draw_odds_match, engine_draw_odds, PileOp};

const PACK: &str = include_str!("../../content/packs/act1-ironclad.json");

/// (name, cost, cost upgraded, type, exhaust, ethereal), from the wiki's
/// Ironclad card list; the upgrade keeps the type and keywords.
const WIKI: [(&str, i8, i8, CardType, bool, bool); 16] = [
    ("Disarm", 1, 1, CardType::Skill, true, false),
    ("Flame Barrier", 2, 2, CardType::Skill, false, false),
    ("Ghostly Armor", 1, 1, CardType::Skill, false, true),
    ("Intimidate", 0, 0, CardType::Skill, true, false),
    ("Power Through", 1, 1, CardType::Skill, false, false),
    ("Reckless Charge", 0, 0, CardType::Attack, false, false),
    ("Searing Blow", 2, 2, CardType::Attack, false, false),
    ("Seeing Red", 1, 0, CardType::Skill, true, false),
    ("Shockwave", 2, 2, CardType::Skill, true, false),
    ("Berserk", 0, 0, CardType::Power, false, false),
    ("Bludgeon", 3, 3, CardType::Attack, false, false),
    ("Double Tap", 1, 1, CardType::Skill, false, false),
    ("Feed", 1, 1, CardType::Attack, true, false),
    ("Immolate", 2, 2, CardType::Attack, false, false),
    ("Impervious", 2, 2, CardType::Skill, true, false),
    ("Offering", 0, 0, CardType::Skill, true, false),
];

fn gen(name: &str) -> String {
    format!("gen:{name}")
}

/// A combat with `deck` bound (names), card `hand[i]` of the deck in hand,
/// 3 energy, empty draw and discard piles, every monster at 100 HP with no
/// block or powers.
fn combat(deck: &[&str], hand: &[usize], enc: Encounter) -> (CombatState, Vec<CardId>) {
    load_pack(PACK).unwrap();
    let (ids, b) = bind(deck).unwrap();
    let mut s = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, enc, &mut Rng::new(1));
    s.hand = Hand::from_cards(&hand.iter().map(|&i| ids[i]).collect::<Vec<_>>());
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    s.player.energy = 3;
    for m in s.monsters.iter_mut().filter(|m| m.alive()) {
        m.hp = 100;
        m.max_hp = 100;
        m.block = 0;
        m.powers = Default::default();
    }
    (s, ids)
}

/// Plays deck card `i` (the first monster as target if it takes one).
fn play(s: &mut CombatState, ids: &[CardId], i: usize) {
    let target = if s.binding.def(ids[i]).targeted() { Some(0) } else { None };
    s.apply_action(Action::Play { card: ids[i], target }).unwrap();
}

/// Plays a lone card `name` against a Jaw Worm; the state after it.
fn after(name: &str) -> (CombatState, CardId) {
    let (mut s, ids) = combat(&[&gen(name)], &[0], Encounter::JawWorm);
    play(&mut s, &ids, 0);
    (s, ids[0])
}

#[test]
fn every_entry_loads_as_the_wiki() {
    load_pack(PACK).unwrap();
    for (name, cost, up_cost, ty, exhaust, ethereal) in WIKI {
        for (id, c) in [(name.to_string(), cost), (format!("{name}+"), up_cost)] {
            let (ids, b) = bind(&[&gen(&id)]).unwrap();
            let d = b.def(ids[0]);
            assert_eq!((d.cost(), d.ty, d.exhaust, d.ethereal), (c, ty, exhaust, ethereal), "{id}");
            assert!(!d.unplayable() && !d.innate && !d.retain && !d.x_cost(), "{id}");
        }
    }
}

#[test]
fn damage_cards() {
    for (name, dmg) in [("Searing Blow", 12), ("Searing Blow+", 16), ("Bludgeon", 32), ("Bludgeon+", 42), ("Feed", 10), ("Feed+", 12)] {
        let (s, card) = after(name);
        assert_eq!(s.monsters[0].hp, 100 - dmg, "{name}");
        let exhausted = name.starts_with("Feed");
        assert_eq!((s.exhaust().count(card), s.discard().count(card)), (exhausted as u8, !exhausted as u8), "{name}");
    }
    for (name, dmg) in [("Reckless Charge", 7), ("Reckless Charge+", 10)] {
        let (s, _) = after(name);
        assert_eq!(s.monsters[0].hp, 100 - dmg, "{name}");
        assert_eq!(s.draw().count(CardId::from_name("Dazed").unwrap()), 1, "{name}: a Dazed in the draw pile");
    }
}

#[test]
fn reckless_charge_dazed_goes_under_the_top_card() {
    // MakeTempCardInDrawPileAction(Dazed, 1, randomSpot true):
    // CardGroup.addToRandomSpot, never on top of a non-empty pile.
    let id = |n: &str| CardId::from_name(n).unwrap();
    let unknown = [id("Strike"), id("Defend"), id("Bash"), id("Strike")];
    let (mut s, ids) = combat(&[&gen("Reckless Charge")], &[0], Encounter::JawWorm);
    s.set_draw(Pile::from_cards(&unknown));
    play(&mut s, &ids, 0);
    assert_eq!(s.top.floaters().collect::<Vec<_>>(), vec![(id("Dazed"), 1)]);
    assert!(engine_draw_odds(&s, 1).iter().all(|(h, _)| !h.contains(&id("Dazed"))));
    assert_draw_odds_match(&s, &[], &unknown, &[PileOp::RandomSpot(id("Dazed"))]);
}

#[test]
fn immolate_hits_all_and_adds_a_burn() {
    for (name, dmg) in [("Immolate", 21), ("Immolate+", 28)] {
        let (mut s, ids) = combat(&[&gen(name)], &[0], Encounter::SmallSlimes);
        play(&mut s, &ids, 0);
        let alive: Vec<i16> = s.monsters.iter().filter(|m| m.max_hp == 100).map(|m| m.hp).collect();
        assert_eq!(alive, [100 - dmg, 100 - dmg], "{name}");
        assert_eq!(s.discard().count(CardId::from_name("Burn").unwrap()), 1, "{name}");
    }
}

#[test]
fn block_cards() {
    for (name, block) in [("Ghostly Armor", 10), ("Ghostly Armor+", 13), ("Impervious", 30), ("Impervious+", 40)] {
        let (s, card) = after(name);
        assert_eq!(s.player.block, block, "{name}");
        let exhausted = name.starts_with("Impervious");
        assert_eq!(s.exhaust().count(card), exhausted as u8, "{name}");
    }
    for (name, block) in [("Power Through", 15), ("Power Through+", 20)] {
        let (s, _) = after(name);
        assert_eq!(s.player.block, block, "{name}");
        assert_eq!(s.hand.count(CardId::from_name("Wound").unwrap()), 2, "{name}");
    }
    // Ethereal: left in hand at the turn's end, Ghostly Armor is exhausted.
    let (mut s, ids) = combat(&[&gen("Ghostly Armor")], &[0], Encounter::JawWorm);
    s.step(Action::EndTurn, &mut Rng::new(3)).unwrap();
    assert_eq!(s.exhaust().count(ids[0]), 1);
}

#[test]
fn debuff_cards() {
    for (name, str_) in [("Disarm", -2), ("Disarm+", -3)] {
        let (s, card) = after(name);
        assert_eq!(s.monsters[0].powers.get(Power::Strength), str_, "{name}");
        assert_eq!(s.exhaust().count(card), 1, "{name}");
    }
    // Disarm's Strength loss is a debuff: Artifact cancels it.
    let (mut s, ids) = combat(&[&gen("Disarm")], &[0], Encounter::JawWorm);
    s.monsters[0].powers.add(Power::Artifact, 1);
    play(&mut s, &ids, 0);
    assert_eq!((s.monsters[0].powers.get(Power::Strength), s.monsters[0].powers.get(Power::Artifact)), (0, 0));
    for (name, weak, vuln) in [("Intimidate", 1, 0), ("Intimidate+", 2, 0), ("Shockwave", 3, 3), ("Shockwave+", 5, 5)] {
        let (mut s, ids) = combat(&[&gen(name)], &[0], Encounter::SmallSlimes);
        play(&mut s, &ids, 0);
        for m in s.monsters.iter().filter(|m| m.max_hp == 100) {
            assert_eq!((m.powers.get(Power::Weak), m.powers.get(Power::Vulnerable)), (weak, vuln), "{name}");
        }
        assert_eq!(s.exhaust().count(ids[0]), 1, "{name}");
    }
}

#[test]
fn energy_cards() {
    for (name, energy) in [("Seeing Red", 4), ("Seeing Red+", 5)] {
        let (s, card) = after(name);
        assert_eq!(s.player.energy, energy, "{name}");
        assert_eq!(s.exhaust().count(card), 1, "{name}");
    }
    for (name, draws) in [("Offering", 3), ("Offering+", 5)] {
        let (mut s, ids) = combat(&[&gen(name), "Strike"], &[0], Encounter::JawWorm);
        s.set_draw(Pile::from_cards(&[ids[1]; 6]));
        play(&mut s, &ids, 0);
        assert_eq!((s.player.hp, s.player.energy, s.hand.len()), (74, 5, draws), "{name}");
        assert_eq!(s.exhaust().count(ids[0]), 1, "{name}");
    }
}

#[test]
fn berserk_vulnerable_and_an_energy_each_turn() {
    for (name, vuln) in [("Berserk", 2), ("Berserk+", 1)] {
        let (mut s, card) = after(name);
        assert_eq!(s.player.powers.get(Power::Vulnerable), vuln, "{name}");
        assert_eq!(s.exhaust().count(card) + s.discard().count(card), 0, "{name}: a power leaves play");
        for turn in 2..4 {
            s.step(Action::EndTurn, &mut Rng::new(turn)).unwrap();
            assert_eq!(s.player.energy, 4, "{name} turn {turn}");
        }
    }
}

/// Barricade (`cards/red/Barricade`: cost 3, upgraded 2, a Power;
/// `BarricadePower` stops the block loss in
/// `GameActionManager.getNextAction`'s turn start).
#[test]
fn barricade_keeps_block() {
    for (name, cost) in [("Barricade", 3), ("Barricade+", 2)] {
        let (mut s, ids) = combat(&[&gen(name)], &[0], Encounter::Cultist);
        assert_eq!(s.binding.def(ids[0]).ty, CardType::Power, "{name}");
        play(&mut s, &ids, 0);
        assert_eq!(s.player.energy, 3 - cost, "{name}");
        assert_eq!(s.exhaust().count(ids[0]) + s.discard().count(ids[0]), 0, "{name}: a power leaves play");
        s.player.block = 20;
        // The Cultist opens with Incantation: no attack.
        s.step(Action::EndTurn, &mut Rng::new(5)).unwrap();
        assert_eq!((s.turn, s.player.block), (2, 20), "{name}: all block kept");
        s.player.block = 30;
        s.step(Action::EndTurn, &mut Rng::new(6)).unwrap();
        assert_eq!(s.player.block, 30 - 6, "{name}: the Dark Strike takes some, the turn start none");
    }
    // Without it the turn start takes all.
    let (mut s, _) = combat(&["Defend"], &[], Encounter::Cultist);
    s.player.block = 20;
    s.step(Action::EndTurn, &mut Rng::new(5)).unwrap();
    assert_eq!(s.player.block, 0);
}

#[test]
fn flame_barrier_hits_back_this_turn_only() {
    for (name, block, back) in [("Flame Barrier", 12, 4), ("Flame Barrier+", 16, 6)] {
        let (mut s, _) = after(name);
        assert_eq!(s.player.block, block, "{name}");
        // The Jaw Worm opens with Chomp (one hit).
        s.step(Action::EndTurn, &mut Rng::new(5)).unwrap();
        assert_eq!(s.monsters[0].hp, 100 - back, "{name}: damage back for one hit");
        let gen_stacks: i16 = Power::GEN.iter().map(|&p| s.player.powers.get(p)).sum();
        assert_eq!(gen_stacks, 0, "{name}: gone at the start of the turn");
    }
}

#[test]
fn double_tap_plays_the_next_attacks_twice() {
    for (name, doubled) in [("Double Tap", 1), ("Double Tap+", 2)] {
        let (mut s, ids) = combat(&[&gen(name), "Strike"], &[0], Encounter::JawWorm);
        s.hand = Hand::from_cards(&[ids[0], ids[1], ids[1], ids[1]]);
        s.player.energy = 4;
        play(&mut s, &ids, 0);
        let mut lost = Vec::new();
        for _ in 0..3 {
            let hp = s.monsters[0].hp;
            play(&mut s, &ids, 1);
            lost.push(hp - s.monsters[0].hp);
        }
        let want: Vec<i16> = (0..3).map(|i| if i < doubled { 12 } else { 6 }).collect();
        assert_eq!(lost, want, "{name}");
    }
    // A Skill doesn't use it up, and it ends with the turn.
    let (mut s, ids) = combat(&[&gen("Double Tap"), "Defend", "Strike"], &[0, 1], Encounter::JawWorm);
    play(&mut s, &ids, 0);
    play(&mut s, &ids, 1);
    assert_eq!(s.player.block, 5, "Defend not replayed");
    s.step(Action::EndTurn, &mut Rng::new(5)).unwrap();
    let gen_stacks: i16 = Power::GEN.iter().map(|&p| s.player.powers.get(p)).sum();
    assert_eq!(gen_stacks, 0);
}

#[test]
fn greedy_plays_decks_of_them_to_an_end() {
    // One fight holds 40 pack cards (docs/specs/pack-slots.md): the 32
    // entries in one deck, every base card of the pack (C1, C2, C4 and step
    // 3's, 27) in another, and C4's four entries in a third, each with the
    // starter deck.
    load_pack(PACK).unwrap();
    let all: Vec<String> = WIKI.iter().flat_map(|w| [gen(w.0), gen(&format!("{}+", w.0))]).collect();
    let bases: Vec<String> = [
        "Disarm", "Flame Barrier", "Ghostly Armor", "Intimidate", "Power Through", "Reckless Charge", "Searing Blow",
        "Seeing Red", "Shockwave", "Berserk", "Bludgeon", "Double Tap", "Feed", "Immolate", "Impervious", "Offering",
        "True Grit", "Burning Pact", "Second Wind", "Sever Soul", "Fiend Fire", "Exhume", "Dark Embrace", "Feel No Pain",
        "Sentinel", "Entrench", "Limit Break",
    ]
    .iter()
    .map(|c| gen(c))
    .collect();
    let c4: Vec<String> = ["Entrench", "Entrench+", "Limit Break", "Limit Break+"].iter().map(|c| gen(c)).collect();
    assert_eq!((all.len(), bases.len()), (32, 27));
    let mut wins = 0;
    for (g, group) in [&all, &bases, &c4].into_iter().enumerate() {
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
                assert!(n < 4000, "deck {g} seed {seed}: no end");
            }
            wins += s.won() as u32;
        }
    }
    println!("greedy with the new cards vs a Jaw Worm: {wins} of 60 won");
    assert!(wins >= 54, "{wins} of 60");
}
