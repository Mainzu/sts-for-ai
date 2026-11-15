//! End to end (docs/specs/potions.md, Verification): a search game holding
//! the Act 1 Fire Potion, Block Potion and Elixir against Jaw Worm. The
//! search player uses its potions when their effects help and wins.

use sts_engine::agent::{Agent, SearchAgent};
use sts_engine::potions::PotionId;
use sts_engine::registry::{load_pack, potions_named, Binding};
use sts_engine::search::{Heuristic, SearchConfig};
use sts_engine::*;

const IRONCLAD: &str = include_str!("../../content/packs/act1-ironclad.json");
const POTIONS: &str = include_str!("../../content/packs/act1-potions.json");

/// Plays one game from `seed`; returns whether it was won and the potions
/// used, in order.
fn play(seed: u64) -> (bool, Vec<&'static str>) {
    load_pack(IRONCLAD).unwrap();
    load_pack(POTIONS).unwrap();
    let potions = potions_named(&["gen:Fire Potion", "gen:Block Potion", "gen:Elixir"]).unwrap();
    let mut rng = Rng::new(seed);
    let mut s = CombatState::new_bound_with(Character::Ironclad, &starter_deck(), &Binding::default(), 80, 80, Encounter::JawWorm, &[], &mut rng);
    s.give_potions(&potions).unwrap();
    s.advance(&mut rng);
    let mut agent = SearchAgent::new(Heuristic, SearchConfig::default());
    let mut agent_rng = Rng::new(seed ^ 0x5eed);
    let mut used = Vec::new();
    while !s.is_over() && s.turn <= 50 {
        let a = agent.act(&s, &mut agent_rng);
        if let Action::UsePotion { slot, .. } = a {
            used.push(s.player.potions.iter().nth(slot as usize).map(PotionId::name).expect("the slot holds a potion"));
        }
        s.step(a, &mut rng).expect("the agent chose a legal action");
    }
    (s.won(), used)
}

#[test]
fn search_game_uses_potions_and_wins() {
    let mut all = Vec::new();
    for seed in 0..3 {
        let (won, used) = play(seed);
        println!("seed {seed}: won {won}, used {used:?}");
        assert!(won, "seed {seed}: the search player wins against Jaw Worm");
        assert!(!used.is_empty(), "seed {seed}: the search player uses a potion");
        all.extend(used);
    }
    for p in ["gen:Fire Potion", "gen:Block Potion", "gen:Elixir"] {
        assert!(all.contains(&p), "{p} is used in some game: {all:?}");
    }
}
