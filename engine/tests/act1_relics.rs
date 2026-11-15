//! The Act 1 relics written as pack data (`content/packs/act1-relics.json`,
//! docs/specs/relics.md step 5): each relic's effect at the first decision
//! and on turn 2, as `docs/research/act1-relics-potions.md` rows say, and
//! the two open checks run first (a hook's draw in the monsters' turn; the
//! turn-1 hooks land after the opening draw).

use sts_engine::monsters::EncounterGroup;
use sts_engine::registry::{bind, bind_power, load_pack, pack_relic_names, relic, relics_named};
use sts_engine::cards::CardType;
use sts_engine::relics::Rarity;
use sts_engine::*;

mod common;

const PACK: &str = include_str!("../../content/packs/act1-relics.json");

fn deck(extra: &[&str]) -> Vec<String> {
    let mut d: Vec<String> = starter_deck().iter().map(|&c| c.def().name.to_string()).collect();
    d.extend(extra.iter().map(|s| s.to_string()));
    d
}

/// A fight with these relics (pack relics by their game name, `gen:` added).
fn fight_with(enc: Encounter, cards: &[String], hp: i16, relics: &[&str], seed: u64) -> CombatState {
    load_pack(PACK).unwrap();
    let names: Vec<String> = relics.iter().map(|r| format!("gen:{r}")).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    let card_refs: Vec<&str> = cards.iter().map(String::as_str).collect();
    let (ids, b) = bind(&card_refs).unwrap();
    CombatState::new_bound_with(Character::Ironclad, &ids, &b, hp, 80, enc, &relics_named(&refs).unwrap(), &mut Rng::new(seed))
}

fn fight(enc: Encounter, relics: &[&str]) -> CombatState {
    fight_with(enc, &deck(&[]), 50, relics, 11)
}

/// Ends the turn with nothing played: the monsters act, then turn 2 starts.
fn next_turn(s: &mut CombatState) {
    let mut rng = Rng::new(12);
    s.step(Action::EndTurn, &mut rng).unwrap();
    s.advance(&mut rng);
    assert!(!s.is_over());
    assert_eq!(s.stage, Stage::PlayerTurn);
}

fn gen_power(s: &CombatState, id: &str) -> Power {
    let (b, p) = bind_power(&s.binding, id).unwrap();
    assert!(b == s.binding, "{id} is bound in the fight");
    p
}

/// Plays `name` from hand (put there if it isn't) at monster 0 with block 0.
fn play(s: &mut CombatState, name: &str) {
    let c = CardId::from_name(name).unwrap();
    if s.hand.count(c) == 0 {
        s.hand.add(c, 1);
    }
    s.player.energy = s.player.energy.max(3);
    s.monsters[0].block = 0;
    let target = if c.def().targeted() { Some(0) } else { None };
    s.step(Action::Play { card: c, target }, &mut Rng::new(13)).unwrap();
}

fn strike_damage(mut s: CombatState) -> i16 {
    let before = s.monsters[0].hp;
    play(&mut s, "Strike");
    before - s.monsters[0].hp
}

#[test]
fn open_check_a_hook_draws_in_the_monsters_turn() {
    // Jaw Worm's first move is Chomp (11): the player loses HP in the
    // monsters' turn, and the draw lands then; turn 2's 5 come on top.
    let mut plain = fight(Encounter::JawWorm, &[]);
    next_turn(&mut plain);
    assert_eq!(plain.player.hp, 39);
    assert_eq!(plain.hand.len(), 5);
    // Centennial Puzzle's counter is the game's `usedThisCombat`
    // (relics/CentennialPuzzle.java `wasHPLost`).
    let mut s = fight(Encounter::JawWorm, &["Centennial Puzzle"]);
    assert_eq!(s.player.relics.counter(0), 0);
    next_turn(&mut s);
    assert_eq!(s.player.hp, 39);
    assert_eq!(s.hand.len(), 8, "3 drawn in the monsters' turn, then 5");
    assert_eq!(s.player.relics.counter(0), 1, "only the first HP loss");
    let mut s = fight(Encounter::JawWorm, &["Runic Cube"]);
    next_turn(&mut s);
    assert_eq!(s.hand.len(), 6);
}

#[test]
fn open_check_turn_one_hooks_after_the_opening_draw() {
    let s = fight(Encounter::JawWorm, &["Bag of Preparation"]);
    assert_eq!(s.hand.len(), 7, "the opening 5 and 2 more");
    assert_eq!(s.draw().len(), 3);
    let wound = CardId::from_name("Wound").unwrap();
    let s = fight(Encounter::JawWorm, &["Mark of Pain"]);
    assert_eq!(s.hand.len(), 5);
    assert_eq!(s.hand.count(wound), 0, "the Wounds miss the opening hand");
    assert_eq!(s.draw().count(wound), 2);
    assert_eq!(s.draw().len(), 7);
}

#[test]
fn mark_of_pain_wounds_go_under_the_top_card() {
    // MarkOfPain.atBattleStart: MakeTempCardInDrawPileAction(Wound, 2,
    // randomSpot true), each copy by CardGroup.addToRandomSpot: neither
    // Wound is the next draw, and every later draw has the game's odds.
    let wound = CardId::from_name("Wound").unwrap();
    let s = fight(Encounter::JawWorm, &["Mark of Pain"]);
    assert_eq!((s.top.n_known(), s.top.floaters().collect::<Vec<_>>()), (0, vec![(wound, 1), (wound, 1)]));
    let mut unknown: Vec<CardId> = s.draw().iter().flat_map(|(c, k)| std::iter::repeat_n(c, k as usize)).filter(|&c| c != wound).collect();
    unknown.sort();
    assert!(common::engine_draw_odds(&s, 1).iter().all(|(h, _)| !h.contains(&wound)));
    common::assert_draw_odds_match(&s, &[], &unknown, &[common::PileOp::RandomSpot(wound), common::PileOp::RandomSpot(wound)]);
}

#[test]
fn every_relic_loads_with_its_rarity() {
    load_pack(PACK).unwrap();
    use Rarity::*;
    let want = [
        ("Vajra", Common),
        ("Oddly Smooth Stone", Common),
        ("Bronze Scales", Common),
        ("Red Skull", Common),
        ("Lantern", Common),
        ("Bag of Preparation", Common),
        ("Ancient Tea Set", Common),
        ("Anchor", Common),
        ("Bag of Marbles", Common),
        ("Centennial Puzzle", Common),
        ("Strike Dummy", Uncommon),
        ("Mercury Hourglass", Uncommon),
        ("Thread and Needle", Rare),
        ("Charon's Ashes", Rare),
        ("Slaver's Collar", Boss),
        ("Philosopher's Stone", Boss),
        ("Mark of Pain", Boss),
        ("Runic Cube", Boss),
        ("Sling of Courage", Shop),
        ("Clockwork Souvenir", Shop),
        ("Brimstone", Shop),
        ("Gremlin Visage", Event),
        ("Sacred Bark", Boss),
        ("Blood Vial", Common),
        ("Happy Flower", Common),
        ("Horn Cleat", Uncommon),
        ("Pantograph", Uncommon),
        ("Self-Forming Clay", Uncommon),
        ("Bird-Faced Urn", Rare),
        ("Captain's Wheel", Rare),
        ("Stone Calendar", Rare),
        ("Incense Burner", Rare),
        ("Kunai", Uncommon),
        ("Shuriken", Uncommon),
        ("Ornamental Fan", Uncommon),
        ("Letter Opener", Uncommon),
        ("Nunchaku", Common),
        ("Ink Bottle", Uncommon),
        ("Akabeko", Common),
        ("Pen Nib", Common),
        ("Orichalcum", Common),
        ("Gremlin Horn", Uncommon),
        ("Ginger", Rare),
        ("Turnip", Rare),
        ("Meat on the Bone", Uncommon),
        ("Gambling Chip", Rare),
        ("Lizard Tail", Rare),
        ("The Boot", Common),
        ("Torii", Rare),
        ("Tungsten Rod", Rare),
        ("Fossilized Helix", Rare),
        ("Art of War", Common),
        ("Pocketwatch", Rare),
        ("Champion Belt", Rare),
        ("Potion Belt", Common),
        ("Snecko Eye", Boss),
        ("Preserved Insect", Common),
        ("Neow's Lament", Event),
        ("Paper Phrog", Uncommon),
        ("Odd Mushroom", Event),
        ("Sundial", Uncommon),
        ("The Abacus", Shop),
        ("Toy Ornithopter", Common),
        ("Magic Flower", Rare),
        ("Orange Pellets", Shop),
    ];
    assert_eq!(want.len(), 65);
    for (name, rarity) in want {
        let r = relic(&format!("gen:{name}")).unwrap_or_else(|| panic!("{name} loaded"));
        assert_eq!(r.rarity, rarity, "{name}");
        assert_eq!(r.win_heal, 0, "{name}");
    }
    let names = pack_relic_names();
    assert_eq!(want.iter().filter(|(n, _)| names.contains(&format!("gen:{n}"))).count(), 65);
    // Black Blood replaces Burning Blood (heal 12 at a won combat's end):
    // the fight's heal starts at the character's 6, so it adds 6.
    let r = relic("gen:Black Blood").unwrap();
    assert_eq!((r.rarity, r.win_heal), (Boss, 6));
    assert_eq!(fight(Encounter::JawWorm, &["Black Blood"]).win_heal, 12);
}

#[test]
fn starting_official_powers() {
    for (name, power, n) in [
        ("Vajra", Power::Strength, 1),
        ("Oddly Smooth Stone", Power::Dexterity, 1),
        ("Bronze Scales", Power::Thorns, 3),
        ("Clockwork Souvenir", Power::Artifact, 1),
        ("Gremlin Visage", Power::Weak, 1),
    ] {
        let s = fight(Encounter::JawWorm, &[name]);
        assert_eq!(s.player.powers.get(power), n, "{name}");
        assert!(!s.has_generated(), "{name}: official powers only, the fight encodes");
        codec::encode(&s);
    }
    // Red Skull: its own hooks, its counter the game's `isActive`
    // (docs/specs/relic-entity.md; what it does: engine/tests/red_skull.rs);
    // the official RedSkull power is no longer used.
    let s = fight(Encounter::JawWorm, &["Red Skull"]);
    assert_eq!(s.player.powers.get(Power::RedSkull), 0);
    assert_eq!(s.player.relics.counter(0), 0, "above half: not active");
    let s = fight_with(Encounter::JawWorm, &deck(&[]), 40, &["Red Skull"], 11);
    assert_eq!(s.player.relics.counter(0), 1, "at half: active");
    // What they do: Vajra's Strike 7, the Stone's Defend 6.
    assert_eq!(strike_damage(fight(Encounter::JawWorm, &["Vajra"])), 7);
    let mut s = fight(Encounter::JawWorm, &["Oddly Smooth Stone"]);
    play(&mut s, "Defend");
    assert_eq!(s.player.block, 6);
    // Gremlin Visage: Weak on turn 1 (Strike 4), gone by turn 2.
    let s = fight(Encounter::Cultist, &["Gremlin Visage"]);
    assert_eq!(strike_damage(s.clone()), 4);
    let mut s2 = s;
    next_turn(&mut s2);
    assert_eq!(s2.player.powers.get(Power::Weak), 0);
    assert_eq!(strike_damage(s2), 6);
    // Bronze Scales: Jaw Worm's Chomp costs it 3.
    let plain = fight(Encounter::JawWorm, &[]);
    let mut s = fight(Encounter::JawWorm, &["Bronze Scales"]);
    let hp0 = s.monsters[0].hp;
    assert_eq!(hp0, plain.monsters[0].hp);
    next_turn(&mut s);
    assert_eq!(s.monsters[0].hp, hp0 - 3);
    // Red Skull: +3 at half HP or less, not above.
    assert_eq!(strike_damage(fight_with(Encounter::JawWorm, &deck(&[]), 40, &["Red Skull"], 11)), 9);
    assert_eq!(strike_damage(fight_with(Encounter::JawWorm, &deck(&[]), 41, &["Red Skull"], 11)), 6);
}

#[test]
fn turn_one_relics() {
    // Lantern: 4 energy, then 3.
    let mut s = fight(Encounter::JawWorm, &["Lantern"]);
    assert_eq!(s.player.energy, 4);
    next_turn(&mut s);
    assert_eq!(s.player.energy, 3);
    // Ancient Tea Set: 5, then 3.
    let mut s = fight(Encounter::JawWorm, &["Ancient Tea Set"]);
    assert_eq!(s.player.energy, 5);
    next_turn(&mut s);
    assert_eq!(s.player.energy, 3);
    // Bag of Preparation: 7 cards, then 5.
    let mut s = fight(Encounter::JawWorm, &["Bag of Preparation"]);
    assert_eq!(s.hand.len(), 7);
    next_turn(&mut s);
    assert_eq!(s.hand.len(), 5);
    // Anchor: 10 block lasts turn 1 (Chomp 11 costs 1 HP), 0 on turn 2.
    let mut s = fight(Encounter::JawWorm, &["Anchor"]);
    assert_eq!(s.player.block, 10);
    next_turn(&mut s);
    assert_eq!(s.player.hp, 49);
    assert_eq!(s.player.block, 0);
    // Bag of Marbles: every enemy Vulnerable on turn 1 (Strike 9).
    let s = fight(Encounter::TwoLouse, &["Bag of Marbles"]);
    for m in s.monsters.iter().filter(|m| m.alive()) {
        assert_eq!(m.powers.get(Power::Vulnerable), 1);
    }
    let mut s2 = fight(Encounter::Cultist, &["Bag of Marbles"]);
    assert_eq!(strike_damage(s2.clone()), 9);
    next_turn(&mut s2);
    assert_eq!(s2.monsters[0].powers.get(Power::Vulnerable), 0);
    assert_eq!(strike_damage(s2), 6);
    // None of their pack powers is left once turn 1 has started.
    for name in ["Lantern", "Ancient Tea Set", "Bag of Preparation", "Anchor", "Bag of Marbles"] {
        let s = fight(Encounter::JawWorm, &[name]);
        assert!(s.player.powers.iter().all(|(p, _)| !Power::GEN.contains(&p)), "{name}");
    }
}

#[test]
fn every_turn_and_triggered_relics() {
    // Mercury Hourglass: 3 to every enemy at each turn start.
    let plain = fight(Encounter::Cultist, &[]);
    let mut s = fight(Encounter::Cultist, &["Mercury Hourglass"]);
    assert_eq!(s.monsters[0].hp, plain.monsters[0].hp - 3);
    next_turn(&mut s);
    assert_eq!(s.monsters[0].hp, plain.monsters[0].hp - 6);
    // Brimstone: the player +2 Strength and every enemy +1, each turn.
    let mut s = fight(Encounter::Cultist, &["Brimstone"]);
    assert_eq!((s.player.powers.get(Power::Strength), s.monsters[0].powers.get(Power::Strength)), (2, 1));
    next_turn(&mut s);
    // The enemy: 2 from Brimstone on top of what the Cultist gains itself.
    assert_eq!(s.player.powers.get(Power::Strength), 4);
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 2 + plain_cultist_strength_turn2());
    // Strike Dummy: Strikes deal 9, other attacks unchanged.
    assert_eq!(strike_damage(fight(Encounter::Cultist, &["Strike Dummy"])), 9);
    let mut s = fight_with(Encounter::Cultist, &deck(&["Pommel Strike"]), 50, &["Strike Dummy"], 11);
    let hp0 = s.monsters[0].hp;
    play(&mut s, "Pommel Strike");
    assert_eq!(hp0 - s.monsters[0].hp, 12, "Pommel Strike is tagged Strike");
    let mut s = fight(Encounter::Cultist, &["Strike Dummy"]);
    let hp0 = s.monsters[0].hp;
    play(&mut s, "Bash");
    assert_eq!(hp0 - s.monsters[0].hp, 8);
    // Charon's Ashes: 3 to every enemy when a card exhausts (Pummel).
    let pummel = |relics: &[&str]| {
        let mut s = fight_with(Encounter::Cultist, &deck(&["Pummel"]), 50, relics, 11);
        let hp0 = s.monsters[0].hp;
        play(&mut s, "Pummel");
        hp0 - s.monsters[0].hp
    };
    assert_eq!(pummel(&["Charon's Ashes"]), pummel(&[]) + 3);
    // Thread and Needle: 4 Plated Armor; 4 block at turn end, so Chomp
    // costs 7, and the unblocked hit takes one stack.
    let mut s = fight(Encounter::JawWorm, &["Thread and Needle"]);
    let plated = gen_power(&s, "PlatedArmor");
    assert_eq!(s.player.powers.get(plated), 4);
    next_turn(&mut s);
    assert_eq!(s.player.hp, 43);
    assert_eq!(s.player.powers.get(plated), 3);
    assert_eq!(s.player.block, 0);
}

fn plain_cultist_strength_turn2() -> i16 {
    let mut s = fight(Encounter::Cultist, &[]);
    next_turn(&mut s);
    s.monsters[0].powers.get(Power::Strength)
}

