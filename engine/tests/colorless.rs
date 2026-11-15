//! The colorless cards and Colorless Potion as pack data
//! (`content/packs/act1-colorless.json`, docs/specs/colorless-cards.md
//! steps 1 to 5): each card base and upgraded against its class in the installed
//! game (`desktop-1.0.jar`, `cards/colorless/*.java`: the constructor,
//! `use()` and `upgrade()`), and the NoBlock power against
//! `powers/NoBlockPower.java`.

use std::collections::BTreeSet;

use sts_engine::cards::CardType;
use sts_engine::potions::Rarity;
use sts_engine::registry::{bind, bind_power, load_pack, potions_named, relics_named};
use sts_engine::*;

mod common;

const IRONCLAD: &str = include_str!("../../content/packs/act1-ironclad.json");
const RELICS: &str = include_str!("../../content/packs/act1-relics.json");
const POTIONS: &str = include_str!("../../content/packs/act1-potions.json");
const COLORLESS: &str = include_str!("../../content/packs/act1-colorless.json");

fn load() {
    load_pack(IRONCLAD).unwrap();
    load_pack(RELICS).unwrap();
    load_pack(POTIONS).unwrap();
    load_pack(COLORLESS).unwrap();
}

fn gen(name: &str) -> String {
    format!("gen:{name}")
}

fn id(name: &str) -> CardId {
    CardId::from_name(name).unwrap()
}

/// A fight against `enc` with the pack card `card` and the official cards
/// `hand` in hand, 3 energy, empty piles, every monster at 100 HP with no
/// block or powers. Returns the state and the pack card's id.
fn setup_in(enc: Encounter, card: &str, hand: &[&str]) -> (CombatState, CardId) {
    load();
    let g = gen(card);
    let mut names = vec![g.as_str()];
    names.extend_from_slice(hand);
    let (ids, b) = bind(&names).unwrap();
    let mut s = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, enc, &mut Rng::new(1));
    s.hand = Hand::from_cards(&ids);
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    s.set_exhaust(Pile::default());
    s.player.energy = 3;
    for m in s.monsters.iter_mut().filter(|m| m.alive()) {
        m.hp = 100;
        m.max_hp = 100;
        m.block = 0;
        m.powers = Default::default();
    }
    (s, ids[0])
}

fn setup(card: &str, hand: &[&str]) -> (CombatState, CardId) {
    setup_in(Encounter::JawWorm, card, hand)
}

fn play(s: &mut CombatState, card: CardId) {
    let target = if s.binding.def(card).targeted() { Some(0) } else { None };
    s.step(Action::Play { card, target }, &mut Rng::new(5)).unwrap();
}

/// The cards the open offer shows.
fn offered(s: &CombatState) -> Vec<CardId> {
    s.legal_actions().iter().filter_map(|a| if let Action::Choose(c) = *a { Some(c) } else { None }).collect()
}

/// (name, cost, type, exhaust, exhaust upgraded, innate), from each class's
/// constructor and `upgrade()`; no upgrade changes a cost.
const GAME: [(&str, i8, CardType, bool, bool, bool); 14] = [
    ("Swift Strike", 0, CardType::Attack, false, false, false),
    ("Flash of Steel", 0, CardType::Attack, false, false, false),
    ("Finesse", 0, CardType::Skill, false, false, false),
    ("Good Instincts", 0, CardType::Skill, false, false, false),
    ("Dramatic Entrance", 0, CardType::Attack, true, true, true),
    ("Blind", 0, CardType::Skill, false, false, false),
    ("Trip", 0, CardType::Skill, false, false, false),
    ("Panacea", 0, CardType::Skill, true, true, false),
    ("Master of Strategy", 0, CardType::Skill, true, true, false),
    ("Purity", 0, CardType::Skill, true, true, false),
    ("Hand of Greed", 2, CardType::Attack, false, false, false),
    ("Panic Button", 0, CardType::Skill, true, true, false),
    ("Discovery", 1, CardType::Skill, true, false, false),
    ("Jack of All Trades", 0, CardType::Skill, true, true, false),
];

#[test]
fn every_entry_loads_as_the_game() {
    load();
    for (name, cost, ty, exhaust, exhaust_up, innate) in GAME {
        for (n, ex) in [(name.to_string(), exhaust), (format!("{name}+"), exhaust_up)] {
            let (ids, b) = bind(&[&gen(&n)]).unwrap();
            let d = b.def(ids[0]);
            assert_eq!((d.cost(), d.ty, d.exhaust, d.innate, d.ethereal, d.retain), (cost, ty, ex, innate, false, false), "{n}");
            assert_eq!(d.has_tag(cards::Tag::Strike), name == "Swift Strike", "{n}: SwiftStrike.java tags STRIKE");
        }
    }
}

#[test]
fn attacks() {
    // DamageAction on the target; Flash of Steel then DrawCardAction(1).
    for (name, dmg, draws) in [
        ("Swift Strike", 7, 0),
        ("Swift Strike+", 10, 0),
        ("Flash of Steel", 3, 1),
        ("Flash of Steel+", 6, 1),
        ("Hand of Greed", 20, 0),
        ("Hand of Greed+", 25, 0),
    ] {
        let (mut s, c) = setup(name, &[]);
        s.set_draw(Pile::from_cards(&[id("Strike"); 4]));
        play(&mut s, c);
        assert_eq!((s.monsters[0].hp, s.hand.len(), s.discard().count(c)), (100 - dmg, draws, 1), "{name}");
        assert_eq!(s.player.energy, 3 - s.binding.def(c).cost() as i16, "{name}");
    }
}

#[test]
fn dramatic_entrance_hits_all_and_exhausts() {
    // DamageAllEnemiesAction 8 (+4); exhaust, innate.
    for (name, dmg) in [("Dramatic Entrance", 8), ("Dramatic Entrance+", 12)] {
        let (mut s, c) = setup_in(Encounter::TwoLouse, name, &[]);
        play(&mut s, c);
        assert!(s.monsters.iter().filter(|m| m.max_hp == 100).all(|m| m.hp == 100 - dmg), "{name}");
        assert_eq!(s.exhaust().count(c), 1, "{name}");
    }
}

#[test]
fn block_skills() {
    // GainBlockAction (card block); Finesse then DrawCardAction(1).
    for (name, block, draws) in [("Finesse", 2, 1), ("Finesse+", 4, 1), ("Good Instincts", 6, 0), ("Good Instincts+", 9, 0)] {
        let (mut s, c) = setup(name, &[]);
        s.set_draw(Pile::from_cards(&[id("Strike"); 4]));
        play(&mut s, c);
        assert_eq!((s.player.block, s.hand.len()), (block, draws), "{name}");
    }
    // Card block: Frail scales it.
    let (mut s, c) = setup("Good Instincts+", &[]);
    s.player.powers.add(Power::Frail, 1);
    play(&mut s, c);
    assert_eq!(s.player.block, 6);
}

#[test]
fn blind_and_trip_one_then_all() {
    // Blind: WeakPower 2 on the target; upgraded, on every monster
    // (`upgrade()` sets target ALL_ENEMY). Trip the same with Vulnerable.
    for (name, power) in [("Blind", Power::Weak), ("Trip", Power::Vulnerable)] {
        let (mut s, c) = setup_in(Encounter::TwoLouse, name, &[]);
        assert!(s.binding.def(c).targeted(), "{name}");
        play(&mut s, c);
        let got: Vec<i16> = s.monsters.iter().filter(|m| m.alive()).map(|m| m.powers.get(power)).collect();
        assert_eq!(got, [2, 0], "{name}");
        let up = format!("{name}+");
        let (mut s, c) = setup_in(Encounter::TwoLouse, &up, &[]);
        assert!(!s.binding.def(c).targeted(), "{up}");
        play(&mut s, c);
        let got: Vec<i16> = s.monsters.iter().filter(|m| m.alive()).map(|m| m.powers.get(power)).collect();
        assert_eq!(got, [2, 2], "{up}");
        assert_eq!(s.discard().count(c), 1);
    }
}

#[test]
fn panacea_gives_artifact() {
    for (name, n) in [("Panacea", 1), ("Panacea+", 2)] {
        let (mut s, c) = setup(name, &[]);
        play(&mut s, c);
        assert_eq!((s.player.powers.get(Power::Artifact), s.exhaust().count(c)), (n, 1), "{name}");
    }
}

#[test]
fn master_of_strategy_draws() {
    for (name, n) in [("Master of Strategy", 3), ("Master of Strategy+", 4)] {
        let (mut s, c) = setup(name, &[]);
        s.set_draw(Pile::from_cards(&[id("Strike"); 6]));
        play(&mut s, c);
        assert_eq!((s.hand.len(), s.exhaust().count(c)), (n, 1), "{name}");
    }
}

#[test]
fn purity_exhausts_up_to_n_chosen() {
    // ExhaustAction(3 (+2), false, true, true): any number up to n, 0 allowed.
    let hand = ["Strike", "Defend", "Bash", "Anger", "Clash", "Cleave"];
    for (name, n) in [("Purity", 3), ("Purity+", 5)] {
        // Taking n ends the pick.
        let (mut s, c) = setup(name, &hand);
        play(&mut s, c);
        for k in 0..n {
            assert!(s.legal_actions().contains(&Action::Done), "{name}: stopping is allowed");
            let Action::Choose(x) = s.legal_actions()[0] else { panic!("{name}: still picking after {k}") };
            s.step(Action::Choose(x), &mut Rng::new(1)).unwrap();
        }
        assert_eq!(s.stage, Stage::PlayerTurn, "{name}");
        assert_eq!((s.exhaust().len(), s.hand.len()), (n + 1, 6 - n), "{name}");
        // None taken.
        let (mut s, c) = setup(name, &hand);
        play(&mut s, c);
        s.step(Action::Done, &mut Rng::new(1)).unwrap();
        assert_eq!((s.stage, s.exhaust().len(), s.hand.len()), (Stage::PlayerTurn, 1, 6), "{name}");
    }
}

