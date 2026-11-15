//! Act 1 monsters the engine lacks, as pack data (`content/packs/act1-monsters.json`,
//! lane act1-content step 2; values in docs/research/act1-inventory.md
//! "Step 2"): each loads, shows its moves in the game's order with the
//! game's damage, and plays to an end.

use sts_engine::agent::greedy_action;
use sts_engine::registry::{load_pack, monster_kinds, Binding};
use sts_engine::*;

const PACK: &str = include_str!("../../content/packs/act1-monsters.json");

fn kind(id: &str) -> MonsterKind {
    load_pack(PACK).unwrap();
    monster_kinds(&[&format!("gen:{id}")]).unwrap()[0]
}

/// (move name on show, player HP lost to it) for each of `turns` monster
/// turns, against a player who only ends the turn.
fn passive(id: &str, seed: u64, turns: usize) -> Vec<(&'static str, i16)> {
    let k = kind(id);
    let mut rng = Rng::new(seed);
    let deck = Character::Ironclad.starter_deck();
    let mut s = CombatState::new_vs(Character::Ironclad, &deck, &Binding::default(), 999, 999, &[k], &mut rng);
    let mut out = Vec::new();
    while out.len() < turns {
        let name = s.monsters[0].intent_def().unwrap().name;
        let hp = s.player.hp;
        s.step(Action::EndTurn, &mut rng).unwrap();
        assert!(!s.is_over(), "{id}: ended against a passive player");
        out.push((name, hp - s.player.hp));
    }
    out
}

#[test]
fn values_as_the_wiki() {
    for (id, hp) in [("Blue Slaver", (46, 50)), ("Fat Gremlin", (13, 17)), ("Sneaky Gremlin", (10, 14)), ("Gremlin Wizard", (23, 25))] {
        let d = kind(id).def();
        assert_eq!((d.hp_min, d.hp_max, d.start_block), (hp.0, hp.1, 0), "{id}");
        assert!(d.start_powers.is_empty(), "{id}");
    }
}

#[test]
fn gremlins_every_turn() {
    for seed in 0..5 {
        assert!(passive("Sneaky Gremlin", seed, 8).iter().all(|&m| m == ("Puncture", 9)));
        // Weak on the player doesn't change the damage it takes.
        assert!(passive("Fat Gremlin", seed, 8).iter().all(|&m| m == ("Smash", 4)));
    }
}

#[test]
fn wizard_charges_two_then_three() {
    for seed in 0..5 {
        let got: Vec<i16> = passive("Gremlin Wizard", seed, 11).iter().map(|m| m.1).collect();
        assert_eq!(got, [0, 0, 25, 0, 0, 0, 25, 0, 0, 0, 25], "seed {seed}");
        assert!(passive("Gremlin Wizard", seed, 11).iter().all(|m| m.0 == if m.1 == 25 { "Ultimate Blast" } else { "Charging" }));
    }
}

#[test]
fn blue_slaver_stab_on_sixty_never_three_running() {
    let (mut first_stab, mut stab, mut all) = (0, 0, 0);
    for seed in 0..400 {
        let ms = passive("Blue Slaver", seed, 10);
        for m in &ms {
            assert!(*m == ("Stab", 12) || *m == ("Rake", 7), "{m:?}");
        }
        for w in ms.windows(3) {
            assert!(!(w[0].0 == w[1].0 && w[1].0 == w[2].0), "seed {seed}: {ms:?}");
        }
        first_stab += (ms[0].0 == "Stab") as u32;
        stab += ms.iter().filter(|m| m.0 == "Stab").count();
        all += ms.len();
    }
    // The first move is a free 60/40 roll (240 of 400 expected); the
    // repeat limits bend the later ones: over the first 10 moves the game's
    // rule gives Stab 0.5407 exactly (a Markov chain on the last two moves).
    assert!((210..=270).contains(&first_stab), "first-move Stab {first_stab} of 400");
    let share = stab as f64 / all as f64;
    println!("Blue Slaver: first-move Stab {first_stab} of 400, Stab share over 10 moves {share:.3}");
    assert!((share - 0.5407).abs() < 0.03, "Stab share {share}");
}

