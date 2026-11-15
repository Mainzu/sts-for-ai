//! The Act 1 single-entry blocks (docs/specs/act1-singles.md), each entry
//! against its game class (the decompiled `aeubanks/sts`, named per test).

mod common;

use common::card;
use sts_engine::codec::{decode, encode};
use sts_engine::registry::{load_pack, potions_named, relics_named, Binding};
use sts_engine::state::{Queued, HAND_LIMIT};
use sts_engine::*;

const IRONCLAD: &str = include_str!("../../content/packs/act1-ironclad.json");
const POTIONS: &str = include_str!("../../content/packs/act1-potions.json");
const RELICS: &str = include_str!("../../content/packs/act1-relics.json");

/// The Ironclad pack first: its pool is what the discovery potions draw from.
fn load() {
    load_pack(IRONCLAD).unwrap();
    load_pack(RELICS).unwrap();
    load_pack(POTIONS).unwrap();
}

/// A Jaw Worm fight on the player's turn, holding `potions` (by game name)
/// and Sacred Bark when `bark`, with exactly `hand` and `discard` and 3
/// energy.
fn fight(potions: &[&str], bark: bool, hand: &[&str], discard: &[&str]) -> CombatState {
    load();
    let relics = if bark { relics_named(&["gen:Sacred Bark"]).unwrap() } else { vec![] };
    let mut s = CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &Binding::default(), 50, 80, Encounter::JawWorm, &relics, &mut Rng::new(3));
    let names: Vec<String> = potions.iter().map(|p| format!("gen:{p}")).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    s.give_potions(&potions_named(&refs).unwrap()).unwrap();
    s.hand = Hand::from_cards(&hand.iter().map(|n| card(n)).collect::<Vec<_>>());
    s.set_discard(Pile::from_cards(&discard.iter().map(|n| card(n)).collect::<Vec<_>>()));
    s.player.energy = 3;
    s
}

/// Uses the potion in slot `slot` (no target).
fn drink(s: &mut CombatState, slot: u8) {
    s.step(Action::UsePotion { slot, target: None }, &mut Rng::new(1)).unwrap();
}

fn choose(s: &mut CombatState, name: &str) {
    s.step(Action::Choose(card(name)), &mut Rng::new(1)).unwrap();
}

fn marked(s: &CombatState, name: &str) -> u8 {
    s.free_in_hand.count(card(name))
}

// Liquid Memories (`potions/LiquidMemories.java`: `BetterDiscardPileToHandAction(potency, 0)`,
// potency 1; the action's `setCostForTurn(0)` on each card it returns).
#[test]
fn liquid_memories_returns_a_card_at_cost_0() {
    let mut s = fight(&["Liquid Memories"], false, &[], &["Bash", "Defend"]);
    drink(&mut s, 0);
    assert!(s.pick().is_some());
    choose(&mut s, "Bash");
    assert_eq!((s.hand.count(card("Bash")), marked(&s, "Bash"), s.cost_of(card("Bash"))), (1, 1, 0));
    assert_eq!(s.stage, Stage::PlayerTurn);
    // Played at 0 energy: it costs nothing, and the mark goes with it.
    s.player.energy = 0;
    assert!(s.legal_actions().contains(&Action::Play { card: card("Bash"), target: Some(0) }));
    s.step(Action::Play { card: card("Bash"), target: Some(0) }, &mut Rng::new(1)).unwrap();
    assert_eq!((s.player.energy, s.free_in_hand.len()), (0, 0));
}

#[test]
fn the_marked_copy_is_played_first_and_kept_last() {
    // Two Bashes in hand, one returned marked: the first play spends 0, the
    // second 2.
    let mut s = fight(&["Liquid Memories"], false, &["Bash"], &["Bash"]);
    drink(&mut s, 0);
    choose(&mut s, "Bash");
    assert_eq!((s.hand.count(card("Bash")), marked(&s, "Bash")), (2, 1));
    s.step(Action::Play { card: card("Bash"), target: Some(0) }, &mut Rng::new(1)).unwrap();
    assert_eq!((s.player.energy, marked(&s, "Bash"), s.cost_of(card("Bash"))), (3, 0, 2));
    // A pick taking a copy from the hand takes the unmarked one first
    // (Gambler's Brew discards one Bash; the marked one stays).
    let mut s = fight(&["Liquid Memories", "Gambler's Brew"], false, &["Bash"], &["Bash"]);
    let slot = |s: &CombatState, name: &str| s.player.potions.iter().position(|p| p.name() == format!("gen:{name}")).unwrap() as u8;
    let i = slot(&s, "Liquid Memories");
    drink(&mut s, i);
    choose(&mut s, "Bash");
    let i = slot(&s, "Gambler's Brew");
    drink(&mut s, i);
    choose(&mut s, "Bash");
    assert_eq!((s.hand.count(card("Bash")), marked(&s, "Bash")), (1, 1));
    // Choosing the last copy takes the mark with it.
    choose(&mut s, "Bash");
    assert_eq!((s.hand.count(card("Bash")), s.free_in_hand.len()), (0, 0));
}

#[test]
fn the_mark_ends_with_the_turn() {
    let mut s = fight(&["Liquid Memories"], false, &[], &["Bash"]);
    drink(&mut s, 0);
    choose(&mut s, "Bash");
    assert_eq!(marked(&s, "Bash"), 1);
    let mut rng = Rng::new(12);
    s.step(Action::EndTurn, &mut rng).unwrap();
    s.advance(&mut rng);
    assert_eq!(s.stage, Stage::PlayerTurn);
    assert!(s.free_in_hand.is_empty());
    // A Bash drawn again costs 2.
    assert_eq!(s.cost_of(card("Bash")), 2);
}

