//! Discovery (docs/specs/discovery.md): card pools as content, the
//! `Discover` effect (the offer a chance event, the pick a decision), and
//! the entries built on it: Attack, Skill and Power Potion, Infernal
//! Blade. Each against the decompiled game (AxorusMT/sts, paths under
//! `com/megacrit/cardcrawl/`), named per test.

use std::collections::BTreeSet;

use sts_engine::agent::{greedy_action, Agent, SearchAgent};
use sts_engine::cards::CardType;
use sts_engine::registry::{bind, bind_power, load_pack, pool_cards, pool_def, potions_named, relics_named, Binding};
use sts_engine::search::{Heuristic, SearchConfig};
use sts_engine::*;

const IRONCLAD: &str = include_str!("../../content/packs/act1-ironclad.json");
const POTIONS: &str = include_str!("../../content/packs/act1-potions.json");
const RELICS: &str = include_str!("../../content/packs/act1-relics.json");
const COLORLESS: &str = include_str!("../../content/packs/act1-colorless.json");

fn load() {
    load_pack(IRONCLAD).unwrap();
    load_pack(RELICS).unwrap();
    load_pack(POTIONS).unwrap();
    load_pack(COLORLESS).unwrap();
}

/// The loaded pool named `name`, by index.
fn pool(name: &str) -> u8 {
    (0..=254u8).find(|&i| pool_def(i).is_some_and(|p| p.name == name)).unwrap_or_else(|| panic!("pool {name:?} loaded"))
}

/// A Jaw Worm fight with the starter deck holding `potions` (pack names)
/// and Sacred Bark when `bark`.
fn fight(potions: &[&str], bark: bool) -> CombatState {
    load();
    let relics = if bark { relics_named(&["gen:Sacred Bark"]).unwrap() } else { vec![] };
    let mut s = CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &Binding::default(), 50, 80, Encounter::JawWorm, &relics, &mut Rng::new(3));
    let names: Vec<String> = potions.iter().map(|p| format!("gen:{p}")).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    s.give_potions(&potions_named(&refs).unwrap()).unwrap();
    s
}

/// Drinks the potion in slot 0; the offer is drawn with `seed`.
fn drink(s: &mut CombatState, seed: u64) {
    s.step(Action::UsePotion { slot: 0, target: None }, &mut Rng::new(seed)).unwrap();
}

/// The cards the open offer shows.
fn offered(s: &CombatState) -> Vec<CardId> {
    s.legal_actions().iter().filter_map(|a| if let Action::Choose(c) = *a { Some(c) } else { None }).collect()
}

fn name(s: &CombatState, c: CardId) -> String {
    s.binding.def(c).name.trim_start_matches("gen:").to_string()
}

// The game's in-combat Ironclad lists with every card unlocked
// (`AbstractDungeon.returnTrulyRandomCardInCombat(type)`: common, uncommon
// and rare, HEALING-tagged Feed and Reaper left out; `cards/red/*.java`).
const GAME_ATTACKS: [&str; 28] = [
    "Anger", "Body Slam", "Clash", "Cleave", "Clothesline", "Headbutt", "Heavy Blade", "Iron Wave", "Perfected Strike", "Pommel Strike",
    "Sword Boomerang", "Thunderclap", "Twin Strike", "Wild Strike", "Blood for Blood", "Carnage", "Dropkick", "Hemokinesis", "Pummel",
    "Rampage", "Reckless Charge", "Searing Blow", "Sever Soul", "Uppercut", "Whirlwind", "Bludgeon", "Fiend Fire", "Immolate",
];
const GAME_SKILLS: [&str; 28] = [
    "Armaments", "Flex", "Havoc", "Shrug It Off", "True Grit", "Warcry", "Battle Trance", "Bloodletting", "Burning Pact", "Disarm",
    "Dual Wield", "Entrench", "Flame Barrier", "Ghostly Armor", "Infernal Blade", "Intimidate", "Power Through", "Rage", "Second Wind",
    "Seeing Red", "Sentinel", "Shockwave", "Spot Weakness", "Double Tap", "Exhume", "Impervious", "Limit Break", "Offering",
];
const GAME_POWERS: [&str; 14] = [
    "Combust", "Dark Embrace", "Evolve", "Feel No Pain", "Fire Breathing", "Inflame", "Metallicize", "Rupture", "Barricade", "Berserk",
    "Brutality", "Corruption", "Demon Form", "Juggernaut",
];
/// The game's cards that don't load yet (docs/research/act1-relics-potions.md
/// "Discovery"): each joins the pool once it loads.
const MISSING: [&str; 0] = [];

