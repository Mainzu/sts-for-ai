//! A cost for the combat (docs/specs/sparse-piles.md step c): Snecko Oil
//! (`potions/SneckoOil.java` 34-42: draw 5, then `RandomizeHandCostAction`,
//! `actions/unique/RandomizeHandCostAction.java` 23-29) and Snecko Eye
//! (`relics/SneckoEye.java` 22, 34: hand size + 2, Confused before battle;
//! `powers/ConfusionPower.java` 32-39: each drawn card), as the decompiled
//! classes in Li-Binghui/MySlayTheSpire read (aeubanks/sts alike). A card
//! whose cost is 0 or more rolls 0-3; a roll equal to its cost changes
//! nothing, any other sets its cost for the combat and for the turn.

use sts_engine::chance::ChanceOutcomes;
use sts_engine::codec::{decode, encode};
use sts_engine::registry::{changed_copy, copy_of, load_pack, potions_named, relics_named, upgraded, Binding, Overrides};
use sts_engine::*;

const POTIONS: &str = include_str!("../../content/packs/act1-potions.json");
const RELICS: &str = include_str!("../../content/packs/act1-relics.json");
const IRONCLAD: &str = include_str!("../../content/packs/act1-ironclad.json");

fn load() {
    load_pack(IRONCLAD).unwrap();
    load_pack(RELICS).unwrap();
    load_pack(POTIONS).unwrap();
}

fn card(name: &str) -> CardId {
    CardId::from_name(name).unwrap()
}

/// A Jaw Worm fight holding Snecko Oil, with `relics` (pack names).
fn oil_fight(relics: &[&str], seed: u64) -> CombatState {
    load();
    let names: Vec<String> = relics.iter().map(|r| format!("gen:{r}")).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    let mut s = CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &Binding::default(), 80, 80, Encounter::JawWorm, &relics_named(&refs).unwrap(), &mut Rng::new(seed));
    s.give_potions(&potions_named(&["gen:Snecko Oil"]).unwrap()).unwrap();
    s
}

fn outcomes(s: &CombatState) -> Vec<(f64, CombatState)> {
    match s.chance_outcomes(100) {
        Some(ChanceOutcomes::Listed(v)) => v,
        x => panic!("listed outcomes expected, got {x:?}"),
    }
}

/// Every card in hand costs 0-3 (or is X-cost or unplayable, never rolled).
fn costs_in_range(s: &CombatState) {
    for (c, _) in s.hand.iter() {
        let d = s.binding.def(c);
        assert!(d.x_cost() || d.unplayable() || (0..=3).contains(&d.cost()), "{} costs {}", d.name, d.cost());
    }
}

#[test]
fn x_cost_and_unplayable_cards_are_never_rolled() {
    // RandomizeHandCostAction.java 24 and ConfusionPower.java 32: only a
    // cost of 0 or more rolls (Whirlwind's X, Dazed's unplayable stay).
    let mut s = oil_fight(&[], 6);
    let whirlwind = CardId::from_name("Whirlwind").unwrap();
    let dazed = card("Dazed");
    s.hand = Hand::from_cards(&[whirlwind, dazed]);
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    s.apply_action(Action::UsePotion { slot: 0, target: None }).unwrap();
    assert!(s.cost_rolls.is_empty() && s.pending.is_none());
    assert_eq!(s.hand, Hand::from_cards(&[whirlwind, dazed]));
    let x = changed_copy(whirlwind, whirlwind.def(), Overrides { cost: Some(2), ..Overrides::default() }).unwrap();
    assert_eq!(x, whirlwind, "an X-cost card takes no cost for the combat");
}

#[test]
fn snecko_oil_draws_five_then_rolls_each_card_in_hand() {
    let mut s = oil_fight(&[], 1);
    assert_eq!(s.hand.len(), 5);
    s.apply_action(Action::UsePotion { slot: 0, target: None }).unwrap();
    // The draw takes the last 5 cards (certain); then every card in hand
    // (10, all costing 0 or more) waits for a roll.
    let mut t = s.clone();
    assert_eq!(t.hand.len(), 10);
    assert_eq!((t.pending, t.cost_rolls.len()), (Some(ChanceEvent::RandomCost), 10));
    // Each roll: 4 outcomes alike, one the card's own cost (unchanged).
    let first = t.cost_rolls.front().unwrap().0;
    let v = outcomes(&t);
    assert_eq!(v.len(), 4);
    assert!(v.iter().all(|(p, _)| *p == 0.25));
    let kept = v.iter().filter(|(_, u)| u.hand.count(first) == t.hand.count(first)).count();
    assert_eq!(kept, 1, "the roll equal to {}'s cost leaves it", first.name());
    let names: Vec<&str> = v.iter().flat_map(|(_, u)| u.hand.iter().map(|(c, _)| u.binding.def(c).name)).collect();
    assert!(names.iter().any(|n| n.ends_with("{cost=0/combat}")), "{names:?}");
    // Played out by sampling: every card rolled, the queue empty.
    let mut rng = Rng::new(7);
    while t.pending.is_some() {
        t.resolve_chance(&mut rng);
    }
    assert!(t.cost_rolls.is_empty());
    assert_eq!(t.hand.len(), 10);
    costs_in_range(&t);
    let c = decode(&encode(&t));
    assert_eq!(c, t, "cost copies round-trip (section 13)");
}