#[test]
fn sacred_bark_returns_two() {
    let mut s = fight(&["Liquid Memories"], true, &[], &["Bash", "Strike", "Defend"]);
    drink(&mut s, 0);
    choose(&mut s, "Bash");
    choose(&mut s, "Strike");
    assert_eq!(s.stage, Stage::PlayerTurn);
    assert_eq!((marked(&s, "Bash"), marked(&s, "Strike"), s.hand.len()), (1, 1, 2));
}

#[test]
fn sacred_bark_returns_two_copies_free() {
    let mut s = fight(&["Liquid Memories"], true, &[], &["Bash", "Bash"]);
    drink(&mut s, 0);
    choose(&mut s, "Bash");
    choose(&mut s, "Bash");
    assert_eq!((s.hand.count(card("Bash")), marked(&s, "Bash")), (2, 2));
    // One played free, the other still free.
    s.step(Action::Play { card: card("Bash"), target: Some(0) }, &mut Rng::new(1)).unwrap();
    assert_eq!((s.player.energy, s.cost_of(card("Bash"))), (3, 0));
}

#[test]
fn a_won_fight_keeps_no_marks() {
    let mut s = fight(&["Liquid Memories"], false, &["Strike"], &["Bash"]);
    drink(&mut s, 0);
    choose(&mut s, "Bash");
    s.monsters[0].hp = 1;
    s.monsters[0].block = 0;
    s.step(Action::Play { card: card("Strike"), target: Some(0) }, &mut Rng::new(1)).unwrap();
    assert!(s.is_over());
    assert!(s.free_in_hand.is_empty());
}

#[test]
fn a_full_hand_takes_nothing_back() {
    let hand = ["Strike"; HAND_LIMIT];
    let mut s = fight(&["Liquid Memories"], false, &hand, &["Bash"]);
    drink(&mut s, 0);
    assert_eq!((s.stage, s.discard().count(card("Bash")), s.free_in_hand.len()), (Stage::PlayerTurn, 1, 0));
}

#[test]
fn mark_free_in_hand_rules() {
    // `AbstractCard.setCostForTurn` changes only `costForTurn >= 0`: an X
    // cost (-1) or unplayable card (-2) keeps its cost; a 0-cost card would
    // gain nothing. Never more marks than copies in hand.
    let mut s = fight(&[], false, &["Whirlwind", "Wound", "Anger", "Bash"], &[]);
    for name in ["Whirlwind", "Wound", "Anger"] {
        assert!(!s.mark_free_in_hand(card(name)), "{name}");
    }
    assert!(!s.mark_free_in_hand(card("Strike")), "not in hand");
    assert!(s.mark_free_in_hand(card("Bash")));
    assert!(!s.mark_free_in_hand(card("Bash")), "one copy, one mark");
    assert_eq!(s.free_in_hand.len(), 1);
    // Two copies take two marks, a third call none.
    s.hand.add(card("Bash"), 1);
    assert!(s.mark_free_in_hand(card("Bash")));
    assert!(!s.mark_free_in_hand(card("Bash")));
    assert_eq!(s.free_in_hand.count(card("Bash")), 2);
    // Whirlwind returned by Liquid Memories stays X-cost.
    let mut s = fight(&["Liquid Memories"], false, &[], &["Whirlwind"]);
    drink(&mut s, 0);
    choose(&mut s, "Whirlwind");
    assert_eq!((s.hand.count(card("Whirlwind")), s.free_in_hand.len()), (1, 0));
}

#[test]
fn an_upgrade_keeps_the_mark() {
    // `AbstractCard.upgradeBaseCost` leaves a `costForTurn` of 0 at 0:
    // Blessing of the Forge upgrades the marked Bash, which stays free.
    let mut s = fight(&["Liquid Memories", "Blessing of the Forge"], false, &["Bash"], &["Bash"]);
    let slot = |s: &CombatState, name: &str| s.player.potions.iter().position(|p| p.name() == format!("gen:{name}")).unwrap() as u8;
    let i = slot(&s, "Liquid Memories");
    drink(&mut s, i);
    choose(&mut s, "Bash");
    let i = slot(&s, "Blessing of the Forge");
    drink(&mut s, i);
    let up = card("Bash+");
    assert_eq!((s.hand.count(up), s.free_in_hand.count(up), s.free_in_hand.len()), (2, 1, 1));
    assert_eq!(s.cost_of(up), 0);
}

#[test]
fn a_marked_state_round_trips() {
    let mut s = fight(&["Liquid Memories"], false, &["Strike"], &["Bash"]);
    drink(&mut s, 0);
    choose(&mut s, "Bash");
    assert!(!s.has_generated(), "{:?}", s.binding);
    let bytes = encode(&s);
    assert_eq!(decode(&bytes), s);
    // An unmarked state encodes without the section: the same bytes as one
    // that never had a mark.
    let mut t = s;
    t.free_in_hand = Default::default();
    assert_eq!(encode(&t).len() + 3, bytes.len());
}