/// The NoBlock power's slot in `s`'s binding.
fn no_block(s: &mut CombatState) -> Power {
    let (b, p) = bind_power(&s.binding, "NoBlock").unwrap();
    assert_eq!(b, s.binding, "the card binds NoBlock");
    p
}

#[test]
fn panic_button_blocks_then_no_card_block() {
    // GainBlockAction 30 (+10), then NoBlockPower 2 on the player
    // (isSourceMonster false: not just applied, so it ticks this round end).
    for (name, block) in [("Panic Button", 30), ("Panic Button+", 40)] {
        let (mut s, c) = setup(name, &["Defend", "Defend"]);
        let nb = no_block(&mut s);
        play(&mut s, c);
        assert_eq!((s.player.block, s.player.powers.get(nb), s.exhaust().count(c)), (block, 2, 1), "{name}");
        // `modifyBlockLast` returns 0: card block is zeroed, Dexterity too.
        s.player.powers.add(Power::Dexterity, 3);
        play(&mut s, id("Defend"));
        assert_eq!(s.player.block, block, "{name}");
        assert_eq!(s.shown_block(5), 0);
    }
    // Two round ends: 2 -> 1 -> gone; card block counts again on turn 3.
    let (mut s, c) = setup("Panic Button", &[]);
    let nb = no_block(&mut s);
    s.player.hp = 80;
    play(&mut s, c);
    s.step(Action::EndTurn, &mut Rng::new(1)).unwrap();
    assert_eq!(s.player.powers.get(nb), 1);
    s.step(Action::EndTurn, &mut Rng::new(1)).unwrap();
    assert_eq!(s.player.powers.get(nb), 0);
    assert_eq!(s.shown_block(5), 5);
}

#[test]
fn no_block_is_a_debuff_artifact_stops() {
    let (mut s, c) = setup("Panic Button", &[]);
    let nb = no_block(&mut s);
    s.player.powers.add(Power::Artifact, 1);
    play(&mut s, c);
    assert_eq!((s.player.block, s.player.powers.get(nb), s.player.powers.get(Power::Artifact)), (30, 0, 0));
}

#[test]
fn no_block_leaves_potion_relic_and_power_block() {
    // The game's NoBlock is `modifyBlockLast`, read only by a card's
    // `applyPowersToBlock`: a potion's, relic's or power's GainBlockAction
    // is raw, as with Frail. The engine's raw paths: potion rows, power
    // hooks, relic hooks.
    load();
    let relics = relics_named(&["gen:Horn Cleat"]).unwrap();
    let (ids, b) = bind(&["gen:Panic Button", "gen:Feel No Pain"]).unwrap();
    let mut s = CombatState::new_bound_with(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &relics, &mut Rng::new(1));
    s.hand = Hand::from_cards(&ids[..1]);
    s.set_draw(Pile::from_cards(&[id("Defend"); 10]));
    s.set_discard(Pile::default());
    s.set_exhaust(Pile::default());
    s.player.energy = 3;
    s.give_potions(&potions_named(&["gen:Block Potion"]).unwrap()).unwrap();
    let nb = no_block(&mut s);
    // Power hook: Feel No Pain's Block 3 when Panic Button exhausts, after
    // its NoBlock lands.
    let fnp = bind_power(&s.binding, "FeelNoPain").unwrap().1;
    s.player.powers.add(fnp, 3);
    play(&mut s, ids[0]);
    assert_eq!((s.player.block, s.player.powers.get(nb)), (30 + 3, 2), "Feel No Pain");
    // Potion: Block Potion's 12.
    s.player.block = 0;
    s.step(Action::UsePotion { slot: 0, target: None }, &mut Rng::new(1)).unwrap();
    assert_eq!(s.player.block, 12, "Block Potion");
    // Relic: Horn Cleat's 14 at the start of turn 2, NoBlock still 1.
    s.step(Action::EndTurn, &mut Rng::new(1)).unwrap();
    assert_eq!((s.player.powers.get(nb), s.player.block), (1, 14), "Horn Cleat");
    // Card block is still zeroed.
    let d = s.hand.iter().map(|(c, _)| c).find(|&c| c == id("Defend")).unwrap();
    play(&mut s, d);
    assert_eq!(s.player.block, 14);
}

#[test]
fn discovery_offers_three_ironclad_cards_free_no_skip() {
    // DiscoveryAction(): cardType null (any type), skippable only with a
    // type, so not; the chosen card costs 0 this turn. Exhaust, upgraded not.
    let ironclad: BTreeSet<String> = pool_names(IRONCLAD, "Ironclad").into_iter().collect();
    let mut types = BTreeSet::new();
    for seed in 0..60 {
        let (mut s, c) = setup("Discovery", &[]);
        s.step(Action::Play { card: c, target: None }, &mut Rng::new(seed)).unwrap();
        let o = offered(&s);
        assert_eq!(o.len(), 3);
        assert!(!s.legal_actions().contains(&Action::Done), "no skip");
        for &x in &o {
            let nm = s.binding.def(x).name.trim_start_matches("gen:").to_string();
            assert!(ironclad.contains(&nm), "seed {seed}: {nm}");
            types.insert(format!("{:?}", s.binding.def(x).ty));
        }
        s.step(Action::Choose(o[0]), &mut Rng::new(1)).unwrap();
        assert_eq!((s.hand.count(o[0]), s.exhaust().count(c), s.player.energy), (1, 1, 2));
        if s.binding.def(o[0]).cost() > 0 {
            assert_eq!(s.free_in_hand.count(o[0]), 1);
        }
    }
    assert_eq!(types.len(), 3, "attacks, skills and powers all show");
    let (mut s, c) = setup("Discovery+", &[]);
    play(&mut s, c);
    let o = offered(&s);
    s.step(Action::Choose(o[0]), &mut Rng::new(1)).unwrap();
    assert_eq!((s.discard().count(c), s.exhaust().count(c)), (1, 0));
}

#[test]
fn jack_of_all_trades_adds_random_colorless() {
    // returnTrulyRandomColorlessCardInCombat into hand (MakeTempCardInHand,
    // no cost change); upgraded, a second roll of its own.
    let pool = colorless_names();
    for (name, n) in [("Jack of All Trades", 1usize), ("Jack of All Trades+", 2)] {
        let mut seen = BTreeSet::new();
        for seed in 0..120 {
            let (mut s, c) = setup(name, &[]);
            s.step(Action::Play { card: c, target: None }, &mut Rng::new(seed)).unwrap();
            assert_eq!(s.stage, Stage::PlayerTurn, "{name}: no decision");
            assert_eq!((s.hand.len(), s.exhaust().count(c)), (n, 1), "{name}");
            for (x, _) in s.hand.iter() {
                let nm = s.binding.def(x).name.trim_start_matches("gen:").to_string();
                assert!(pool.contains(&nm), "{nm}");
                assert_eq!(s.binding.def(x).level, 0);
                assert_eq!(s.free_in_hand.count(x), 0, "not free");
                seen.insert(nm);
            }
        }
        assert!(seen.len() >= 10, "{name}: {seen:?}");
    }
}

fn colorless_names() -> BTreeSet<String> {
    pool_names(COLORLESS, "Colorless").into_iter().collect()
}

/// The pool `name` of a pack's text, as written.
fn pool_names(pack: &str, name: &str) -> Vec<String> {
    let key = format!("\"{name}\": [");
    let start = pack.find(&key).unwrap() + key.len();
    let end = start + pack[start..].find(']').unwrap();
    pack[start..end].split(',').map(|s| s.trim().trim_matches('"').to_string()).collect()
}

#[test]
fn colorless_potion_offers_three_colorless_free_no_skip() {
    // ColorlessPotion.java: common, potency 1, DiscoveryAction(true, potency):
    // the colorless pool, no type so no skip; copies cost 0 this turn.
    load();
    let p = registry::potion("gen:Colorless Potion").unwrap();
    assert_eq!((p.rarity, p.potency), (Rarity::Common, 1));
    let pool = colorless_names();
    let mut seen = BTreeSet::new();
    for seed in 0..200 {
        let (ids, b) = bind(&["Strike"]).unwrap();
        let mut s = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &mut Rng::new(seed));
        s.give_potions(&potions_named(&["gen:Colorless Potion"]).unwrap()).unwrap();
        s.step(Action::UsePotion { slot: 0, target: None }, &mut Rng::new(seed)).unwrap();
        let o = offered(&s);
        assert_eq!(o.len(), 3);
        assert_eq!(o.iter().collect::<BTreeSet<_>>().len(), 3, "three different cards");
        assert!(!s.legal_actions().contains(&Action::Done), "no skip");
        for &x in &o {
            seen.insert(s.binding.def(x).name.trim_start_matches("gen:").to_string());
        }
        let hand = s.hand.len();
        s.step(Action::Choose(o[0]), &mut Rng::new(1)).unwrap();
        assert_eq!(s.hand.len(), hand + 1);
        if s.binding.def(o[0]).cost() > 0 {
            assert_eq!(s.free_in_hand.count(o[0]), 1);
        }
    }
    assert_eq!(seen, pool, "every card of the pool shows, nothing else");
}

// Step 4: the pile words (HandToTop, DrawPileSize, ShuffleDiscardIntoDraw,
// UpgradeAll) with Thinking Ahead, Mind Blast, Deep Breath, Apotheosis and
// Warcry (`cards/red/Warcry.java`), against `PutOnDeckAction`,
// `EmptyDeckShuffleAction`, `ShuffleAction` and `ApotheosisAction`.

/// A test card: the pick alone.
const PUT_TOP: &str = r#"{"version": 2, "cards": [
{"id": "pw-PutTop", "cost": 0, "type": "Skill", "effects": [{"Pick": {"kind": "HandToTop", "n": 1, "exact": true}}]}
]}"#;

