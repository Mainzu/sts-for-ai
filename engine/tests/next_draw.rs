//! `CombatState::next_draw` (docs/specs/draw-knowledge.md item 2): the next
//! turn's start draw as (min, max), with the game's rules
//! (docs/research/build-plans-2026-11-14/draw-next-and-inputs.md).

mod common;

use common::*;
use sts_engine::character::Character;
use sts_engine::monsters::MonsterKind as K;
use sts_engine::registry::{bind, bind_power, load_pack, relics_named};
use sts_engine::*;

const RELICS: &str = include_str!("../../content/packs/act1-relics.json");
const IRONCLAD: &str = include_str!("../../content/packs/act1-ironclad.json");

/// A fight at turn 1's first decision, of `cards` with `relics` (pack
/// relics by their game name).
fn fight(character: Character, cards: &[&str], relics: &[&str], seed: u64) -> CombatState {
    load_pack(RELICS).unwrap();
    load_pack(IRONCLAD).unwrap();
    let names: Vec<String> = relics.iter().map(|r| format!("gen:{r}")).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    let (ids, b) = bind(cards).unwrap();
    CombatState::new_bound_with(character, &ids, &b, 80, 80, Encounter::JawWorm, &relics_named(&refs).unwrap(), &mut Rng::new(seed))
}

fn starter() -> Vec<&'static str> {
    starter_deck().iter().map(|&c| c.def().name).collect()
}

/// `s` as before the opening draw (turn 0, the monsters' first rolls
/// done): the hand back in the draw pile, the relics' counters at rest.
fn unstarted(s: &CombatState) -> CombatState {
    let mut z = s.clone();
    let mut draw = z.draw().to_pile();
    draw.add_pile(z.hand.view());
    z.set_draw(draw);
    z.hand = Hand::default();
    z.turn = 0;
    z.stage = Stage::MonsterRolls { next: 5 };
    z
}

/// A pack power bound in the fight.
fn gen_power(s: &CombatState, id: &str) -> Power {
    let (b, p) = bind_power(&s.binding, id).unwrap();
    assert!(b == s.binding, "{id} is bound in the fight");
    p
}

#[test]
fn turn_start_draws() {
    let s = fight(Character::Ironclad, &starter(), &[], 1);
    assert_eq!((s.turn, s.stage), (1, Stage::PlayerTurn));
    assert_eq!(unstarted(&s).next_draw(), (5, 5));
    assert_eq!(s.next_draw(), (5, 5));
    let s = fight(Character::Silent, &starter(), &[], 1);
    assert_eq!(unstarted(&s).next_draw(), (7, 7), "the Silent's first turn draws 2 more");
    assert_eq!(s.next_draw(), (5, 5));
    let s = fight(Character::Ironclad, &starter(), &["Bag of Preparation"], 1);
    assert_eq!(unstarted(&s).next_draw(), (7, 7), "Bag of Preparation's 2 after the opening draw");
    assert_eq!(s.hand.len(), 7);
    assert_eq!(s.next_draw(), (5, 5));
}

#[test]
fn relic_and_power_draws() {
    let mut s = fight(Character::Ironclad, &starter(), &["Snecko Eye"], 1);
    assert_eq!(s.next_draw(), (7, 7), "Snecko Eye's 2 every turn");
    let mut s = fight(Character::Ironclad, &starter(), &[], 1);
    s.player.powers.add(Power::Brutality, 2);
    assert_eq!(s.next_draw(), (7, 7), "Brutality by its stacks");
}

/// A2: retained cards take the next hand's space.
#[test]
fn retained_cards_take_hand_space() {
    let mut s = fight(Character::Ironclad, &["Protect"; 10], &[], 1);
    assert_eq!(s.hand.len(), 5);
    end_turn(&mut s);
    s.advance(&mut Rng::new(2));
    assert_eq!(s.hand.len(), 10);
    assert_eq!(s.next_draw(), (0, 0));
    let mut s = vs(&[K::JawWorm], &["Protect"; 8], Some(100));
    s.set_draw(Pile::from_cards(&[card("Strike"); 10]));
    assert_eq!(s.next_draw(), (2, 2));
}

#[test]
fn runic_pyramid_keeps_the_hand_but_not_ethereal_cards() {
    let mut s = fight(Character::Ironclad, &starter(), &["Runic Pyramid"], 1);
    s.hand = Hand::from_cards(&[card("Strike"); 7]);
    assert_eq!(s.next_draw(), (3, 3));
    s.hand = Hand::from_cards(&[&[card("Strike"); 6][..], &[card("Dazed")]].concat());
    assert_eq!(s.next_draw(), (4, 4), "Dazed exhausts at turn end");
}