#[test]
fn free_this_turn_only_on_a_pick_into_the_hand() {
    let e = load_pack(r#"{"version": 2, "potions": [{"id": "ft-bad", "rarity": "common", "effects": [{"Pick": {"kind": "DiscardFromHand", "n": 1, "free_this_turn": true}}]}]}"#).unwrap_err();
    assert!(e.contains("free_this_turn"), "{e}");
}

/// A Cultist fight from the starter deck plus `extra` (pack cards by game
/// name), holding these relics (game names), the first relic's counter set
/// to `counter` when given; turn 1 like later turns when `pre_draw`.
fn relic_fight(relics: &[&str], extra: &[&str], counter: Option<i16>, pre_draw: bool) -> CombatState {
    load();
    load_pack(IRONCLAD).unwrap();
    let names: Vec<String> = relics.iter().map(|r| format!("gen:{r}")).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    let mut given = relics_named(&refs).unwrap();
    if let Some(c) = counter {
        given[0].1.counter = c;
    }
    let mut deck: Vec<String> = starter_deck().iter().map(|&c| c.def().name.to_string()).collect();
    deck.extend(extra.iter().map(|n| format!("gen:{n}")));
    let deck_refs: Vec<&str> = deck.iter().map(String::as_str).collect();
    let (ids, b) = sts_engine::registry::bind(&deck_refs).unwrap();
    CombatState::new_bound_turn1(Character::Ironclad, &ids, &b, 80, 80, Encounter::Cultist, &given, pre_draw, Default::default(), None, &mut Rng::new(5))
}

/// Plays `name`, putting it in hand first if it isn't there, with energy
/// enough; targets monster 0.
fn play_card(s: &mut CombatState, c: CardId) {
    if s.hand.count(c) == 0 {
        s.hand.add(c, 1);
    }
    s.player.energy = s.player.energy.max(3);
    let target = if s.binding.def(c).targeted() { Some(0) } else { None };
    s.step(Action::Play { card: c, target }, &mut Rng::new(13)).unwrap();
}

fn end_turn(s: &mut CombatState) {
    let mut rng = Rng::new(12);
    s.step(Action::EndTurn, &mut rng).unwrap();
    s.advance(&mut rng);
    assert!(!s.is_over());
    assert_eq!(s.stage, Stage::PlayerTurn);
}

// Art of War (`relics/ArtOfWar.java`): `atPreBattle` sets `firstTurn`;
// `atTurnStart` gains 1 energy when `gainEnergyNext && !firstTurn`; an
// Attack's `onUseCard` clears `gainEnergyNext`.
#[test]
fn art_of_war() {
    for pre_draw in [false, true] {
        // Turn 1 never gains; a turn with no Attack gives turn 2 its +1.
        let mut s = relic_fight(&["Art of War"], &[], None, pre_draw);
        assert_eq!(s.player.energy, 3, "turn 1");
        play_card(&mut s, card("Defend"));
        end_turn(&mut s);
        assert_eq!(s.player.energy, 4, "after a Skill-only turn");
        // A turn with an Attack: none.
        play_card(&mut s, card("Strike"));
        end_turn(&mut s);
        assert_eq!(s.player.energy, 3, "after an Attack");
        // A caller's counter 1 is reset at the fight's start: no turn-1 energy.
        let s = relic_fight(&["Art of War"], &[], Some(1), pre_draw);
        assert_eq!(s.player.energy, 3, "a caller's counter");
    }
}

// Pocketwatch (`relics/Pocketwatch.java`): `atBattleStart` sets the
// counter to 0 and `firstTurn`; `onPlayCard` adds 1 to the counter for each
// card played (`GameActionManager.getNextAction`, every card queue item
// that passes `canUse` and isn't `dontTriggerOnUseCard`: Double Tap's copy
// and Havoc's card too); `atTurnStartPostDraw` draws 3 when the counter is
// at most 3 and it isn't the first turn (else clears `firstTurn`), then
// sets the counter to 0; `onVictory` sets it to -1.
#[test]
fn pocketwatch() {
    let mut s = relic_fight(&["Pocketwatch"], &[], None, false);
    assert_eq!(s.hand.len(), 5, "turn 1 draws no more");
    assert_eq!(s.player.relics.counter(0), 0);
    for (n, c) in ["Strike", "Strike", "Defend"].into_iter().enumerate() {
        play_card(&mut s, card(c));
        assert_eq!(s.player.relics.counter(0), n as i16 + 1, "one per card played");
    }
    end_turn(&mut s);
    assert_eq!(s.hand.len(), 8, "3 played: 5 + 3");
    assert_eq!(s.player.relics.counter(0), 0, "reset after the post-draw");
    for c in ["Strike", "Strike", "Defend", "Defend"] {
        play_card(&mut s, card(c));
    }
    assert_eq!(s.player.relics.counter(0), 4);
    end_turn(&mut s);
    assert_eq!((s.hand.len(), s.player.relics.counter(0)), (5, 0), "4 played: no draw, reset");
    end_turn(&mut s);
    assert_eq!(s.hand.len(), 8, "none played: 0 is at most 3");
    // The first turn: the counter a caller gives (a fight rebuilt from the
    // game) is reset at the fight's start, and turn 1 never draws.
    let s = relic_fight(&["Pocketwatch"], &[], Some(2), false);
    assert_eq!((s.hand.len(), s.player.relics.counter(0)), (5, 0));
    // The game's count passes through a rebuilt turn: 2 played before it,
    // 2 more make 4, no draw.
    let mut s = relic_fight(&["Pocketwatch"], &[], None, false);
    end_turn(&mut s);
    s.player.relics.set_counter(0, 2);
    play_card(&mut s, card("Strike"));
    assert_eq!(s.player.relics.counter(0), 3);
    let mut t = s.clone();
    end_turn(&mut t);
    assert_eq!(t.hand.len(), 5 + 3, "3: draws");
    play_card(&mut s, card("Defend"));
    end_turn(&mut s);
    assert_eq!(s.hand.len(), 5, "4: no draw");
    // Double Tap, then Strike: Double Tap, Strike and its copy are 3 plays.
    let mut s = relic_fight(&["Pocketwatch"], &["Double Tap"], None, false);
    let dt = sts_engine::registry::bind(&["gen:Double Tap"]).unwrap().0[0];
    let dt = if s.binding.def(dt).name == "gen:Double Tap" { dt } else { panic!("Double Tap's id") };
    play_card(&mut s, dt);
    play_card(&mut s, card("Strike"));
    assert_eq!((s.cards_played_this_turn, s.player.relics.counter(0)), (3, 3), "the copy counts");
    end_turn(&mut s);
    assert_eq!(s.hand.len(), 8, "3 plays with the copy");
    let mut s = relic_fight(&["Pocketwatch"], &["Double Tap"], None, false);
    play_card(&mut s, dt);
    play_card(&mut s, card("Strike"));
    play_card(&mut s, card("Strike"));
    assert_eq!(s.player.relics.counter(0), 4);
    end_turn(&mut s);
    assert_eq!(s.hand.len(), 5, "4 plays with the copy");
    // Havoc's card counts: Havoc and the Strike it plays are 2.
    let mut s = relic_fight(&["Pocketwatch"], &["Havoc"], None, false);
    let havoc = sts_engine::registry::bind(&["gen:Havoc"]).unwrap().0[0];
    assert_eq!(s.binding.def(havoc).name, "gen:Havoc");
    s.set_draw(Pile::from_cards(&[card("Strike")]));
    play_card(&mut s, havoc);
    assert_eq!((s.cards_played_this_turn, s.player.relics.counter(0)), (2, 2), "Havoc's card counts");
}

// Distilled Chaos (`potions/DistilledChaosPotion.java`, potency 3): one
// `PlayTopCardAction` per potency, each with a random monster chosen at
// use. Each takes the top card (`EmptyDeckShuffleAction` first when the
// draw pile is empty; nothing when both piles are) and queues it to
// autoplay; all are taken before any plays (`GameActionManager` ~183:
// the card queue waits for the actions). An autoplayed card costs nothing
// (`AbstractPlayer.useCard` ~1360), counts as played (~235), and an X-cost
// one plays at the energy when queued without spending it (~1348).

/// A Jaw Worm fight at the player's turn with exactly `draw` (game names)
/// as the draw pile, an empty hand and discard pile, Jaw Worm at 200 HP.
fn chaos(draw: &[&str], bark: bool) -> CombatState {
    let mut s = fight(&["Distilled Chaos"], bark, &[], &[]);
    s.set_draw(Pile::from_cards(&draw.iter().map(|n| card(n)).collect::<Vec<_>>()));
    s.monsters[0].hp = 200;
    s.monsters[0].max_hp = 200;
    s.monsters[0].block = 0;
    s
}

#[test]
fn distilled_chaos_plays_the_top_three_free() {
    let mut s = chaos(&["Strike", "Strike", "Strike", "Strike"], false);
    drink(&mut s, 0);
    assert_eq!(s.stage, Stage::PlayerTurn);
    assert_eq!((s.monsters[0].hp, s.player.energy, s.cards_played_this_turn), (200 - 18, 3, 3));
    assert_eq!((s.draw().len(), s.discard().count(card("Strike")), s.hand.len()), (1, 3, 0));
    // Sacred Bark: 6.
    let mut s = chaos(&["Strike"; 6], true);
    drink(&mut s, 0);
    assert_eq!((s.monsters[0].hp, s.cards_played_this_turn), (200 - 36, 6));
}

#[test]
fn distilled_chaos_reshuffles_once_the_draw_pile_is_empty() {
    // One card on the draw pile, two in the discard: the one, then the
    // reshuffled two; the first is in limbo, so it can't come back.
    let mut s = chaos(&["Strike"], false);
    s.set_discard(Pile::from_cards(&[card("Defend"), card("Defend")]));
    drink(&mut s, 0);
    assert_eq!((s.monsters[0].hp, s.player.block, s.cards_played_this_turn), (194, 10, 3));
    assert_eq!((s.draw().len(), s.discard().len()), (0, 3));
    // Both piles empty: nothing.
    let mut s = chaos(&[], false);
    drink(&mut s, 0);
    assert_eq!((s.cards_played_this_turn, s.stage), (0, Stage::PlayerTurn));
}

#[test]
fn the_cards_are_taken_before_any_plays() {
    // Three Pommel Strikes, each drawing 1: all three were taken first, so
    // the first draws nothing (both piles empty); the second reshuffles the
    // first back and draws it, the third the second. Taken one at a time,
    // the first would draw the second and only two would play.
    let mut s = chaos(&["Pommel Strike"; 3], false);
    drink(&mut s, 0);
    assert_eq!((s.hand.len(), s.discard().count(card("Pommel Strike")), s.cards_played_this_turn), (2, 1, 3));
}

#[test]
fn a_card_that_cant_play_goes_to_the_discard_pile() {
    // A Wound is unplayable (`AbstractCard.canUse` false): discarded, not
    // counted (`GameActionManager` ~287: `UseCardAction` with
    // `dontTriggerOnUseCard`).
    let mut s = chaos(&["Wound"], false);
    drink(&mut s, 0);
    assert_eq!((s.discard().count(card("Wound")), s.cards_played_this_turn), (1, 0));
    // Its target died first: the second Strike does nothing
    // (`cardPlayable` false on a dying monster).
    let mut s = chaos(&[], false);
    s.monsters[1] = s.monsters[0];
    s.monsters[0].hp = 6;
    for _ in 0..2 {
        s.top_queue.push(Queued { card: card("Strike"), target: Some(0), x: 0, exhaust: false });
    }
    drink(&mut s, 0);
    assert_eq!((s.monsters[0].hp, s.monsters[1].hp, s.cards_played_this_turn), (0, 200, 1));
    assert_eq!((s.discard().count(card("Strike")), s.stage), (2, Stage::PlayerTurn));
}

#[test]
fn an_x_cost_card_plays_at_the_energy_when_taken() {
    // Whirlwind: 5 damage X times, X the energy at use (3), none spent.
    let mut s = chaos(&["Whirlwind"], false);
    drink(&mut s, 0);
    assert_eq!((s.monsters[0].hp, s.player.energy), (200 - 15, 3));
}

#[test]
fn a_queued_pick_pauses_and_the_queue_goes_on() {
    // Two Survivors (8 Block, discard 1): the first opens its pick, the
    // second waits in the queue (and round-trips through the codec there).
    let mut s = chaos(&["Survivor", "Survivor"], false);
    s.hand = Hand::from_cards(&[card("Strike")]);
    drink(&mut s, 0);
    assert!(s.pick().is_some());
    assert_eq!(s.top_queue.len(), 1);
    assert!(!s.has_generated());
    assert_eq!(decode(&encode(&s)), s);
    choose(&mut s, "Strike");
    // The second Survivor: 8 more Block, nothing to discard.
    assert_eq!((s.player.block, s.cards_played_this_turn, s.stage), (16, 2, Stage::PlayerTurn));
    assert_eq!((s.discard().count(card("Survivor")), s.discard().count(card("Strike"))), (2, 1));
}

#[test]
fn the_take_is_a_chance_event_while_uncertain() {
    // Two kinds on the draw pile: the take pauses; its outcomes sum to 1,
    // each card as likely as its count, and the open event round-trips.
    let mut s = chaos(&["Strike", "Strike", "Defend"], false);
    s.apply_action(Action::UsePotion { slot: 0, target: None }).unwrap();
    assert!(matches!(s.pending, Some(ChanceEvent::TakeTop { exhaust: false })));
    assert_eq!(decode(&encode(&s)), s);
    let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(100) else { panic!("listed") };
    let total: f64 = v.iter().map(|(p, _)| p).sum();
    assert!((total - 1.0).abs() < 1e-9, "{total}");
    // Two monsters: each card that targets one splits by target.
    let mut s = chaos(&["Strike", "Defend"], false);
    s.monsters[1] = s.monsters[0];
    s.apply_action(Action::UsePotion { slot: 0, target: None }).unwrap();
    let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(100) else { panic!("listed") };
    assert!(v.len() >= 2);
    let total: f64 = v.iter().map(|(p, _)| p).sum();
    assert!((total - 1.0).abs() < 1e-9, "{total}");
}

#[test]
fn greedy_and_the_search_finish_fights_holding_it() {
    use sts_engine::agent::greedy_action;
    use sts_engine::search::{search, Heuristic, SearchConfig};
    for seed in 0..3 {
        let mut s = fight(&["Distilled Chaos"], false, &[], &[]);
        let mut rng = Rng::new(seed);
        let mut n = 0;
        while !s.is_over() && n < 200 {
            let a = if n % 2 == 0 { greedy_action(&s) } else { search(&s, &mut Heuristic, &SearchConfig { seed, ..SearchConfig::default() }).action };
            s.step(a, &mut rng).unwrap();
            n += 1;
        }
        assert!(s.is_over(), "seed {seed}");
    }
}

// Havoc (`cards/red/Havoc.java`): cost 1 (upgraded 0), `PlayTopCardAction`
// with exhaust: the card it plays exhausts (`exhaustOnUseOnce`).
#[test]
fn havoc() {
    load();
    load_pack(IRONCLAD).unwrap();
    let (ids, b) = sts_engine::registry::bind(&["gen:Havoc", "gen:Havoc+", "Strike", "Wound"]).unwrap();
    let mut s = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &mut Rng::new(1));
    let (havoc, up) = (ids[0], ids[1]);
    assert_eq!((s.binding.def(havoc).cost(), s.binding.def(up).cost()), (1, 0));
    s.hand = Hand::from_cards(&[havoc]);
    s.set_draw(Pile::from_cards(&[card("Strike")]));
    s.set_discard(Pile::default());
    s.player.energy = 3;
    s.monsters[0].hp = 50;
    s.monsters[0].block = 0;
    s.step(Action::Play { card: havoc, target: None }, &mut Rng::new(1)).unwrap();
    assert_eq!((s.monsters[0].hp, s.player.energy, s.cards_played_this_turn), (44, 2, 2));
    assert_eq!((s.exhaust().count(card("Strike")), s.discard().count(havoc)), (1, 1));
    // A Havoc'd card paused at its pick round-trips with its exhaust mark
    // (bit 1 of the in-play copy byte).
    let mut u = fight(&["Distilled Chaos"], false, &["Strike"], &[]);
    u.set_draw(Pile::default());
    u.top_queue.push(Queued { card: card("Survivor"), target: None, x: 0, exhaust: true });
    drink(&mut u, 0);
    assert!(matches!(u.stage, Stage::PlayingCard { more, .. } if more.exhaust && more.pick.is_some()), "{:?}", u.stage);
    assert_eq!(decode(&encode(&u)), u);
    choose(&mut u, "Strike");
    assert_eq!(u.exhaust().count(card("Survivor")), 1);
    // An unplayable card it takes is exhausted too.
    s.hand = Hand::from_cards(&[up]);
    s.set_draw(Pile::from_cards(&[card("Wound")]));
    s.step(Action::Play { card: up, target: None }, &mut Rng::new(1)).unwrap();
    assert_eq!((s.exhaust().count(card("Wound")), s.player.energy), (1, 2));
}

