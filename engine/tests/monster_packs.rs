//! Monsters from packs (docs/specs/monsters-from-packs.md): every official
//! monster without code-only parts written as a pack entry loads back
//! unchanged and plays the same games; packs that can't play are refused.

use sts_engine::agent::greedy_action;
use sts_engine::codec::{encode, MONSTER_KINDS};
use sts_engine::monsters::{has_code, MonsterDef};
use sts_engine::registry::{load_pack, monster_json, monster_kinds, Binding};
use sts_engine::*;

fn official() -> impl Iterator<Item = MonsterKind> {
    MONSTER_KINDS.into_iter().skip(1)
}

fn pack_of(entries: &[String]) -> String {
    format!("{{\"version\": 1, \"monsters\": [{}]}}", entries.join(", "))
}

/// Loads every official monster with a pack form as `gen:<Kind>`; returns
/// (official, its pack copy).
fn round_tripped() -> Vec<(MonsterKind, MonsterKind)> {
    let mut out = Vec::new();
    for k in official().filter(|&k| !has_code(k)) {
        let id = format!("{k:?}");
        let entry = monster_json(&id, k).unwrap();
        load_pack(&pack_of(&[entry.clone()])).unwrap_or_else(|e| panic!("{k:?}: {e}\n{entry}"));
        out.push((k, monster_kinds(&[&format!("gen:{id}")]).unwrap()[0]));
    }
    out
}

fn same_def(a: &MonsterDef, b: &MonsterDef) {
    assert_eq!((a.hp_min, a.hp_max, a.start_block), (b.hp_min, b.hp_max, b.start_block), "{}", a.name);
    assert_eq!(a.start_powers, b.start_powers, "{}", a.name);
    assert_eq!(a.moves.len(), b.moves.len(), "{}", a.name);
    for (x, y) in a.moves.iter().zip(b.moves) {
        assert_eq!((x.name, x.effects), (y.name, y.effects), "{}", a.name);
    }
    assert_eq!(a.pattern, b.pattern, "{}", a.name);
    assert_eq!((a.split_move, a.split_into), (b.split_move, b.split_into), "{}", a.name);
}

#[test]
fn official_monsters_round_trip() {
    let coded: Vec<MonsterKind> = official().filter(|&k| has_code(k)).collect();
    assert_eq!(coded.len(), 5);
    for &k in &coded {
        assert!(monster_json("x", k).is_none(), "{k:?} has code but a pack form");
    }
    let pairs = round_tripped();
    for &(k, g) in &pairs {
        assert!(!g.is_official());
        assert_eq!(g.def().name, format!("gen:{k:?}"));
        same_def(k.def(), g.def());
    }
    println!("official monsters loaded from a pack and checked equal: {} of {}", pairs.len(), official().count());
    assert_eq!(pairs.len(), 13);
}

/// The game played by the greedy agent, as a list of (player HP, monsters
/// with the pack kind written as `as_kind`) after each step.
fn play(kind: MonsterKind, as_kind: MonsterKind, seed: u64) -> Vec<String> {
    let mut rng = Rng::new(seed);
    let deck = Character::Ironclad.starter_deck();
    let mut s = CombatState::new_vs(Character::Ironclad, &deck, &Binding::default(), 80, 80, &[kind], &mut rng);
    let mut out = Vec::new();
    for _ in 0..2000 {
        let ms: Vec<_> = s.monsters.iter().map(|m| (if m.kind == kind { as_kind } else { m.kind }, m.hp, m.block, m.moves, m.powers, m.escaped)).collect();
        out.push(format!("{} {} {:?}", s.player.hp, s.turn, ms));
        if s.is_over() {
            out.push(format!("won {}", s.won()));
            return out;
        }
        s.step(greedy_action(&s), &mut rng).unwrap();
    }
    panic!("{kind:?} seed {seed}: no end");
}

#[test]
fn generated_copies_play_the_same() {
    for (k, g) in round_tripped() {
        for seed in 0..20 {
            assert_eq!(play(k, k, seed), play(g, k, seed), "{k:?} seed {seed}");
        }
    }
}