#[test]
fn greedy_plays_each_to_an_end() {
    for id in ["Blue Slaver", "Fat Gremlin", "Sneaky Gremlin", "Gremlin Wizard"] {
        let k = kind(id);
        for seed in 0..10 {
            let mut rng = Rng::new(seed);
            let deck = Character::Ironclad.starter_deck();
            let mut s = CombatState::new_vs(Character::Ironclad, &deck, &Binding::default(), 80, 80, &[k], &mut rng);
            let mut n = 0;
            while !s.is_over() {
                s.step(greedy_action(&s), &mut rng).unwrap();
                n += 1;
                assert!(n < 2000, "{id} seed {seed}: no end");
            }
            assert!(s.won(), "{id} seed {seed}: the starter deck lost to one {id}");
        }
    }
}

#[test]
fn m6_m7_values_as_the_wiki() {
    for (id, hp) in [("Shield Gremlin", (12, 15)), ("Red Slaver", (46, 50))] {
        let d = kind(id).def();
        assert_eq!((d.hp_min, d.hp_max, d.start_block), (hp.0, hp.1, 0), "{id}");
    }
    // Alone from the start, the Shield Gremlin opens with Protect (the
    // game's getMove always sets it), shielding itself, then bashes.
    for seed in 0..5 {
        let moves = passive("Shield Gremlin", seed, 6);
        assert_eq!(moves[0], ("Protect", 0));
        assert!(moves[1..].iter().all(|&m| m == ("Shield Bash", 6)), "{moves:?}");
    }
    let mut rng = Rng::new(1);
    let deck = Character::Ironclad.starter_deck();
    let mut s = CombatState::new_vs(Character::Ironclad, &deck, &Binding::default(), 80, 80, &[kind("Shield Gremlin")], &mut rng);
    s.step(Action::EndTurn, &mut rng).unwrap();
    assert_eq!((s.monsters[0].block, s.monsters[0].intent_def().unwrap().name), (7, "Shield Bash"));
}

#[test]
fn red_slaver_pattern() {
    let (mut second_entangle, mut after, mut after_stab) = (0, 0, 0);
    for seed in 0..400 {
        let ms = passive("Red Slaver", seed, 12);
        assert_eq!(ms[0], ("Stab", 13), "seed {seed}: first move");
        let tangles: Vec<usize> = (0..ms.len()).filter(|&i| ms[i].0 == "Entangle").collect();
        assert!(tangles.len() <= 1, "seed {seed}: Entangle twice {ms:?}");
        for w in ms.windows(3) {
            assert!(!(w[0].0 == "Scrape" && w[1].0 == "Scrape" && w[2].0 == "Scrape"), "seed {seed}: {ms:?}");
        }
        if let Some(&i) = tangles.first() {
            assert_eq!(ms[i].1, 0, "Entangle deals nothing");
            if i + 1 < ms.len() {
                after += 1;
                after_stab += (ms[i + 1].0 == "Stab") as u32;
            }
            for w in ms[i + 1..].windows(3) {
                assert!(!(w[0].0 == "Stab" && w[1].0 == "Stab" && w[2].0 == "Stab"), "seed {seed}: {ms:?}");
            }
        } else {
            // Before Entangle a Stab only follows Scrape twice running (or opens).
            for i in 1..ms.len() {
                if ms[i].0 == "Stab" {
                    assert!(i >= 2 && ms[i - 1].0 == "Scrape" && ms[i - 2].0 == "Scrape", "seed {seed}: {ms:?}");
                }
            }
        }
        second_entangle += (ms[1].0 == "Entangle") as u32;
    }
    // Second move: roll 75 or more (100 of 400 expected); after Entangle, Stab on 50 or more.
    assert!((70..=130).contains(&second_entangle), "second-move Entangle {second_entangle} of 400");
    assert!(after > 300 && (after_stab as f64 / after as f64 - 0.5).abs() < 0.1, "Stab after Entangle {after_stab} of {after}");
}