#[test]
fn a_roll_keeps_or_ends_the_free_mark() {
    let mut s = oil_fight(&[], 2);
    s.hand = Hand::from_cards(&[card("Bash")]);
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    s.mark_free_in_hand(card("Bash"));
    assert_eq!(s.cost_of(card("Bash")), 0);
    s.apply_action(Action::UsePotion { slot: 0, target: None }).unwrap();
    assert_eq!(s.pending, Some(ChanceEvent::RandomCost));
    assert_eq!(s.cost_rolls.iter().collect::<Vec<_>>(), [(card("Bash"), true)]);
    // Codec: the waiting roll and its mark round-trip (tag 7, section 14).
    assert_eq!(decode(&encode(&s)), s);
    for (_, u) in outcomes(&s) {
        let (c, _) = u.hand.iter().next().unwrap();
        if c == card("Bash") {
            // Rolled 2, Bash's own cost: still free this turn.
            assert_eq!(u.cost_of(c), 0);
        } else {
            let v = u.binding.def(c).cost();
            assert_eq!((u.cost_of(c), u.free_in_hand.count(c)), (v, 0), "{}", u.binding.def(c).name);
        }
    }
}

#[test]
fn snecko_eye_draws_seven_and_rolls_each_drawn_card() {
    let mut changed = 0;
    for seed in 0..8 {
        let s = oil_fight(&["Snecko Eye"], seed);
        assert_eq!(s.hand.len(), 7, "5 + Snecko Eye's 2");
        assert!(s.cost_rolls.is_empty());
        costs_in_range(&s);
        changed += s.hand.iter().filter(|(c, _)| copy_of(*c).is_some()).count();
    }
    assert!(changed > 0, "some opening cards rolled a new cost");
    // Turn 2: 7 more, rolled too.
    let mut s = oil_fight(&["Snecko Eye"], 3);
    let mut rng = Rng::new(5);
    s.step(Action::EndTurn, &mut rng).unwrap();
    s.advance(&mut rng);
    assert_eq!(s.hand.len(), 7);
    costs_in_range(&s);
}

#[test]
fn snecko_eye_pauses_at_each_drawn_cards_roll() {
    // Turn 2's draw of 7: each drawn card waits for its own roll, one
    // chance event of 4 alike at a time. (A fight binding a pack power
    // isn't encodable; the codec is checked with Snecko Oil.)
    load();
    let relics = relics_named(&["gen:Snecko Eye"]).unwrap();
    let mut s = CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &Binding::default(), 80, 80, Encounter::JawWorm, &relics, &mut Rng::new(4));
    s.apply_action(Action::EndTurn).unwrap();
    let mut rng = Rng::new(10);
    let mut rolls = 0;
    while s.pending.is_some() {
        if s.pending == Some(ChanceEvent::RandomCost) {
            let v = outcomes(&s);
            assert_eq!(v.len(), 4);
            assert!(v.iter().all(|(_, u)| u.cost_rolls.len() + 1 == s.cost_rolls.len() || u.pending != Some(ChanceEvent::RandomCost)));
            rolls += 1;
        }
        s.resolve_chance(&mut rng);
    }
    assert_eq!(rolls, 7, "one roll per card drawn (all cost 0 or more)");
    assert_eq!(s.hand.len(), 7);
}

#[test]
fn an_upgrade_that_changes_the_cost_resets_it() {
    // The game's upgradeBaseCost (cards/AbstractCard.java 890-900 in
    // Li-Binghui/MySlayTheSpire): the new base cost replaces a cost for the
    // combat; an upgrade that leaves the cost keeps it.
    let b = Binding::default();
    let lowers = CardId::all().find(|&c| !c.upgraded() && c.def().cost() >= 1 && CardId(c.0 + 1).def().cost() < c.def().cost()).expect("a card whose upgrade lowers its cost");
    let keeps = card("Strike");
    for (c, reset) in [(lowers, true), (keeps, false)] {
        let rolled = changed_copy(c, c.def(), Overrides { cost: Some(3), ..Overrides::default() }).unwrap();
        let up = upgraded(&b, rolled).unwrap();
        let cost = b.def(up).cost();
        if reset {
            assert_eq!(up, CardId(c.0 + 1), "{} upgraded is the plain +", c.name());
            assert_eq!(cost, CardId(c.0 + 1).def().cost());
        } else {
            assert_eq!((b.def(up).name, cost), ("Strike+{cost=3/combat}", 3));
        }
    }
}

#[test]
fn a_cost_equal_to_the_cards_own_is_the_plain_card() {
    let s = card("Strike");
    assert_eq!(changed_copy(s, s.def(), Overrides { cost: Some(1), ..Overrides::default() }).unwrap(), s);
    let x = changed_copy(s, s.def(), Overrides { cost: Some(0), ..Overrides::default() }).unwrap();
    assert_eq!(Binding::default().def(x).name, "Strike{cost=0/combat}");
}