/// `setup` with nothing known about the draw pile.
fn setup4(card: &str, hand: &[&str]) -> (CombatState, CardId) {
    load();
    load_pack(PUT_TOP).unwrap();
    let (mut s, c) = setup(card, hand);
    s.top = Default::default();
    (s, c)
}

fn pile(names: &[&str]) -> Pile {
    Pile::from_cards(&names.iter().map(|n| id(n)).collect::<Vec<_>>())
}

fn known(s: &CombatState) -> Vec<CardId> {
    s.top.known().collect()
}

fn choices(s: &CombatState) -> Vec<CardId> {
    s.legal_actions().iter().filter_map(|a| if let Action::Choose(c) = *a { Some(c) } else { None }).collect()
}

/// (name, cost, type, exhaust, innate), base and upgraded, from each
/// class's constructor and `upgrade()`.
#[test]
fn step4_card_stats() {
    load();
    let rows: [(&str, i8, CardType, bool, bool); 10] = [
        ("Thinking Ahead", 0, CardType::Skill, true, false),
        ("Thinking Ahead+", 0, CardType::Skill, false, false),
        ("Mind Blast", 2, CardType::Attack, false, true),
        ("Mind Blast+", 1, CardType::Attack, false, true),
        ("Deep Breath", 0, CardType::Skill, false, false),
        ("Deep Breath+", 0, CardType::Skill, false, false),
        ("Apotheosis", 2, CardType::Skill, true, false),
        ("Apotheosis+", 1, CardType::Skill, true, false),
        ("Warcry", 0, CardType::Skill, true, false),
        ("Warcry+", 0, CardType::Skill, true, false),
    ];
    for (name, cost, ty, exhaust, innate) in rows {
        let (ids, b) = bind(&[format!("gen:{name}").as_str()]).unwrap();
        let d = b.def(ids[0]);
        assert_eq!((d.cost(), d.ty, d.exhaust, d.innate, d.ethereal, d.retain), (cost, ty, exhaust, innate, false, false), "{name}");
    }
}

#[test]
fn thinking_ahead_draws_two_then_puts_one_chosen_card_on_top() {
    // DrawCardAction 2, then PutOnDeckAction 1 (not random): the chosen
    // hand card goes on top, known. Exhaust; upgraded not.
    for (name, exhausted) in [("Thinking Ahead", true), ("Thinking Ahead+", false)] {
        let (mut s, c) = setup4(name, &["Strike", "Defend"]);
        s.set_draw(pile(&["Bash", "Anger"]));
        play(&mut s, c);
        assert_eq!(s.hand.len(), 4, "{name}");
        let mut want: Vec<CardId> = ["Strike", "Defend", "Bash", "Anger"].iter().map(|n| id(n)).collect();
        want.sort();
        let mut got = choices(&s);
        got.sort();
        assert_eq!(got, want, "{name}");
        s.apply_action(Action::Choose(id("Defend"))).unwrap();
        assert_eq!(s.stage, Stage::PlayerTurn, "{name}");
        assert_eq!((s.hand.len(), s.hand.count(id("Defend")), s.draw().len()), (3, 0, 1), "{name}");
        assert_eq!(known(&s), vec![id("Defend")], "{name}");
        assert_eq!((s.exhaust().count(c), s.discard().count(c)), (exhausted as u8, !exhausted as u8), "{name}");
        assert_eq!(s.player.energy, 3, "{name}");
    }
}

#[test]
fn hand_to_top_is_made_at_once_with_one_kind_in_hand() {
    // PutOnDeckAction with hand size <= amount moves the whole hand, no screen.
    let (mut s, c) = setup4("Thinking Ahead", &[]);
    s.set_draw(pile(&["Bash"]));
    play(&mut s, c);
    assert_eq!(s.stage, Stage::PlayerTurn);
    assert_eq!((s.hand.len(), s.draw().len()), (0, 1));
    assert_eq!(known(&s), vec![id("Bash")]);
    // An empty hand: nothing (the draw found nothing).
    let (mut s, c) = setup4("Thinking Ahead", &[]);
    play(&mut s, c);
    assert_eq!((s.stage, s.hand.len(), s.draw().len(), s.top.n_known()), (Stage::PlayerTurn, 0, 0, 0));
    // Two copies of one card, n 1: still a choice the game shows, but one
    // afterstate: made at once only when the hand holds at most n.
    let (mut s, c) = setup4("pw-PutTop", &["Strike", "Strike"]);
    play(&mut s, c);
    assert_eq!(choices(&s), vec![id("Strike")]);
    s.apply_action(Action::Choose(id("Strike"))).unwrap();
    assert_eq!((s.stage, s.hand.len(), known(&s)), (Stage::PlayerTurn, 1, vec![id("Strike")]));
}

#[test]
fn hand_to_top_goes_above_a_known_top_and_its_floaters() {
    // Known top Bash, a floater Anger with nothing certainly above it.
    let (mut s, c) = setup4("pw-PutTop", &["Defend", "Strike"]);
    s.set_draw(pile(&["Bash", "Anger", "Strike"]));
    s.top = sts_engine::state::Top::from_parts(&[id("Bash")], &[(id("Anger"), 0)]).unwrap();
    play(&mut s, c);
    s.apply_action(Action::Choose(id("Defend"))).unwrap();
    assert_eq!(known(&s), vec![id("Defend"), id("Bash")]);
    assert_eq!(s.top.floaters().collect::<Vec<_>>(), vec![(id("Anger"), 1)]);
    assert_eq!(s.draw().len(), 4);
    // The next draw is the chosen card.
    let mut t = s.clone();
    t.pending = Some(sts_engine::chance::ChanceEvent::Draw { n: 1 });
    t.resolve_chance(&mut Rng::new(3));
    assert_eq!(t.hand.count(id("Defend")), 1);
}

#[test]
fn warcry_draws_then_puts_one_on_top() {
    // Draw magicNumber 1 (+1), then PutOnDeckAction 1; exhaust both.
    for (name, draws) in [("Warcry", 1usize), ("Warcry+", 2)] {
        let (mut s, c) = setup4(name, &["Strike"]);
        s.set_draw(pile(&["Bash", "Anger"]));
        play(&mut s, c);
        assert_eq!(s.hand.len(), 1 + draws, "{name}");
        s.apply_action(Action::Choose(id("Strike"))).unwrap();
        assert_eq!((s.hand.len(), s.draw().len()), (draws, 3 - draws), "{name}");
        assert_eq!(known(&s), vec![id("Strike")], "{name}");
        assert_eq!(s.exhaust().count(c), 1, "{name}");
    }
}

#[test]
fn mind_blast_hits_for_the_draw_pile_size() {
    // baseDamage = drawPile.size() in applyPowers, a NORMAL DamageAction:
    // Strength and Vulnerable apply. Cost 2, upgraded 1; innate.
    for (name, cost) in [("Mind Blast", 2), ("Mind Blast+", 1)] {
        let (mut s, c) = setup4(name, &[]);
        s.set_draw(pile(&["Strike", "Strike", "Defend", "Bash", "Anger", "Defend", "Strike"]));
        play(&mut s, c);
        assert_eq!((s.monsters[0].hp, s.player.energy), (93, 3 - cost), "{name}");
        let (mut s, c) = setup4(name, &[]);
        s.set_draw(pile(&["Strike", "Strike", "Defend", "Bash"]));
        s.player.powers.add(Power::Strength, 2);
        s.monsters[0].powers.add(Power::Vulnerable, 1);
        play(&mut s, c);
        // (4 + 2) * 1.5 = 9.
        assert_eq!(s.monsters[0].hp, 91, "{name}");
        // An empty draw pile: 0 damage.
        let (mut s, c) = setup4(name, &[]);
        play(&mut s, c);
        assert_eq!(s.monsters[0].hp, 100, "{name}");
    }
}

#[test]
fn deep_breath_shuffles_the_discard_in_and_forgets_the_top() {
    // discardPile.size() > 0: EmptyDeckShuffleAction and ShuffleAction of
    // the draw pile, then Draw magicNumber 1 (+1).
    for (name, draws) in [("Deep Breath", 1usize), ("Deep Breath+", 2)] {
        let (mut s, c) = setup4(name, &[]);
        s.set_draw(pile(&["Defend", "Anger"]));
        s.top = sts_engine::state::Top::from_parts(&[id("Defend")], &[(id("Anger"), 0)]).unwrap();
        s.set_discard(pile(&["Strike", "Strike", "Bash"]));
        play(&mut s, c);
        assert!(s.top.is_empty(), "{name}");
        assert_eq!((s.hand.len(), s.draw().len(), s.discard().len()), (draws, 5 - draws, 1), "{name}");
        assert_eq!(s.discard().count(c), 1, "{name}");
    }
    // An empty discard pile: no shuffle, so the known top stays and is drawn.
    let (mut s, c) = setup4("Deep Breath", &[]);
    s.set_draw(pile(&["Defend", "Anger", "Strike"]));
    s.top = sts_engine::state::Top::from_parts(&[id("Defend")], &[]).unwrap();
    play(&mut s, c);
    assert_eq!(s.hand.count(id("Defend")), 1);
    assert_eq!(s.draw().len(), 2);
}