#[test]
fn dark_embrace_draws_for_an_ethereal_exhaust() {
    let mut s = fight(Character::Ironclad, &[&starter()[..], &["gen:Dark Embrace"]].concat(), &[], 1);
    let de = gen_power(&s, "DarkEmbrace");
    s.player.powers.add(de, 1);
    s.hand = Hand::from_cards(&[card("Strike"), card("Dazed")]);
    assert_eq!(s.next_draw(), (6, 6));
}

#[test]
fn pocketwatch_counts_plays() {
    let mut s = fight(Character::Ironclad, &["Defend"; 20], &["Pocketwatch"], 1);
    assert_eq!(unstarted(&s).next_draw(), (5, 5), "no Pocketwatch draw on turn 1");
    let defend = |s: &mut CombatState| {
        s.player.energy = 3;
        play(s, "Defend", None);
    };
    defend(&mut s);
    defend(&mut s);
    assert_eq!(s.hand.len(), 3);
    assert_eq!(s.next_draw(), (5, 8), "1 more play keeps it at 3 or fewer");
    defend(&mut s);
    let mut leaf = s.clone();
    leaf.apply_action(Action::EndTurn).unwrap();
    assert_eq!(leaf.next_draw(), (8, 8), "3 played");
    defend(&mut s);
    assert_eq!(s.next_draw(), (5, 5));
    let mut leaf = s.clone();
    leaf.apply_action(Action::EndTurn).unwrap();
    assert_eq!(leaf.next_draw(), (5, 5), "4 played");
}

/// Evolve draws for a Status drawn: a known one counts for both, an
/// unknown one for the most only.
#[test]
fn evolve_on_known_and_unknown_status() {
    let deck = [&starter()[..], &["gen:Evolve", "Headbutt", "Wild Strike"]].concat();
    let mut s = fight(Character::Ironclad, &deck, &[], 1);
    let ev = gen_power(&s, "Evolve");
    s.player.powers.add(ev, 1);
    s.hand = Hand::from_cards(&[card("Headbutt"), card("Wild Strike")]);
    s.set_draw(Pile::from_cards(&[card("Strike"); 6]));
    s.set_discard(Pile::from_cards(&[card("Dazed")]));
    s.player.energy = 3;
    play(&mut s, "Headbutt", Some(0));
    s.apply_action(Action::Choose(card("Dazed"))).unwrap();
    assert_eq!(s.top.known().collect::<Vec<_>>(), vec![card("Dazed")]);
    assert_eq!(s.next_draw(), (6, 6), "the known Dazed draws one more");
    let mut w = s.clone();
    w.set_discard(Pile::from_cards(&[card("Wound")]));
    assert_eq!(w.next_draw(), (6, 6), "a Wound in the discard comes only after a reshuffle");
    s.player.energy = 3;
    play(&mut s, "Wild Strike", Some(0));
    assert_eq!(s.next_draw(), (6, 7), "Wild Strike's Wound may be drawn");
}

/// Property (test 8, light): at End Turn leaves of random fights the turn
/// start draws a count within [min, max] (capped by the cards left).
#[test]
fn end_turn_leaves_bound_the_draw() {
    let deck = [&starter()[..], &["Pommel Strike", "Shrug It Off", "Protect", "gen:Battle Trance", "Brutality", "gen:Offering"]].concat();
    let mut checked = 0;
    for seed in 0..40 {
        let mut s = fight(Character::Ironclad, &deck, &["Bag of Preparation", "Pocketwatch", "Snecko Eye"][..(seed % 4) as usize], seed);
        let mut rng = Rng::new(seed);
        for _ in 0..200 {
            if s.is_over() {
                break;
            }
            let acts = s.legal_actions();
            let a = acts[rng.below(acts.len() as u32) as usize];
            if a == Action::EndTurn && rng.below(2) == 0 {
                let mut leaf = s.clone();
                leaf.apply_action(Action::EndTurn).unwrap();
                let (lo, hi) = leaf.next_draw();
                assert_eq!(lo, hi, "no CardDrawn draw hook held");
                // Jaw Worm adds no cards; a leaf paused before the discard
                // still holds the turn's hand.
                if matches!(leaf.stage, Stage::EndingTurn { .. }) {
                    s.step(a, &mut rng).unwrap();
                    continue;
                }
                let (kept, left) = (leaf.hand.len(), (leaf.draw().len() + leaf.discard().len()) as u8);
                let mut next = leaf.clone();
                next.advance(&mut rng);
                if next.is_over() || next.stage != Stage::PlayerTurn {
                    s.step(a, &mut rng).unwrap();
                    continue;
                }
                let drew = (next.hand.len() - kept) as u8;
                assert!((lo.min(left)..=hi.min(left)).contains(&drew), "seed {seed}: drew {drew}, next_draw ({lo}, {hi}), {left} left");
                checked += 1;
            }
            s.step(a, &mut rng).unwrap();
        }
    }
    assert!(checked > 20, "{checked} leaves checked");
}
