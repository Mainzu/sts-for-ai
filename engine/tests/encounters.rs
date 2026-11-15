//! Encounters as data (docs/specs/encounters-as-data.md): the official
//! encounters roll exactly as the Rust table they replaced.

use sts_engine::monsters::{EncounterGroup, MonsterKind as K};
use sts_engine::rng::Rng;
use sts_engine::Encounter;

fn any_louse(rng: &mut Rng) -> K {
    if rng.below(2) == 0 { K::RedLouse } else { K::GreenLouse }
}

fn medium_slime(rng: &mut Rng) -> K {
    if rng.below(2) == 0 { K::AcidSlimeM } else { K::SpikeSlimeM }
}

fn louse_or_medium_slime(rng: &mut Rng) -> K {
    if rng.below(2) == 0 { any_louse(rng) } else { medium_slime(rng) }
}

/// Today's table, frozen: (name, group, roll) by encounter, in enum order.
fn reference(i: usize, rng: &mut Rng) -> (&'static str, EncounterGroup, Vec<K>) {
    use EncounterGroup::*;
    match i {
        0 => ("cultist", Hallway, vec![K::Cultist]),
        1 => ("jaw_worm", Hallway, vec![K::JawWorm]),
        2 => ("two_louse", Hallway, vec![any_louse(rng), any_louse(rng)]),
        3 => ("small_slimes", Hallway, if rng.below(2) == 0 { vec![K::SpikeSlimeM, K::AcidSlimeS] } else { vec![K::AcidSlimeM, K::SpikeSlimeS] }),
        4 => ("large_slime", Hallway, vec![if rng.below(2) == 0 { K::AcidSlimeL } else { K::SpikeSlimeL }]),
        5 => ("lots_of_slimes", Hallway, vec![K::SpikeSlimeS, K::SpikeSlimeS, K::SpikeSlimeS, K::AcidSlimeS, K::AcidSlimeS]),
        6 => ("three_louse", Hallway, vec![any_louse(rng), any_louse(rng), any_louse(rng)]),
        7 => ("two_fungi_beasts", Hallway, vec![K::FungiBeast, K::FungiBeast]),
        8 => ("looter", Hallway, vec![K::Looter]),
        9 => {
            let first = louse_or_medium_slime(rng);
            ("exordium_thugs", Hallway, vec![first, if rng.below(2) == 0 { K::Cultist } else { K::Looter }])
        }
        10 => {
            let first = if rng.below(2) == 0 { K::FungiBeast } else { K::JawWorm };
            ("exordium_wildlife", Hallway, vec![first, louse_or_medium_slime(rng)])
        }
        11 => ("gremlin_nob", Elite, vec![K::GremlinNob]),
        12 => ("lagavulin", Elite, vec![K::Lagavulin]),
        13 => ("three_sentries", Elite, vec![K::Sentry, K::Sentry, K::Sentry]),
        14 => ("slime_boss", Boss, vec![K::SlimeBoss]),
        15 => ("hexaghost", Boss, vec![K::Hexaghost]),
        16 => ("the_guardian", Boss, vec![K::TheGuardian]),
        _ => unreachable!(),
    }
}

#[test]
fn official_rolls_frozen() {
    let all: Vec<Encounter> = Encounter::every().collect();
    assert_eq!(all.len(), 17);
    assert_eq!(Encounter::ALL.len(), 15);
    for (i, &e) in all.iter().enumerate() {
        for seed in 0..1000u64 {
            let (mut a, mut b) = (Rng::new(seed), Rng::new(seed));
            let (name, group, kinds) = reference(i, &mut b);
            assert_eq!(e.name(), name);
            assert_eq!(e.group(), group, "{name}");
            assert_eq!(Encounter::from_name(name), Some(e));
            assert_eq!(e.roll_monsters(&mut a), kinds, "{name} seed {seed}");
            assert_eq!(a.next_u64(), b.next_u64(), "{name} seed {seed}: draws differ");
        }
    }
}