// Perfected Strike played by Havoc (`PlayTopCardAction` puts it in limbo)
// or as Double Tap's copy (`makeSameInstanceOf` in limbo, the original
// already discarded) doesn't count itself: `PerfectedStrike.countCards`
// reads hand, draw and discard only. Played from the hand it does (live run
// 2026-11-14, The Guardian: 18 damage where the engine said 21).
#[test]
fn perfected_strike_from_limbo_does_not_count_itself() {
    load();
    load_pack(IRONCLAD).unwrap();
    let (ids, b) = sts_engine::registry::bind(&["gen:Havoc", "gen:Double Tap", "Perfected Strike", "Strike"]).unwrap();
    let (havoc, tap, ps) = (ids[0], ids[1], ids[2]);
    let mut s = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &mut Rng::new(1));
    s.monsters[0].hp = 80;
    s.monsters[0].block = 0;
    s.player.energy = 3;
    s.hand = Hand::from_cards(&[havoc]);
    s.set_draw(Pile::from_cards(&[ps]));
    s.set_discard(Pile::from_cards(&[card("Strike"), card("Strike")]));
    s.step(Action::Play { card: havoc, target: None }, &mut Rng::new(1)).unwrap();
    assert_eq!(s.monsters[0].hp, 80 - (6 + 2 * 2));
    // Double Tap: the first play counts itself (in the hand), the copy
    // counts the original (now in the discard pile) but not itself.
    let mut t = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &mut Rng::new(1));
    t.monsters[0].hp = 80;
    t.monsters[0].block = 0;
    t.player.energy = 3;
    t.hand = Hand::from_cards(&[tap, ps]);
    t.set_draw(Pile::default());
    t.set_discard(Pile::default());
    t.step(Action::Play { card: tap, target: None }, &mut Rng::new(1)).unwrap();
    t.step(Action::Play { card: ps, target: Some(0) }, &mut Rng::new(1)).unwrap();
    assert_eq!(t.monsters[0].hp, 80 - 2 * (6 + 2));
    // Played from the hand it counts itself (cards_ironclad.rs has the rest).
    t.hand = Hand::from_cards(&[ps]);
    t.set_discard(Pile::default());
    t.player.energy = 3;
    t.monsters[0].block = 0;
    let hp = t.monsters[0].hp;
    t.step(Action::Play { card: ps, target: Some(0) }, &mut Rng::new(1)).unwrap();
    assert_eq!(t.monsters[0].hp, hp - (6 + 2));
}