#[test]
fn the_ironclad_pool_is_the_games_less_the_missing_cards() {
    load();
    let p = pool_def(pool("Ironclad")).unwrap();
    for (ty, game) in [(CardType::Attack, &GAME_ATTACKS[..]), (CardType::Skill, &GAME_SKILLS[..]), (CardType::Power, &GAME_POWERS[..])] {
        let have: BTreeSet<&str> = p.cards.iter().filter(|c| c.ty == ty).map(|c| c.official.map_or_else(|| c.pack.unwrap(), |id| id.name())).collect();
        let want: BTreeSet<&str> = game.iter().copied().filter(|n| !MISSING.contains(n)).collect();
        assert_eq!(have, want, "{ty:?}");
    }
    assert_eq!(p.cards.len(), 28 + 28 + 14);
}

// The game's in-combat colorless pool
// (`AbstractDungeon.returnTrulyRandomColorlessCardInCombat`: every
// `cards/colorless/*.java` card not BASIC, SPECIAL or STATUS, HEALING-tagged
// Bandage Up left out): 19 uncommon, 15 rare. Names as the cards' display
// names (the ids HandOfGreed, PanicButton, Jack Of All Trades differ).
const GAME_COLORLESS: [&str; 34] = [
    "Blind", "Dark Shackles", "Deep Breath", "Discovery", "Dramatic Entrance", "Enlightenment", "Finesse", "Flash of Steel",
    "Forethought", "Good Instincts", "Impatience", "Jack of All Trades", "Madness", "Mind Blast", "Panacea", "Panic Button", "Purity",
    "Swift Strike", "Trip", "Apotheosis", "Chrysalis", "Hand of Greed", "Magnetism", "Master of Strategy", "Mayhem", "Metamorphosis",
    "Panache", "Sadistic Nature", "Secret Technique", "Secret Weapon", "The Bomb", "Thinking Ahead", "Transmutation", "Violence",
];
/// The game's colorless cards that don't load yet
/// (docs/specs/colorless-cards.md): each joins the pool once it loads.
const MISSING_COLORLESS: [&str; 3] = ["The Bomb", "Panache", "Forethought"];

#[test]
fn the_colorless_pool_is_the_games_less_the_missing_cards() {
    load();
    let p = pool_def(pool("Colorless")).unwrap();
    let have: BTreeSet<&str> = p.cards.iter().map(|c| c.official.map_or_else(|| c.pack.unwrap(), |id| id.name())).collect();
    let want: BTreeSet<&str> = GAME_COLORLESS.iter().copied().filter(|n| !MISSING_COLORLESS.contains(n)).collect();
    assert_eq!(have, want);
    assert_eq!(p.cards.len(), 34 - MISSING_COLORLESS.len());
}

