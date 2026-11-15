//! Same seed and same actions give the same state.

use sts_engine::agent::random_action;
use sts_engine::*;

/// Plays a combat with chance from `seed` and actions picked by `pick_seed`;
/// returns the actions and the final state.
fn play(enc: Encounter, seed: u64, pick_seed: u64) -> (Vec<Action>, CombatState) {
    let mut rng = Rng::new(seed);
    let mut pick = Rng::new(pick_seed);
    let mut s = CombatState::new(&starter_deck(), 80, 80, enc, &mut rng);
    let mut actions = Vec::new();
    while let Some(a) = random_action(&s, &mut pick) {
        actions.push(a);
        s.step(a, &mut rng).unwrap();
    }
    (actions, s)
}

#[test]
fn same_seed_and_actions_give_identical_state() {
    for enc in Encounter::ALL {
        for seed in 0..50 {
            let (actions, end) = play(enc, seed, seed + 1000);
            let mut rng = Rng::new(seed);
            let mut s = CombatState::new(&starter_deck(), 80, 80, enc, &mut rng);
            for &a in &actions {
                s.step(a, &mut rng).unwrap();
            }
            assert_eq!(s, end);
        }
    }
}

#[test]
fn different_seeds_differ() {
    let (_, a) = play(Encounter::JawWorm, 1, 5);
    let (_, b) = play(Encounter::JawWorm, 2, 5);
    assert_ne!(a, b);
}

#[test]
fn silent_same_seed_and_actions_give_identical_state() {
    use sts_engine::cards::class_cards;
    let c = Character::Silent;
    let pool: Vec<CardId> = class_cards(c.class()).collect();
    for enc in Encounter::ALL {
        for seed in 0..30 {
            let mut deck = c.starter_deck();
            deck.extend((0..5).map(|k| pool[(seed as usize * 7 + k * 11) % pool.len()]));
            let run = |actions: Option<&[Action]>| {
                let mut rng = Rng::new(seed);
                let mut pick = Rng::new(seed + 1000);
                let mut s = CombatState::new_as(c, &deck, 70, 70, enc, &mut rng);
                let mut taken = Vec::new();
                let mut i = 0;
                loop {
                    let a = match actions {
                        Some(v) => match v.get(i) {
                            Some(&a) => a,
                            None => break,
                        },
                        None => match random_action(&s, &mut pick) {
                            Some(a) => a,
                            None => break,
                        },
                    };
                    i += 1;
                    taken.push(a);
                    s.step(a, &mut rng).unwrap();
                }
                (taken, s)
            };
            let (actions, end) = run(None);
            let (_, again) = run(Some(&actions));
            assert_eq!(again, end);
        }
    }
}

/// `play` is `play_from` on the spec's start state: same result and
/// trajectory, for the random agent and search (check 4's spec mix).
#[test]
fn play_from_matches_play() {
    use sts_engine::agent::{RandomAgent, SearchAgent};
    use sts_engine::heuristic::Heuristic;
    use sts_engine::monsters::EncounterGroup;
    use sts_engine::runner::{group_specs, play, play_from, CombatResult};
    use sts_engine::search::SearchConfig;

    fn same(a: &CombatResult, b: &CombatResult) {
        assert_eq!((a.won, a.hp_end, a.hp_start, a.turns, a.score), (b.won, b.hp_end, b.hp_start, b.turns, b.score));
        assert_eq!(a.trajectory, b.trajectory);
        let vals = |r: &CombatResult| -> Vec<Vec<(Vec<Action>, f32)>> {
            r.option_values.iter().map(|o| o.iter().map(|x| (x.actions.clone(), x.value)).collect()).collect()
        };
        assert_eq!(vals(a), vals(b));
    }
    let mut specs = Vec::new();
    for g in [EncounterGroup::Hallway, EncounterGroup::Elite, EncounterGroup::Boss] {
        specs.extend(group_specs(g, 200, 5, 1));
    }
    for (i, spec) in specs.iter().enumerate() {
        let start = |spec: &sts_engine::runner::GameSpec| {
            let mut rng = Rng::new(spec.seed);
            let mut s = CombatState::new_as(spec.character, &spec.deck, spec.hp, spec.max_hp, spec.encounter, &mut rng);
            s.no_death = spec.no_death;
            (s, rng, Rng::new(spec.seed ^ 0xa6e7_a6e7))
        };
        let (s, mut rng, mut agent_rng) = start(spec);
        same(&play(spec, &mut RandomAgent, true), &play_from(s, &mut rng, &mut agent_rng, &mut RandomAgent, true, spec.hp));
        if i % 10 == 0 {
            let mut a = SearchAgent::new(Heuristic, SearchConfig::default());
            let mut b = SearchAgent::new(Heuristic, SearchConfig::default());
            let (s, mut rng, mut agent_rng) = start(spec);
            same(&play(spec, &mut a, true), &play_from(s, &mut rng, &mut agent_rng, &mut b, true, spec.hp));
        }
    }
}