// Entropic Brew (`potions/EntropicBrew.java`: one
// `ObtainPotionAction(returnRandomPotion(true))` per potion slot, full ones
// skipped; `AbstractDungeon.returnRandomPotion` ~809: a 0-99 roll, common
// below 65, uncommon below 90, else rare, then uniform within, never Fruit
// Juice) and Potion Belt (`relics/PotionBelt.java`, +2 slots).

/// A Jaw Worm fight holding `potions` (by game name) and `relics`.
fn brew_fight_with(potions: &[&str], relics: &[&str]) -> CombatState {
    load();
    let relics: Vec<String> = relics.iter().map(|r| format!("gen:{r}")).collect();
    let relics = relics_named(&relics.iter().map(String::as_str).collect::<Vec<_>>()).unwrap();
    let mut s = CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &Binding::default(), 50, 80, Encounter::JawWorm, &relics, &mut Rng::new(3));
    let names: Vec<String> = potions.iter().map(|p| format!("gen:{p}")).collect();
    let refs: Vec<&str> = names.iter().map(String::as_str).collect();
    s.give_potions(&potions_named(&refs).unwrap()).unwrap();
    s
}

/// `brew_fight_with`, with Potion Belt when `belt`.
fn brew_fight(potions: &[&str], belt: bool) -> CombatState {
    brew_fight_with(potions, if belt { &["Potion Belt"] } else { &[] })
}