#[test]
fn m6_m7_encounters_load_and_play() {
    use sts_engine::monsters::Encounter;
    load_pack(PACK).unwrap();
    let gremlins = ["Mad Gremlin", "Sneaky Gremlin", "Fat Gremlin", "Shield Gremlin", "Gremlin Wizard"].map(kind);
    for id in ["Gremlin Gang", "Red Slaver", "Exordium Thugs"] {
        let e = Encounter::from_name(&format!("gen:{id}")).unwrap_or_else(|| panic!("no encounter {id}"));
        for seed in 0..20 {
            let mut rng = Rng::new(seed);
            let kinds = e.roll_monsters(&mut rng);
            if id == "Gremlin Gang" {
                assert_eq!(kinds.len(), 4);
                assert!(kinds.iter().all(|k| gremlins.contains(k)), "{kinds:?}");
            }
            let deck = Character::Ironclad.starter_deck();
            let mut s = CombatState::new_vs(Character::Ironclad, &deck, &Binding::default(), 80, 80, &kinds, &mut rng);
            for m in s.monsters.iter().filter(|m| m.alive() && m.kind == gremlins[3]) {
                assert_eq!(m.intent_def().unwrap().name, "Protect", "with allies the Shield Gremlin protects");
            }
            let mut n = 0;
            while !s.is_over() {
                s.step(greedy_action(&s), &mut rng).unwrap();
                n += 1;
                assert!(n < 4000, "{id} seed {seed}: no end");
            }
        }
    }
}

/// The burning elite's fourth buff, Regenerate (`RegenerateMonsterPower`):
/// the pack power `Regenerate`, 3 in Act 1 (2n+1), heals its owner by its
/// stacks at the end of the monster's turn (`atEndOfTurn`'s `HealAction`),
/// up to max HP. Bound only in a fight with that buff: another buff's
/// fight keeps the plain binding.
#[test]
fn burning_elite_regenerate_heals_at_its_turn_end() {
    load_pack(PACK).unwrap();
    let fight = |b: Option<EliteBuff>| {
        let mut s = CombatState::new_with_turn1(
            Character::Ironclad,
            &Character::Ironclad.starter_deck(),
            &Binding::default(),
            500,
            500,
            &[MonsterKind::GremlinNob],
            sts_engine::monsters::EncounterGroup::Elite,
            &[],
            false,
            Default::default(),
            b,
            &mut Rng::new(5),
        );
        s.player.hp = 500;
        s
    };
    let plain = fight(None);
    assert!(fight(Some(EliteBuff::Strength)).binding == plain.binding);
    let mut s = fight(Some(EliteBuff::Regenerate));
    let (_, p) = sts_engine::registry::bind_power(&s.binding, EliteBuff::REGENERATE).unwrap();
    assert_eq!(s.monsters[0].powers.get(p), 3);
    assert_eq!((s.monsters[0].hp, s.monsters[0].max_hp), (plain.monsters[0].hp, plain.monsters[0].max_hp));
    s.monsters[0].hp -= 10;
    let hp = s.monsters[0].hp;
    let mut rng = Rng::new(1);
    s.step(Action::EndTurn, &mut rng).unwrap();
    assert_eq!(s.monsters[0].hp, hp + 3, "heals 3 at its turn end");
    s.monsters[0].hp = s.monsters[0].max_hp - 1;
    s.step(Action::EndTurn, &mut rng).unwrap();
    assert_eq!(s.monsters[0].hp, s.monsters[0].max_hp, "never above max HP");
    assert_eq!(s.monsters[0].powers.get(p), 3, "the monster's Regenerate doesn't wane");
}