#[test]
fn apotheosis_upgrades_every_pile_but_itself() {
    // ApotheosisAction: canUpgrade() cards in hand, draw, discard and
    // exhaust pile; the card in play is in none (it exhausts after).
    for (name, cost) in [("Apotheosis", 2), ("Apotheosis+", 1)] {
        let (mut s, c) = setup4(name, &["Strike", "Dazed"]);
        s.set_draw(pile(&["Bash", "Defend", "Wound"]));
        s.top = sts_engine::state::Top::from_parts(&[id("Bash")], &[(id("Defend"), 0), (id("Wound"), 1)]).unwrap();
        s.set_discard(pile(&["Anger", "Strike+"]));
        s.set_exhaust(pile(&["Defend"]));
        play(&mut s, c);
        assert_eq!(s.player.energy, 3 - cost, "{name}");
        assert_eq!((s.hand.count(id("Strike+")), s.hand.count(id("Dazed"))), (1, 1), "{name}");
        assert_eq!((s.draw().count(id("Bash+")), s.draw().count(id("Defend+")), s.draw().count(id("Wound"))), (1, 1, 1), "{name}");
        assert_eq!((s.discard().count(id("Anger+")), s.discard().count(id("Strike+"))), (1, 1), "{name}");
        assert_eq!((s.exhaust().count(id("Defend+")), s.exhaust().count(c)), (1, 1), "{name}");
        assert_eq!(known(&s), vec![id("Bash+")], "{name}");
        assert_eq!(s.top.floaters().collect::<Vec<_>>(), vec![(id("Defend+"), 0), (id("Wound"), 1)], "{name}");
    }
}

#[test]
fn apotheosis_raises_searing_blow_one_level_per_copy() {
    // Searing Blow's levels: a copy at level 0 and one at level 1 in the
    // draw pile each go up once (upgradeDamage(4 + timesUpgraded): 12 ->
    // 16 at level 1 -> 21 at level 2).
    load();
    let (ids, b) = bind(&["gen:Apotheosis", "gen:Searing Blow", "gen:Searing Blow+"]).unwrap();
    let mut s = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &mut Rng::new(1));
    s.hand = Hand::from_cards(&ids[..1]);
    s.set_draw(Pile::from_cards(&ids[1..]));
    s.set_discard(Pile::default());
    s.set_exhaust(Pile::default());
    s.top = Default::default();
    s.player.energy = 3;
    play(&mut s, ids[0]);
    let mut dmg: Vec<i16> = s
        .draw()
        .iter()
        .map(|(x, _)| match s.binding.def(x).effects[0] {
            sts_engine::effects::Effect::Damage { amount, .. } => amount,
            _ => 0,
        })
        .collect();
    dmg.sort();
    assert_eq!(dmg, vec![16, 21]);
}

// ---- Step 2: Impatience, Dark Shackles, Sadistic Nature (conditions
// HandNone, TargetLacks, ApplyingDebuff; powers Shackled and Sadistic,
// against powers/GainStrengthPower.java and SadisticPower.java).

/// A pack card's bound name, an official one's as it is.
fn gen2(name: &str) -> String {
    if CardId::from_name(name).is_some() { name.to_string() } else { format!("gen:{name}") }
}

/// A combat with `deck` bound, `deck[i]` for each `i` of `hand` in hand, the
/// rest of the deck as the draw pile, 3 energy, an empty discard and a Jaw
/// Worm at 100 HP with no block or powers.
fn combat2(deck: &[&str], hand: &[usize]) -> (CombatState, Vec<CardId>) {
    load();
    let names: Vec<String> = deck.iter().map(|n| gen2(n)).collect();
    let (ids, b) = bind(&names.iter().map(String::as_str).collect::<Vec<_>>()).unwrap();
    let mut s = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &mut Rng::new(1));
    s.hand = Hand::from_cards(&hand.iter().map(|&i| ids[i]).collect::<Vec<_>>());
    let mut draw = Pile::default();
    for (_, &c) in ids.iter().enumerate().filter(|(i, _)| !hand.contains(i)) {
        draw.add(c, 1);
    }
    s.set_draw(draw);
    s.set_discard(Pile::default());
    s.player.energy = 3;
    let m = &mut s.monsters[0];
    m.hp = 100;
    m.max_hp = 100;
    m.block = 0;
    m.powers = Default::default();
    (s, ids)
}

fn play2(s: &mut CombatState, c: CardId) {
    let target = s.binding.def(c).targeted().then_some(0);
    s.step(Action::Play { card: c, target }, &mut Rng::new(5)).unwrap();
}