fn slot_of(s: &CombatState, name: &str) -> u8 {
    s.player.potions.iter().position(|p| p.name() == format!("gen:{name}")).unwrap() as u8
}

/// Drinks the Brew in `s` and samples what it makes with `seed`.
fn brew(mut s: CombatState, seed: u64) -> CombatState {
    let mut rng = Rng::new(seed);
    s.step(Action::UsePotion { slot: slot_of(&s, "Entropic Brew"), target: None }, &mut rng).unwrap();
    s.advance(&mut rng);
    assert_eq!(s.stage, Stage::PlayerTurn);
    s
}

fn brewed(potions: &[&str], belt: bool, seed: u64) -> CombatState {
    brew(brew_fight(potions, belt), seed)
}

#[test]
fn entropic_brew_fills_every_empty_slot() {
    for seed in 0..20 {
        // Alone: its own slot and the two empty ones.
        let s = brewed(&["Entropic Brew"], false, seed);
        assert_eq!(s.player.potions.len(), 3);
        // Two others held: the slot it left.
        let s = brewed(&["Entropic Brew", "Block Potion", "Fire Potion"], false, seed);
        assert_eq!(s.player.potions.len(), 3);
        let names: Vec<&str> = s.player.potions.iter().map(|p| p.name()).collect();
        assert!(names.contains(&"gen:Block Potion") && names.contains(&"gen:Fire Potion"), "{names:?}");
        // Potion Belt: 5 slots, 5 - held made.
        let s = brewed(&["Entropic Brew"], true, seed);
        assert_eq!(s.player.potions.len(), 5);
        assert!(s.player.potions.iter().all(|p| p.name() != "gen:Fruit Juice"));
        assert_eq!(brewed(&["Entropic Brew", "Block Potion"], true, seed).player.potions.len(), 5);
        // More potions than slots (allowed): it fills none.
        let held = ["Entropic Brew", "Block Potion", "Fire Potion", "Swift Potion", "Weak Potion"];
        assert_eq!(brewed(&held, false, seed).player.potions.len(), 4);
        // Sacred Bark doesn't change it (the loop reads the slots, not potency).
        assert_eq!(brew(brew_fight_with(&["Entropic Brew"], &["Sacred Bark"]), seed).player.potions.len(), 3);
    }
}