#[test]
fn pool_load_errors() {
    load();
    let err = |text: &str| load_pack(text).unwrap_err();
    assert!(err(r#"{"version": 2, "pools": {"pl-bad": ["Anger", "No Such Card"]}}"#).contains("not a loaded card"));
    assert!(err(r#"{"version": 2, "pools": {"pl-twice": ["Anger", "Anger"]}}"#).contains("twice"));
    assert!(err(r#"{"version": 2, "pools": {"Ironclad": ["Anger"]}}"#).contains("redefined"));
    let unknown = r#"{"version": 2, "potions": [{"id": "pl-unknown", "rarity": "common", "effects": [{"Discover": {"pool": "pl-none"}}]}]}"#;
    assert!(err(unknown).contains("unknown pool"));
    let in_hook = r#"{"version": 2, "powers": [{"id": "pl-hook", "hooks": [{"trigger": "OwnerTurnStart", "condition": "Always", "effects": [{"Discover": {"pool": "Ironclad"}}]}]}]}"#;
    let e = err(in_hook);
    assert!(e.contains("Discover") && e.contains("hook"), "{e}");
    let relic = r#"{"version": 2, "relics": [{"id": "pl-relic", "rarity": "shop", "hooks": [{"trigger": "CombatStart", "condition": "Always", "effects": [{"Discover": {"pool": "Ironclad"}}]}]}]}"#;
    assert!(load_pack(relic).is_err());
    // A pool loaded again as it was is skipped.
    load_pack(IRONCLAD).unwrap();
}

#[test]
fn attack_potion_offers_three_different_attacks_from_the_pool() {
    // `DiscoveryAction.generateCardChoices`: three cards, a repeat drawn again.
    let mut seen = BTreeSet::new();
    for seed in 0..400 {
        let mut s = fight(&["Attack Potion"], false);
        drink(&mut s, seed);
        let o = offered(&s);
        assert_eq!(o.len(), 3, "seed {seed}");
        for &c in &o {
            assert_eq!(s.binding.def(c).ty, CardType::Attack);
            assert_eq!(s.binding.def(c).level, 0, "an unupgraded copy");
            seen.insert(name(&s, c));
        }
        // Skippable (`customCombatOpen(.., this.cardType != null)`).
        assert!(s.legal_actions().contains(&Action::Done));
    }
    let want: BTreeSet<String> = GAME_ATTACKS.iter().map(|n| n.to_string()).collect();
    assert_eq!(seen, want, "every attack of the pool shows, nothing else (no Feed, no Reaper)");
}

#[test]
fn skill_and_power_potions_offer_their_type() {
    for (potion, ty) in [("Skill Potion", CardType::Skill), ("Power Potion", CardType::Power)] {
        for seed in 0..40 {
            let mut s = fight(&[potion], false);
            drink(&mut s, seed);
            let o = offered(&s);
            assert_eq!(o.len(), 3);
            assert!(o.iter().all(|&c| s.binding.def(c).ty == ty), "{potion}");
        }
    }
}

#[test]
fn taking_and_skipping() {
    // `DiscoveryAction.update`: the chosen card into hand; a skip adds nothing.
    let mut s = fight(&["Attack Potion"], false);
    let hand = s.hand.len();
    drink(&mut s, 7);
    let c = offered(&s)[1];
    s.step(Action::Choose(c), &mut Rng::new(1)).unwrap();
    assert_eq!(s.stage, Stage::PlayerTurn);
    assert_eq!((s.hand.len(), s.hand.count(c)), (hand + 1, 1));
    assert!(s.offer.is_empty() && s.player.potions.is_empty());
    let mut s = fight(&["Attack Potion"], false);
    drink(&mut s, 7);
    s.step(Action::Done, &mut Rng::new(1)).unwrap();
    assert_eq!((s.stage, s.hand.len()), (Stage::PlayerTurn, hand));
    assert!(s.offer.is_empty() && s.player.potions.is_empty(), "the potion is used up");
}

#[test]
fn sacred_bark_two_copies_and_a_full_hand() {
    // Potency 2 with Sacred Bark: two copies; `hand.size() + amount <= 10`
    // both to hand, at 9 one to hand and one to discard, else both discard.
    let strike = CardId::from_name("Strike").unwrap();
    for (bark, extra, to_hand, to_discard) in [(true, 0, 2, 0), (true, 4, 1, 1), (true, 5, 0, 2), (false, 4, 1, 0), (false, 5, 0, 1)] {
        let mut s = fight(&["Attack Potion"], bark);
        s.hand.add(strike, extra);
        let k = extra.min(s.draw().count(strike));
        s.draw_mut().remove(strike, k);
        let (hand, discard) = (s.hand.len(), s.discard().len());
        drink(&mut s, 3);
        let c = offered(&s)[0];
        s.step(Action::Choose(c), &mut Rng::new(1)).unwrap();
        assert_eq!((s.hand.len() - hand, s.discard().len() - discard), (to_hand, to_discard), "bark {bark}, hand {hand}");
        assert_eq!(s.hand.count(c) as usize + s.discard().count(c) as usize, to_hand + to_discard);
        // Only the copies put in hand are free (the discarded one isn't: a named limit).
        if s.binding.def(c).cost() > 0 && !s.binding.def(c).x_cost() {
            assert_eq!(s.free_in_hand.count(c) as usize, to_hand);
        }
    }
}

#[test]
fn infernal_blade_adds_one_random_attack_with_no_choice() {
    // `cards/red/InfernalBlade.java`: one `returnTrulyRandomCardInCombat(ATTACK)`
    // into hand; exhaust; cost 1, upgraded 0.
    load();
    let (ids, b) = bind(&["Strike", "Defend", "gen:Infernal Blade", "gen:Infernal Blade+"]).unwrap();
    let (blade, blade_up) = (ids[2], ids[3]);
    assert_eq!((b.def(blade).cost(), b.def(blade_up).cost()), (1, 0));
    let mut seen = BTreeSet::new();
    for seed in 0..200 {
        let mut s = CombatState::new_bound_with(Character::Ironclad, &ids, &b, 50, 80, Encounter::JawWorm, &[], &mut Rng::new(seed));
        s.hand.clear();
        s.hand.add(blade, 1);
        s.player.energy = 3;
        s.step(Action::Play { card: blade, target: None }, &mut Rng::new(seed)).unwrap();
        assert_eq!(s.stage, Stage::PlayerTurn, "no decision");
        assert_eq!((s.hand.len(), s.exhaust().count(blade)), (1, 1));
        let (c, _) = s.hand.iter().next().unwrap();
        assert_eq!(s.binding.def(c).ty, CardType::Attack);
        // `setCostForTurn(0)`: free this turn unless X-cost or already 0.
        let base = s.binding.def(c).cost();
        assert_eq!(s.cost_of(c), if base > 0 { 0 } else { base }, "{}", name(&s, c));
        seen.insert(name(&s, c));
    }
    assert_eq!(seen.len(), 28, "every attack of the pool");
}

/// A small test pool (official attacks only) and a potion discovering it.
fn small(n: usize) -> CombatState {
    load();
    let cards = ["Anger", "Cleave", "Clash", "Iron Wave"][..n].iter().map(|c| format!("{c:?}")).collect::<Vec<_>>().join(", ");
    let id = format!("dv-small-{n}");
    let pack = format!(
        r#"{{"version": 2, "pools": {{"{id}": [{cards}]}}, "potions": [{{"id": "{id}", "rarity": "common", "potency": 1, "effects": [{{"Discover": {{"pool": "{id}", "skip": true}}}}]}}]}}"#
    );
    load_pack(&pack).unwrap();
    let mut s = CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &Binding::default(), 50, 80, Encounter::JawWorm, &[], &mut Rng::new(3));
    s.give_potions(&potions_named(&[&format!("gen:{id}")]).unwrap()).unwrap();
    s
}

#[test]
fn the_offer_is_a_chance_event_over_combinations() {
    let mut s = small(4);
    s.apply_action(Action::UsePotion { slot: 0, target: None }).unwrap();
    assert!(matches!(s.pending, Some(chance::ChanceEvent::Offer { k: 3, .. })));
    let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(100) else { panic!("listed") };
    assert_eq!(v.len(), 4, "C(4, 3)");
    assert!(v.iter().all(|(p, t)| (*p - 0.25).abs() < 1e-12 && offered(t).len() == 3));
    assert!(matches!(s.chance_outcomes(3), Some(ChanceOutcomes::Large)));
    // Equal hands reached through different offers are equal states.
    let anger = CardId::from_name("Anger").unwrap();
    let after: Vec<CombatState> = v
        .into_iter()
        .filter(|(_, t)| offered(t).contains(&anger))
        .map(|(_, mut t)| {
            t.step(Action::Choose(anger), &mut Rng::new(1)).unwrap();
            t
        })
        .collect();
    assert_eq!(after.len(), 3);
    assert!(after.windows(2).all(|w| w[0] == w[1]));
    // An official-only pool leaves the binding empty: the open offer still
    // makes the state unencodable (`has_generated`).
    assert!(s.binding.is_empty() && s.has_generated());
    // A pool of 3: no chance event, the pick opens at once.
    let mut s = small(3);
    s.apply_action(Action::UsePotion { slot: 0, target: None }).unwrap();
    assert!(s.pending.is_none());
    assert_eq!(offered(&s).len(), 3);
}

#[test]
fn the_heal_bound_follows_the_offer() {
    // Nothing in the Ironclad attacks heals; a pool holding Bandage-like
    // healing makes the potion count.
    let s = fight(&["Attack Potion"], false);
    assert!(!s.can_heal());
    load_pack(r#"{"version": 2, "cards": [{"id": "dv-heal", "cost": 1, "type": "Skill", "effects": [{"Heal": 4}]}], "pools": {"dv-heal": ["dv-heal", "Anger", "Cleave", "Clash"]}, "potions": [{"id": "dv-heal", "rarity": "common", "potency": 1, "effects": [{"Discover": {"pool": "dv-heal"}}]}]}"#).unwrap();
    let mut s = CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &Binding::default(), 50, 80, Encounter::JawWorm, &[], &mut Rng::new(3));
    s.give_potions(&potions_named(&["gen:dv-heal"]).unwrap()).unwrap();
    assert!(s.can_heal());
    let p = pool("dv-heal");
    assert_eq!(pool_cards(&s.binding, p, None).len(), 4);
}

#[test]
fn agents_finish_fights_with_each_potion() {
    for potion in ["Attack Potion", "Skill Potion", "Power Potion"] {
        for seed in 0..3 {
            let mut s = fight(&[potion], seed == 0);
            let mut rng = Rng::new(seed);
            s.advance(&mut rng);
            while !s.is_over() && s.turn <= 50 {
                let a = greedy_action(&s);
                s.step(a, &mut rng).unwrap();
            }
            assert!(s.is_over(), "greedy, {potion}, seed {seed}");
            let mut s = fight(&[potion], false);
            s.advance(&mut rng);
            let mut agent = SearchAgent::new(Heuristic, SearchConfig::default());
            let mut agent_rng = Rng::new(seed ^ 0x5eed);
            while !s.is_over() && s.turn <= 50 {
                let a = agent.act(&s, &mut agent_rng);
                s.step(a, &mut rng).expect("the agent chose a legal action");
            }
            assert!(s.won(), "search, {potion}, seed {seed}");
        }
    }
}

#[test]
fn a_taken_card_costs_0_this_turn_only() {
    // `disCard.setCostForTurn(0)`; `AbstractRoom.endTurn` resets it.
    let mut checked = BTreeSet::new();
    for seed in 0..200 {
        let mut s = fight(&["Attack Potion"], seed % 2 == 0);
        drink(&mut s, seed);
        let c = offered(&s)[0];
        let base = s.binding.def(c).cost();
        s.step(Action::Choose(c), &mut Rng::new(1)).unwrap();
        let copies = if seed % 2 == 0 { 2 } else { 1 };
        if s.binding.def(c).x_cost() {
            // Whirlwind: `costForTurn` -1 isn't changed.
            assert_eq!((s.cost_of(c), s.free_in_hand.len()), (base, 0));
            checked.insert("x");
            continue;
        }
        if base == 0 {
            assert_eq!(s.cost_of(c), 0);
            continue;
        }
        assert_eq!((s.cost_of(c), s.free_in_hand.count(c) as usize), (0, copies), "both of Bark's copies are free");
        if checked.insert("played") {
            // It plays for 0 energy.
            let e = s.player.energy;
            let target = s.binding.def(c).targeted().then_some(0);
            s.step(Action::Play { card: c, target }, &mut Rng::new(2)).unwrap();
            assert_eq!(s.player.energy, e);
            continue;
        }
        // Next turn the copy costs its own cost.
        s.step(Action::EndTurn, &mut Rng::new(2)).unwrap();
        if s.is_over() {
            continue;
        }
        assert!(s.free_in_hand.is_empty());
        // Blood for Blood's own discount for HP lost still applies: the
        // copy taken (any pile) carries one drop per loss.
        let lost = if s.binding.def(c).cost_less_per_hp_loss { s.times_lost_hp as i8 } else { 0 };
        let base_of = |h: CardId| sts_engine::registry::copy_of(h).map_or(h, |x| x.0);
        let held = s.hand.iter().chain(s.draw().iter()).chain(s.discard().iter()).map(|(h, _)| h).find(|&h| base_of(h) == c).unwrap_or(c);
        assert_eq!(s.cost_of(held), (base - lost).max(0));
        checked.insert("next turn");
    }
    assert_eq!(checked.len(), 3, "{checked:?}");
}

#[test]
fn with_corruption_a_discovered_skill_costs_0_and_exhausts() {
    let mut s = fight(&["Skill Potion"], false);
    let (b, corruption) = bind_power(&s.binding, "Corruption").unwrap();
    s.binding = b;
    s.player.powers.add(corruption, 1);
    drink(&mut s, 5);
    let c = *offered(&s).iter().find(|&&c| s.binding.def(c).cost() > 0 && !s.binding.def(c).unplayable()).expect("a skill costing energy");
    s.step(Action::Choose(c), &mut Rng::new(1)).unwrap();
    assert_eq!(s.cost_of(c), 0);
    let target = s.binding.def(c).targeted().then_some(0);
    s.step(Action::Play { card: c, target }, &mut Rng::new(2)).unwrap();
    while s.pick().is_some() {
        let a = s.legal_actions()[0];
        s.step(a, &mut Rng::new(2)).unwrap();
    }
    assert_eq!(s.exhaust().count(c), 1);
}

#[test]
fn a_deck_binds_its_pools_in_slot_order() {
    // Two cards discovering from two pools: the pool cards' slots follow
    // the deck's order, whatever the process's hash order.
    load();
    load_pack(r#"{"version": 2, "cards": [
        {"id": "dv-p1", "cost": 1, "type": "Attack", "effects": [{"Damage": {"amount": 1, "hits": 1, "target": "Opponent"}}]},
        {"id": "dv-p2", "cost": 1, "type": "Attack", "effects": [{"Damage": {"amount": 2, "hits": 1, "target": "Opponent"}}]},
        {"id": "dv-da", "cost": 1, "type": "Skill", "effects": [{"Discover": {"pool": "dv-pa", "offer": 1}}]},
        {"id": "dv-db", "cost": 1, "type": "Skill", "effects": [{"Discover": {"pool": "dv-pb", "offer": 1}}]}],
        "pools": {"dv-pa": ["dv-p1", "Anger"], "dv-pb": ["dv-p2", "Cleave"]}}"#).unwrap();
    let first = bind(&["Strike", "gen:dv-da", "gen:dv-db"]).unwrap().1;
    for _ in 0..30 {
        assert_eq!(bind(&["Strike", "gen:dv-da", "gen:dv-db"]).unwrap().1, first);
    }
    let pack = |p: &str| pool_cards(&first, pool(p), None).iter().copied().find(|c| !c.is_official()).unwrap();
    assert!(pack("dv-pa") < pack("dv-pb"), "dv-da's pool card is bound before dv-db's");
}