#[test]
fn energy_relics_and_fight_kinds() {
    // Slaver's Collar: +1 energy each turn in elite and boss fights only.
    let mut s = fight(Encounter::GremlinNob, &["Slaver's Collar"]);
    assert_eq!(s.player.energy, 4);
    next_turn(&mut s);
    assert_eq!(s.player.energy, 4);
    assert_eq!(fight(Encounter::SlimeBoss, &["Slaver's Collar"]).player.energy, 4);
    assert!(fight(Encounter::JawWorm, &["Slaver's Collar"]) == fight(Encounter::JawWorm, &[]));
    // Sling of Courage: 2 Strength in elites only.
    assert_eq!(fight(Encounter::GremlinNob, &["Sling of Courage"]).player.powers.get(Power::Strength), 2);
    assert_eq!(fight(Encounter::SlimeBoss, &["Sling of Courage"]).player.powers.get(Power::Strength), 0);
    assert_eq!(fight(Encounter::JawWorm, &["Sling of Courage"]).player.powers.get(Power::Strength), 0);
    let r = relic("gen:Sling of Courage").unwrap();
    assert!(r.acts_in(EncounterGroup::Elite) && !r.acts_in(EncounterGroup::Hallway) && !r.acts_in(EncounterGroup::Boss));
    // Philosopher's Stone: +1 energy each turn; every enemy 1 Strength once.
    let mut s = fight(Encounter::JawWorm, &["Philosopher's Stone"]);
    assert_eq!(s.player.energy, 4);
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 1);
    let plain = {
        let mut p = fight(Encounter::JawWorm, &[]);
        next_turn(&mut p);
        p
    };
    next_turn(&mut s);
    assert_eq!(s.player.energy, 4);
    assert_eq!(s.monsters[0].powers.get(Power::Strength), plain.monsters[0].powers.get(Power::Strength) + 1);
    assert_eq!(s.player.hp, plain.player.hp - 1, "Chomp hits 12");
    // Mark of Pain: +1 energy each turn; 2 Wounds in the draw pile once.
    let wound = CardId::from_name("Wound").unwrap();
    let mut s = fight(Encounter::JawWorm, &["Mark of Pain"]);
    assert_eq!(s.player.energy, 4);
    next_turn(&mut s);
    assert_eq!(s.player.energy, 4);
    let held = s.hand.count(wound) + s.draw().count(wound) + s.discard().count(wound);
    assert_eq!(held, 2, "no more Wounds on turn 2");
    // A run's worth of relics together plays a turn.
    let some = [
        "Vajra", "Anchor", "Lantern", "Bronze Scales", "Thread and Needle", "Runic Cube", "Strike Dummy", "Slaver's Collar", "Mark of Pain",
    ];
    let mut s = fight(Encounter::GremlinNob, &some);
    assert_eq!(s.player.energy, 6);
    next_turn(&mut s);
    assert_eq!(s.player.energy, 5);
    // 16 at once (RELIC_CAP): relics hold no helper powers, so they fit the
    // player's 12 power slots (docs/specs/relic-entity.md).
    load_pack(PACK).unwrap();
    // Gambling Chip opens a pick on turn 1 (its own test plays it).
    let all: Vec<String> =
        pack_relic_names().iter().map(|n| n.trim_start_matches("gen:").to_string()).filter(|n| n != "Gambling Chip").take(16).collect();
    let refs: Vec<&str> = all.iter().map(String::as_str).collect();
    let mut s = fight(Encounter::GremlinNob, &refs);
    assert_eq!(s.player.relics.len(), 16);
    next_turn(&mut s);
}