#[test]
fn entries_load_as_the_jar() {
    load();
    // (name, type, exhaust, targeted): every cost 0, upgraded too.
    for (name, ty, exhaust, targeted) in [
        ("Impatience", CardType::Skill, false, false),
        ("Dark Shackles", CardType::Skill, true, true),
        ("Sadistic Nature", CardType::Power, false, false),
    ] {
        for id in [name.to_string(), format!("{name}+")] {
            let (ids, b) = bind(&[&gen2(&id)]).unwrap();
            let d = b.def(ids[0]);
            assert_eq!((d.cost(), d.ty, d.exhaust, d.targeted()), (0, ty, exhaust, targeted), "{id}");
            assert!(!d.ethereal && !d.innate && !d.retain && !d.x_cost(), "{id}");
        }
    }
    // ApplyingDebuff is an OwnerApplied hook's only.
    let bad = load_pack(r#"{"version": 2, "cards": [{"id": "cl-bad", "cost": 0, "type": "Skill", "rows": [{"condition": "ApplyingDebuff", "effects": [{"Block": 1}]}]}]}"#);
    assert!(bad.unwrap_err().contains("OwnerApplied hook's only"));
}

/// Impatience: Draw 2 (3 upgraded) when no Attack is in hand once it has
/// left it (`ConditionalDrawAction`).
#[test]
fn impatience_draws_without_attacks_in_hand() {
    for (name, n) in [("Impatience", 2), ("Impatience+", 3)] {
        let deck = [name, "Defend", "Strike", "Strike", "Strike", "Strike"];
        let (mut s, ids) = combat2(&deck, &[0, 1]);
        play2(&mut s, ids[0]);
        assert_eq!(s.hand.len(), 1 + n, "{name}: Defend and {n} drawn");
        // Alone in hand: still draws (the card in play isn't in hand).
        let (mut s, ids) = combat2(&deck, &[0]);
        play2(&mut s, ids[0]);
        assert_eq!(s.hand.len(), n, "{name} alone");
        // A Strike in hand: no draw.
        let (mut s, ids) = combat2(&deck, &[0, 1, 2]);
        play2(&mut s, ids[0]);
        assert_eq!(s.hand.len(), 2, "{name} with a Strike");
        assert_eq!(s.player.energy, 3);
    }
}

/// Dark Shackles: Strength -9 (-15 upgraded) on the target and, with no
/// Artifact at play, Shackled 9 (15), which gives it back at the end of the
/// monster's turn. Exhausts.
#[test]
fn dark_shackles_takes_strength_for_a_turn() {
    for (name, n) in [("Dark Shackles", 9), ("Dark Shackles+", 15)] {
        let (mut s, ids) = combat2(&[name], &[0]);
        let b = s.binding.clone();
        let shackled = b.powers_in_play().iter().copied().find(|&p| b.power_id(p) == Some("Shackled")).expect("Shackled bound");
        let chomp = sts_engine::agent::intent_damage(&s, 0);
        play2(&mut s, ids[0]);
        assert_eq!(s.monsters[0].powers.get(Power::Strength), -n, "{name}");
        assert_eq!(s.monsters[0].powers.get(shackled), n, "{name}");
        assert_eq!(s.exhaust().count(ids[0]), 1, "{name} exhausts");
        let hp = s.player.hp;
        s.step(Action::EndTurn, &mut Rng::new(7)).unwrap();
        assert_eq!(hp - s.player.hp, (chomp - n).max(0), "{name}: the attack with Strength -{n}");
        assert_eq!(s.monsters[0].powers.get(Power::Strength), 0, "{name}: back after its turn");
        assert_eq!(s.monsters[0].powers.get(shackled), 0, "{name}: Shackled removed");
        // Artifact at play: it blocks the Strength loss, and no Shackled.
        let (mut s, ids) = combat2(&[name], &[0]);
        s.monsters[0].powers.add(Power::Artifact, 1);
        play2(&mut s, ids[0]);
        assert_eq!(s.monsters[0].powers.get(Power::Strength), 0, "{name} vs Artifact");
        assert_eq!(s.monsters[0].powers.get(Power::Artifact), 0, "{name}: Artifact spent");
        assert_eq!(s.monsters[0].powers.get(shackled), 0, "{name}: no Shackled");
    }
}

/// Sadistic Nature: 5 (7 upgraded) THORNS damage, per stack, each time the
/// player applies a debuff to an enemy that gets past Artifact; Shackled is
/// no debuff, Strength -n is.
#[test]
fn sadistic_nature_damages_on_debuffs() {
    for (name, n) in [("Sadistic Nature", 5), ("Sadistic Nature+", 7)] {
        // Bash: 8 damage, Vulnerable 2 -> n more, no Strength added.
        let (mut s, ids) = combat2(&[name, "Bash"], &[0, 1]);
        play2(&mut s, ids[0]);
        s.player.powers.add(Power::Strength, 2);
        play2(&mut s, ids[1]);
        assert_eq!(100 - s.monsters[0].hp, 10 + n, "{name} + Bash");
        // Dark Shackles: Strength -9 fires it, Shackled doesn't.
        let (mut s, ids) = combat2(&[name, "Dark Shackles"], &[0, 1]);
        play2(&mut s, ids[0]);
        play2(&mut s, ids[1]);
        assert_eq!(100 - s.monsters[0].hp, n, "{name} + Dark Shackles");
        // Artifact blocks the debuff: no damage.
        let (mut s, ids) = combat2(&[name, "Bash"], &[0, 1]);
        s.monsters[0].powers.add(Power::Artifact, 1);
        play2(&mut s, ids[0]);
        play2(&mut s, ids[1]);
        assert_eq!(100 - s.monsters[0].hp, 8, "{name} vs Artifact");
        // Two copies stack.
        let (mut s, ids) = combat2(&[name, name, "Bash"], &[0, 1, 2]);
        play2(&mut s, ids[0]);
        play2(&mut s, ids[1]);
        play2(&mut s, ids[2]);
        assert_eq!(100 - s.monsters[0].hp, 8 + 2 * n, "two {name}");
    }
}

// Step 5: Madness (`cards/colorless/Madness.java`, `MadnessAction`).

/// Plays `card` without sampling its chance event.
fn start(s: &mut CombatState, card: CardId) {
    s.apply_action(Action::Play { card, target: None }).unwrap();
}

/// The hand's changed copies (each checked to cost 0 for the combat).
fn zeroed(s: &CombatState) -> Vec<CardId> {
    let z: Vec<CardId> = s.hand.iter().filter(|&(c, _)| sts_engine::registry::copy_of(c).is_some()).map(|(c, _)| c).collect();
    for &c in &z {
        assert_eq!(s.binding.def(c).cost(), 0);
    }
    z
}

#[test]
fn madness_stats() {
    load();
    for (name, cost) in [("Madness", 1), ("Madness+", 0)] {
        let (ids, b) = bind(&[format!("gen:{name}").as_str()]).unwrap();
        let d = b.def(ids[0]);
        assert_eq!((d.cost(), d.ty, d.exhaust, d.innate, d.targeted()), (cost, CardType::Skill, true, false, false), "{name}");
    }
}

#[test]
fn madness_with_one_card_above_zero_changes_it_at_once() {
    // X-cost (-1), unplayable (-2) and 0-cost cards never qualify; one
    // qualifying card needs no roll. Its cost stays 0 for the combat.
    for (name, cost) in [("Madness", 1), ("Madness+", 0)] {
        let (mut s, c) = setup(name, &["Strike", "Anger", "Whirlwind", "Dazed"]);
        start(&mut s, c);
        assert_eq!(s.pending, None, "{name}");
        assert_eq!(s.player.energy, 3 - cost, "{name}");
        assert_eq!((s.hand.len(), s.hand.count(id("Strike")), s.exhaust().count(c)), (4, 0, 1), "{name}");
        let z = zeroed(&s);
        assert_eq!(z.len(), 1, "{name}");
        assert_eq!(s.cost_of(z[0]), 0, "{name}");
        assert_eq!(s.binding.def(z[0]).effects, s.binding.def(id("Strike")).effects, "{name}");
    }
}

#[test]
fn madness_picks_by_copies_among_cards_costing_above_zero_this_turn() {
    // costForTurn > 0 cards first, getRandomCard uniform over the hand
    // (redrawn until one qualifies): by copies. A marked (free this turn)
    // Bash is passed over while an unmarked card qualifies.
    for name in ["Madness", "Madness+"] {
        let (mut s, c) = setup(name, &["Strike", "Strike", "Defend", "Bash", "Anger"]);
        assert!(s.mark_free_in_hand(id("Bash")));
        start(&mut s, c);
        assert_eq!(s.pending, Some(ChanceEvent::RandomZeroCost), "{name}");
        let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(10) else { panic!("listed") };
        assert_eq!(v.len(), 2, "{name}");
        for (p, o) in &v {
            let strike = o.hand.count(id("Strike")) == 1;
            let want = if strike { 2.0 / 3.0 } else { 1.0 / 3.0 };
            assert!((p - want).abs() < 1e-9, "{name} {p}");
            assert_eq!(o.hand.count(id("Defend")), strike as u8, "{name}");
            assert_eq!((o.hand.count(id("Bash")), o.free_in_hand.count(id("Bash"))), (1, 1), "{name}");
            assert_eq!(zeroed(o).len(), 1, "{name}");
        }
        let mut t = s.clone();
        t.resolve_chance(&mut Rng::new(3));
        assert_eq!((t.pending, zeroed(&t).len(), t.hand.len()), (None, 1, 5), "{name}");
    }
}

#[test]
fn madness_falls_back_to_marked_cards_and_clears_the_mark() {
    // No card costs above 0 this turn: a card with cost > 0 (marked free)
    // gets cost 0, its mark gone (costForTurn was 0 already).
    for name in ["Madness", "Madness+"] {
        let (mut s, c) = setup(name, &["Bash", "Strike", "Anger"]);
        assert!(s.mark_free_in_hand(id("Bash")));
        assert!(s.mark_free_in_hand(id("Strike")));
        start(&mut s, c);
        assert_eq!(s.pending, Some(ChanceEvent::RandomZeroCost), "{name}");
        let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(10) else { panic!("listed") };
        assert_eq!(v.len(), 2, "{name}");
        for (p, o) in &v {
            assert!((p - 0.5).abs() < 1e-9, "{name} {p}");
            assert_eq!((o.hand.len(), o.free_in_hand.len(), zeroed(o).len()), (3, 1, 1), "{name}");
            let kept = if o.hand.count(id("Bash")) == 1 { "Bash" } else { "Strike" };
            assert_eq!(o.free_in_hand.count(id(kept)), 1, "{name}");
        }
        // One marked card: no roll.
        let (mut s, c) = setup(name, &["Bash", "Anger"]);
        assert!(s.mark_free_in_hand(id("Bash")));
        start(&mut s, c);
        assert_eq!((s.pending, s.hand.count(id("Bash")), s.free_in_hand.len(), zeroed(&s).len()), (None, 0, 0, 1), "{name}");
    }
}

// Step 3: random cards made (MakeRandom) with Chrysalis, Metamorphosis
// (`cards/colorless/*.java`: n rolls of `returnTrulyRandomCardInCombat(type)`,
// cost set to 0 when above 0, `MakeTempCardInDrawPileAction` at a random
// spot: `CardGroup.addToRandomSpot`, `random(size - 1)`, never the top)
// and Transmutation (`TransmutationAction`: X rolls of
// `returnTrulyRandomColorlessCardInCombat`, upgraded when it is,
// `setCostForTurn(0)`, `MakeTempCardInHandAction`).

fn bare(s: &CombatState, c: CardId) -> String {
    let n = s.binding.def(c).name.trim_start_matches("gen:");
    n.split('{').next().unwrap().trim_end_matches('+').to_string()
}

#[test]
fn step3_card_stats() {
    load();
    // (name, cost, X): no upgrade changes cost or keywords; all exhaust.
    for (name, cost, x) in [
        ("Chrysalis", 2, false),
        ("Chrysalis+", 2, false),
        ("Metamorphosis", 2, false),
        ("Metamorphosis+", 2, false),
        ("Transmutation", 0, true),
        ("Transmutation+", 0, true),
    ] {
        let (ids, b) = bind(&[format!("gen:{name}").as_str()]).unwrap();
        let d = b.def(ids[0]);
        assert_eq!((d.cost(), d.x_cost(), d.ty, d.exhaust, d.innate, d.ethereal, d.retain), (cost, x, CardType::Skill, true, false, false, false), "{name}");
    }
}

#[test]
fn chrysalis_and_metamorphosis_shuffle_n_zero_cost_cards_of_a_type_into_the_draw_pile() {
    let ironclad: BTreeSet<String> = pool_names(IRONCLAD, "Ironclad").into_iter().collect();
    for (name, ty, n) in [
        ("Chrysalis", CardType::Skill, 3usize),
        ("Chrysalis+", CardType::Skill, 5),
        ("Metamorphosis", CardType::Attack, 3),
        ("Metamorphosis+", CardType::Attack, 5),
    ] {
        let mut seen = BTreeSet::new();
        let mut repeat = false;
        for seed in 0..80 {
            let (mut s, c) = setup4(name, &[]);
            s.step(Action::Play { card: c, target: None }, &mut Rng::new(seed)).unwrap();
            assert_eq!(s.stage, Stage::PlayerTurn, "{name}");
            assert_eq!((s.hand.len(), s.draw().len(), s.exhaust().count(c), s.player.energy), (0, n, 1, 1), "{name}");
            // The first into the empty pile is just its card; each later
            // one goes under the top card.
            assert_eq!(s.top.n_known(), 0, "{name}");
            assert_eq!(s.top.floaters().map(|(_, above)| above).collect::<Vec<_>>(), vec![1; n - 1], "{name}");
            repeat |= s.draw().iter().any(|(_, k)| k > 1);
            for (x, _) in s.draw().iter() {
                let d = s.binding.def(x);
                let nm = bare(&s, x);
                assert!(ironclad.contains(&nm), "{name}: {nm}");
                assert_eq!((d.ty, d.level), (ty, 0), "{name}: {nm}");
                // Cost 0 for the combat when above 0; X stays X (Whirlwind).
                let base = registry::copy_of(x).map_or(x, |(b, _)| b);
                assert_eq!(registry::copy_of(x).is_some(), s.binding.def(base).cost() > 0, "{name}: {nm}");
                assert_eq!((d.cost(), d.x_cost()), (0, s.binding.def(base).x_cost()), "{name}: {nm}");
                seen.insert(nm);
            }
        }
        assert!(repeat, "{name}: independent rolls repeat");
        assert!(seen.len() >= 10, "{name}: {seen:?}");
    }
}

#[test]
fn make_random_is_one_chance_event_per_roll_over_the_typed_pool() {
    let (mut s, c) = setup4("Chrysalis", &[]);
    s.apply_action(Action::Play { card: c, target: None }).unwrap();
    let skills = registry_pool_len(&s, CardType::Skill);
    for roll in 0..3 {
        assert!(matches!(s.pending, Some(chance::ChanceEvent::MakeRandom { .. })), "roll {roll}");
        let Some(chance::ChanceOutcomes::Listed(v)) = s.chance_outcomes(1000) else { panic!("listed") };
        assert_eq!(v.len(), skills, "roll {roll}: one outcome per Ironclad Skill");
        assert!(v.iter().all(|(p, _)| (p - 1.0 / skills as f64).abs() < 1e-12));
        s = v[0].1.clone();
    }
    assert_eq!((s.pending, s.draw().len()), (None, 3));
}

/// Ironclad pool cards of type `ty`, as the pack writes the pool.
fn registry_pool_len(s: &CombatState, ty: CardType) -> usize {
    let _ = s;
    pool_names(IRONCLAD, "Ironclad").iter().filter(|n| {
        let (ids, b) = bind(&[n.as_str()]).or_else(|_| bind(&[gen(n).as_str()])).unwrap();
        b.def(ids[0]).ty == ty
    }).count()
}

#[test]
fn chrysalis_goes_under_a_known_top() {
    // addToRandomSpot: never the top, so a known top stays the next draw.
    let (mut s, c) = setup4("Chrysalis", &[]);
    s.set_draw(pile(&["Bash", "Strike"]));
    s.top = sts_engine::state::Top::from_parts(&[id("Bash")], &[]).unwrap();
    s.step(Action::Play { card: c, target: None }, &mut Rng::new(2)).unwrap();
    assert_eq!(s.draw().len(), 5);
    assert_eq!(known(&s), vec![id("Bash")]);
    let floaters: Vec<(CardId, u8)> = s.top.floaters().collect();
    assert_eq!(floaters.len(), 3);
    assert!(floaters.iter().all(|&(_, above)| above == 1), "{floaters:?}");
    for seed in 0..20 {
        let mut t = s.clone();
        t.pending = Some(chance::ChanceEvent::Draw { n: 1 });
        t.resolve_chance(&mut Rng::new(seed));
        assert_eq!(t.hand.count(id("Bash")), 1);
    }
}

#[test]
fn chrysalis_cards_go_under_an_unknown_top_at_the_games_odds() {
    // addToRandomSpot with nothing known: none of the made cards is the
    // next draw, and every later draw has the game's odds.
    let unknown = [id("Strike"), id("Defend"), id("Bash")];
    let (mut s, c) = setup4("Chrysalis", &[]);
    s.set_draw(Pile::from_cards(&unknown));
    s.apply_action(Action::Play { card: c, target: None }).unwrap();
    let mut ops = Vec::new();
    for roll in 0..3 {
        let Some(chance::ChanceOutcomes::Listed(v)) = s.chance_outcomes(1000) else { panic!("listed") };
        // Two different cards and a repeat.
        let next = v[[3, 7, 3][roll] % v.len()].1.clone();
        let made = next.draw().iter().find(|&(x, k)| k > s.draw().count(x)).expect("one card made").0;
        ops.push(common::PileOp::RandomSpot(made));
        s = next;
    }
    assert_eq!((s.pending, s.draw().len()), (None, 6));
    assert!(s.top.floaters().all(|(_, above)| above == 1));
    assert!(common::engine_draw_odds(&s, 1).iter().all(|(h, _)| h.iter().all(|x| unknown.contains(x))));
    common::assert_draw_odds_match(&s, &[], &unknown, &ops);
}

#[test]
fn transmutation_adds_x_free_colorless_cards_upgraded_when_it_is() {
    let pool = colorless_names();
    for (name, up) in [("Transmutation", false), ("Transmutation+", true)] {
        let mut seen = BTreeSet::new();
        for seed in 0..60 {
            let (mut s, c) = setup(name, &[]);
            s.step(Action::Play { card: c, target: None }, &mut Rng::new(seed)).unwrap();
            assert_eq!(s.stage, Stage::PlayerTurn, "{name}");
            assert_eq!((s.hand.len(), s.player.energy, s.exhaust().count(c)), (3, 0, 1), "{name}: X = 3");
            for (x, k) in s.hand.iter() {
                let d = s.binding.def(x);
                let nm = bare(&s, x);
                assert!(pool.contains(&nm), "{name}: {nm}");
                assert_eq!(d.level, up as u8, "{name}: {nm}");
                // setCostForTurn(0): this turn only, the card's cost kept.
                assert_eq!(s.free_in_hand.count(x), if d.cost() > 0 { k } else { 0 }, "{name}: {nm}");
                seen.insert(nm);
            }
        }
        assert!(seen.len() >= 10, "{name}: {seen:?}");
    }
    // No energy: X is 0, nothing made.
    let (mut s, c) = setup("Transmutation", &[]);
    s.player.energy = 0;
    play(&mut s, c);
    assert_eq!((s.hand.len(), s.pending), (0, None));
}

#[test]
fn transmutation_past_the_hand_limit_goes_to_the_discard_pile_unmarked() {
    let hand = ["Strike"; 9];
    let (mut s, c) = setup("Transmutation", &hand);
    play(&mut s, c);
    // MakeTempCardInHandAction: the first fills the hand, the rest go to
    // the discard pile; only the hand's copy costs 0 this turn.
    assert_eq!((s.hand.len(), s.discard().len()), (10, 2));
    let (made, _) = s.hand.iter().find(|&(x, _)| x != id("Strike")).expect("one made card in hand");
    let marked: usize = s.hand.iter().map(|(x, _)| s.free_in_hand.count(x) as usize).sum();
    assert_eq!(marked, (s.binding.def(made).cost() > 0) as usize);
}

#[test]
fn deep_breath_fires_the_shuffle_relics() {
    // DeepBreath.use: EmptyDeckShuffleAction (`onShuffle`: The Abacus's 6
    // block) only with a non-empty discard; its draw of 1 then finds the
    // draw pile full (docs/specs/blocked-relics.md step 3).
    for (discard, block) in [(0, 0), (2, 6)] {
        load();
        let relics = relics_named(&["gen:The Abacus"]).unwrap();
        let (ids, b) = bind(&["gen:Deep Breath", "Defend", "Defend", "Defend", "Defend", "Defend"]).unwrap();
        let mut s = CombatState::new_bound_with(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &relics, &mut Rng::new(1));
        let c = ids[0];
        s.hand = Hand::from_cards(&[c]);
        s.set_draw(pile(&["Defend"]));
        s.set_discard(pile(&vec!["Strike"; discard]));
        s.player.block = 0;
        play(&mut s, c);
        assert_eq!(s.player.block, block, "discard pile {discard}");
        assert_eq!(s.hand.len(), 1);
    }
}

// Build A of docs/research/build-plans-2026-11-14/colorless-powers.md:
// Magnetism (`cards/colorless/Magnetism.java`: cost 2, Power, rare,
// `ApplyPowerAction(MagnetismPower(p, 1), 1)`, upgrade cost 1;
// `powers/MagnetismPower.java` `atStartOfTurn`: `amount` times
// `MakeTempCardInHandAction(returnTrulyRandomColorlessCardInCombat())`,
// queued before the turn's draw).

/// The loaded Colorless pool's index.
fn colorless_pool() -> u8 {
    (0..=254u8).find(|&i| registry::pool_def(i).is_some_and(|p| p.name == "Colorless")).expect("Colorless pool loaded")
}

/// Ends the turn and resolves chance events up to the next Colorless
/// `MakeRandom` roll; returns false when the turn settled without one.
fn to_next_colorless_roll(s: &mut CombatState, rng: &mut Rng) -> bool {
    let pool = colorless_pool();
    loop {
        match s.pending {
            Some(chance::ChanceEvent::MakeRandom { pool: p, .. }) if p == pool => return true,
            Some(_) => s.resolve_chance(rng),
            None => return false,
        }
    }
}

#[test]
fn magnetism_card_stats() {
    load();
    // (name, cost): a Power with no keywords; the upgrade only lowers the cost.
    for (name, cost) in [("Magnetism", 2), ("Magnetism+", 1)] {
        let (ids, b) = bind(&[gen(name).as_str()]).unwrap();
        let d = b.def(ids[0]);
        assert_eq!((d.cost(), d.ty, d.exhaust, d.targeted(), d.x_cost()), (cost, CardType::Power, false, false, false), "{name}");
        assert!(!d.ethereal && !d.innate && !d.retain, "{name}");
    }
}

/// A1, A2: each stack makes one random colorless card in hand at turn
/// start, rolled before the turn's draw.
#[test]
fn magnetism_adds_a_colorless_card_to_hand_before_the_draw() {
    for (copies, energy) in [(1usize, 3), (2, 4)] {
        let mut deck = vec!["Magnetism"; copies];
        deck.extend(["Defend"; 9]);
        let (mut s, ids) = combat2(&deck, &(0..copies).collect::<Vec<_>>());
        s.player.energy = energy;
        for &c in &ids[..copies] {
            play2(&mut s, c);
        }
        let b = s.binding.clone();
        let mag = b.powers_in_play().iter().copied().find(|&p| b.power_id(p) == Some("Magnetism")).expect("Magnetism bound");
        assert_eq!(s.player.powers.get(mag), copies as i16, "{copies}: one stack per card");
        let mut rng = Rng::new(9);
        s.apply_action(Action::EndTurn).unwrap();
        for roll in 0..copies {
            assert!(to_next_colorless_roll(&mut s, &mut rng), "{copies}: roll {roll}");
            assert_eq!((s.draw().len(), s.hand.len()), (9, roll), "{copies}: roll {roll} comes before the draw");
            s.resolve_chance(&mut rng);
        }
        assert!(!to_next_colorless_roll(&mut s, &mut rng), "{copies}: no more rolls");
        assert_eq!(s.stage, Stage::PlayerTurn);
        assert_eq!((s.hand.len(), s.draw().len()), (copies + 5, 4), "{copies}: made, then 5 drawn");
        let pool = colorless_names();
        let made: Vec<String> = s.hand.iter().filter(|&(x, _)| x != id("Defend")).map(|(x, _)| bare(&s, x)).collect();
        assert!(made.iter().all(|n| pool.contains(n)), "{copies}: {made:?}");
    }
}

// Build B of the same plan: Mayhem (`cards/colorless/Mayhem.java`: cost 2,
// Power, rare, `ApplyPowerAction(MayhemPower(p, 1), 1)`, upgrade cost 1;
// `powers/MayhemPower.java` `atStartOfTurn`: `amount` times
// `addToBot(PlayTopCardAction(random monster, false))`). The take is queued
// at the bottom, so it comes after the turn's draw and the post-draw hooks
// but before the work the draw's triggers queue (Evolve).

/// A Mayhem game: `stacks` Mayhem cards and `more` cards played on turn 1
/// (energy for all), then the piles set as `draw` (the first `known` cards
/// of it a known top, in order) and `discard` before End Turn. Returns the
/// state at turn 1's end.
fn mayhem_game(stacks: usize, more: &[&str], draw: &[&str], known: &[&str], discard: &[&str]) -> CombatState {
    let mut deck: Vec<&str> = vec!["Mayhem"; stacks];
    deck.extend_from_slice(more);
    let n_hand = deck.len();
    deck.extend_from_slice(draw);
    deck.extend_from_slice(discard);
    let (mut s, ids) = combat2(&deck, &(0..n_hand).collect::<Vec<_>>());
    s.top = Default::default();
    s.player.energy = 2 * stacks as i16 + 8;
    for &c in &ids[..n_hand] {
        play2(&mut s, c);
    }
    let named = |names: &[&str], from: usize| -> Vec<CardId> { names.iter().enumerate().map(|(i, _)| ids[from + i]).collect() };
    s.set_draw(Pile::from_cards(&named(draw, n_hand)));
    s.set_discard(Pile::from_cards(&named(discard, n_hand + draw.len())));
    if !known.is_empty() {
        s.top = sts_engine::state::Top::from_parts(&named(known, n_hand), &[]).unwrap();
    }
    s
}

/// End Turn and every chance event after it, up to the next decision.
fn end_turn_through(s: &mut CombatState) {
    let mut rng = Rng::new(9);
    s.apply_action(Action::EndTurn).unwrap();
    while s.pending.is_some() {
        s.resolve_chance(&mut rng);
    }
}

#[test]
fn mayhem_card_stats() {
    load();
    for (name, cost) in [("Mayhem", 2), ("Mayhem+", 1)] {
        let (ids, b) = bind(&[gen(name).as_str()]).unwrap();
        let d = b.def(ids[0]);
        assert_eq!((d.cost(), d.ty, d.exhaust, d.targeted(), d.x_cost()), (cost, CardType::Power, false, false, false), "{name}");
        assert!(!d.ethereal && !d.innate && !d.retain, "{name}");
    }
}

/// B1: the take comes after the draw and plays free at the monster.
#[test]
fn mayhem_plays_the_top_card_after_the_draw() {
    let mut s = mayhem_game(1, &[], &["Strike"; 10], &[], &[]);
    end_turn_through(&mut s);
    assert_eq!(s.stage, Stage::PlayerTurn);
    assert_eq!((s.monsters[0].hp, s.player.energy, s.cards_played_this_turn), (94, 3, 1));
    assert_eq!((s.hand.len(), s.draw().len(), s.discard().count(id("Strike"))), (5, 4, 1));
}

/// B2: the draw empties the pile; the take reshuffles the discard pile.
#[test]
fn mayhem_reshuffles_when_the_draw_empties_the_pile() {
    let mut s = mayhem_game(1, &[], &["Strike"; 5], &[], &["Defend"]);
    end_turn_through(&mut s);
    assert_eq!((s.player.block, s.cards_played_this_turn), (5, 1));
    assert_eq!((s.hand.len(), s.hand.count(id("Strike")), s.draw().len(), s.discard().count(id("Defend"))), (5, 5, 0, 1));
}

/// B3: after the post-draw hooks: Demon Form's Strength comes first.
#[test]
fn mayhem_plays_after_the_post_draw_hooks() {
    let mut s = mayhem_game(1, &["Demon Form"], &["Strike"; 10], &[], &[]);
    assert_eq!(s.player.powers.get(Power::Strength), 0, "none on turn 1");
    end_turn_through(&mut s);
    assert_eq!(s.player.powers.get(Power::Strength), 2);
    assert_eq!(s.monsters[0].hp, 100 - 6 - 2, "Strike 6 + Strength 2");
}

/// B4: two stacks take both cards before either plays.
#[test]
fn mayhem_stacks_take_all_cards_before_any_plays() {
    let mut draw = vec!["Defend"; 5];
    draw.extend(["Flash of Steel", "Strike", "Bash"]);
    let mut s = mayhem_game(2, &[], &draw, &draw[..7], &[]);
    end_turn_through(&mut s);
    assert_eq!((s.monsters[0].hp, s.cards_played_this_turn, s.player.energy), (100 - 3 - 6, 2, 3));
    assert_eq!((s.hand.len(), s.hand.count(id("Bash")), s.draw().len()), (6, 1, 0));
}

/// B5: Magnetism's card is made before the draw; the top card plays after.
#[test]
fn mayhem_and_magnetism() {
    let mut s = mayhem_game(1, &["Magnetism"], &["Strike"; 10], &[], &[]);
    let mut rng = Rng::new(9);
    s.apply_action(Action::EndTurn).unwrap();
    assert!(to_next_colorless_roll(&mut s, &mut rng));
    assert_eq!((s.draw().len(), s.hand.len(), s.cards_played_this_turn), (10, 0, 0));
    while s.pending.is_some() {
        s.resolve_chance(&mut rng);
    }
    assert_eq!((s.hand.len(), s.hand.count(id("Strike")), s.draw().len(), s.cards_played_this_turn, s.monsters[0].hp), (6, 5, 4, 1, 94));
}

/// B6: nothing to take.
#[test]
fn mayhem_with_both_piles_empty_does_nothing() {
    let mut s = mayhem_game(1, &[], &[], &[], &[]);
    end_turn_through(&mut s);
    assert_eq!((s.stage, s.pending, s.cards_played_this_turn, s.hand.len()), (Stage::PlayerTurn, None, 0, 0));
    assert!(s.owed_late.is_empty());
}

/// B7: a take needs a turn that stays open.
#[test]
fn a_hook_that_plays_the_top_card_must_leave_the_turn_open() {
    load();
    for (i, trigger) in ["OwnerTurnEnd", "RoundEnd", "OwnerDied", "CombatWon", "OwnerUsedPotion"].into_iter().enumerate() {
        let text = format!(
            r#"{{"version": 2, "powers": [{{"id": "pl-top{i}", "hooks": [{{"trigger": "{trigger}", "condition": "Always", "effects": [{{"PlayTop": {{"n": 1, "exhaust": false}}}}]}}]}}]}}"#
        );
        let err = load_pack(&text).unwrap_err();
        assert!(err.contains("PlayTop"), "{trigger}: {err}");
    }
}

/// A relic's hook may play the top card too (after the turn start
/// settles), and is refused in a turn-end hook like a power's.
#[test]
fn a_relic_hook_plays_the_top_card_after_the_draw() {
    load();
    load_pack(r#"{"version": 2, "relics": [{"id": "pl-top-relic", "rarity": "common", "hooks": [{"trigger": "OwnerTurnStartPostDraw", "condition": "Always", "effects": [{"PlayTop": {"n": 1, "exhaust": false}}]}]}]}"#).unwrap();
    let err = load_pack(r#"{"version": 2, "relics": [{"id": "pl-top-relic-end", "rarity": "common", "hooks": [{"trigger": "OwnerTurnEnd", "condition": "Always", "effects": [{"PlayTop": {"n": 1, "exhaust": false}}]}]}]}"#).unwrap_err();
    assert!(err.contains("PlayTop"), "{err}");
    let (ids, b) = bind(&["Strike"; 10]).unwrap();
    let relics = relics_named(&["gen:pl-top-relic"]).unwrap();
    let mut rng = Rng::new(3);
    let mut s = CombatState::new_with(Character::Ironclad, &ids, &b, 80, 80, &[sts_engine::monsters::MonsterKind::JawWorm], sts_engine::monsters::EncounterGroup::Hallway, &relics, &mut rng);
    while s.pending.is_some() {
        s.resolve_chance(&mut rng);
    }
    let hp = s.monsters[0].max_hp;
    assert_eq!((hp - s.monsters[0].hp, s.cards_played_this_turn, s.player.energy), (6, 1, 3), "Strike played free");
    assert_eq!((s.hand.len(), s.draw().len(), s.discard().len()), (5, 4, 1));
}

/// B9: the take comes before the work the turn's draw triggers (Evolve).
#[test]
fn mayhem_takes_before_evolve_draws() {
    let draw = ["Wound", "Bash", "Bash", "Bash", "Bash", "Strike", "Defend"];
    let mut s = mayhem_game(1, &["Evolve"], &draw, &draw, &[]);
    end_turn_through(&mut s);
    assert_eq!((s.monsters[0].hp, s.cards_played_this_turn), (94, 1), "Strike played");
    assert_eq!((s.hand.len(), s.hand.count(id("Defend")), s.draw().len()), (6, 1, 0), "Evolve drew Defend");
}

// Build A of docs/research/build-plans-2026-11-14/colorless-piles.md:
// Enlightenment and the turn cost marks (`CombatState::turn_costs`), the
// game's `EnlightenmentAction` and `updateCost` read in desktop-1.0.jar.

/// The one card in hand whose definition is named `prefix` or is a changed
/// copy of it (`prefix{cost=..}`).
fn held(s: &CombatState, prefix: &str) -> CardId {
    let found: Vec<CardId> = s.hand.iter().map(|(c, _)| c).filter(|&c| s.binding.def(c).name.starts_with(prefix)).collect();
    assert_eq!(found.len(), 1, "{prefix}: {found:?}");
    found[0]
}

/// A1: Enlightenment: cards costing 2 or more cost 1 this turn; a cost of
/// 1, X and unplayable stay; plays spend the marked cost; End Turn clears.
#[test]
fn enlightenment_caps_the_hand_this_turn() {
    let (mut s, enl) = setup("Enlightenment", &["Bash", "Carnage", "Strike", "Whirlwind", "Burn"]);
    let (bash, carnage, strike, whirl, burn) = (id("Bash"), id("Carnage"), id("Strike"), id("Whirlwind"), id("Burn"));
    play(&mut s, enl);
    assert_eq!([bash, carnage, strike].map(|c| s.cost_of(c)), [1, 1, 1]);
    assert_eq!((s.cost_of(whirl), s.cost_of(burn), s.turn_costs.count(whirl) + s.turn_costs.count(burn)), (0, 0, 0), "X-cost and unplayable never qualify");
    assert_eq!(s.turn_costs.len(), 2, "Bash and Carnage only");
    assert!(s.free_in_hand.is_empty());
    play(&mut s, bash);
    play(&mut s, carnage);
    assert_eq!(s.player.energy, 1);
    s.step(Action::EndTurn, &mut Rng::new(5)).unwrap();
    assert!(s.turn_costs.is_empty());
}

/// A2: Enlightenment+ also lowers the cost for the combat: the copy keeps
/// costing 1 in the discard pile and when drawn again.
#[test]
fn enlightenment_plus_lowers_the_combat_cost() {
    let (mut s, enl) = setup("Enlightenment+", &["Bash", "Carnage", "Strike", "Whirlwind", "Burn"]);
    play(&mut s, enl);
    let bash = held(&s, "Bash");
    assert_ne!(bash, id("Bash"), "the changed copy");
    assert_eq!(sts_engine::registry::copy_of(bash).map(|(b, _)| b), Some(id("Bash")));
    assert_eq!((s.binding.def(bash).cost(), s.cost_of(bash)), (1, 1));
    assert!(s.turn_costs.is_empty(), "a mark that no longer lowers the cost goes");
    assert_eq!(s.hand.count(id("Whirlwind")) + s.hand.count(id("Burn")), 2, "X-cost and unplayable keep their cards");
    s.step(Action::EndTurn, &mut Rng::new(5)).unwrap();
    let copies: u8 = [s.hand.view(), s.draw(), s.discard()].into_iter().map(|p| p.count(bash)).sum();
    assert_eq!(copies, 1, "still the cost-1 copy after the turn");
    assert_eq!(s.cost_of(bash), 1);
}

/// A3: a copy marked 0 keeps its mark under Enlightenment+: it costs 0 this
/// turn and 1 for the combat.
#[test]
fn enlightenment_plus_keeps_a_zero_mark() {
    let (mut s, enl) = setup("Enlightenment+", &["Bash"]);
    assert!(s.mark_free_in_hand(id("Bash")));
    play(&mut s, enl);
    let bash = held(&s, "Bash");
    assert_eq!((s.binding.def(bash).cost(), s.cost_of(bash), s.free_in_hand.count(bash)), (1, 0, 1));
    s.player.energy = 0;
    play(&mut s, bash);
    assert_eq!(s.player.energy, 0, "played free");
}

/// A4: Blood for Blood (cost 4) under Enlightenment costs 1; one HP loss
/// takes its combat cost to 3 and this turn's to 0 (the game's `updateCost`
/// keeps the gap: diff 3, `costForTurn` 0).
#[test]
fn enlightenment_then_blood_for_blood_loses_hp() {
    let (mut s, enl) = setup("Enlightenment", &["gen:Blood for Blood", "Bloodletting"]);
    let bfb = held(&s, "gen:Blood for Blood");
    play(&mut s, enl);
    assert_eq!(s.cost_of(bfb), 1);
    play(&mut s, id("Bloodletting"));
    let moved = held(&s, "gen:Blood for Blood");
    assert_ne!(moved, bfb);
    assert_eq!((s.binding.def(moved).cost(), s.cost_of(moved)), (3, 0));
    assert_eq!((s.turn_costs.len(), s.free_in_hand.count(moved)), (0, 1), "at 0 it is a free mark");
}

/// A5: of two Bashes one marked 1, a play takes the cheap one; a discard
/// pick takes the dear one.
#[test]
fn a_play_takes_the_cheapest_copy_and_a_pick_the_dearest() {
    let (mut s, _) = setup("Enlightenment", &[]);
    let (bash, survivor) = (id("Bash"), id("Survivor"));
    s.hand = Hand::from_cards(&[bash, bash]);
    assert!(s.turn_costs.add(bash, 1));
    assert_eq!(s.cost_of(bash), 1);
    play(&mut s, bash);
    assert_eq!((s.player.energy, s.hand.count(bash), s.cost_of(bash), s.turn_costs.len()), (2, 1, 2, 0));
    s.player.energy = 3;
    s.hand = Hand::from_cards(&[bash, bash, survivor]);
    s.turn_costs.add(bash, 1);
    play(&mut s, survivor);
    s.apply_action(Action::Choose(bash)).unwrap();
    assert_eq!((s.hand.count(bash), s.discard().count(bash)), (1, 2), "the played Bash and the picked one");
    assert_eq!((s.cost_of(bash), s.turn_costs.len()), (1, 1), "the kept Bash is the marked one");
}

// Random hand picks roll over copy classes: a card's unmarked copies, its
// copies at each cost this turn, and its copies marked 0 (`HandMark`).

const CLASSES: &str = r#"{"version": 1, "cards": [
{"id": "ClsFree", "cost": 0, "type": "Skill", "effects": ["ZeroCostRandomTurn"]},
{"id": "ClsUp", "cost": 0, "type": "Skill", "effects": ["UpgradeRandom"]},
{"id": "ClsEx", "cost": 0, "type": "Skill", "effects": ["ExhaustRandom"]}
]}"#;

/// `card` and two Bashes in hand, one of them at cost 1 this turn; the
/// card is played with its chance event left pending.
fn two_classes(card: &str, mark: bool) -> CombatState {
    load_pack(CLASSES).unwrap();
    let (mut s, c) = setup(card, &["Bash"]);
    let bash = id("Bash");
    s.hand = Hand::from_cards(&[c, bash, bash]);
    if mark {
        assert!(s.turn_costs.add(bash, 1));
    }
    s.apply_action(Action::Play { card: c, target: None }).unwrap();
    s
}

fn outcomes_of(s: &CombatState) -> Vec<(f64, CombatState)> {
    let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(10) else { panic!("listed") };
    v
}

/// (free marks, cost-this-turn marks) of each outcome, with its weight.
fn marks(v: &[(f64, CombatState)]) -> Vec<(u8, u8, u8)> {
    let mut out: Vec<(u8, u8, u8)> = v.iter().map(|(p, t)| ((p * 100.0).round() as u8, t.free_in_hand.len() as u8, t.turn_costs.len() as u8)).collect();
    out.sort();
    out
}

#[test]
fn random_zero_cost_rolls_over_copy_classes() {
    let s = two_classes("Madness", true);
    assert_eq!(s.pending, Some(ChanceEvent::RandomZeroCost));
    let v = outcomes_of(&s);
    // The unmarked copy goes (the mark stays), or the marked one (it goes).
    assert_eq!(marks(&v), [(50, 0, 0), (50, 0, 1)]);
    for (_, t) in &v {
        assert_eq!(t.hand.len(), 2);
    }
    // One class: no pause.
    for mark in [false] {
        assert_eq!(two_classes("Madness", mark).pending, None);
    }
}

#[test]
fn random_free_turn_rolls_over_copy_classes() {
    let s = two_classes("ClsFree", true);
    assert_eq!(s.pending, Some(ChanceEvent::RandomFreeTurn));
    let v = outcomes_of(&s);
    // The unmarked copy is freed (the cost-1 mark stays), or the marked one
    // is (its mark is replaced).
    assert_eq!(marks(&v), [(50, 1, 0), (50, 1, 1)]);
    assert_eq!(two_classes("ClsFree", false).pending, None);
}

#[test]
fn random_upgrade_rolls_over_copy_classes() {
    let s = two_classes("ClsUp", true);
    assert_eq!(s.pending, Some(ChanceEvent::RandomUpgrade));
    let v = outcomes_of(&s);
    assert_eq!(marks(&v), [(50, 0, 1), (50, 0, 1)]);
    let (bash, up) = (id("Bash"), id("Bash+"));
    let mut which: Vec<CardId> = v.iter().map(|(_, t)| t.turn_costs.iter().next().unwrap().0).collect();
    which.sort();
    assert_eq!(which, [bash, up], "the upgraded copy keeps its cost this turn, or the plain one does");
    assert_eq!(two_classes("ClsUp", false).pending, None);
}

#[test]
fn random_exhaust_rolls_over_copy_classes() {
    let s = two_classes("ClsEx", true);
    assert_eq!(s.pending, Some(ChanceEvent::RandomExhaust));
    let v = outcomes_of(&s);
    assert_eq!(marks(&v), [(50, 0, 0), (50, 0, 1)]);
    assert_eq!(two_classes("ClsEx", false).pending, None);
}

/// Dual Wield copies a card whose every copy is at a cost this turn: the
/// copy carries the mark (the game's copy keeps `costForTurn`).
#[test]
fn dual_wield_copies_a_cost_this_turn_mark() {
    let (mut s, dw) = setup("Dual Wield", &["Bash"]);
    let bash = id("Bash");
    s.hand = Hand::from_cards(&[dw, bash, bash]);
    assert!(s.turn_costs.add(bash, 1));
    assert!(s.turn_costs.add(bash, 1));
    play(&mut s, dw);
    if s.pick().is_some() {
        s.apply_action(Action::Choose(bash)).unwrap();
    }
    assert_eq!((s.hand.count(bash), s.turn_costs.count(bash), s.cost_of(bash)), (3, 3, 1));
    // A mix of marked and unmarked copies: the copy is unmarked, as before.
    let (mut s, dw) = setup("Dual Wield", &["Bash"]);
    s.hand = Hand::from_cards(&[dw, bash, bash]);
    assert!(s.turn_costs.add(bash, 1));
    play(&mut s, dw);
    if s.pick().is_some() {
        s.apply_action(Action::Choose(bash)).unwrap();
    }
    assert_eq!((s.hand.count(bash), s.turn_costs.count(bash)), (3, 1));
}
