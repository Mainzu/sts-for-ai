//! Random-agent fuzzing with invariants after every step, over every
//! encounter, with the starter deck and with the starter plus 5 random
//! in-scope cards, for the Ironclad and the Silent (Silent extras from its
//! whole pool, Poison included; Ironclad extras include the held-out cards). Full run:
//! `cargo test --release --test fuzz -- --ignored`.

mod common;
use common::*;
use sts_engine::agent::random_action;
use sts_engine::cards::{class_cards, held_out_cards};
use sts_engine::*;

fn deck_for(character: Character, i: u64, rng: &mut Rng) -> Vec<CardId> {
    let mut deck = character.starter_deck();
    if i % 2 == 1 {
        let mut pool: Vec<CardId> = class_cards(character.class()).collect();
        if character == Character::Ironclad {
            pool.extend(held_out_cards());
        }
        // Rules-engine proving content of the character's class.
        let proving = sts_engine::card_sets::get("proving").expect("the proving set");
        pool.extend(proving.iter().filter(|c| c.def().class == character.class()));
        for _ in 0..5 {
            deck.push(pool[rng.below(pool.len() as u32) as usize]);
        }
    }
    deck
}

fn run_fuzz(character: Character, combats: u64) -> (u64, u64) {
    let mut wins = 0;
    let hp = character.max_hp();
    for i in 0..combats {
        let enc = Encounter::ALL[(i / 2 % Encounter::ALL.len() as u64) as usize];
        let mut rng = Rng::new(i);
        let deck = deck_for(character, i, &mut rng);
        let mut s = CombatState::new_as(character, &deck, hp, hp, enc, &mut rng);
        loop {
            check_invariants(&s, deck.len());
            let Some(a) = random_action(&s, &mut rng) else { break };
            s.step(a, &mut rng).unwrap();
        }
        assert!(s.is_over());
        wins += s.won() as u64;
    }
    (wins, combats)
}

#[test]
fn fuzz_quick() {
    let (wins, n) = run_fuzz(Character::Ironclad, 3_000);
    assert!(wins > 0 && wins < n, "random agent should win some and lose some: {wins}/{n}");
}

#[test]
fn fuzz_quick_silent() {
    let (wins, n) = run_fuzz(Character::Silent, 3_000);
    assert!(wins > 0 && wins < n, "random agent should win some and lose some: {wins}/{n}");
}

#[test]
#[ignore = "slow in debug; run with --release -- --ignored"]
fn fuzz_100k() {
    let (wins, n) = run_fuzz(Character::Ironclad, 100_000);
    println!("random agent won {wins}/{n}");
}

#[test]
#[ignore = "slow in debug; run with --release -- --ignored"]
fn fuzz_100k_silent() {
    let (wins, n) = run_fuzz(Character::Silent, 100_000);
    println!("silent: random agent won {wins}/{n}");
}