#[test]
fn new_vs_matches_encounter() {
    let deck = Character::Ironclad.starter_deck();
    for enc in Encounter::every() {
        for seed in 0..10 {
            let a = CombatState::new_bound(Character::Ironclad, &deck, &Binding::default(), 70, 80, enc, &mut Rng::new(seed));
            let mut rng = Rng::new(seed);
            let kinds = enc.roll_monsters(&mut rng);
            let b = CombatState::new_vs(Character::Ironclad, &deck, &Binding::default(), 70, 80, &kinds, &mut rng);
            assert!(a == b, "{enc:?} seed {seed}");
        }
    }
}

const MOVE: &str = r#"{"name": "Hit", "effects": [{"Damage": {"amount": 5, "hits": 1, "target": "Opponent"}}]}"#;
const LAST: &str = r#"{"when": [], "then": {"Move": 0}}"#;

fn monster(id: &str, extra: &str, moves: &str, pattern: &str) -> String {
    format!(r#"{{"id": "{id}", "hp": [10, 12]{extra}, "moves": [{moves}], "pattern": [{pattern}]}}"#)
}

#[test]
fn load_refusals() {
    let ok = monster("refusal_base", "", MOVE, LAST);
    load_pack(&pack_of(&[ok.clone()])).unwrap();
    let cases: Vec<(&str, &str, String)> = vec![
        ("redefined", "redefined", monster("refusal_base", r#", "start_block": 3"#, MOVE, LAST)),
        ("hp below 1", "hp range", r#"{"id": "r1", "hp": [0, 5], "moves": [{"name": "a", "effects": []}], "pattern": [{"when": [], "then": {"Move": 0}}]}"#.into()),
        ("hp min over max", "hp range", r#"{"id": "r2", "hp": [9, 5], "moves": [{"name": "a", "effects": []}], "pattern": [{"when": [], "then": {"Move": 0}}]}"#.into()),
        ("no moves", "moves", monster("r3", "", "", LAST)),
        ("move out of range", "out of range", monster("r4", "", MOVE, r#"{"when": [], "then": {"Move": 1}}"#)),
        ("condition out of range", "out of range", monster("r5", "", MOVE, &format!(r#"{{"when": [{{"LastMove": 3}}], "then": {{"Move": 0}}}}, {LAST}"#))),
        ("last row has conditions", "last row", monster("r6", "", MOVE, r#"{"when": ["FirstTurn"], "then": {"Move": 0}}"#)),
        ("p out of range", "Chance p", monster("r7", "", MOVE, r#"{"when": [], "then": {"Chance": {"p": 1.0, "yes": 0, "no": 0}}}"#)),
        ("generated start power", "not official", monster("r8", r#", "start_powers": [{"power": "gen_thing", "amount": 1}]"#, MOVE, LAST)),
        ("generated power applied", "generated power", monster("r9", "", r#"{"name": "a", "effects": [{"Apply": {"power": "gen_thing", "amount": 1, "target": "Opponent"}}]}"#, LAST)),
        ("pick", "monster move", monster("r10", "", r#"{"name": "a", "effects": [{"Pick": {"kind": "DiscardFromHand", "n": 1}}]}"#, LAST)),
        ("random damage", "monster move", monster("r11", "", r#"{"name": "a", "effects": [{"RandomDamage": {"amount": 1, "hits": 2}}]}"#, LAST)),
        ("power-only effect", "monster move", monster("r12", "", r#"{"name": "a", "effects": ["RemoveSelf"]}"#, LAST)),
        ("rolled attack", "RolledAttack", monster("r13", "", r#"{"name": "a", "effects": ["RolledAttack"]}"#, LAST)),
        ("split without split", "no split", monster("r14", "", r#"{"name": "a", "effects": ["Split"]}"#, LAST)),
        ("unknown split child", "split child", monster("r15", r#", "split": {"move": 0, "into": ["gen:nobody", "Cultist"]}"#, MOVE, LAST)),
        ("too many split slots", "slots", monster("r16", r#", "split": {"move": 0, "into": ["Slime Boss", "Slime Boss"]}"#, MOVE, LAST)),
        ("random apply", "monster move", monster("r20", "", r#"{"name": "a", "effects": [{"RandomApply": {"power": "Weak", "amount": 1, "hits": 2}}]}"#, LAST)),
        ("grow damage", "monster move", monster("r21", "", r#"{"name": "a", "effects": [{"GrowDamage": 2}]}"#, LAST)),
        ("replay card", "monster move", monster("r22", "", r#"{"name": "a", "effects": ["ReplayCard"]}"#, LAST)),
        ("reduce self", "monster move", monster("r23", "", r#"{"name": "a", "effects": [{"ReduceSelf": 1}]}"#, LAST)),
        ("draw", "monster move", monster("r24", "", r#"{"name": "a", "effects": [{"Draw": 2}]}"#, LAST)),
        ("gain energy", "monster move", monster("r25", "", r#"{"name": "a", "effects": [{"GainEnergy": 1}]}"#, LAST)),
    ];
    for (what, word, entry) in &cases {
        match load_pack(&pack_of(&[entry.clone()])) {
            Ok(_) => panic!("{what} was accepted: {entry}"),
            Err(e) => assert!(e.contains(word), "{what}: the error {e:?} doesn't say {word:?}"),
        }
    }
    // Twice in one pack, and a child defined after its parent.
    let twice = monster("r17", "", MOVE, LAST);
    assert!(load_pack(&pack_of(&[twice.clone(), twice])).is_err(), "twice in a pack was accepted");
    let parent = monster("r18", r#", "split": {"move": 0, "into": ["gen:r19", "Cultist"]}"#, MOVE, LAST);
    assert!(load_pack(&pack_of(&[parent, monster("r19", "", MOVE, LAST)])).is_err(), "a child after its parent was accepted");
    // Nothing from a refused pack is loaded.
    for id in ["r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15", "r16", "r17", "r18", "r19", "r20", "r21", "r22", "r23", "r24", "r25"] {
        assert!(monster_kinds(&[&format!("gen:{id}")]).is_err(), "{id} loaded from a refused pack");
    }
    // Combats: 1 to 5 monsters, splits counted.
    assert!(monster_kinds(&[]).is_err());
    assert!(monster_kinds(&["Cultist"; 6]).is_err());
    assert!(monster_kinds(&["Slime Boss", "Cultist", "Cultist"]).is_err());
    assert!(monster_kinds(&["Slime Boss", "Cultist"]).is_ok());
    assert!(monster_kinds(&["Nobody"]).is_err());
}

#[test]
fn split_into_generated() {
    let child = monster("split_child", "", MOVE, LAST);
    let parent = monster(
        "split_parent",
        r#", "split": {"move": 1, "into": ["gen:split_child", "Spike Slime (S)"]}"#,
        &format!(r#"{MOVE}, {{"name": "Split", "effects": ["Split"]}}"#),
        LAST,
    )
    .replace(r#""hp": [10, 12]"#, r#""hp": [40, 40]"#);
    load_pack(&pack_of(&[child, parent])).unwrap();
    let kinds = monster_kinds(&["gen:split_parent"]).unwrap();
    let deck = Character::Ironclad.starter_deck();
    let mut rng = Rng::new(3);
    let mut s = CombatState::new_vs(Character::Ironclad, &deck, &Binding::default(), 80, 80, &kinds, &mut rng);
    for _ in 0..200 {
        if s.is_over() || s.monsters[1].kind != MonsterKind::None {
            break;
        }
        s.step(greedy_action(&s), &mut rng).unwrap();
    }
    let child = monster_kinds(&["gen:split_child"]).unwrap()[0];
    assert_eq!((s.monsters[0].kind, s.monsters[1].kind), (child, MonsterKind::SpikeSlimeS));
    assert_eq!(s.monsters[0].max_hp, s.monsters[1].max_hp);
    assert!(s.monsters[0].max_hp <= 20);
}

#[test]
#[should_panic(expected = "generated content")]
fn generated_monster_does_not_encode() {
    load_pack(&pack_of(&[monster("no_codec", "", MOVE, LAST)])).unwrap();
    let kinds = monster_kinds(&["gen:no_codec"]).unwrap();
    let s = CombatState::new_vs(Character::Ironclad, &Character::Ironclad.starter_deck(), &Binding::default(), 80, 80, &kinds, &mut Rng::new(1));
    assert!(s.has_generated());
    encode(&s);
}