/// Relics starting the player with more than 12 powers bind and play: a
/// creature holds any number of powers, as the game's `ArrayList`
/// (engine-caps plan; the old 12-power cap was an error here).
#[test]
fn thirteen_relic_powers_bind() {
    load_pack(PACK).unwrap();
    // Toolbox is the colorless pack's, which another test here loads; the
    // ow- relics are owed_work_in_any_hook's.
    assert_eq!(pack_relic_names().iter().filter(|n| n.as_str() != "gen:Toolbox" && !n.starts_with("gen:ow-")).count(), 80);
    // 14 relics, each starting the player with a different official buff.
    let powers = ["Strength", "Dexterity", "Thorns", "Artifact", "Ritual", "Metallicize", "Combust", "DemonForm", "Brutality", "Rage",
        "Rupture", "Accuracy", "Enrage", "Burst"];
    let entries: Vec<String> = powers.iter().map(|p| format!(r#"{{"id": "cap-{p}", "rarity": "common", "powers": [{{"power": "{p}", "amount": 1}}]}}"#)).collect();
    load_pack(&format!(r#"{{"version": 2, "relics": [{}]}}"#, entries.join(", "))).unwrap();
    let names: Vec<String> = powers.iter().map(|p| format!("gen:cap-{p}")).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    let all = relics_named(&refs).unwrap();
    sts_engine::registry::bind_relics(&Default::default(), all.iter(), Character::Ironclad).unwrap();
    let bare: Vec<String> = powers.iter().map(|p| format!("cap-{p}")).collect();
    let mut s = fight(Encounter::JawWorm, &bare.iter().map(String::as_str).collect::<Vec<_>>());
    assert!(s.player.powers.iter().count() >= 13, "{:?}", s.player.powers);
    next_turn(&mut s);
}

/// Ends turns until turn `t` has started.
fn to_turn(s: &mut CombatState, t: u16) {
    while (s.turn as u16) < t {
        next_turn(s);
    }
}

/// Relics written with their counter (the game's `counter`) or a heal,
/// from the decompiled `relics/<Name>.java` (aeubanks/sts, read
/// 2026-11-12): in-fight parts of blocks R3 (turn number) and R4 (every N),
/// and R7 (heal).
#[test]
fn counter_and_heal_relics() {
    // Blood Vial (`atBattleStart` Heal 2): 50 -> 52.
    assert_eq!(fight(Encounter::JawWorm, &["Blood Vial"]).player.hp, 52);
    // Pantograph (`atBattleStart`, a boss in the fight: Heal 25).
    assert_eq!(fight(Encounter::SlimeBoss, &["Pantograph"]).player.hp, 75);
    assert_eq!(fight(Encounter::GremlinNob, &["Pantograph"]).player.hp, 50);
    // Bird-Faced Urn (`onUseCard` Power: Heal 2).
    let mut s = fight_with(Encounter::JawWorm, &deck(&["Inflame"]), 50, &["Bird-Faced Urn"], 11);
    play(&mut s, "Strike");
    assert_eq!(s.player.hp, 50);
    play(&mut s, "Inflame");
    assert_eq!(s.player.hp, 52);
    // Horn Cleat: 14 block at the start of turn 2 only (counter 1, 2, then -1).
    let mut s = fight(Encounter::Cultist, &["Horn Cleat"]);
    assert_eq!((s.player.block, s.player.relics.counter(0)), (0, 1));
    next_turn(&mut s);
    assert_eq!((s.player.block, s.player.relics.counter(0)), (14, -1));
    next_turn(&mut s);
    assert_eq!(s.player.block, 0);
    // Captain's Wheel: 18 block at the start of turn 3 only.
    let mut s = fight(Encounter::Cultist, &["Captain's Wheel"]);
    next_turn(&mut s);
    assert_eq!(s.player.block, 0);
    next_turn(&mut s);
    assert_eq!((s.player.block, s.player.relics.counter(0)), (18, -1));
    next_turn(&mut s);
    assert_eq!(s.player.block, 0);
    // Stone Calendar: 52 to every enemy at the end of turn 7 only.
    let mut s = fight_with(Encounter::Cultist, &deck(&[]), 80, &["Stone Calendar"], 11);
    s.monsters[0].max_hp = 500;
    s.monsters[0].hp = 500;
    to_turn(&mut s, 7);
    let hp7 = s.monsters[0].hp;
    s.player.hp = 80;
    next_turn(&mut s);
    assert_eq!(hp7 - s.monsters[0].hp, 52);
    s.player.hp = 80;
    let hp8 = s.monsters[0].hp;
    next_turn(&mut s);
    assert_eq!(s.monsters[0].hp, hp8);
    // Happy Flower: +1 energy every 3rd turn; the counter is the caller's.
    let mut s = fight(Encounter::Cultist, &["Happy Flower"]);
    let mut seen = vec![s.player.energy];
    for _ in 0..5 {
        s.player.hp = 50;
        next_turn(&mut s);
        seen.push(s.player.energy);
    }
    assert_eq!(seen, [3, 3, 4, 3, 3, 4]);
    // Incense Burner: 1 Intangible on turn 6, gone after the round.
    let mut s = fight_with(Encounter::Cultist, &deck(&[]), 80, &["Incense Burner"], 11);
    to_turn(&mut s, 5);
    assert_eq!(s.player.powers.get(Power::Intangible), 0);
    s.player.hp = 80;
    next_turn(&mut s);
    assert_eq!((s.player.powers.get(Power::Intangible), s.player.relics.counter(0)), (1, 0));
    next_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Intangible), 0);
    // Self-Forming Clay: Chomp's HP loss gives 3 Next Turn Block, spent
    // at turn 2's start.
    let mut s = fight(Encounter::JawWorm, &["Self-Forming Clay"]);
    next_turn(&mut s);
    assert_eq!(s.player.hp, 39);
    assert_eq!(s.player.block, 3);
    assert_eq!(s.player.powers.get(gen_power(&s, "NextTurnBlock")), 0);
}

/// Relics that act once the card has resolved (the game's `onUseCard`
/// queueing its action behind the card), the engine's `CardPlayed by
/// Owner` trigger, with a counter (decompiled `relics/<Name>.java`).
#[test]
fn after_the_card_relics() {
    let extra = deck(&["Strike", "Strike", "Strike", "Defend", "Defend", "Defend", "Body Slam"]);
    let start = |relics: &[&str]| {
        let mut s = fight_with(Encounter::Cultist, &extra, 50, relics, 11);
        s.monsters[0].max_hp = 500;
        s.monsters[0].hp = 500;
        s
    };
    let dealt = |s: &mut CombatState, card: &str| {
        let hp = s.monsters[0].hp;
        play(s, card);
        hp - s.monsters[0].hp
    };
    // Shuriken: the 3rd Attack itself deals 6; the 4th deals 7.
    let mut s = start(&["Shuriken"]);
    assert_eq!([dealt(&mut s, "Strike"), dealt(&mut s, "Strike"), dealt(&mut s, "Strike")], [6, 6, 6]);
    assert_eq!(s.player.powers.get(Power::Strength), 1);
    assert_eq!(s.player.relics.counter(0), 0);
    assert_eq!(dealt(&mut s, "Strike"), 7);
    // Skills don't count; the count restarts each turn.
    let mut s = start(&["Shuriken"]);
    play(&mut s, "Strike");
    play(&mut s, "Defend");
    play(&mut s, "Strike");
    assert_eq!(s.player.relics.counter(0), 2);
    next_turn(&mut s);
    assert_eq!(s.player.relics.counter(0), 0);
    // Kunai: 1 Dexterity after the 3rd Attack.
    let mut s = start(&["Kunai"]);
    for _ in 0..3 {
        play(&mut s, "Strike");
    }
    assert_eq!(s.player.powers.get(Power::Dexterity), 1);
    // Ornamental Fan: 4 block after the 3rd Attack, so Body Slam as the 3rd
    // doesn't count it.
    let mut s = start(&["Ornamental Fan"]);
    play(&mut s, "Strike");
    play(&mut s, "Strike");
    assert_eq!(dealt(&mut s, "Body Slam"), 0);
    assert_eq!(s.player.block, 4);
    // Letter Opener: 5 to every enemy after the 3rd Skill.
    let mut s = start(&["Letter Opener"]);
    play(&mut s, "Defend");
    play(&mut s, "Defend");
    assert_eq!(dealt(&mut s, "Defend"), 5);
    // Nunchaku: +1 energy on the 10th Attack; the counter is the caller's.
    let mut s = start(&["Nunchaku"]);
    s.player.relics.set_counter(0, 9);
    s.player.energy = 3;
    play(&mut s, "Strike");
    assert_eq!((s.player.energy, s.player.relics.counter(0)), (3, 0));
    // Ink Bottle: draw 1 on the 10th card.
    let mut s = start(&["Ink Bottle"]);
    s.player.relics.set_counter(0, 9);
    let hand = s.hand.len();
    play(&mut s, "Defend");
    s.advance(&mut Rng::new(14));
    assert_eq!((s.hand.len(), s.player.relics.counter(0)), (hand, 0), "one played, one drawn");
    // Akabeko: 8 Vigor, spent by the first Attack (both of its hits).
    let mut s = fight_with(Encounter::Cultist, &deck(&["Twin Strike"]), 50, &["Akabeko"], 11);
    let vigor = gen_power(&s, "Vigor");
    assert_eq!(s.player.powers.get(vigor), 8);
    play(&mut s, "Defend");
    assert_eq!(s.player.powers.get(vigor), 8);
    assert_eq!(dealt(&mut s, "Twin Strike"), 26);
    assert_eq!(s.player.powers.get(vigor), 0);
    assert_eq!(dealt(&mut s, "Strike"), 6);
}

/// A fight with one relic started at `counter` (the caller's, as the run
/// layer will pass a counter carried between fights).
fn fight_at(enc: Encounter, cards: &[String], relic_name: &str, counter: i16) -> CombatState {
    load_pack(PACK).unwrap();
    let mut given = relics_named(&[&format!("gen:{relic_name}")]).unwrap();
    given[0].1.counter = counter;
    let card_refs: Vec<&str> = cards.iter().map(String::as_str).collect();
    let (ids, b) = bind(&card_refs).unwrap();
    CombatState::new_bound_with(Character::Ironclad, &ids, &b, 50, 80, enc, &given, &mut Rng::new(11))
}

/// docs/specs/fight-vocabulary.md steps 2: a hook with two conditions
/// (Pen Nib), `OwnerBlockIs` (Orichalcum), `OpponentDied` (Gremlin Horn),
/// each against its decompiled class.
#[test]
fn two_conditions_block_and_death_relics() {
    let big = |mut s: CombatState| {
        s.monsters[0].max_hp = 500;
        s.monsters[0].hp = 500;
        s
    };
    let dealt = |s: &mut CombatState, card: &str| {
        let hp = s.monsters[0].hp;
        play(s, card);
        hp - s.monsters[0].hp
    };
    // Pen Nib (`relics/PenNib.java`, `powers/PenNibPower.java`): the 9th
    // Attack gives Pen Nib, a Skill at 9 doesn't give it again, the 10th
    // deals double and spends it, the 11th is plain.
    let cards = deck(&["Strike", "Strike", "Strike"]);
    let mut s = big(fight_at(Encounter::Cultist, &cards, "Pen Nib", 8));
    let nib = gen_power(&s, "PenNib");
    assert_eq!(s.player.powers.get(nib), 0);
    assert_eq!(dealt(&mut s, "Strike"), 6);
    assert_eq!((s.player.powers.get(nib), s.player.relics.counter(0)), (1, 9));
    play(&mut s, "Defend");
    assert_eq!(s.player.powers.get(nib), 1, "a Skill at counter 9 adds nothing");
    assert_eq!(dealt(&mut s, "Strike"), 12);
    assert_eq!((s.player.powers.get(nib), s.player.relics.counter(0)), (0, 0));
    assert_eq!(dealt(&mut s, "Strike"), 6);
    // A fight starting at 9 doubles its first Attack; with 1 Strength and
    // Weak, trunc((6 + 1) × 2 × 3/4) = 10, as the game's float.
    let mut s = big(fight_at(Encounter::Cultist, &cards, "Pen Nib", 9));
    assert_eq!(s.player.powers.get(nib), 1);
    s.player.powers.add(Power::Strength, 1);
    s.player.powers.add(Power::Weak, 1);
    assert_eq!(dealt(&mut s, "Strike"), 10);
    // Orichalcum (`relics/Orichalcum.java`): 6 block at turn end with none;
    // Chomp (11) then costs 5.
    let mut s = fight(Encounter::JawWorm, &["Orichalcum"]);
    next_turn(&mut s);
    assert_eq!(s.player.hp, 45);
    // With 1 block, none: Chomp costs 10.
    let mut s = fight(Encounter::JawWorm, &["Orichalcum"]);
    s.player.block = 1;
    next_turn(&mut s);
    assert_eq!(s.player.hp, 40);
    // Relics before powers: Metallicize 3's block comes after the check, 9.
    let mut s = fight(Encounter::JawWorm, &["Orichalcum"]);
    s.player.powers.add(Power::Metallicize, 3);
    next_turn(&mut s);
    assert_eq!(s.player.hp, 48);
    // Gremlin Horn (`relics/GremlinHorn.java`): killing one of two gives
    // 1 energy and 1 card; killing the last ends the fight with nothing.
    let mut s = fight(Encounter::TwoLouse, &["Gremlin Horn"]);
    s.monsters[0].hp = 1;
    s.player.energy = 3;
    let hand = s.hand.len();
    play(&mut s, "Strike");
    s.advance(&mut Rng::new(14));
    assert!(!s.monsters[0].alive());
    assert_eq!((s.player.energy, s.hand.len()), (3, hand), "1 spent, 1 back; 1 played, 1 drawn");
    let other = (0..s.monsters.len()).find(|&i| s.monsters[i].alive()).unwrap();
    s.monsters[other].hp = 1;
    s.monsters[other].block = 0;
    let c = CardId::from_name("Strike").unwrap();
    s.hand.add(c, 1);
    s.player.energy = 3;
    let hand = s.hand.len();
    s.step(Action::Play { card: c, target: Some(other as u8) }, &mut Rng::new(15)).unwrap();
    assert!(s.is_over());
    assert_eq!((s.player.energy, s.hand.len()), (2, hand - 1), "the last kill gives nothing");
    // Two deaths from one Cleave with a third alive: 2 energy and 2 cards
    // (a second draw in the pass adds to the pending one).
    let mut s = fight_with(Encounter::ThreeLouse, &deck(&["Cleave"]), 50, &["Gremlin Horn"], 11);
    let alive: Vec<usize> = (0..s.monsters.len()).filter(|&i| s.monsters[i].alive()).collect();
    assert_eq!(alive.len(), 3);
    for &i in &alive[..2] {
        s.monsters[i].hp = 1;
        s.monsters[i].block = 0;
    }
    s.monsters[alive[2]].hp = 500;
    s.monsters[alive[2]].max_hp = 500;
    let cleave = CardId::from_name("Cleave").unwrap();
    if s.hand.count(cleave) == 0 {
        s.hand.add(cleave, 1);
    }
    s.player.energy = 3;
    let hand = s.hand.len();
    s.step(Action::Play { card: cleave, target: None }, &mut Rng::new(16)).unwrap();
    s.advance(&mut Rng::new(17));
    assert_eq!((s.player.energy, s.hand.len()), (4, hand + 1), "Cleave out, 2 drawn");
}

/// A hook's condition list: two that both hold; more, or two numbers, is a
/// load error (docs/specs/fight-vocabulary.md). A power's hooks, so the
/// relic count other tests read stays the pack's.
#[test]
fn condition_list_load_errors() {
    let pack = |cond: &str| {
        format!(r#"{{"version": 2, "powers": [{{"id": "cl-test", "hooks": [{{"trigger": "OwnerTurnEnd", "condition": {cond}, "effects": [{{"Block": 1}}]}}]}}]}}"#)
    };
    load_pack(&pack(r#"[{"CardType": "Attack"}, {"OwnerBlockIs": 0}]"#)).unwrap();
    let e = load_pack(&pack(r#"[{"CardsPlayedThisTurnBelow": 1}, {"OwnerBlockIs": 0}]"#)).unwrap_err();
    assert!(e.contains("one number between them"), "{e}");
    let e = load_pack(&pack(r#"["Always", "Always", "Always"]"#)).unwrap_err();
    assert!(e.contains("two conditions, not 3"), "{e}");
}

/// docs/specs/fight-vocabulary.md step 3: a `DebuffApplied` replacement
/// filtered to one power (Ginger, Turnip; `ApplyPowerAction.java` ~132:
/// both checked before Artifact, which keeps its stack).
#[test]
fn debuff_filter_relics() {
    load_pack(PACK).unwrap();
    load_pack(
        r#"{"version": 2, "cards": [{"id": "df-SelfDebuffs", "cost": 0, "type": "Skill", "effects": [
        {"Apply": {"power": "Weak", "amount": 2, "target": "Me"}}, {"Apply": {"power": "Frail", "amount": 2, "target": "Me"}},
        {"Apply": {"power": "Vulnerable", "amount": 1, "target": "Me"}}]}]}"#,
    )
    .unwrap();
    let cards = deck(&["gen:df-SelfDebuffs"]);
    let got = |relics: &[&str], artifact: i16| {
        let mut s = fight_with(Encounter::Cultist, &cards, 50, relics, 11);
        s.player.powers.add(Power::Artifact, artifact);
        let c = s.hand.iter().chain(s.draw().iter()).map(|(c, _)| c).find(|&c| s.binding.def(c).name == "gen:df-SelfDebuffs").unwrap();
        if s.hand.count(c) == 0 {
            s.hand.add(c, 1);
        }
        s.step(Action::Play { card: c, target: None }, &mut Rng::new(13)).unwrap();
        let p = &s.player.powers;
        (p.get(Power::Weak), p.get(Power::Frail), p.get(Power::Vulnerable), p.get(Power::Artifact))
    };
    assert_eq!(got(&[], 0), (2, 2, 1, 0));
    assert_eq!(got(&["Ginger"], 0), (0, 2, 1, 0));
    assert_eq!(got(&["Turnip"], 0), (2, 0, 1, 0));
    assert_eq!(got(&["Ginger", "Turnip"], 0), (0, 0, 1, 0));
    // Artifact 1: Ginger takes the Weak first, Artifact the Frail.
    assert_eq!(got(&["Ginger"], 1), (0, 0, 1, 0));
    assert_eq!(got(&["Ginger"], 3), (0, 0, 0, 1));
    // A filter is for DebuffApplied only, and names an official power.
    let bad = |r: &str| load_pack(&format!(r#"{{"version": 2, "powers": [{{"id": "df-bad", "replacements": [{r}]}}]}}"#)).unwrap_err();
    assert!(bad(r#"{"event": "HpLoss", "power": "Weak", "action": "Cancel"}"#).contains("only a DebuffApplied"));
    assert!(bad(r#"{"event": "DebuffApplied", "power": "Nope", "action": "Cancel"}"#).contains("not an official power"));
}

/// docs/specs/fight-vocabulary.md step 4: `CombatWon`, before the
/// combat-end heal (`AbstractRoom.endBattle`: Meat on the Bone's
/// `onTrigger` before `player.onVictory()`, Burning Blood).
#[test]
fn combat_won_relics() {
    let won_at = |hp: i16| {
        let mut s = fight_with(Encounter::Cultist, &deck(&[]), hp, &["Meat on the Bone"], 11);
        assert!(s.can_heal(), "the bound counts the hook's heal");
        s.monsters[0].hp = 1;
        play(&mut s, "Strike");
        assert!(s.is_over());
        (s.player.hp, s.won_healed.0)
    };
    // `currentHealth <= maxHealth / 2.0F`, checked before Burning Blood's 6;
    // `won_healed` is the HP the win actually gave (capped at max HP 80).
    assert_eq!(won_at(40), (40 + 12 + 6, 18));
    assert_eq!(won_at(41), (41 + 6, 6));
    assert_eq!(won_at(37), (37 + 12 + 6, 18));
    assert_eq!(won_at(77), (80, 3));
    // Only CombatWon's own effects load.
    load_pack(PACK).unwrap();
    let e = load_pack(r#"{"version": 2, "relics": [{"id": "cw-bad", "rarity": "common", "hooks": [{"trigger": "CombatWon", "condition": "Always", "effects": [{"Draw": 1}]}]}]}"#)
        .unwrap_err();
    assert!(e.contains("heals or changes a counter only"), "{e}");
}

/// docs/specs/would-die.md step 1: Lizard Tail (`relics/LizardTail.java`;
/// `AbstractPlayer.damage`: below 1 HP, HP goes to 0, `onTrigger` heals
/// `maxHealth / 2` and sets the counter to -2, used up).
#[test]
fn lizard_tail() {
    // Bloodletting at 2 HP would kill: saved to 80 / 2, used up.
    let lethal_card = |mut s: CombatState| {
        s.player.hp = 2;
        play(&mut s, "Bloodletting");
        s
    };
    let s = lethal_card(fight(Encounter::Cultist, &["Lizard Tail"]));
    assert!(!s.is_over());
    assert_eq!((s.player.hp, s.player.relics.counter(0)), (40, -2));
    assert!(s.can_heal(), "the bound counts the hook's heal");
    // A second lethal loss kills; so does one with the counter at -2 (the
    // run layer's carried "used").
    let s = lethal_card(s);
    assert!(s.is_over() && !s.won());
    let s = lethal_card(fight_at(Encounter::Cultist, &deck(&[]), "Lizard Tail", -2));
    assert!(s.is_over() && !s.won());
    // A loss that doesn't kill leaves it unused.
    let mut s = fight(Encounter::Cultist, &["Lizard Tail"]);
    play(&mut s, "Bloodletting");
    assert_eq!((s.player.hp, s.player.relics.counter(0)), (47, -1));
    // In the monsters' turn: Jaw Worm's Chomp (11) at 5 HP. The HP loss's
    // reactions still run after the save (Runic Cube draws 1, as the
    // game's queued `wasHPLost` action resolves after the death check).
    let mut s = fight_with(Encounter::JawWorm, &deck(&[]), 5, &["Lizard Tail", "Runic Cube"], 11);
    next_turn(&mut s);
    assert_eq!((s.player.hp, s.player.relics.counter(0)), (40, -2));
    assert_eq!(s.hand.len(), 6);
    // The hit that the save undid still counts as a hit that made the
    // player lose HP: the attacker's OwnerAttackHit hooks run (WeakOnHit),
    // as for an unsaved player.
    let weak_after = |hp: i16, relics: &[&str]| {
        let mut s = fight_with(Encounter::JawWorm, &deck(&[]), hp, relics, 11);
        s.monsters[0].powers.add(Power::WeakOnHit, 1);
        next_turn(&mut s);
        s.player.powers.get(Power::Weak)
    };
    assert!(weak_after(30, &[]) > 0);
    assert_eq!(weak_after(5, &["Lizard Tail"]), weak_after(30, &[]));
    // From above half to the save's half: Red Skull's bloodied fires once
    // (the game's `onBloodied` before the death check), +3 Strength.
    let mut s = fight_with(Encounter::JawWorm, &deck(&[]), 50, &["Lizard Tail", "Red Skull"], 11);
    s.monsters[0].powers.add(Power::Strength, 100);
    next_turn(&mut s);
    assert_eq!(s.player.hp, 40);
    assert_eq!(s.player.powers.get(Power::Strength), 3);
    // No-death mode: the same save below 1; once used, HP goes below 0.
    let mut s = fight(Encounter::Cultist, &["Lizard Tail"]);
    s.no_death = true;
    let s = lethal_card(s);
    assert_eq!(s.player.hp, 40);
    let mut s = fight_at(Encounter::Cultist, &deck(&[]), "Lizard Tail", -2);
    s.no_death = true;
    let s = lethal_card(s);
    assert_eq!(s.player.hp, -1);
    // Only a save's effects load in a relic's OwnerDied hook.
    load_pack(PACK).unwrap();
    let e = load_pack(r#"{"version": 2, "relics": [{"id": "od-bad", "rarity": "common", "hooks": [{"trigger": "OwnerDied", "condition": "Always", "effects": [{"Draw": 1}]}]}]}"#)
        .unwrap_err();
    assert!(e.contains("heals or changes a counter only"), "{e}");
}

/// HP the player loses over the monsters' turn, ending it with `block`.
fn lost_in_monsters_turn(mut s: CombatState, block: i16) -> i16 {
    s.player.block = block;
    let hp = s.player.hp;
    next_turn(&mut s);
    hp - s.player.hp
}

/// HP monster 0 loses to `name` played at it with `block`.
fn dealt_through(mut s: CombatState, name: &str, block: i16) -> i16 {
    let c = CardId::from_name(name).unwrap();
    s.hand.add(c, 1);
    s.player.energy = 3;
    s.monsters[0].block = block;
    let hp = s.monsters[0].hp;
    s.step(Action::Play { card: c, target: Some(0) }, &mut Rng::new(13)).unwrap();
    hp - s.monsters[0].hp
}

#[test]
fn after_block_relics() {
    // docs/specs/after-block.md: the game's `damage` order.
    // The Boot (relics/Boot.java `onAttackToChangeDamage`): unblocked
    // attack damage 1..4 -> 5.
    let boot = fight(Encounter::JawWorm, &["The Boot"]);
    assert_eq!(dealt_through(boot.clone(), "Strike", 3), 5);
    assert_eq!(dealt_through(boot.clone(), "Strike", 0), 6);
    assert_eq!(dealt_through(boot.clone(), "Strike", 6), 0, "fully blocked");
    // Not THORNS damage: Mercury Hourglass's 3 and Bronze Scales' 3.
    let monster_loss = |relics: &[&str]| {
        let mut s = fight(Encounter::JawWorm, relics);
        let hp = s.monsters[0].hp;
        next_turn(&mut s);
        hp - s.monsters[0].hp
    };
    assert_eq!(monster_loss(&["The Boot", "Mercury Hourglass"]), monster_loss(&["Mercury Hourglass"]));
    assert_eq!(monster_loss(&["The Boot", "Bronze Scales"]), 3);
    // Torii (relics/Torii.java `onAttacked`): unblocked attack damage
    // 2..5 -> 1. Jaw Worm's Chomp is 11.
    let torii = fight(Encounter::JawWorm, &["Torii"]);
    assert_eq!(lost_in_monsters_turn(torii.clone(), 6), 1, "5 -> 1");
    assert_eq!(lost_in_monsters_turn(torii.clone(), 9), 1, "2 -> 1");
    assert_eq!(lost_in_monsters_turn(torii.clone(), 5), 6);
    let mut t = torii.clone();
    play(&mut t, "Bloodletting");
    assert_eq!(t.player.hp, 47, "HP loss: not an attack");
    // Tungsten Rod (relics/TungstenRod.java `onLoseHpLast`): 1 less, every loss.
    let rod = fight(Encounter::JawWorm, &["Tungsten Rod"]);
    assert_eq!(lost_in_monsters_turn(rod.clone(), 0), 10);
    assert_eq!(lost_in_monsters_turn(rod.clone(), 10), 0, "1 -> 0");
    let mut r = rod.clone();
    play(&mut r, "Bloodletting");
    assert_eq!(r.player.hp, 48);
    assert_eq!(lost_in_monsters_turn(fight(Encounter::JawWorm, &["Torii", "Tungsten Rod"]), 6), 0, "5 -> 1 -> 0");
    // A loss brought to 0 is no loss: Centennial Puzzle doesn't draw.
    let mut cp = fight(Encounter::JawWorm, &["Tungsten Rod", "Centennial Puzzle"]);
    cp.player.block = 10;
    next_turn(&mut cp);
    assert_eq!((cp.player.hp, cp.hand.len(), cp.player.relics.counter(1)), (50, 5, 0));
}

#[test]
fn fossilized_helix_gives_buffer() {
    // relics/FossilizedHelix.java `atBattleStart`: 1 Buffer
    // (powers/BufferPower.java: the next unblocked hit or HP loss -> 0).
    let s = fight(Encounter::JawWorm, &["Fossilized Helix"]);
    let buffer = gen_power(&s, "Buffer");
    assert_eq!(s.player.powers.get(buffer), 1);
    let mut blocked = s.clone();
    blocked.player.block = 11;
    next_turn(&mut blocked);
    assert_eq!((blocked.player.hp, blocked.player.powers.get(buffer)), (50, 1), "a blocked hit doesn't spend it");
    let mut open = s.clone();
    next_turn(&mut open);
    assert_eq!((open.player.hp, open.player.powers.get(buffer)), (50, 0), "Chomp absorbed");
    // HP loss too: Bloodletting loses nothing and gives its energy; the
    // second loses 3.
    let mut b = s.clone();
    play(&mut b, "Bloodletting");
    assert_eq!((b.player.hp, b.player.energy, b.player.powers.get(buffer)), (50, 5, 0), "3 energy, +2");
    play(&mut b, "Bloodletting");
    assert_eq!(b.player.hp, 47);
    // Before Torii: 4 past block spends Buffer, Torii doesn't act.
    let mut t = fight(Encounter::JawWorm, &["Fossilized Helix", "Torii"]);
    t.player.block = 7;
    next_turn(&mut t);
    assert_eq!((t.player.hp, t.player.powers.get(buffer)), (50, 0));
    // An absorbed hit is no HP loss: Plated Armor keeps its stacks,
    // Centennial Puzzle doesn't draw.
    let mut pa = fight(Encounter::JawWorm, &["Fossilized Helix", "Thread and Needle"]);
    let plated = gen_power(&pa, "PlatedArmor");
    next_turn(&mut pa);
    assert_eq!((pa.player.hp, pa.player.powers.get(plated)), (50, 4));
    let mut cp = fight(Encounter::JawWorm, &["Fossilized Helix", "Centennial Puzzle"]);
    next_turn(&mut cp);
    assert_eq!((cp.player.hp, cp.hand.len(), cp.player.relics.counter(1)), (50, 5, 0));
}

#[test]
fn after_block_before_the_save() {
    // docs/specs/after-block.md and would-die.md: in `AbstractPlayer.damage`
    // the after-block passes come before the death check, so the save sees
    // the amount they leave.
    let bloodletting_at = |hp: i16, relics: &[&str]| {
        let mut s = fight(Encounter::Cultist, relics);
        s.player.hp = hp;
        play(&mut s, "Bloodletting");
        s
    };
    // Tungsten Rod: 3 -> 2. At 2 HP still lethal: Lizard Tail saves.
    let s = bloodletting_at(2, &["Tungsten Rod", "Lizard Tail"]);
    assert!(!s.is_over());
    assert_eq!((s.player.hp, s.player.relics.counter(1)), (40, -2));
    // At 3 HP no longer lethal: 1 HP left, Lizard Tail unused.
    let s = bloodletting_at(3, &["Tungsten Rod", "Lizard Tail"]);
    assert_eq!((s.player.hp, s.player.relics.counter(1)), (1, -1));
    // Buffer absorbs a would-be-lethal hit (Chomp 11 at 5 HP): no save.
    let mut s = fight_with(Encounter::JawWorm, &deck(&[]), 5, &["Fossilized Helix", "Lizard Tail"], 11);
    let buffer = gen_power(&s, "Buffer");
    next_turn(&mut s);
    assert_eq!((s.player.hp, s.player.relics.counter(1), s.player.powers.get(buffer)), (5, -1, 0));
}

/// docs/specs/act1-singles.md section 6: trigger `OwnerApplied`, Champion
/// Belt (`ApplyPowerAction.java` ~105, `relics/ChampionsBelt.java`): a
/// Vulnerable the player applies that lands (no Artifact cancel) adds 1
/// Weak on that creature.
#[test]
fn champion_belt() {
    load_pack(include_str!("../../content/packs/act1-ironclad.json")).unwrap();
    let powers = |m: &sts_engine::monsters::Monster| (m.powers.get(Power::Vulnerable), m.powers.get(Power::Weak), m.powers.get(Power::Artifact));
    // Plays `name` (a pack card by its `gen:` name) at monster 0.
    let played = |enc: Encounter, name: &str, relics: &[&str]| {
        let mut s = fight_with(enc, &deck(&[name]), 50, relics, 11);
        let c = s.hand.iter().chain(s.draw().iter()).map(|(c, _)| c).find(|&c| s.binding.def(c).name == name).unwrap();
        if s.hand.count(c) == 0 {
            s.hand.add(c, 1);
        }
        s.player.energy = 3;
        let target = s.binding.def(c).targeted().then_some(0);
        s.step(Action::Play { card: c, target }, &mut Rng::new(13)).unwrap();
        s
    };
    let belt = &["Champion Belt"];
    // Bash on Jaw Worm: 2 Vulnerable and 1 Weak; without the Belt no Weak.
    assert_eq!(powers(&played(Encounter::JawWorm, "Bash", belt).monsters[0]), (2, 1, 0));
    assert_eq!(powers(&played(Encounter::JawWorm, "Bash", &[]).monsters[0]), (2, 0, 0));
    // Thunderclap: each Louse 1 Weak.
    let s = played(Encounter::ThreeLouse, "Thunderclap", belt);
    assert_eq!(s.monsters.iter().filter(|m| m.alive()).count(), 3);
    for m in s.monsters.iter().filter(|m| m.alive()) {
        assert_eq!(powers(m), (1, 1, 0));
    }
    // A Sentry with Artifact 1: Bash's Vulnerable is cancelled (Artifact
    // goes), so the Belt gives nothing.
    let s = played(Encounter::ThreeSentries, "Bash", belt);
    assert_eq!(powers(&s.monsters[0]), (0, 0, 0));
    // Shockwave: Artifact takes the Weak 3, the Vulnerable 3 lands, then
    // the Belt's Weak 1.
    let s = played(Encounter::ThreeSentries, "gen:Shockwave", belt);
    for m in s.monsters.iter().filter(|m| m.alive()) {
        assert_eq!(powers(m), (3, 1, 0));
    }
    // Bag of Marbles at combat start, in either relic order.
    for relics in [["Bag of Marbles", "Champion Belt"], ["Champion Belt", "Bag of Marbles"]] {
        let s = fight(Encounter::ThreeLouse, &relics);
        for m in s.monsters.iter().filter(|m| m.alive()) {
            assert_eq!(powers(m), (1, 1, 0), "{relics:?}");
        }
    }
    // A monster's Vulnerable on the player (Gremlin Nob's Skull Bash)
    // gives nothing.
    let mut s = fight(Encounter::GremlinNob, belt);
    s.monsters[0].moves[0] = 2;
    next_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Vulnerable), 2);
    assert_eq!((s.player.powers.get(Power::Weak), s.monsters[0].powers.get(Power::Weak)), (0, 0));
}

/// Toolbox (`relics/Toolbox.java`, shop; in `act1-colorless.json`, whose
/// Colorless pool it names): `atBattleStartPreDraw` queues
/// `ChooseOneColorless`, three different cards of the Colorless pool
/// (`returnTrulyRandomColorlessCardInCombat`), no skip, not free, into hand.
/// The offer opens once the pre-draw pass has run (Snecko Eye's Confused is
/// on) and before the opening draw, which follows the pick.
#[test]
fn toolbox() {
    const IRONCLAD: &str = include_str!("../../content/packs/act1-ironclad.json");
    const COLORLESS: &str = include_str!("../../content/packs/act1-colorless.json");
    load_pack(PACK).unwrap();
    load_pack(IRONCLAD).unwrap();
    load_pack(COLORLESS).unwrap();
    assert_eq!(relic("gen:Toolbox").unwrap().rarity, Rarity::Shop);
    let pool = {
        let s = fight(Encounter::JawWorm, &["Toolbox"]);
        let i = (0..).find(|&i| sts_engine::registry::pool_def(i).unwrap().name == "Colorless").unwrap();
        sts_engine::registry::pool_cards(&s.binding, i, None).iter().map(|&c| s.binding.def(c).name).collect::<std::collections::BTreeSet<_>>()
    };
    let mut seen = std::collections::BTreeSet::new();
    for seed in 0..120 {
        let mut s = fight_with(Encounter::JawWorm, &deck(&[]), 50, &["Toolbox", "Snecko Eye"], seed);
        assert!(matches!(s.stage, Stage::RelicOffer { pick: Some(_), .. }), "{:?}", s.stage);
        assert!(s.awaiting_action());
        // Before the opening draw: the whole deck is in the draw pile.
        assert_eq!((s.hand.len(), s.draw().len()), (0, 10));
        assert_eq!(s.player.powers.get(gen_power(&s, "Confused")), 1, "the pass ran first");
        let o: Vec<CardId> = s.legal_actions().iter().filter_map(|a| if let Action::Choose(c) = *a { Some(c) } else { None }).collect();
        assert_eq!(o.len(), 3);
        assert_eq!(o.iter().collect::<std::collections::BTreeSet<_>>().len(), 3, "three different cards");
        assert!(!s.legal_actions().contains(&Action::Done), "no skip");
        seen.extend(o.iter().map(|&c| s.binding.def(c).name));
        s.step(Action::Choose(o[0]), &mut Rng::new(seed)).unwrap();
        s.advance(&mut Rng::new(seed));
        assert_eq!(s.stage, Stage::PlayerTurn);
        // The card, then the opening draw (5, Snecko Eye's 2 more); not free.
        assert_eq!((s.hand.len(), s.draw().len()), (8, 3));
        assert!(s.hand.count(o[0]) >= 1);
        assert_eq!(s.free_in_hand.count(o[0]), 0);
    }
    assert_eq!(seen, pool, "every pool card shows, nothing else");
    // Turn 2 has no offer.
    let mut s = fight_with(Encounter::JawWorm, &deck(&[]), 50, &["Toolbox"], 3);
    let c = s.legal_actions().iter().find_map(|a| if let Action::Choose(c) = *a { Some(c) } else { None }).unwrap();
    s.step(Action::Choose(c), &mut Rng::new(3)).unwrap();
    s.advance(&mut Rng::new(3));
    next_turn(&mut s);
    // Discover runs in a relic's CombatStartPreDraw hook only.
    let bad = r#"{"version": 2, "powers": [{"id": "tb-bad-power", "hooks": [{"trigger": "CombatStartPreDraw", "condition": "Always", "effects": [{"Discover": {"pool": "Colorless"}}]}]}]}"#;
    assert!(load_pack(bad).unwrap_err().contains("can't run in a hook"));
    let bad = r#"{"version": 2, "relics": [{"id": "tb-bad", "rarity": "shop", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "effects": [{"Discover": {"pool": "Colorless"}}]}]}]}"#;
    assert!(load_pack(bad).unwrap_err().contains("can't run in a hook"));
}

/// Blocked relics step 1 (docs/specs/blocked-relics.md): the rarities from
/// the jar's classes (`relics/ChemicalX`, `IceCream`, `VelvetChoker`,
/// `RunicPyramid`, `Calipers`).
#[test]
fn step1_relics_load_with_their_rarity() {
    load_pack(PACK).unwrap();
    use Rarity::*;
    for (name, rarity) in [("Chemical X", Shop), ("Ice Cream", Rare), ("Velvet Choker", Boss), ("Runic Pyramid", Boss), ("Calipers", Rare)] {
        assert_eq!(relic(&format!("gen:{name}")).unwrap_or_else(|| panic!("{name} loaded")).rarity, rarity, "{name}");
    }
    let bad = r#"{"version": 2, "relics": [{"id": "cx-bad", "rarity": "shop", "x_bonus": -1}]}"#;
    assert!(load_pack(bad).unwrap_err().contains("x_bonus"));
    let bad = r#"{"version": 2, "relics": [{"id": "ic-bad", "rarity": "rare", "keeps_energy": 1}]}"#;
    assert!(load_pack(bad).unwrap_err().contains("keeps_energy"));
}

/// Whirlwind's damage to a lone Jaw Worm at `energy`, with these relics.
fn whirlwind_damage(relics: &[&str], energy: i16) -> i16 {
    let mut s = fight_with(Encounter::JawWorm, &deck(&["Whirlwind"]), 50, relics, 11);
    let c = CardId::from_name("Whirlwind").unwrap();
    if s.hand.count(c) == 0 {
        s.hand.add(c, 1);
    }
    s.player.energy = energy;
    s.monsters[0].block = 0;
    let before = s.monsters[0].hp;
    s.step(Action::Play { card: c, target: None }, &mut Rng::new(13)).unwrap();
    assert_eq!(s.player.energy, 0, "X spends all the energy, no more");
    before - s.monsters[0].hp
}

/// Chemical X (`WhirlwindAction.update`: X is the energy spent, + 2 with
/// the relic, also at 0 energy).
#[test]
fn chemical_x() {
    assert_eq!(whirlwind_damage(&[], 3), 15);
    assert_eq!(whirlwind_damage(&["Chemical X"], 3), 25);
    assert_eq!(whirlwind_damage(&[], 0), 0);
    assert_eq!(whirlwind_damage(&["Chemical X"], 0), 10);
}

/// Ice Cream (`EnergyManager.recharge`: adds the turn's energy to what is
/// left instead of setting it; turn 1 starts from 0).
#[test]
fn ice_cream() {
    let mut s = fight(Encounter::Cultist, &["Ice Cream"]);
    assert_eq!(s.player.energy, 3);
    next_turn(&mut s);
    assert_eq!(s.player.energy, 6);
    play(&mut s, "Strike");
    assert_eq!(s.player.energy, 5);
    next_turn(&mut s);
    assert_eq!(s.player.energy, 8);
    // Without it, the turn sets 3.
    let mut s = fight(Encounter::Cultist, &[]);
    next_turn(&mut s);
    assert_eq!(s.player.energy, 3);
}

fn can_play_any(s: &CombatState) -> bool {
    s.legal_actions().iter().any(|a| matches!(a, Action::Play { .. }))
}

/// Velvet Choker (`VelvetChoker.canPlay`: no card once 6 were played this
/// turn, the counter reset at turn start; +1 energy; a queued copy goes
/// through `canUse` too, so Double Tap's copy past the 6th isn't played).
#[test]
fn velvet_choker() {
    const IRONCLAD: &str = include_str!("../../content/packs/act1-ironclad.json");
    load_pack(PACK).unwrap();
    load_pack(IRONCLAD).unwrap();
    let mut s = fight(Encounter::Cultist, &["Velvet Choker"]);
    assert_eq!(s.player.energy, 4);
    for i in 0..6 {
        assert!(can_play_any(&s), "play {}", i + 1);
        play(&mut s, "Defend");
    }
    assert_eq!(s.cards_played_this_turn, 6);
    s.hand.add(CardId::from_name("Defend").unwrap(), 1);
    assert!(!can_play_any(&s), "no 7th play");
    assert!(s.legal_actions().contains(&Action::EndTurn));
    next_turn(&mut s);
    assert_eq!(s.player.energy, 4);
    assert!(can_play_any(&s), "the count starts again");
    // Double Tap as the 5th play: the Strike is the 6th and its copy would
    // be the 7th.
    let cards = deck(&["gen:Double Tap"]);
    for (double_tap_at, damage) in [(4, 12), (5, 6)] {
        let mut s = fight_with(Encounter::Cultist, &cards, 50, &["Velvet Choker"], 11);
        let dt = s.hand.iter().chain(s.draw().iter()).map(|(c, _)| c).find(|&c| s.binding.def(c).name == "gen:Double Tap").unwrap();

        for _ in 0..double_tap_at - 1 {
            play(&mut s, "Defend");
        }
        if s.hand.count(dt) == 0 {
            s.hand.add(dt, 1);
        }
        s.player.energy = 3;
        s.step(Action::Play { card: dt, target: None }, &mut Rng::new(13)).unwrap();
        let before = s.monsters[0].hp;
        play(&mut s, "Strike");
        assert_eq!(before - s.monsters[0].hp, damage, "Double Tap as play {double_tap_at}");
    }
}

/// Runic Pyramid (`DiscardAtEndOfTurnAction.update`: no discard with the
/// relic; ethereal cards still exhaust; Burn is played at turn end and goes
/// to the discard pile; the draw stops at 10 cards).
#[test]
fn runic_pyramid() {
    let burn = CardId::from_name("Burn").unwrap();
    let dazed = CardId::from_name("Dazed").unwrap();
    let mut s = fight_with(Encounter::Cultist, &deck(&["Burn", "Dazed"]), 50, &["Runic Pyramid"], 11);
    s.hand.add(burn, 1);
    s.hand.add(dazed, 1);
    let (burns, dazeds) = (s.hand.count(burn) as usize, s.hand.count(dazed) as usize);
    let kept = s.hand.len() - burns - dazeds;
    let hp = s.player.hp;
    next_turn(&mut s);
    assert_eq!(s.player.hp, hp - 2 * burns as i16, "each Burn acted");
    assert_eq!(s.hand.len(), (kept + 5).min(10));
    assert!(s.exhaust().count(dazed) >= 1, "ethereal Dazed exhausted");
    assert_eq!(s.exhaust().count(dazed) as usize, dazeds);
    assert_eq!(s.discard().count(burn) as usize, burns, "each Burn went to the discard pile (no reshuffle: 7 left to draw)");
    assert!(s.hand.len() >= kept, "the rest kept");
    next_turn(&mut s);
    assert_eq!(s.hand.len(), 10, "the hand stops at 10");
    // Without it the hand is discarded: turn 2 holds the 5 drawn.
    let mut s = fight(Encounter::Cultist, &[]);
    next_turn(&mut s);
    assert_eq!(s.hand.len(), 5);
}

/// Calipers (`GameActionManager.getNextAction`: `loseBlock(15)` at the
/// player's turn start, after the monsters acted; Barricade first, which
/// keeps all).
#[test]
fn calipers() {
    for (relics, block, kept) in [(&[][..], 20, 0), (&["Calipers"][..], 20, 5), (&["Calipers"][..], 10, 0)] {
        let mut s = fight(Encounter::Cultist, relics);
        s.player.block = block;
        next_turn(&mut s);
        assert_eq!(s.player.block, kept, "{relics:?} at {block}");
    }
    // With Barricade (`hasPower("Barricade")` comes first) all is kept.
    load_pack(include_str!("../../content/packs/act1-ironclad.json")).unwrap();
    let mut s = fight_with(Encounter::Cultist, &deck(&["gen:Barricade"]), 50, &["Calipers"], 11);
    let b = s.hand.iter().chain(s.draw().iter()).map(|(c, _)| c).find(|&c| s.binding.def(c).name == "gen:Barricade").unwrap();
    if s.hand.count(b) == 0 {
        s.hand.add(b, 1);
    }
    s.step(Action::Play { card: b, target: None }, &mut Rng::new(13)).unwrap();
    s.player.block = 20;
    next_turn(&mut s);
    assert_eq!(s.player.block, 20);
}

/// docs/specs/blocked-relics.md step 2: Preserved Insect and Neow's Lament
/// (`CapHp`), each against its class's `atBattleStart`.
#[test]
fn combat_start_hp_relics() {
    // Preserved Insect (relics.PreservedInsect): in an elite fight (the
    // room's eliteTrigger), each monster's HP above (int)(max * 0.75f)
    // becomes that, a field write: max HP, block and powers untouched.
    for enc in [Encounter::GremlinNob, Encounter::Lagavulin, Encounter::ThreeSentries] {
        let plain = fight(enc, &[]);
        let s = fight(enc, &["Preserved Insect"]);
        assert!(s.monsters.iter().any(|m| m.alive()));
        for (m, p) in s.monsters.iter().zip(&plain.monsters).filter(|(_, p)| p.alive()) {
            assert_eq!(m.max_hp, p.max_hp);
            assert_eq!(m.hp, p.hp.min((p.max_hp as f32 * (1.0f32 - 0.25f32)) as i16), "{enc:?}");
            assert!(m.hp < p.hp);
            assert_eq!((m.block, &m.powers), (p.block, &p.powers));
        }
        assert_eq!((s.player.hp, s.player.block), (plain.player.hp, plain.player.block));
    }
    load_pack(PACK).unwrap();
    let r = relic("gen:Preserved Insect").unwrap();
    assert!(r.acts_in(EncounterGroup::Elite) && !r.acts_in(EncounterGroup::Hallway) && !r.acts_in(EncounterGroup::Boss));
    assert!(fight(Encounter::JawWorm, &["Preserved Insect"]) == fight(Encounter::JawWorm, &[]));
    assert!(fight(Encounter::SlimeBoss, &["Preserved Insect"]) == fight(Encounter::SlimeBoss, &[]));
    // The engine's cap (max x 3 / 4, rounded down) is the game's float for
    // every Act 1 max HP and odd ones.
    for m in [85i16, 86, 87, 88, 1000, 4097] {
        assert_eq!((m as f32 * 0.75f32) as i16, 3 * m / 4, "the cap is floor(3m/4) for {m}");
    }

    // Neow's Lament (relics.NeowsLament): while its counter is above 0,
    // one use per fight: every monster to 1 HP, the counter down by 1,
    // and from 1 to -2 (used up). Every fight kind.
    let hp1 = |s: &CombatState| s.monsters.iter().filter(|m| m.max_hp > 0).all(|m| m.hp == 1);
    for enc in [Encounter::JawWorm, Encounter::ThreeSentries, Encounter::SlimeBoss] {
        // The hook-order trap: the counter-3 hook runs last in the pass,
        // so 3 spends one use (2), not three in a cascade.
        for (start, end) in [(3, 2), (2, 1), (1, -2)] {
            let s = fight_at(enc, &deck(&[]), "Neow's Lament", start);
            assert!(hp1(&s), "{enc:?} at {start}");
            assert_eq!(s.player.relics.counter(0), end, "{enc:?} at {start}");
            assert!(s.monsters.iter().filter(|m| m.max_hp > 0).all(|m| m.max_hp > 1));
        }
        for start in [0, -2] {
            let s = fight_at(enc, &deck(&[]), "Neow's Lament", start);
            assert!(s.monsters.iter().filter(|m| m.max_hp > 0).all(|m| m.hp == m.max_hp), "{enc:?} at {start}: used up");
            assert_eq!(s.player.relics.counter(0), start);
        }
    }
    // The pack's own counter is 3.
    let s = fight(Encounter::JawWorm, &["Neow's Lament"]);
    assert_eq!((s.monsters[0].hp, s.player.relics.counter(0)), (1, 2));
    // Slime Boss at 1 HP dies to a Strike without splitting (its split
    // waits for half HP in damage(), which a dying monster skips).
    let mut s = fight(Encounter::SlimeBoss, &["Neow's Lament"]);
    play(&mut s, "Strike");
    assert!(s.is_over(), "won: {:?}", s.monsters.iter().map(|m| m.hp).collect::<Vec<_>>());
}

/// docs/specs/blocked-relics.md step 2: Paper Phrog and Odd Mushroom
/// (`StaticCondition::Holds` helper powers), against
/// powers.VulnerablePower.atDamageReceive: NORMAL damage x1.75 to a monster
/// with Paper Frog, x1.25 to the player with Odd Mushroom, rounded down
/// once at the end of the chain.
#[test]
fn vulnerable_relics() {
    // Paper Phrog: a Vulnerable monster takes x1.75 from attacks.
    let vuln = |relics: &[&str], strength: i16, weak: bool| {
        let mut s = fight(Encounter::JawWorm, relics);
        s.monsters[0].powers.add(Power::Vulnerable, 2);
        s.player.powers.add(Power::Strength, strength);
        if weak {
            s.player.powers.add(Power::Weak, 2);
        }
        s
    };
    assert_eq!(strike_damage(vuln(&[], 0, false)), 9);
    assert_eq!(strike_damage(vuln(&["Paper Phrog"], 0, false)), 10, "6 x 1.75 = 10.5");
    assert_eq!(strike_damage(vuln(&["Paper Phrog"], 2, false)), 14, "8 x 1.75");
    assert_eq!(strike_damage(vuln(&["Paper Phrog"], 0, true)), 7, "6 x 0.75 x 1.75 = 7.875");
    assert_eq!(strike_damage(vuln(&["Paper Phrog"], 1, true)), 9, "7 x 0.75 x 1.75 = 9.1875");
    // Without Vulnerable on the target, nothing changes; the card's shown
    // damage leaves the target out, as the game's card text does.
    assert_eq!(strike_damage(fight(Encounter::JawWorm, &["Paper Phrog"])), 6);
    let s = vuln(&["Paper Phrog"], 0, false);
    assert_eq!(s.shown_damage(6, 1), 6);
    assert_eq!(s.attack_damage(Who::Player, Who::Monster(0), 6), 10);
    assert_eq!(s.interpret_attack_damage(Who::Player, Who::Monster(0), 6), 10);
    // The player's own Vulnerable keeps x1.5 under Paper Phrog.
    let mut s = fight(Encounter::JawWorm, &["Paper Phrog"]);
    s.player.powers.add(Power::Vulnerable, 2);
    assert_eq!(s.attack_damage(Who::Monster(0), Who::Player, 11), 16);

    // Odd Mushroom: the Vulnerable player takes x1.25.
    let mush = |relics: &[&str], weak: bool| {
        let mut s = fight(Encounter::JawWorm, relics);
        s.player.powers.add(Power::Vulnerable, 2);
        if weak {
            s.monsters[0].powers.add(Power::Weak, 2);
        }
        s
    };
    for (relics, weak, base, want) in [
        (&[][..], false, 9, 13),
        (&["Odd Mushroom"][..], false, 9, 11),
        // The research's check: floor(9 x 0.75 x 1.25) = 8.
        (&["Odd Mushroom"][..], true, 9, 8),
        (&["Odd Mushroom"][..], true, 11, 10),
        (&["Odd Mushroom", "Paper Phrog"][..], false, 11, 13),
    ] {
        let s = mush(relics, weak);
        assert_eq!(s.attack_damage(Who::Monster(0), Who::Player, base), want, "{relics:?} weak {weak} base {base}");
        assert_eq!(s.interpret_attack_damage(Who::Monster(0), Who::Player, base), want);
    }
    // Without Vulnerable on the player: x1 (the helper is held, no change).
    let s = fight(Encounter::JawWorm, &["Odd Mushroom"]);
    assert_eq!(s.attack_damage(Who::Monster(0), Who::Player, 11), 11);
    // A monster with Vulnerable still takes x1.5 from the player.
    let mut s = fight(Encounter::JawWorm, &["Odd Mushroom"]);
    s.monsters[0].powers.add(Power::Vulnerable, 1);
    assert_eq!(strike_damage(s), 9);
    // Played out: Jaw Worm's opening Chomp (11) on a Vulnerable player
    // holding the Mushroom, with the worm Weak: 11 x 0.75 x 1.25 = 10.3.
    for (relics, weak, lost) in [(&[][..], false, 16), (&["Odd Mushroom"][..], false, 13), (&["Odd Mushroom"][..], true, 10)] {
        let mut s = mush(relics, weak);
        let before = s.player.hp;
        next_turn(&mut s);
        assert_eq!(before - s.player.hp, lost, "{relics:?} weak {weak}");
    }
}

/// docs/specs/blocked-relics.md step 3: `Trigger::Shuffled`, the game's
/// `onShuffle`, from `EmptyDeckShuffleAction`'s constructor. Sundial
/// (`relics/Sundial.java`: counter +1, at 3 back to 0 and `GainEnergyAction`
/// 2) and The Abacus (`relics/Abacus.java`, ID "TheAbacus":
/// `GainBlockAction` 6, raw).
const IRONCLAD: &str = include_str!("../../content/packs/act1-ironclad.json");

/// A fight against Cultist (no attack on turn 1) with `cards` (5 Defends
/// added, so the opening draw doesn't shuffle) and one relic at `counter`;
/// returns the state and the cards' ids.
fn shuffle_fight(cards: &[&str], relic_name: &str, counter: i16) -> (CombatState, Vec<CardId>) {
    load_pack(IRONCLAD).unwrap();
    load_pack(PACK).unwrap();
    let mut given = relics_named(&[&format!("gen:{relic_name}")]).unwrap();
    given[0].1.counter = counter;
    let mut cards = cards.to_vec();
    cards.extend(["Defend"; 5]);
    let (ids, b) = bind(&cards).unwrap();
    let s = CombatState::new_bound_with(Character::Ironclad, &ids, &b, 50, 80, Encounter::Cultist, &given, &mut Rng::new(11));
    assert_eq!((s.player.block, s.player.relics.counter(0)), (0, counter));
    (s, ids)
}

/// Turn 2's draw of 5 with an empty hand and these piles: the player's
/// block and energy, the relic's counter and the hand's size after it.
fn turn_two_draw(relic_name: &str, counter: i16, draw: usize, discard: usize) -> (i16, i16, i16, usize) {
    let (mut s, _) = shuffle_fight(&["Strike", "Defend"], relic_name, counter);
    let (strike, defend) = (CardId::from_name("Strike").unwrap(), CardId::from_name("Defend").unwrap());
    s.hand = Hand::default();
    s.set_draw(Pile::from_cards(&vec![strike; draw]));
    s.set_discard(Pile::from_cards(&vec![defend; discard]));
    next_turn(&mut s);
    (s.player.block, s.player.energy as i16, s.player.relics.counter(0), s.hand.len())
}

#[test]
fn shuffle_relics_on_the_draw() {
    // DrawCardAction.update: amount (capped by the hand) > drawPile.size
    // with draw + discard > 0 queues EmptyDeckShuffleAction, even with an
    // empty discard; its follow-up DrawCardAction(amount - draw) is built
    // with shuffleCheck false and checks again, so a draw past both piles
    // with a non-empty discard shuffles twice.
    let abacus = |d, dd| {
        let (block, _, _, hand) = turn_two_draw("The Abacus", 0, d, dd);
        (block, hand)
    };
    assert_eq!(abacus(5, 3), (0, 5), "the draw pile holds the 5");
    assert_eq!(abacus(2, 5), (6, 5), "one shuffle");
    assert_eq!(abacus(2, 0), (6, 2), "an empty discard still shuffles");
    assert_eq!(abacus(2, 2), (12, 4), "past both piles: two shuffles");
    assert_eq!(abacus(0, 3), (12, 3), "past both piles from an empty draw pile");
    assert_eq!(abacus(0, 0), (0, 0), "no card left: no shuffle");
    assert_eq!(abacus(0, 5), (6, 5));
    // Sundial: +1 per shuffle, at 3 +2 energy and back to 0. Two shuffles
    // run the hooks twice, so 2 -> 3 (energy) -> 0 -> 1.
    let sundial = |counter, d, dd| {
        let (_, energy, counter, _) = turn_two_draw("Sundial", counter, d, dd);
        (energy, counter)
    };
    assert_eq!(sundial(0, 2, 5), (3, 1));
    assert_eq!(sundial(1, 5, 3), (3, 1), "no shuffle");
    assert_eq!(sundial(2, 2, 5), (5, 0));
    assert_eq!(sundial(1, 2, 2), (5, 0), "two shuffles: 1 -> 2 -> 3");
    assert_eq!(sundial(2, 2, 2), (5, 1), "two shuffles: 2 -> 3, then 0 -> 1");
    // A request merged into a pending draw counts against the piles as
    // they are once the pending part is drawn (Bag of Preparation's 2
    // after the opening 5, each its own DrawCardAction in the game).
    let opening = |n: usize| {
        let mut cards = vec!["Strike"; n];
        cards.push("Defend");
        load_pack(PACK).unwrap();
        let given = relics_named(&["gen:Bag of Preparation", "gen:Sundial"]).unwrap();
        let (ids, b) = bind(&cards).unwrap();
        let s = CombatState::new_bound_with(Character::Ironclad, &ids, &b, 50, 80, Encounter::Cultist, &given, &mut Rng::new(11));
        (s.hand.len(), s.player.relics.counter(1))
    };
    assert_eq!(opening(6), (7, 0), "7 cards: 5, then 2, no shuffle");
    assert_eq!(opening(5), (6, 1), "6 cards: the 2 find 1, one shuffle");
    assert_eq!(opening(3), (4, 1), "4 cards: the opening 5 shuffles, the 2 find none");
}

#[test]
fn shuffle_relics_on_havoc() {
    // PlayTopCardAction: an empty draw pile with a card in the discard
    // queues EmptyDeckShuffleAction.
    for (draw, block) in [(1, 0), (0, 6)] {
        let (mut s, ids) = shuffle_fight(&["gen:Havoc", "Strike"], "The Abacus", 0);
        s.hand = Hand::from_cards(&[ids[0]]);
        s.set_draw(Pile::from_cards(&vec![ids[1]; draw]));
        s.set_discard(Pile::from_cards(&vec![ids[1]; 1 - draw]));
        s.player.energy = 3;
        s.step(Action::Play { card: ids[0], target: None }, &mut Rng::new(1)).unwrap();
        assert_eq!(s.player.block, block, "draw pile {draw}");
    }
}

#[test]
fn shuffled_hooks_load_only_on_relics_and_only_block_energy_counters() {
    let power = r#"{"version": 2, "powers": [{"id": "pw-Shuf", "hooks": [{"trigger": "Shuffled", "condition": "Always", "effects": [{"Block": 1}]}]}]}"#;
    assert!(load_pack(power).unwrap_err().contains("relic's"));
    let draws = r#"{"version": 2, "relics": [{"id": "rl-Shuf", "rarity": "common", "hooks": [{"trigger": "Shuffled", "condition": "Always", "effects": [{"Draw": 1}]}]}]}"#;
    assert!(load_pack(draws).unwrap_err().contains("Shuffled"));
}

/// Blocked relics step 5 (docs/specs/blocked-relics.md): random work a
/// hook owes waits in `CombatState::owed` and is paid, as its own chance
/// event, before anything else goes on.
///
/// A fight against Jaw Worm (Chomp, 11, on turn 1) with `cards` and these
/// relics, the Ironclad pack loaded (Dead Branch's class pool); the state
/// and the cards' ids.
fn owed_fight(cards: &[&str], relics: &[&str], seed: u64) -> (CombatState, Vec<CardId>) {
    owed_fight_as(Character::Ironclad, cards, relics, seed)
}

fn owed_fight_as(character: Character, cards: &[&str], relics: &[&str], seed: u64) -> (CombatState, Vec<CardId>) {
    load_pack(IRONCLAD).unwrap();
    load_pack(PACK).unwrap();
    let names: Vec<String> = relics.iter().map(|r| format!("gen:{r}")).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    let (ids, b) = bind(cards).unwrap();
    let s = CombatState::new_bound_with(character, &ids, &b, 50, 80, Encounter::JawWorm, &relics_named(&refs).unwrap(), &mut Rng::new(seed));
    (s, ids)
}

/// The Ironclad pool's index and cards in this fight.
fn ironclad_pool(s: &CombatState) -> (u8, Vec<CardId>) {
    let i = (0..).find(|&i| sts_engine::registry::pool_def(i).unwrap().name == "Ironclad").unwrap();
    (i, sts_engine::registry::pool_cards(&s.binding, i, None).to_vec())
}

/// Plays card `c` (energy topped up), stopping at the first chance event.
fn play_id(s: &mut CombatState, c: CardId) {
    s.player.energy = 3;
    let target = if s.binding.def(c).targeted() { Some(0) } else { None };
    s.apply_action(Action::Play { card: c, target }).unwrap();
}

/// Ends the turn and resolves chance events until `stop` holds for the
/// pending one, which is left pending (or none is pending).
fn end_turn_until(s: &mut CombatState, rng: &mut Rng, stop: impl Fn(&CombatState) -> bool) {
    s.apply_action(Action::EndTurn).unwrap();
    while s.pending.is_some() && !stop(s) {
        s.resolve_chance(rng);
    }
}

/// Dead Branch (`relics/DeadBranch.java`, rare): `onExhaust`, while a
/// monster lives, `MakeTempCardInHandAction(returnTrulyRandomCardInCombat())`:
/// one card of the player's class pools (srcCommon + srcUncommon + srcRare,
/// HEALING left out), every card alike, per card exhausted.
#[test]
fn dead_branch() {
    load_pack(IRONCLAD).unwrap();
    load_pack(PACK).unwrap();
    assert_eq!(relic("gen:Dead Branch").unwrap().rarity, Rarity::Rare);
    // Slimed exhausts when played: one roll of the class pool into the hand.
    let (mut s, ids) = owed_fight(&["Slimed", "Strike", "Defend", "Defend", "Defend"], &["Dead Branch"], 1);
    let (pool, cards) = ironclad_pool(&s);
    assert!(!cards.iter().any(|&c| ["Feed", "Reaper"].contains(&s.binding.def(c).name)), "HEALING cards left out");
    s.hand = Hand::from_cards(&[ids[0], ids[1]]);
    play_id(&mut s, ids[0]);
    assert_eq!(s.pending, Some(ChanceEvent::MakeRandom { pool, ty: None, pile: sts_engine::effects::PileKind::Hand, zero_cost: false, free: false, up: false }));
    let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(1000) else { panic!("listed") };
    assert_eq!(v.len(), cards.len(), "every pool card, alike");
    for (p, t) in &v {
        assert!((p - 1.0 / cards.len() as f64).abs() < 1e-12);
        assert_eq!(t.hand.len(), 2);
        assert_eq!(t.hand.count(ids[1]), 1);
        assert_eq!(t.pending, None);
    }
    // Second Wind exhausts two Defends: two rolls, one after the other.
    let (mut s, ids) = owed_fight(&["gen:Second Wind", "Strike", "Defend", "Defend", "Defend"], &["Dead Branch"], 2);
    s.hand = Hand::from_cards(&[ids[0], ids[1], ids[2], ids[2]]);
    play_id(&mut s, ids[0]);
    let mut rng = Rng::new(5);
    assert!(matches!(s.pending, Some(ChanceEvent::MakeRandom { .. })));
    s.resolve_chance(&mut rng);
    assert!(matches!(s.pending, Some(ChanceEvent::MakeRandom { .. })), "the second card's roll");
    s.resolve_chance(&mut rng);
    assert_eq!(s.pending, None);
    assert_eq!(s.hand.len(), 3, "Strike and the two made");
    assert_eq!(s.exhaust().len(), 2);
    // At turn end an ethereal card exhausts before the hand is discarded,
    // and Dead Branch's add is queued behind the discard
    // (AbstractRoom.endTurn): the card stays in hand into the next turn.
    // It lands before the monsters act.
    let (mut s, ids) = owed_fight(&["Dazed", "Strike", "Defend", "Defend", "Defend", "Defend"], &["Dead Branch"], 3);
    s.hand = Hand::from_cards(&[ids[0], ids[1]]);
    s.set_draw(Pile::from_cards(&[ids[2], ids[2], ids[2], ids[2], ids[2]]));
    s.set_discard(Pile::default());
    let mut rng = Rng::new(7);
    s.apply_action(Action::EndTurn).unwrap();
    assert!(matches!(s.pending, Some(ChanceEvent::MakeRandom { .. })));
    assert_eq!(s.stage, Stage::EndingTurn { part: 2 });
    assert_eq!((s.player.hp, s.hand.len(), s.discard().len()), (50, 0, 1), "discarded; Chomp still to come");
    s.resolve_chance(&mut rng);
    assert_eq!(s.player.hp, 39);
    s.advance(&mut rng);
    assert_eq!(s.stage, Stage::PlayerTurn);
    assert_eq!(s.hand.len(), 6, "the made card and turn 2's 5");
    assert_eq!(s.hand.count(ids[2]), 5);
    // A Silent fight has no Silent pool loaded: nothing is made.
    let (mut s, ids) = owed_fight_as(Character::Silent, &["Slimed", "Strike", "Defend", "Defend", "Defend"], &["Dead Branch"], 1);
    s.hand = Hand::from_cards(&[ids[0], ids[1]]);
    play_id(&mut s, ids[0]);
    assert_eq!((s.pending, s.hand.len()), (None, 1));
}

/// Mummified Hand (`relics/MummifiedHand.java`, uncommon): `onUseCard` of a
/// POWER picks `cardRandomRng.random(size - 1)` among the hand cards with
/// `cost > 0 && costForTurn > 0 && !freeToPlayOnce` and sets its
/// `costForTurn` to 0 at once, before the Power's own actions; no fallback.
#[test]
fn mummified_hand() {
    let (s, _) = owed_fight(&["Strike"], &["Mummified Hand"], 1);
    assert_eq!(relic("gen:Mummified Hand").unwrap().rarity, Rarity::Uncommon);
    drop(s);
    let cards = ["Inflame", "Strike", "Bash", "Defend", "Anger", "Whirlwind", "Dazed"];
    let (mut s, ids) = owed_fight(&cards, &["Mummified Hand"], 1);
    let [inflame, strike, bash, defend, anger, whirlwind, dazed] = ids[..] else { unreachable!() };
    s.hand = Hand::from_cards(&[inflame, strike, strike, bash, defend, anger, whirlwind, dazed]);
    play_id(&mut s, inflame);
    assert_eq!(s.pending, Some(ChanceEvent::RandomFreeTurn));
    assert_eq!(s.player.powers.get(Power::Strength), 0, "picked before Inflame's Strength");
    let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(10) else { panic!("listed") };
    let got: Vec<(f64, CardId)> = v.iter().map(|(p, t)| (*p, t.free_in_hand.iter().next().unwrap())).collect();
    assert_eq!(got.len(), 3, "not Anger (cost 0), Whirlwind (X) or Dazed: {got:?}");
    for (p, c) in got {
        let want = if c == strike { 0.5 } else { 0.25 };
        assert!([strike, bash, defend].contains(&c));
        assert!((p - want).abs() < 1e-12, "{c:?} {p}");
    }
    for (_, t) in &v {
        assert_eq!((t.free_in_hand.len(), t.player.powers.get(Power::Strength)), (1, 2));
    }
    // One distinct candidate: marked at once. Not on a non-Power card.
    // Brutality costs 0, so its other copies never qualify.
    let (mut s, ids) = owed_fight(&["Brutality", "Bash", "Strike"], &["Mummified Hand"], 1);
    s.hand = Hand::from_cards(&[ids[0], ids[0], ids[0], ids[1], ids[1], ids[2]]);
    play_id(&mut s, ids[2]);
    assert!(s.free_in_hand.is_empty());
    play_id(&mut s, ids[0]);
    assert_eq!((s.pending, s.free_in_hand.count(ids[1])), (None, 1));
    play_id(&mut s, ids[0]);
    assert_eq!((s.pending, s.free_in_hand.count(ids[1])), (None, 2));
    // Every copy already costs 0 this turn: nothing (no fallback tier).
    play_id(&mut s, ids[0]);
    assert_eq!((s.pending, s.free_in_hand.count(ids[1])), (None, 2));
}

/// Warped Tongs (`relics/WarpedTongs.java`, special): `atTurnStartPostDraw`
/// queues `UpgradeRandomCardAction`: among the hand cards with
/// `canUpgrade() && type != STATUS`, one alike (`CardGroup.shuffle`, then
/// the first), upgraded for the combat; nothing with none.
#[test]
fn warped_tongs() {
    let (_, _) = owed_fight(&["Strike"], &["Warped Tongs"], 1);
    assert_eq!(relic("gen:Warped Tongs").unwrap().rarity, Rarity::Event);
    let up = |s: &CombatState, c: CardId| sts_engine::registry::upgraded(&s.binding, c).unwrap();
    // Turn 2's draw is the whole draw pile: 3 Strikes, Bash, Defend.
    let (mut s, ids) = owed_fight(&["Strike", "Bash", "Defend", "Dazed"], &["Warped Tongs"], 1);
    let [strike, bash, defend, dazed] = ids[..] else { unreachable!() };
    s.hand = Hand::default();
    s.set_draw(Pile::from_cards(&[strike, strike, strike, bash, defend]));
    s.set_discard(Pile::default());
    let mut rng = Rng::new(3);
    end_turn_until(&mut s, &mut rng, |s| s.pending == Some(ChanceEvent::RandomUpgrade));
    assert_eq!((s.stage, s.hand.len()), (Stage::PlayerTurn, 5));
    let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(10) else { panic!("listed") };
    assert_eq!(v.len(), 3);
    for (p, t) in &v {
        let (c, want) = [(strike, 0.6), (bash, 0.2), (defend, 0.2)].into_iter().find(|&(c, _)| t.hand.count(up(&s, c)) == 1).unwrap();
        assert!((p - want).abs() < 1e-12, "{c:?} {p}");
        assert_eq!(t.hand.len(), 5);
    }
    // A Status is never picked; one candidate is upgraded at once; an
    // upgraded Strike (at its max level) can't be.
    let (mut s, _) = owed_fight(&["Strike", "Bash", "Defend", "Dazed"], &["Warped Tongs"], 1);
    s.hand = Hand::default();
    s.set_draw(Pile::from_cards(&[dazed, dazed, strike, up(&s, bash), up(&s, defend)]));
    s.set_discard(Pile::default());
    end_turn_until(&mut s, &mut rng, |_| false);
    assert_eq!((s.hand.count(up(&s, strike)), s.hand.count(dazed), s.hand.count(strike)), (1, 2, 0));
    // Brutality's draw (atStartOfTurnPostDraw powers, after the relics')
    // is queued behind the upgrade: the upgrade picks from turn 2's 5.
    let (mut s, _) = owed_fight(&["Strike", "Bash", "Defend", "Dazed"], &["Warped Tongs"], 1);
    s.player.powers.add(Power::Brutality, 1);
    s.hand = Hand::default();
    s.set_draw(Pile::from_cards(&[strike, strike, strike, bash, defend, defend]));
    s.set_discard(Pile::default());
    end_turn_until(&mut s, &mut rng, |s| s.pending == Some(ChanceEvent::RandomUpgrade));
    assert_eq!((s.pending, s.hand.len()), (Some(ChanceEvent::RandomUpgrade), 5));
    s.advance(&mut rng);
    assert_eq!(s.hand.len(), 6);
    // Gambling Chip's pick (its own GamblingChipAction, queued in relic
    // order): before the upgrade when Gambling Chip comes first, after it
    // when Warped Tongs does.
    for (relics, upgraded_at_pick) in [(["Gambling Chip", "Warped Tongs"], 0), (["Warped Tongs", "Gambling Chip"], 1)] {
        let cards = ["Strike", "Strike", "Strike", "Strike", "Strike", "Bash", "Bash", "Bash", "Bash", "Bash"];
        let (mut s, ids) = owed_fight(&cards, &relics, 4);
        assert!(matches!(s.stage, Stage::RelicPick { pick: Some(_), .. }), "{relics:?}: {:?}", s.stage);
        let n_up = |s: &CombatState| s.hand.count(up(s, ids[0])) + s.hand.count(up(s, ids[5]));
        assert_eq!(n_up(&s), upgraded_at_pick, "{relics:?}");
        s.step(Action::Done, &mut Rng::new(4)).unwrap();
        s.advance(&mut Rng::new(4));
        assert_eq!((s.stage, n_up(&s)), (Stage::PlayerTurn, 1), "{relics:?}");
    }
}

/// Random work in a power's hook (any hook may owe it): a pack power's
/// `UpgradeRandom` runs once per stack; owed at turn end, it is paid before
/// the hand is discarded (`Stage::EndingTurn` part 1), and such a state
/// round-trips through the codec. The loader keeps the rest refused.
#[test]
fn owed_work_in_any_hook() {
    load_pack(PACK).unwrap();
    let pack = r#"{"version": 2,
        "powers": [{"id": "ow-Tongs", "hooks": [{"trigger": "OwnerTurnStartPostDraw", "condition": "Always", "effects": ["UpgradeRandom"]}]}],
        "relics": [{"id": "ow-Twice", "rarity": "common", "powers": [{"power": "ow-Tongs", "amount": 2}]},
                   {"id": "ow-AtEnd", "rarity": "common", "hooks": [{"trigger": "OwnerTurnEnd", "condition": "Always", "effects": ["UpgradeRandom", "UpgradeRandom"]}]}]}"#;
    load_pack(pack).unwrap();
    let strike = CardId::from_name("Strike").unwrap();
    let bash = CardId::from_name("Bash").unwrap();
    let start = |relic: &str| {
        let (ids, b) = bind(&["Strike", "Bash", "Defend"]).unwrap();
        CombatState::new_bound_with(Character::Ironclad, &ids, &b, 50, 80, Encounter::JawWorm, &relics_named(&[relic]).unwrap(), &mut Rng::new(1))
    };
    let mut s = start("gen:ow-Twice");
    let strike_up = sts_engine::registry::upgraded(&s.binding, strike).unwrap();
    s.hand = Hand::default();
    s.set_draw(Pile::from_cards(&[strike; 5]));
    s.set_discard(Pile::default());
    let mut rng = Rng::new(2);
    end_turn_until(&mut s, &mut rng, |_| false);
    assert_eq!(s.hand.count(strike_up), 2, "two stacks, two upgrades");
    // At turn end: the first upgrade pauses End Turn before the discard.
    let mut s = start("gen:ow-AtEnd");
    s.hand = Hand::from_cards(&[strike, strike, bash]);
    s.apply_action(Action::EndTurn).unwrap();
    assert_eq!((s.stage, s.pending, s.hand.len()), (Stage::EndingTurn { part: 1 }, Some(ChanceEvent::RandomUpgrade), 3));
    assert_eq!(s.owed.iter().map(|e| e.n).collect::<Vec<_>>(), vec![1]);
    assert!(!s.has_generated());
    let bytes = sts_engine::codec::encode(&s);
    assert_eq!(sts_engine::codec::decode(&bytes), s, "EndingTurn, RandomUpgrade and the owed entry round-trip");
    s.advance(&mut rng);
    assert_eq!(s.stage, Stage::PlayerTurn);
    let ups = [sts_engine::registry::upgraded(&s.binding, strike).unwrap(), sts_engine::registry::upgraded(&s.binding, bash).unwrap()];
    let piles = [s.hand.view(), s.draw(), s.discard(), s.exhaust()];
    assert_eq!(piles.iter().map(|p| p.len()).sum::<usize>(), 3);
    assert_eq!(piles.iter().map(|p| ups.iter().map(|&c| p.count(c) as usize).sum::<usize>()).sum::<usize>(), 2, "both upgrades");
    // The loader.
    let bad = |hook: &str| load_pack(&format!(r#"{{"version": 2, "relics": [{{"id": "ow-bad", "rarity": "common", "hooks": [{hook}]}}]}}"#)).unwrap_err();
    assert!(bad(r#"{"trigger": "CardExhausted", "condition": "Always", "effects": [{"MakeRandom": {"pool": "Class", "n": 1, "pile": "Hand", "match_level": true}}]}"#).contains("match_level"));
    assert!(bad(r#"{"trigger": "CardExhausted", "condition": "Always", "effects": ["ExhaustRandom"]}"#).contains("can't run in a hook"));
    let power = r#"{"version": 2, "powers": [{"id": "ow-bad-power", "hooks": [{"trigger": "CardExhausted", "condition": "Always", "effects": [{"MakeRandom": {"pool": "Class", "n": 1, "pile": "Hand"}}]}]}]}"#;
    assert!(load_pack(power).unwrap_err().contains("relic's hook"));
    let card = r#"{"version": 2, "cards": [{"id": "ow-bad-card", "cost": 1, "type": "Skill", "effects": [{"MakeRandom": {"pool": "Class", "n": 1, "pile": "Hand"}}]}]}"#;
    assert!(load_pack(card).unwrap_err().contains("Class"));
}

/// Owed work and the rest of the engine (step 5's review): a fight ended by
/// a later hook of the same pass drops what was owed; a search leaf after
/// End Turn lies past the owed work, where the monsters have acted; and a
/// pack power a relic's hook applies has its pool's cards bound.
#[test]
fn owed_work_at_the_edges() {
    use sts_engine::search::{search, Evaluator, Heuristic, SearchConfig};
    // Dead Branch owes a card; Charon's Ashes, next in the pass, kills.
    let (mut s, ids) = owed_fight(&["Slimed", "Strike", "Defend", "Defend", "Defend"], &["Dead Branch", "Charon's Ashes"], 1);
    s.monsters[0].hp = 2;
    s.hand = Hand::from_cards(&[ids[0], ids[1]]);
    play_id(&mut s, ids[0]);
    assert!(s.won());
    assert!(s.owed.is_empty(), "{:?}", s.owed);
    assert_eq!(s.pending, None);
    // Every End Turn leaf has had the monsters act (as without the relic).
    struct Record(Vec<CombatState>);
    impl Evaluator for Record {
        fn evaluate(&mut self, states: &[CombatState]) -> Vec<f32> {
            self.0.extend_from_slice(states);
            Heuristic.evaluate(states)
        }
    }
    let (mut s, ids) = owed_fight(&["Dazed", "Strike", "Defend", "Defend", "Defend", "Defend"], &["Dead Branch"], 3);
    s.hand = Hand::from_cards(&[ids[0], ids[1]]);
    let mut rec = Record(Vec::new());
    search(&s, &mut rec, &SearchConfig::default());
    assert!(!rec.0.is_empty());
    assert!(rec.0.iter().all(|t| !matches!(t.stage, Stage::EndingTurn { .. })), "no leaf before the monsters act");
    // A relic's hook applies a pack power whose hook makes Ironclad cards.
    load_pack(IRONCLAD).unwrap();
    let pack = r#"{"version": 2,
        "powers": [{"id": "ow-Mag", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "effects": [{"MakeRandom": {"pool": "Ironclad", "n": 1, "pile": "Hand"}}]}]}],
        "relics": [{"id": "ow-GiveMag", "rarity": "common", "hooks": [{"trigger": "CombatStart", "condition": "Always", "effects": [{"Apply": {"power": "ow-Mag", "amount": 1, "target": "Me"}}]}]}]}"#;
    load_pack(pack).unwrap();
    let (ids, b) = bind(&["Strike", "Defend"]).unwrap();
    let mut s = CombatState::new_bound_with(Character::Ironclad, &ids, &b, 50, 80, Encounter::JawWorm, &relics_named(&["gen:ow-GiveMag"]).unwrap(), &mut Rng::new(1));
    let mut rng = Rng::new(2);
    s.step(Action::EndTurn, &mut rng).unwrap();
    s.advance(&mut rng);
    // Turn 1's card (the hooks run after the opening draw) goes to the
    // discard pile and comes back in turn 2's draw with the deck.
    assert_eq!(s.hand.len(), 4, "turn 2: its made card, then the 3 cards drawn");
}

/// docs/specs/blocked-relics.md step 4: a fight holding `relics` and
/// `potions` (by game name), the Ironclad and potion packs loaded.
fn potion_fight(enc: Encounter, hp: i16, relics: &[&str], potions: &[&str]) -> CombatState {
    load_pack(include_str!("../../content/packs/act1-ironclad.json")).unwrap();
    load_pack(PACK).unwrap();
    load_pack(include_str!("../../content/packs/act1-potions.json")).unwrap();
    let mut s = fight_with(enc, &deck(&[]), hp, relics, 11);
    let names: Vec<String> = potions.iter().map(|p| format!("gen:{p}")).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    s.give_potions(&sts_engine::registry::potions_named(&refs).unwrap()).unwrap();
    s
}

/// Uses the potion in slot `slot` (at monster 0 when it takes a target).
fn use_potion(s: &mut CombatState, slot: u8) {
    let a = *s.legal_actions().iter().find(|a| matches!(a, Action::UsePotion { slot: x, .. } if *x == slot)).expect("the potion is usable");
    s.step(a, &mut Rng::new(1)).unwrap();
}

/// Toy Ornithopter (`relics/ToyOrnithopter.java` `onUsePotion`: in combat
/// `addToBot(HealAction(5))`, called from `PotionPopUp` right after
/// `potion.use`): heals 5 once the potion has resolved, also when the
/// potion ended the fight (`GameActionManager.clearPostCombatActions`
/// keeps a `HealAction`; `AbstractMonster.die` runs `endBattle` first),
/// never for Fairy in a Bottle's save.
#[test]
fn toy_ornithopter() {
    // Block Potion: 12 block and 5 HP.
    let mut s = potion_fight(Encounter::JawWorm, 50, &["Toy Ornithopter"], &["Block Potion"]);
    use_potion(&mut s, 0);
    assert_eq!((s.player.hp, s.player.block, s.stage), (55, 12, Stage::PlayerTurn));
    // Capped at max HP.
    let mut s = potion_fight(Encounter::JawWorm, 78, &["Toy Ornithopter"], &["Block Potion"]);
    use_potion(&mut s, 0);
    assert_eq!(s.player.hp, 80);
    // Behind the potion's own actions: Elixir's pick pauses the potion, and
    // the heal waits for it.
    let mut s = potion_fight(Encounter::JawWorm, 50, &["Toy Ornithopter"], &["Elixir"]);
    use_potion(&mut s, 0);
    assert!(matches!(s.stage, Stage::UsingPotion { .. }));
    assert_eq!(s.player.hp, 50);
    while s.stage != Stage::PlayerTurn {
        let a = *s.legal_actions().last().unwrap();
        s.step(a, &mut Rng::new(1)).unwrap();
    }
    assert_eq!(s.player.hp, 55);
    // The potion kills the last monster: Burning Blood's 6 at the end of
    // the battle, then the queued 5.
    let mut s = potion_fight(Encounter::Cultist, 50, &["Toy Ornithopter"], &["Fire Potion"]);
    s.monsters[0].hp = 1;
    use_potion(&mut s, 0);
    assert!(s.won());
    assert_eq!((s.player.hp, s.won_healed.0), (61, 6));
    // Smoke Bomb's escape ends the fight as won; the heal still comes.
    let mut s = potion_fight(Encounter::Cultist, 50, &["Toy Ornithopter"], &["Smoke Bomb"]);
    use_potion(&mut s, 0);
    assert!(s.won());
    assert_eq!(s.player.hp, 61);
    // Fairy in a Bottle saves without a use (30% of 80 = 24 HP, no 5).
    let mut s = potion_fight(Encounter::Cultist, 2, &["Toy Ornithopter"], &["Fairy in a Bottle"]);
    play(&mut s, "Bloodletting");
    assert_eq!(s.player.hp, 24);
    // The bound counts the heal only while a potion is held or in use.
    let mut s = potion_fight(Encounter::Cultist, 50, &["Toy Ornithopter"], &["Block Potion"]);
    assert!(s.can_heal());
    use_potion(&mut s, 0);
    assert!(!s.can_heal());
    // Without the relic, no heal.
    let mut s = potion_fight(Encounter::JawWorm, 50, &[], &["Block Potion"]);
    use_potion(&mut s, 0);
    assert_eq!(s.player.hp, 50);
    // An OwnerUsedPotion hook heals or changes a counter only.
    load_pack(PACK).unwrap();
    let e = load_pack(r#"{"version": 2, "relics": [{"id": "up-bad", "rarity": "common", "hooks": [{"trigger": "OwnerUsedPotion", "condition": "Always", "effects": [{"Draw": 1}]}]}]}"#)
        .unwrap_err();
    assert!(e.contains("heals or changes a counter only"), "{e}");
}

/// Magic Flower (`relics/MagicFlower.java` `onPlayerHeal`: in combat
/// `MathUtils.round(amount * 1.5f)`, run by `AbstractCreature.heal` for the
/// player only, on every in-combat heal and the battle end's, Burning
/// Blood's `onVictory` included).
#[test]
fn magic_flower() {
    let s = potion_fight(Encounter::Cultist, 40, &["Magic Flower"], &[]);
    // Half rounded up.
    for (n, want) in [(0, 0), (1, 2), (2, 3), (3, 5), (5, 8), (6, 9), (12, 18), (16, 24)] {
        assert_eq!(s.player_heal(n), want, "heal {n}");
    }
    assert_eq!(s.win_heal, 6);
    assert_eq!(s.win_heal_scaled(), 9);
    // Burning Blood's 6 becomes 9; Meat on the Bone's 12 becomes 18.
    let won = |relics: &[&str]| {
        let mut s = potion_fight(Encounter::Cultist, 40, relics, &[]);
        s.monsters[0].hp = 1;
        play(&mut s, "Strike");
        assert!(s.won());
        s.player.hp
    };
    assert_eq!(won(&["Magic Flower"]), 49);
    assert_eq!(won(&["Magic Flower", "Meat on the Bone"]), 40 + 18 + 9);
    assert_eq!(won(&[]), 46);
    // Blood Vial's 2 at the fight's start becomes 3.
    assert_eq!(potion_fight(Encounter::Cultist, 40, &["Magic Flower", "Blood Vial"], &[]).player.hp, 43);
    assert_eq!(potion_fight(Encounter::Cultist, 40, &["Blood Vial"], &[]).player.hp, 42);
    // Blood Potion: 20% of 80 = 16, raised to 24.
    let mut s = potion_fight(Encounter::Cultist, 40, &["Magic Flower"], &["Blood Potion"]);
    use_potion(&mut s, 0);
    assert_eq!(s.player.hp, 64);
    // With Toy Ornithopter: 5 becomes 8.
    let mut s = potion_fight(Encounter::Cultist, 40, &["Magic Flower", "Toy Ornithopter"], &["Block Potion"]);
    use_potion(&mut s, 0);
    assert_eq!(s.player.hp, 48);
    // The saves: Lizard Tail's 40 becomes 60, Fairy in a Bottle's 24 becomes 36.
    let mut s = potion_fight(Encounter::Cultist, 2, &["Magic Flower", "Lizard Tail"], &[]);
    play(&mut s, "Bloodletting");
    assert_eq!(s.player.hp, 60);
    let mut s = potion_fight(Encounter::Cultist, 2, &["Magic Flower"], &["Fairy in a Bottle"]);
    play(&mut s, "Bloodletting");
    assert_eq!(s.player.hp, 36);
    // The bound reads the scaled combat-end heal: 30 + 9, not 30 + 6.
    let mut s = potion_fight(Encounter::Cultist, 40, &["Magic Flower"], &[]);
    s.player.hp = 30;
    assert!(!s.can_heal());
    assert!((s.upper_bound() - (2.0 - 1.0 / 100.0)).abs() < 1e-9, "{}", s.upper_bound());
    // The file's key: [numerator, denominator].
    load_pack(PACK).unwrap();
    assert_eq!(relic("gen:Magic Flower").unwrap().heal_scale, (3, 2));
    for bad in ["[3]", "[3, 0]", "1.5"] {
        let e = load_pack(&format!(r#"{{"version": 2, "relics": [{{"id": "hs-bad", "rarity": "common", "heal_scale": {bad}}}]}}"#)).unwrap_err();
        assert!(e.contains("heal_scale"), "{e}");
    }
}

/// Orange Pellets (`relics/OrangePellets.java`: an Attack, a Skill and a
/// Power played since the turn started set its three flags; the third
/// queues `RemoveDebuffsAction` behind the card and clears the flags, so a
/// second set in the same turn fires again; `atTurnStart` clears them.
/// `RemoveDebuffsAction`: every power of type `DEBUFF` on the player).
#[test]
fn orange_pellets() {
    let debuffed = || {
        let mut s = potion_fight(Encounter::Cultist, 50, &["Orange Pellets"], &[]);
        for (p, n) in [(Power::Weak, 2), (Power::Vulnerable, 2), (Power::Frail, 2), (Power::Strength, -3), (Power::Dexterity, 2)] {
            s.player.powers.add(p, n);
        }
        s
    };
    let debuffs = |s: &CombatState| [Power::Weak, Power::Vulnerable, Power::Frail].map(|p| s.player.powers.get(p));
    // Attack, Skill, then Power: Inflame's +2 lands first (Strength -1, a
    // debuff, removed); Dexterity +2 is a buff and stays.
    let mut s = debuffed();
    s.monsters[0].powers.add(Power::Weak, 1);
    play(&mut s, "Strike");
    play(&mut s, "Defend");
    assert_eq!(debuffs(&s), [2, 2, 2]);
    assert_eq!(s.player.relics.counter(0), 3);
    play(&mut s, "Inflame");
    assert_eq!(debuffs(&s), [0, 0, 0]);
    assert_eq!((s.player.powers.get(Power::Strength), s.player.powers.get(Power::Dexterity)), (0, 2));
    assert_eq!(s.player.relics.counter(0), 0);
    // A monster's debuffs stay.
    assert_eq!(s.monsters[0].powers.get(Power::Weak), 1);
    // Any order; a repeated type adds nothing.
    let mut s = debuffed();
    for c in ["Inflame", "Bash", "Strike"] {
        play(&mut s, c);
    }
    assert_eq!(debuffs(&s), [2, 2, 2]);
    play(&mut s, "Defend");
    assert_eq!(debuffs(&s), [0, 0, 0]);
    // A second set in the same turn fires again.
    s.player.powers.add(Power::Weak, 1);
    play(&mut s, "Strike");
    play(&mut s, "Defend");
    assert_eq!(s.player.powers.get(Power::Weak), 1);
    play(&mut s, "Inflame");
    assert_eq!(s.player.powers.get(Power::Weak), 0);
    // The turn start clears the flags: Attack and Skill on turn 1, the
    // Power on turn 2 removes nothing.
    let mut s = debuffed();
    s.player.powers.add(Power::Weak, 5);
    play(&mut s, "Strike");
    play(&mut s, "Defend");
    next_turn(&mut s);
    assert_eq!(s.player.relics.counter(0), 0);
    play(&mut s, "Inflame");
    assert!(s.player.powers.get(Power::Weak) > 0);
    // Flex's LoseStrength is a debuff: removed, the Strength kept; Snecko
    // Eye's Confused too.
    let mut s = potion_fight(Encounter::Cultist, 50, &["Snecko Eye", "Orange Pellets"], &[]);
    let confused = gen_power(&s, "Confused");
    assert_eq!(s.player.powers.get(confused), 1);
    s.player.powers.add(Power::Strength, 2);
    s.player.powers.add(Power::LoseStrength, 2);
    for c in ["Strike", "Defend", "Inflame"] {
        play(&mut s, c);
    }
    assert_eq!((s.player.powers.get(confused), s.player.powers.get(Power::LoseStrength), s.player.powers.get(Power::Strength)), (0, 0, 4));
}

// ---- docs/specs/blocked-relics.md step 6: curses, Blue Candle, Medical Kit, Du-Vu Doll ----

const COLORLESS_PACK: &str = include_str!("../../content/packs/act1-colorless.json");

/// The curses an Ironclad run can hold (`cards.curses.*` but Pride, which
/// no event, relic or `CardLibrary.getCurse` gives).
const CURSES: [&str; 13] = [
    "Ascender's Bane", "Clumsy", "Curse of the Bell", "Decay", "Doubt", "Injury", "Necronomicurse", "Normality", "Pain", "Parasite", "Regret",
    "Shame", "Writhe",
];

/// A Cultist fight (turn 1: Incantation, no attack) with these pack cards
/// in the deck and these relics.
fn curse_fight(extra: &[&str], relics: &[&str]) -> CombatState {
    load_pack(include_str!("../../content/packs/act1-ironclad.json")).unwrap();
    load_pack(COLORLESS_PACK).unwrap();
    let extra: Vec<String> = extra.iter().map(|c| format!("gen:{c}")).collect();
    let refs: Vec<&str> = extra.iter().map(String::as_str).collect();
    fight_with(Encounter::Cultist, &deck(&refs), 50, relics, 11)
}

/// The fight's id of pack card `name`; one copy added to the hand.
fn to_hand(s: &mut CombatState, name: &str) -> CardId {
    let c = bound_card(s, name);
    s.hand.add(c, 1);
    c
}

fn bound_card(s: &CombatState, name: &str) -> CardId {
    let full = format!("gen:{name}");
    s.hand.iter().chain(s.draw().iter()).chain(s.discard().iter()).chain(s.exhaust().iter()).map(|(c, _)| c).find(|&c| s.binding.def(c).name == full).unwrap()
}

fn can_play_card(s: &CombatState, c: CardId) -> bool {
    s.legal_actions().iter().any(|a| matches!(*a, Action::Play { card, .. } if card == c))
}

/// Every curse loads as the game's class: type CURSE, cost -2 (unplayable),
/// the flags its constructor sets; never upgraded, never in a pool.
#[test]
fn curses_load_as_their_classes() {
    let s = curse_fight(&CURSES, &[]);
    for name in CURSES {
        let d = s.binding.def(bound_card(&s, name));
        assert_eq!(d.ty, CardType::Curse, "{name}");
        assert!(d.unplayable(), "{name}");
        assert!(!sts_engine::registry::general_upgrade(d), "{name}");
        assert_eq!(d.ethereal, matches!(name, "Ascender's Bane" | "Clumsy"), "{name}");
        assert_eq!(d.innate, name == "Writhe", "{name}");
        assert_eq!(d.plays_per_turn, if name == "Normality" { 3 } else { 0 }, "{name}");
        assert_eq!(!d.other_played.is_empty(), name == "Pain", "{name}");
        assert_eq!(!d.turn_end.is_empty(), matches!(name, "Decay" | "Doubt" | "Regret" | "Shame"), "{name}");
        assert_eq!(!d.exhausted.is_empty(), name == "Necronomicurse", "{name}");
    }
    let pools = COLORLESS_PACK.lines().find(|l| l.starts_with("\"pools\"")).unwrap();
    assert!(CURSES.iter().all(|c| !pools.contains(&format!("\"{c}\""))), "no curse in a pool");
    // Without a rule none is playable.
    let mut s = curse_fight(&CURSES, &[]);
    for name in CURSES {
        let c = to_hand(&mut s, name);
        assert!(!can_play_card(&s, c), "{name}");
        s.hand.remove(c, 1);
    }
}

/// Writhe is innate (in the opening hand); Ascender's Bane and Clumsy are
/// ethereal (exhausted at turn end); Injury, Parasite and Curse of the Bell
/// stay in hand and go to the discard pile.
#[test]
fn innate_ethereal_and_inert_curses() {
    for seed in 0..10 {
        load_pack(include_str!("../../content/packs/act1-ironclad.json")).unwrap();
        load_pack(COLORLESS_PACK).unwrap();
        let s = fight_with(Encounter::Cultist, &deck(&["gen:Writhe"]), 50, &[], seed);
        assert_eq!(s.hand.count(bound_card(&s, "Writhe")), 1, "seed {seed}");
    }
    let names = ["Ascender's Bane", "Clumsy", "Injury", "Parasite", "Curse of the Bell"];
    let mut s = curse_fight(&names, &[]);
    let ids: Vec<CardId> = names.iter().map(|n| to_hand(&mut s, n)).collect();
    let held = (s.hand.count(ids[0]), s.hand.count(ids[1]));
    let hp = s.player.hp;
    next_turn(&mut s);
    assert_eq!(s.player.hp, hp, "no effect");
    assert_eq!((s.exhaust().count(ids[0]), s.exhaust().count(ids[1])), held, "ethereal");
    for &c in &ids[2..] {
        assert_eq!(s.exhaust().count(c), 0);
        assert!(s.discard().count(c) + s.hand.count(c) >= 1);
    }
}

/// Decay (`triggerOnEndOfTurnForPlayingCard`: DamageAction 2 THORNS on the
/// player, block absorbs it); Regret (LoseHPAction of hand.size, Regret
/// counted, through block); Doubt and Shame (Weak / Frail 1 with
/// isSourceMonster: they skip the first round end, so turn 2 has them).
#[test]
fn turn_end_curses() {
    let mut s = curse_fight(&["Decay"], &[]);
    let decay = to_hand(&mut s, "Decay");
    let k = s.hand.count(decay) as i16;
    let hp = s.player.hp;
    s.player.block = 1;
    next_turn(&mut s);
    assert_eq!(s.player.hp, hp - (2 * k - 1), "2 per Decay held, 1 blocked");
    let mut s = curse_fight(&["Regret"], &[]);
    let regret = to_hand(&mut s, "Regret");
    s.player.block = 20;
    let (hp, held, k) = (s.player.hp, s.hand.len() as i16, s.hand.count(regret) as i16);
    next_turn(&mut s);
    assert_eq!(s.player.hp, hp - k * held, "each Regret: HP loss equal to the hand, Regrets counted, block ignored");
    assert!(s.discard().count(regret) >= 1, "played at turn end: to the discard pile");
    for (name, p) in [("Doubt", Power::Weak), ("Shame", Power::Frail)] {
        let mut s = curse_fight(&[name], &[]);
        let c = to_hand(&mut s, name);
        let k = s.hand.count(c) as i16;
        next_turn(&mut s);
        assert_eq!(s.player.powers.get(p), k, "{name}: 1 per copy held, lasts into turn 2");
    }
    // Weak from Doubt cuts turn 2's Strike (6 -> 4).
    let mut s = curse_fight(&["Doubt"], &[]);
    to_hand(&mut s, "Doubt");
    next_turn(&mut s);
    assert_eq!(strike_damage(s), 4);
}

/// Pain (`triggerOnOtherCardPlayed`: LoseHPAction 1, per Pain held, on each
/// other card played; not at the turn end).
#[test]
fn pain() {
    let mut s = curse_fight(&["Pain"], &[]);
    let pain = to_hand(&mut s, "Pain");
    let k = s.hand.count(pain) as i16;
    let hp = s.player.hp;
    play(&mut s, "Defend");
    assert_eq!(s.player.hp, hp - k, "1 per Pain held");
    to_hand(&mut s, "Pain");
    s.player.block = 30;
    play(&mut s, "Defend");
    assert_eq!(s.player.hp, hp - 2 * k - 1, "one more held: 1 more, through block");
    let mut s = curse_fight(&["Pain"], &[]);
    to_hand(&mut s, "Pain");
    let hp = s.player.hp;
    next_turn(&mut s);
    assert_eq!(s.player.hp, hp);
}

/// Normality (`canPlay`: false once cardsPlayedThisTurn >= 3, while held).
#[test]
fn normality() {
    let mut s = curse_fight(&["Normality"], &[]);
    let n = to_hand(&mut s, "Normality");
    for i in 0..3 {
        assert!(can_play_any(&s), "play {}", i + 1);
        play(&mut s, "Defend");
    }
    s.hand.add(CardId::from_name("Defend").unwrap(), 1);
    s.player.energy = 3;
    assert!(!can_play_any(&s), "no 4th play");
    // Not held: no limit.
    s.hand.remove(n, s.hand.count(n));
    assert!(can_play_any(&s));
}

/// Blue Candle (`AbstractCard.canUse`: a CURSE is playable with it;
/// `useCard` spends energy only above cost 0; `BlueCandle.onUseCard`:
/// LoseHPAction 1 and exhaust). A played curse is a card played: Pain sees
/// it. Necronomicurse exhausted returns to the hand (`triggerOnExhaust`).
#[test]
fn blue_candle() {
    let mut s = curse_fight(&["Injury", "Pain", "Necronomicurse"], &["Blue Candle"]);
    let injury = to_hand(&mut s, "Injury");
    assert!(can_play_card(&s, injury));
    let (hp, energy, played) = (s.player.hp, s.player.energy, s.cards_played_this_turn);
    s.step(Action::Play { card: injury, target: None }, &mut Rng::new(13)).unwrap();
    assert_eq!((s.player.hp, s.player.energy, s.cards_played_this_turn), (hp - 1, energy, played + 1));
    assert_eq!(s.exhaust().count(injury), 1);
    // Pain held and Pain played: the held one costs 1, the candle 1.
    let pain = to_hand(&mut s, "Pain");
    to_hand(&mut s, "Pain");
    let left = s.hand.count(pain) as i16 - 1;
    let hp = s.player.hp;
    s.step(Action::Play { card: pain, target: None }, &mut Rng::new(13)).unwrap();
    assert_eq!(s.player.hp, hp - left - 1, "each Pain still held, then the candle");
    // A Strike costs no HP (only curses).
    s.hand.remove(pain, s.hand.count(pain));
    let hp = s.player.hp;
    play(&mut s, "Strike");
    assert_eq!(s.player.hp, hp);
    // Necronomicurse: exhausted, and a copy is in hand again.
    let necro = to_hand(&mut s, "Necronomicurse");
    let held = s.hand.count(necro);
    s.step(Action::Play { card: necro, target: None }, &mut Rng::new(13)).unwrap();
    assert_eq!((s.exhaust().count(necro), s.hand.count(necro)), (1, held));
    // Statuses stay unplayable.
    let wound = CardId::from_name("Wound").unwrap();
    let mut s = curse_fight(&["Injury"], &["Blue Candle"]);
    s.hand.add(wound, 1);
    assert!(!can_play_card(&s, wound));
}

/// Medical Kit (`AbstractCard.canUse`: a STATUS is playable with it, free;
/// `MedicalKit.onUseCard`: exhaust, no HP loss). Burn played deals nothing
/// (its damage is its turn-end auto-play); Slimed still costs 1.
#[test]
fn medical_kit() {
    load_pack(COLORLESS_PACK).unwrap();
    let cards = deck(&["Wound", "Burn", "Dazed", "Slimed", "gen:Injury"]);
    let mut s = fight_with(Encounter::Cultist, &cards, 50, &["Medical Kit"], 11);
    for name in ["Wound", "Burn", "Dazed"] {
        let c = CardId::from_name(name).unwrap();
        s.hand.add(c, 1);
        let (hp, energy) = (s.player.hp, s.player.energy);
        let exhausted = s.exhaust().count(c);
        assert!(can_play_card(&s, c), "{name}");
        s.step(Action::Play { card: c, target: None }, &mut Rng::new(13)).unwrap();
        assert_eq!((s.player.hp, s.player.energy, s.exhaust().count(c)), (hp, energy, exhausted + 1), "{name}");
    }
    let slimed = CardId::from_name("Slimed").unwrap();
    s.hand.add(slimed, 1);
    let energy = s.player.energy;
    s.step(Action::Play { card: slimed, target: None }, &mut Rng::new(13)).unwrap();
    assert_eq!(s.player.energy, energy - 1);
    let injury = to_hand(&mut s, "Injury");
    assert!(!can_play_card(&s, injury), "curses stay unplayable");
}

/// Du-Vu Doll (`atBattleStart`: Strength equal to the deck's curses, none
/// when 0).
#[test]
fn du_vu_doll() {
    let s = curse_fight(&["Injury", "Regret"], &["Du-Vu Doll"]);
    assert_eq!(s.player.powers.get(Power::Strength), 2);
    let s = curse_fight(&[], &["Du-Vu Doll"]);
    assert_eq!(s.player.powers.get(Power::Strength), 0);
    let s = curse_fight(&["Injury", "Injury", "Pain"], &["Du-Vu Doll"]);
    assert_eq!(s.player.powers.get(Power::Strength), 3);
}

#[test]
fn step6_relics_load_with_their_rarity() {
    load_pack(PACK).unwrap();
    for (name, r) in [("Blue Candle", Rarity::Uncommon), ("Du-Vu Doll", Rarity::Rare), ("Medical Kit", Rarity::Shop)] {
        assert_eq!(relic(&format!("gen:{name}")).unwrap().rarity, r, "{name}");
    }
}

/// The step's load checks: AddCopy only in `exhausted`; the card-type
/// rules take any type.
#[test]
fn step6_load_errors() {
    for bad in [
        r#"{"version": 2, "cards": [{"id": "S6a", "cost": 0, "type": "Skill", "effects": [{"AddCopy": {"n": 1, "pile": "Hand"}}]}]}"#,
        r#"{"version": 2, "cards": [{"id": "S6b", "cost": -2, "type": "Curse", "effects": [], "turn_end": [{"AddCopy": {"n": 1, "pile": "Hand"}}]}]}"#,
        r#"{"version": 2, "cards": [{"id": "S6c", "cost": -2, "type": "Curse", "effects": [], "other_played": [{"AddCopy": {"n": 1, "pile": "Hand"}}]}]}"#,
        r#"{"version": 2, "powers": [{"id": "S6d", "plays_unplayable": "Card"}]}"#,
    ] {
        assert!(load_pack(bad).is_err(), "{bad}");
    }
    load_pack(r#"{"version": 2, "powers": [{"id": "S6e", "plays_unplayable": "Status", "forbids": "Curse"}]}"#).unwrap();
}

/// Plays `c` (put in hand if it isn't, energy topped up to 3) at monster 0,
/// keeping its block.
fn play_at(s: &mut CombatState, c: CardId) {
    if s.hand.count(c) == 0 {
        s.hand.add(c, 1);
    }
    s.player.energy = s.player.energy.max(3);
    let target = if s.binding.def(c).targeted() { Some(0) } else { None };
    s.step(Action::Play { card: c, target }, &mut Rng::new(13)).unwrap();
}

/// Hand Drill (`relics/HandDrill.java` `onBlockBroken`: `addToBot`
/// Vulnerable 2 on that monster, from the player), called by
/// `AbstractCreature.brokeBlock` from `decrementBlock` for monsters only,
/// on non-HP-loss damage with block above 0 and damage at least the block
/// (an exact break included). Queued at the bottom: it lands after the
/// card, so a later hit of the same card isn't boosted.
#[test]
fn hand_drill() {
    let strike = CardId::from_name("Strike").unwrap();
    for (block, vulnerable) in [(6, 2), (5, 2), (7, 0), (0, 0)] {
        let mut s = curse_fight(&[], &["Hand Drill"]);
        s.monsters[0].block = block;
        play_at(&mut s, strike);
        assert_eq!(s.monsters[0].powers.get(Power::Vulnerable), vulnerable, "block {block}");
    }
    let mut s = curse_fight(&[], &[]);
    s.monsters[0].block = 6;
    play_at(&mut s, strike);
    assert_eq!(s.monsters[0].powers.get(Power::Vulnerable), 0, "no relic");
    // Twin Strike (5 x2) on 5 block: the first hit breaks it, the second
    // deals 5, not 7.
    let mut s = curse_fight(&[], &["Hand Drill"]);
    s.monsters[0].block = 5;
    let hp = s.monsters[0].hp;
    play_at(&mut s, CardId::from_name("Twin Strike").unwrap());
    assert_eq!((hp - s.monsters[0].hp, s.monsters[0].powers.get(Power::Vulnerable)), (5, 2));
    // A monster the card killed gets nothing (the fight is won).
    let mut s = curse_fight(&[], &["Hand Drill"]);
    s.monsters[0].block = 5;
    s.monsters[0].hp = 1;
    play_at(&mut s, strike);
    assert!(s.won());
    // Combust's THORNS damage at the turn's end breaks it too; a
    // Vulnerable from the player counts down at that round's end (2 -> 1).
    let mut s = curse_fight(&[], &["Hand Drill"]);
    s.player.powers.add(Power::Combust, 1);
    s.player.powers.add(Power::CombustDamage, 5);
    s.monsters[0].block = 5;
    next_turn(&mut s);
    assert_eq!(s.monsters[0].powers.get(Power::Vulnerable), 1);
    // A potion's damage breaks it too.
    let mut s = potion_fight(Encounter::Cultist, 50, &["Hand Drill"], &["Fire Potion"]);
    s.monsters[0].block = 5;
    use_potion(&mut s, 0);
    assert_eq!(s.monsters[0].powers.get(Power::Vulnerable), 2);
}

/// Unceasing Top (`relics/UnceasingTop.java` `onRefreshHand`: nothing left
/// to resolve, an empty hand, the turn not ended, a card in the draw or
/// discard pile: draw 1, again each time the hand empties).
#[test]
fn unceasing_top() {
    let strike = CardId::from_name("Strike").unwrap();
    let mut s = curse_fight(&[], &["Unceasing Top"]);
    s.hand = Hand::from_cards(&[strike]);
    let draw = s.draw().len();
    play_at(&mut s, strike);
    assert_eq!((s.hand.len(), s.draw().len(), s.stage), (1, draw - 1, Stage::PlayerTurn));
    let c = s.hand.iter().next().unwrap().0;
    play_at(&mut s, c);
    assert_eq!(s.hand.len(), 1, "again");
    let mut s = curse_fight(&[], &[]);
    s.hand = Hand::from_cards(&[strike]);
    play_at(&mut s, strike);
    assert_eq!(s.hand.len(), 0, "no relic");
    // Both piles empty: the played Strike is in the discard pile by then,
    // and comes back.
    let mut s = curse_fight(&[], &["Unceasing Top"]);
    s.hand = Hand::from_cards(&[strike]);
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    play_at(&mut s, strike);
    assert_eq!(s.hand.count(strike), 1);
    // An exhausted card with both piles empty: nothing to draw; the turn
    // settles with an empty hand.
    let mut s = curse_fight(&["Seeing Red"], &["Unceasing Top"]);
    let c = bound_card(&s, "Seeing Red");
    s.hand = Hand::from_cards(&[c]);
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    play_at(&mut s, c);
    assert_eq!((s.hand.len(), s.stage), (0, Stage::PlayerTurn));
    assert!(s.legal_actions().contains(&Action::EndTurn));
    // Not at the turn end: the hand is discarded, and turn 2 draws 5.
    let mut s = curse_fight(&[], &["Unceasing Top"]);
    next_turn(&mut s);
    assert_eq!(s.hand.len(), 5);
}

fn listed(s: &CombatState) -> Vec<(f64, CombatState)> {
    let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(16) else { panic!("listed") };
    v
}

/// Strange Spoon (`actions/utility/UseCardAction.update`: a played card
/// that would exhaust, not a Power, with the relic held:
/// `cardRandomRng.randomBoolean()`; on true it goes to the discard pile and
/// no `onExhaust` fires). Covers Corruption's Skills and a card Havoc
/// cannot play (it still passes `UseCardAction`).
#[test]
fn strange_spoon() {
    let deck = ["Seeing Red", "Feel No Pain", "Corruption", "Havoc", "Injury"];
    let mut s = curse_fight(&deck, &["Strange Spoon"]);
    let c = to_hand(&mut s, "Seeing Red");
    let fnp = bind_power(&s.binding, "FeelNoPain").unwrap().1;
    s.player.powers.add(fnp, 3);
    s.player.energy = 3;
    let (discard, exhaust) = (s.discard().count(c), s.exhaust().count(c));
    s.apply_action(Action::Play { card: c, target: None }).unwrap();
    assert_eq!(s.pending, Some(ChanceEvent::ExhaustSave { queued: false }));
    let v = listed(&s);
    assert_eq!(v.len(), 2);
    let saved = v.iter().find(|(_, o)| o.exhaust().count(c) == exhaust).unwrap();
    let gone = v.iter().find(|(_, o)| o.exhaust().count(c) == exhaust + 1).unwrap();
    assert_eq!((saved.0, saved.1.discard().count(c), saved.1.player.block, saved.1.player.energy), (0.5, discard + 1, 0, 4));
    assert_eq!((gone.0, gone.1.discard().count(c), gone.1.player.block, gone.1.player.energy), (0.5, discard, 3, 4));
    // Sampled: one of the two.
    s.advance(&mut Rng::new(3));
    assert!(s.pending.is_none() && s.stage == Stage::PlayerTurn);
    // A Power is not rolled.
    let mut s = curse_fight(&deck, &["Strange Spoon"]);
    let p = to_hand(&mut s, "Feel No Pain");
    s.player.energy = 3;
    s.apply_action(Action::Play { card: p, target: None }).unwrap();
    assert_eq!(s.pending, None);
    // Without the relic, no roll.
    let mut s = curse_fight(&deck, &[]);
    let c = to_hand(&mut s, "Seeing Red");
    s.player.energy = 3;
    s.apply_action(Action::Play { card: c, target: None }).unwrap();
    assert_eq!(s.pending, None);
    // Corruption: a Skill that exhausts as played rolls.
    let mut s = curse_fight(&deck, &["Strange Spoon"]);
    let corruption = bind_power(&s.binding, "Corruption").unwrap().1;
    s.player.powers.add(corruption, 1);
    let defend = CardId::from_name("Defend").unwrap();
    s.hand.add(defend, 1);
    s.apply_action(Action::Play { card: defend, target: None }).unwrap();
    assert_eq!(s.pending, Some(ChanceEvent::ExhaustSave { queued: false }));
    // Havoc on Injury: unplayable, it would exhaust; the roll decides.
    let mut s = curse_fight(&deck, &["Strange Spoon"]);
    let injury = bound_card(&s, "Injury");
    let havoc = to_hand(&mut s, "Havoc");
    s.set_draw(Pile::from_cards(&[injury]));
    s.set_discard(Pile::default());
    s.set_exhaust(Pile::default());
    s.player.energy = 3;
    s.apply_action(Action::Play { card: havoc, target: None }).unwrap();
    assert_eq!(s.pending, Some(ChanceEvent::ExhaustSave { queued: true }));
    let v = listed(&s);
    assert_eq!(v.len(), 2);
    assert!(v.iter().any(|(p, o)| *p == 0.5 && o.discard().count(injury) == 1 && o.exhaust().count(injury) == 0));
    assert!(v.iter().any(|(p, o)| *p == 0.5 && o.discard().count(injury) == 0 && o.exhaust().count(injury) == 1));
}

/// The roll and its mark round-trip through the codec (official cards:
/// Slimed exhausts).
#[test]
fn strange_spoon_codec() {
    let mut s = fight_with(Encounter::Cultist, &deck(&["Slimed"]), 50, &["Strange Spoon"], 11);
    assert!(!s.has_generated());
    let slimed = CardId::from_name("Slimed").unwrap();
    s.hand.add(slimed, 1);
    s.player.energy = 3;
    s.apply_action(Action::Play { card: slimed, target: None }).unwrap();
    assert_eq!(s.pending, Some(ChanceEvent::ExhaustSave { queued: false }));
    assert_eq!(sts_engine::codec::decode(&sts_engine::codec::encode(&s)), s);
    for (queued, save) in [(true, Some(true)), (false, Some(false))] {
        let mut t = s.clone();
        t.pending = Some(ChanceEvent::ExhaustSave { queued });
        let Stage::PlayingCard { more, .. } = &mut t.stage else { panic!("in play") };
        more.save = save;
        assert_eq!(sts_engine::codec::decode(&sts_engine::codec::encode(&t)), t, "{queued} {save:?}");
    }
}

#[test]
fn step7_relics_load_with_their_rarity() {
    load_pack(PACK).unwrap();
    for (name, r) in [("Hand Drill", Rarity::Shop), ("Unceasing Top", Rarity::Rare), ("Strange Spoon", Rarity::Shop)] {
        assert_eq!(relic(&format!("gen:{name}")).unwrap().rarity, r, "{name}");
    }
    for bad in ["[0, 2]", "[3, 2]", "[1, 0]", "[1]", "true"] {
        let pack = format!(r#"{{"version": 2, "relics": [{{"id": "s7bad", "rarity": "shop", "exhaust_save": {bad}}}]}}"#);
        assert!(load_pack(&pack).is_err(), "{bad}");
    }
}