#[test]
fn official_encounters_round_trip() {
    use sts_engine::registry::{encounter_json, official, parse_official, OFFICIAL_FILES};
    let o = official();
    let lines: Vec<String> = Encounter::every().map(|e| encounter_json(e.name(), e.def())).collect();
    let text = format!("{{\"version\": 1, \"encounters\": [\n{}\n]}}\n", lines.join(",\n"));
    assert_eq!(text.replace("\r\n", "\n"), OFFICIAL_FILES[3].replace("\r\n", "\n"), "the writer reproduces the file");
    let [c, p, m, _] = OFFICIAL_FILES;
    let again = parse_official([c, p, m, &text]).expect("written file parses");
    assert_eq!(again.encounters, o.encounters);
}

// ---- pack encounters (build step 3) ----

use sts_engine::agent::greedy_action;
use sts_engine::monsters::EncounterSlot;
use sts_engine::registry::{load_pack, monster_kinds};
use sts_engine::CombatState;

const HIT: &str = r#"{"name": "Hit", "effects": [{"Damage": {"amount": 5, "hits": 1, "target": "Opponent"}}]}"#;
const LAST: &str = r#"{"when": [], "then": {"Move": 0}}"#;

fn monster(id: &str) -> String {
    format!(r#"{{"id": "{id}", "hp": [10, 12], "moves": [{HIT}], "pattern": [{LAST}]}}"#)
}

#[test]
fn pack_encounter_plays() {
    let pack = format!(
        r#"{{"version": 1, "monsters": [{}], "encounters": [{{"id": "enc_pair", "group": "elite", "monsters": ["gen:enc_m", {{"one_of": [["Jaw Worm"], ["Cultist"]]}}]}}]}}"#,
        monster("enc_m")
    );
    load_pack(&pack).unwrap();
    load_pack(&pack).expect("the same pack again is skipped");
    let e = Encounter::from_name("gen:enc_pair").expect("a loaded pack encounter by name");
    assert!(!e.is_official());
    assert_eq!(e.name(), "gen:enc_pair");
    assert_eq!(e.group(), EncounterGroup::Elite);
    assert!(!Encounter::every().any(|x| x == e), "every() stays official");
    let m = monster_kinds(&["gen:enc_m"]).unwrap()[0];
    let mut seen = [false; 2];
    for seed in 0..50 {
        let kinds = e.roll_monsters(&mut Rng::new(seed));
        assert_eq!(kinds[0], m);
        assert!(kinds[1] == K::JawWorm || kinds[1] == K::Cultist, "{kinds:?}");
        seen[(kinds[1] == K::Cultist) as usize] = true;
    }
    assert_eq!(seen, [true, true]);
    let mut rng = Rng::new(7);
    let mut s = CombatState::new(&sts_engine::starter_deck(), 80, 80, e, &mut rng);
    for _ in 0..2000 {
        if s.is_over() {
            break;
        }
        s.step(greedy_action(&s), &mut rng).unwrap();
    }
    assert!(s.is_over(), "the combat plays to an end");
}

#[test]
fn pack_encounter_refusals() {
    let enc = |id: &str, body: &str| format!(r#"{{"id": "{id}", {body}}}"#);
    let cases: Vec<(&str, &str, String)> = vec![
        ("unknown monster", "unknown monster", enc("ref_e1", r#""group": "hallway", "monsters": ["Jaw Wurm"]"#)),
        ("bad group", "group", enc("ref_e2", r#""group": "act2", "monsters": ["Jaw Worm"]"#)),
        ("draw over the list", "draw 3 from 2", enc("ref_e3", r#""group": "hallway", "monsters": [{"draw": 3, "from": ["Cultist", "Looter"]}]"#)),
        (
            "over MAX_MONSTERS with splits",
            "slots",
            enc("ref_e4", r#""group": "hallway", "monsters": ["Jaw Worm", "Looter", {"one_of": [["Cultist"], ["Acid Slime (L)", "Spike Slime (L)"]]}]"#),
        ),
        ("empty one_of", "one_of without options", enc("ref_e5", r#""group": "hallway", "monsters": [{"one_of": []}]"#)),
        ("unknown key", "unknown key", enc("ref_e6", r#""group": "hallway", "monsters": ["Cultist"], "weights": [1]"#)),
        ("no monster", "no monster", enc("ref_e7", r#""group": "hallway", "monsters": []"#)),
    ];
    for (what, needle, e) in cases {
        let pack = format!(r#"{{"version": 1, "monsters": [{}], "encounters": [{e}]}}"#, monster("ref_m"));
        let err = load_pack(&pack).expect_err(what);
        assert!(err.contains(needle), "{what}: {err}");
        assert!(monster_kinds(&["gen:ref_m"]).is_err(), "{what}: the pack's monster stayed unloaded");
    }
    for id in ["ref_e1", "ref_e2", "ref_e3", "ref_e4", "ref_e5", "ref_e6", "ref_e7"] {
        assert!(Encounter::from_name(&format!("gen:{id}")).is_none(), "{id} loaded");
    }
    // A redefinition is refused whole; twice in one pack too.
    let base = enc("ref_base", r#""group": "hallway", "monsters": ["Cultist"]"#);
    load_pack(&format!(r#"{{"version": 1, "encounters": [{base}]}}"#)).unwrap();
    let other = enc("ref_base", r#""group": "hallway", "monsters": ["Looter"]"#);
    let err = load_pack(&format!(r#"{{"version": 1, "monsters": [{}], "encounters": [{other}]}}"#, monster("ref_m2"))).unwrap_err();
    assert!(err.contains("redefined"), "{err}");
    assert!(monster_kinds(&["gen:ref_m2"]).is_err());
    let twice = enc("ref_twice", r#""group": "hallway", "monsters": ["Cultist"]"#);
    let err = load_pack(&format!(r#"{{"version": 1, "encounters": [{twice}, {twice}]}}"#)).unwrap_err();
    assert!(err.contains("twice"), "{err}");
    assert_eq!(Encounter::from_name("gen:ref_base").unwrap().roll_monsters(&mut Rng::new(0)), vec![K::Cultist]);
}

#[test]
fn draw_without_replacement() {
    let names = r#"["Red Louse", "Red Louse", "Green Louse", "Green Louse", "Cultist", "Cultist", "Looter", "Jaw Worm"]"#;
    let pack = format!(r#"{{"version": 1, "encounters": [{{"id": "draw_gang", "group": "hallway", "monsters": [{{"draw": 4, "from": {names}}}]}}]}}"#);
    load_pack(&pack).unwrap();
    let e = Encounter::from_name("gen:draw_gang").unwrap();
    let EncounterSlot::Draw { k, from } = &e.def().slots[0] else { panic!("a draw slot") };
    assert_eq!((*k, from.len()), (4, 8));
    // Replay the draw on the same seed to recover the list positions picked.
    let n = 4000;
    let mut picked = [0u32; 8];
    for seed in 0..n {
        let kinds = e.roll_monsters(&mut Rng::new(seed));
        let mut rng = Rng::new(seed);
        let mut left: Vec<usize> = (0..8).collect();
        let mut pos = Vec::new();
        for _ in 0..4 {
            let i = rng.below(left.len() as u32) as usize;
            pos.push(left.remove(i));
        }
        assert_eq!(kinds, pos.iter().map(|&p| from[p]).collect::<Vec<_>>(), "seed {seed}");
        let mut sorted = pos.clone();
        sorted.sort_unstable();
        sorted.dedup();
        assert_eq!(sorted.len(), 4, "a list position repeated at seed {seed}");
        for p in pos {
            picked[p] += 1;
        }
    }
    let se = (n as f64 * 0.5 * 0.5).sqrt();
    for (p, &c) in picked.iter().enumerate() {
        assert!((c as f64 - n as f64 / 2.0).abs() < 4.0 * se, "position {p} picked {c} of {n}");
    }
}