#[test]
fn one_slot_odds() {
    // One empty slot: 65/25/10 by rarity, uniform within, no Fruit Juice.
    let mut s = brew_fight(&["Entropic Brew", "Block Potion", "Fire Potion"], false);
    s.apply_action(Action::UsePotion { slot: slot_of(&s, "Entropic Brew"), target: None }).unwrap();
    let Some(chance::ChanceOutcomes::Listed(outs)) = s.chance_outcomes(1000) else { panic!("a listed chance event") };
    let pack = registry::json::parse(POTIONS).unwrap();
    let rarities: Vec<(String, String)> = pack
        .get("potions")
        .unwrap()
        .items()
        .iter()
        .map(|p| (format!("gen:{}", p.get("id").unwrap().str().unwrap()), p.get("rarity").unwrap().str().unwrap().to_string()))
        .filter(|(id, _)| id != "gen:Fruit Juice")
        .collect();
    let count = |r: &str| rarities.iter().filter(|(_, x)| x == r).count() as f64;
    assert_eq!(outs.len(), rarities.len());
    let total: f64 = outs.iter().map(|(p, _)| p).sum();
    assert!((total - 1.0).abs() < 1e-9, "{total}");
    for (p, t) in &outs {
        assert_eq!(t.stage, Stage::PlayerTurn);
        let mut left: Vec<&str> = t.player.potions.iter().map(|p| p.name()).collect();
        for held in ["gen:Block Potion", "gen:Fire Potion"] {
            left.remove(left.iter().position(|n| *n == held).unwrap());
        }
        let [made] = left[..] else { panic!("{left:?}") };
        let r = &rarities.iter().find(|(id, _)| id == made).unwrap().1;
        let w = match r.as_str() {
            "common" => 0.65,
            "uncommon" => 0.25,
            _ => 0.10,
        };
        assert!((p - w / count(r)).abs() < 1e-9, "{made}: {p}");
    }
    // Sampled the same way: a rare about a tenth of the time.
    let rare = (0..2000)
        .filter(|&seed| {
            let s = brewed(&["Entropic Brew", "Block Potion", "Fire Potion"], false, seed);
            let rare = s.player.potions.iter().any(|p| p.spec().unwrap().rarity == potions::Rarity::Rare);
            rare
        })
        .count();
    assert!((140..260).contains(&rare), "{rare} rares in 2000");
}

#[test]
fn a_potion_it_makes_works() {
    // Speed Potion's pack power (LoseDexterity) is bound with the Brew.
    let mut s = brew_fight(&["Entropic Brew", "Block Potion", "Fire Potion"], false);
    s.apply_action(Action::UsePotion { slot: slot_of(&s, "Entropic Brew"), target: None }).unwrap();
    let Some(chance::ChanceOutcomes::Listed(outs)) = s.chance_outcomes(1000) else { panic!("a listed chance event") };
    let with = |name: &str| outs.iter().map(|(_, t)| t.clone()).find(|t| t.player.potions.iter().any(|p| p.name() == format!("gen:{name}"))).unwrap();
    let mut t = with("Speed Potion");
    t.step(Action::UsePotion { slot: slot_of(&t, "Speed Potion"), target: None }, &mut Rng::new(1)).unwrap();
    let lose = registry::bind_power(&t.binding, "LoseDexterity").unwrap().1;
    assert_eq!((t.player.powers.get(Power::Dexterity), t.player.powers.get(lose)), (5, 5));
    // Essence of Steel's too, and Attack Potion's cards (its discovery).
    let mut t = with("Essence of Steel");
    t.step(Action::UsePotion { slot: slot_of(&t, "Essence of Steel"), target: None }, &mut Rng::new(1)).unwrap();
    assert_eq!(t.player.powers.get(registry::bind_power(&t.binding, "PlatedArmor").unwrap().1), 4);
    let mut t = with("Attack Potion");
    let mut rng = Rng::new(2);
    t.step(Action::UsePotion { slot: slot_of(&t, "Attack Potion"), target: None }, &mut rng).unwrap();
    t.advance(&mut rng);
    assert!(t.pick().is_some());
}

#[test]
fn obtain_random_potions_load_errors() {
    // A rarity with no potion in the pool: the game would draw forever.
    let no_rare = r#"{"version": 2, "potions": [
        {"id": "orp-c", "rarity": "common", "effects": [{"Block": 1}]},
        {"id": "orp-u", "rarity": "uncommon", "effects": [{"Block": 2}]},
        {"id": "orp-b", "rarity": "rare", "effects": [{"ObtainRandomPotions": {"except": ["orp-b"]}}]}]}"#;
    let e = load_pack(no_rare).unwrap_err();
    assert!(e.contains("no rare potion"), "{e}");
    // `except` names a potion of the pack.
    let e = load_pack(r#"{"version": 2, "potions": [{"id": "orp-x", "rarity": "rare", "effects": [{"ObtainRandomPotions": {"except": ["orp-none"]}}]}]}"#).unwrap_err();
    assert!(e.contains("orp-none"), "{e}");
    // A pack potion's effect only.
    let e = load_pack(r#"{"version": 2, "cards": [{"id": "orp-card", "cost": 1, "type": "Skill", "effects": ["ObtainRandomPotions"]}]}"#).unwrap_err();
    assert!(e.contains("ObtainRandomPotions"), "{e}");
    let e = load_pack(r#"{"version": 2, "relics": [{"id": "orp-r", "rarity": "shop", "potion_slots": -1}]}"#).unwrap_err();
    assert!(e.contains("potion_slots"), "{e}");
}

#[test]
fn a_smoke_bomb_it_makes_after_a_split_isnt_legal() {
    // SmokeBomb.java canUse: never in a boss room. Slime Boss's split leaves
    // no slot holding a boss, so a fight holding a maker carries the mark.
    use sts_engine::monsters::{slime_boss, MonsterKind as K};
    load();
    let mut s = CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &Binding::default(), 500, 500, Encounter::SlimeBoss, &[], &mut Rng::new(3));
    s.give_potions(&potions_named(&["gen:Entropic Brew", "gen:Block Potion", "gen:Fire Potion"]).unwrap()).unwrap();
    assert!(s.boss_fight);
    s.monsters[0].hp = 70;
    s.monsters[0].set_move(slime_boss::SPLIT);
    end_turn(&mut s);
    assert!(s.monsters.iter().all(|m| m.kind != K::SlimeBoss));
    s.apply_action(Action::UsePotion { slot: slot_of(&s, "Entropic Brew"), target: None }).unwrap();
    let Some(chance::ChanceOutcomes::Listed(outs)) = s.chance_outcomes(1000) else { panic!("a listed chance event") };
    let t = outs.iter().map(|(_, t)| t).find(|t| t.player.potions.iter().any(|p| p.name() == "gen:Smoke Bomb")).unwrap();
    assert!(!t.is_legal(Action::UsePotion { slot: slot_of(t, "Smoke Bomb"), target: None }));
    // A boss fight holding no maker or boss-bound potion carries no mark.
    let mut u = CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &Binding::default(), 500, 500, Encounter::SlimeBoss, &[], &mut Rng::new(3));
    u.give_potions(&potions_named(&["gen:Fire Potion"]).unwrap()).unwrap();
    assert!(!u.boss_fight);
}

#[test]
fn every_ironclad_pack_card_and_the_brew_bind() {
    // The Brew brings Attack, Skill and Power Potion, so a fight given it
    // binds every pack card of the Ironclad pool (33 with Havoc): past the
    // old 32 card slots, within the 40 (docs/specs/act1-singles.md section 5).
    load();
    let pack = registry::json::parse(IRONCLAD).unwrap();
    let mut deck: Vec<String> = starter_deck().iter().map(|&c| c.def().name.to_string()).collect();
    for c in pack.get("cards").unwrap().items() {
        let id = c.get("id").unwrap().str().unwrap();
        if !id.ends_with('+') {
            deck.push(format!("gen:{id}"));
        }
    }
    assert!(deck.len() > 32 + 10, "{}", deck.len());
    let (ids, b) = registry::bind(&deck.iter().map(String::as_str).collect::<Vec<_>>()).unwrap();
    let mut s = CombatState::new_bound_with(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &[], &mut Rng::new(3));
    s.give_potions(&potions_named(&["gen:Entropic Brew"]).unwrap()).unwrap();
    // Every potion it makes can be drunk.
    for seed in 0..10 {
        let mut t = brew(s.clone(), seed);
        for _ in 0..3 {
            let mut rng = Rng::new(seed);
            let Some(a) = t.legal_actions().into_iter().find(|a| matches!(a, Action::UsePotion { .. })) else { break };
            t.step(a, &mut rng).unwrap();
            while t.pick().is_some() && !t.is_over() {
                let a = t.legal_actions()[0];
                t.step(a, &mut rng).unwrap();
            }
            if t.is_over() {
                break;
            }
        }
    }
}
