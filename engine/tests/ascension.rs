//! Ascension in combat (docs/specs/ascension.md), target A20: every Act 1
//! monster's A20 numbers and rules against the research table
//! (docs/research/ascension-act1-2026-11-14.md, every row but the Looter's
//! gold), one fight per elite and boss move by move against the game's A20
//! AI, the A20 run-start helpers, the potion slots and the codec. A0 is
//! the golden games' (`golden.rs`).

mod common;
use common::*;
use sts_engine::codec::{decode, encode};
use sts_engine::effects::Effect;
use sts_engine::monsters::{Ascension, MonsterDef, PatCond, PatCond::*, PatPick, MAX_ASCENSION};
use sts_engine::monsters::{guardian, MonsterKind as K};
use sts_engine::registry::{load_pack, monster_kinds, Binding};
use sts_engine::threshold::threshold;
use sts_engine::*;

const PACK: &str = include_str!("../../content/packs/act1-monsters.json");
const A20: Ascension = Ascension(MAX_ASCENSION);

fn kind(name: &str) -> MonsterKind {
    load_pack(PACK).unwrap();
    monster_kinds(&[name]).unwrap()[0]
}

/// An effect's number: damage, block, an applied amount, cards added.
fn num(e: &Effect) -> i16 {
    match *e {
        Effect::Damage { amount, .. } | Effect::Apply { amount, .. } | Effect::ApplyPack { amount, .. } => amount,
        Effect::Block(n) | Effect::BlockAlly(n) => n,
        Effect::AddCard { n, .. } => n as i16,
        ref e => panic!("no number in {e:?}"),
    }
}

/// What the research says a monster is at A20.
enum Want {
    Hp(i16, i16),
    /// The number of a move's effect (move, effect index, number).
    Num(usize, usize, i16),
    /// The hits of a move's damage effect (move, effect index, hits).
    Hits(usize, usize, u8),
    /// The applied power of a move's effect (move, effect index, power).
    Applies(usize, usize, Power),
    Effects(usize, usize),
    StartPower(Power, i16),
    /// A pack start power's amount (index in `gen_powers`).
    GenStart(usize, i16),
    StartBlock(i16),
    Rolled(i16, i16),
    RolledPower(Power, i16, i16),
    Row(usize, &'static [PatCond], PatPick),
    Pattern(Vec<(&'static [PatCond], PatPick)>),
}
use Want::*;

const fn m(x: u8) -> PatPick {
    PatPick::Move(x)
}

const fn ch(p: f64, yes: u8, no: u8) -> PatPick {
    PatPick::Chance { p, yes, no }
}

/// The research table at A20, by monster (rows citing its classes).
fn table() -> Vec<(&'static str, Vec<Want>)> {
    vec![
        // Cultist: A7 HP; A2 ritualAmount 4, A17 +1.
        ("Cultist", vec![Hp(50, 56), Num(0, 0, 5), Num(1, 0, 6)]),
        // JawWorm: A7 HP; A17 Str 5, Block 9, Chomp 12, Thrash 7 + 5.
        ("Jaw Worm", vec![Hp(42, 46), Num(0, 0, 12), Num(1, 0, 7), Num(1, 1, 5), Num(2, 0, 5), Num(2, 1, 9)]),
        // LouseNormal: A7 HP; A2 bite 6-8; A17 Curl Up 9-12, Grow 4, Grow after one Grow blocked.
        ("Red Louse", vec![Hp(11, 16), Rolled(6, 8), RolledPower(Power::CurlUp, 9, 12), Num(1, 0, 4), Row(0, &[RollBelow(25), LastMove(1)], m(0))]),
        // LouseDefensive: A7 HP; A2 bite 6-8; A17 Curl Up 9-12, Spit Web after one blocked; Weak 2 unchanged.
        ("Green Louse", vec![Hp(12, 18), Rolled(6, 8), RolledPower(Power::CurlUp, 9, 12), Num(1, 0, 2), Row(0, &[RollBelow(25), LastMove(1)], m(0))]),
        // AcidSlime_S: A7 HP; A2 Tackle 4; A17 opens with Lick.
        ("Acid Slime (S)", vec![Hp(9, 13), Num(1, 0, 4), Row(0, &[FirstTurn], m(0))]),
        // AcidSlime_M: A7 HP; A2 Spit 8, Tackle 12; A17 AI.
        ("Acid Slime (M)", vec![Hp(29, 34), Num(0, 0, 8), Num(1, 0, 12), Num(2, 0, 1), Pattern(vec![
            (&[RollBelow(40), LastTwo(0)], ch(0.5, 1, 2)), (&[RollBelow(40)], m(0)),
            (&[RollBelow(80), LastTwo(1)], ch(0.5, 0, 2)), (&[RollBelow(80)], m(1)),
            (&[LastMove(2)], ch(0.4, 0, 1)), (&[], m(2)),
        ])]),
        // AcidSlime_L: A7 HP; A2 Spit 12, Tackle 18; A17 AI.
        ("Acid Slime (L)", vec![Hp(68, 72), Num(0, 0, 12), Num(1, 0, 18), Pattern(vec![
            (&[RollBelow(40), LastTwo(0)], ch(0.6, 1, 2)), (&[RollBelow(40)], m(0)),
            (&[RollBelow(70), LastTwo(1)], ch(0.6, 0, 2)), (&[RollBelow(70)], m(1)),
            (&[LastMove(2)], ch(0.4, 0, 1)), (&[], m(2)),
        ])]),
        // SpikeSlime_S: A7 HP; A2 Tackle 6.
        ("Spike Slime (S)", vec![Hp(11, 15), Num(0, 0, 6)]),
        // SpikeSlime_M: A7 HP; A2 Flame Tackle 10; A17 Lick never twice; Frail stays 1.
        ("Spike Slime (M)", vec![Hp(29, 34), Num(0, 0, 10), Num(1, 0, 1), Row(2, &[LastMove(1)], m(0))]),
        // SpikeSlime_L: A7 HP; A2 Flame Tackle 18; A17 Frail 3, Lick never twice.
        ("Spike Slime (L)", vec![Hp(67, 73), Num(0, 0, 18), Num(1, 0, 3), Row(2, &[LastMove(1)], m(0))]),
        // FungiBeast: A7 HP; A2 strAmt 4, A17 +1; bite 6.
        ("Fungi Beast", vec![Hp(24, 28), Num(0, 0, 6), Num(1, 0, 5)]),
        // Looter: A7 HP; A2 Mug 11, Lunge 14 (A17 gold: no gold in combat).
        ("Looter", vec![Hp(46, 50), Num(0, 0, 11), Num(1, 0, 14)]),
        // GremlinNob: A8 HP; A3 bash 8, rush 16; A18 Anger 3 and the A18 AI.
        ("Gremlin Nob", vec![Hp(85, 90), Num(0, 0, 3), Num(1, 0, 16), Num(2, 0, 8), Num(2, 1, 2), Pattern(vec![
            (&[FirstTurn], m(0)), (&[LastMove(2)], m(1)), (&[Window(1, 2)], m(1)), (&[], m(2)),
        ])]),
        // Lagavulin: A8 HP; A3 attack 20; A18 debuff -2; Metallicize 8 and block 8 unchanged.
        ("Lagavulin", vec![Hp(112, 115), Num(3, 0, 20), Num(4, 0, -2), Num(4, 1, -2), StartPower(Power::Metallicize, 8), StartBlock(8)]),
        // Sentry: A8 HP; A3 beam 10; A18 3 Dazed; Artifact 1 unchanged.
        ("Sentry", vec![Hp(39, 45), Num(1, 0, 10), Num(0, 0, 3), StartPower(Power::Artifact, 1)]),
        // SlimeBoss: A9 HP; A4 Slam 38; A19 5 Slimed.
        ("Slime Boss", vec![Hp(150, 150), Num(2, 0, 38), Num(0, 0, 5)]),
        // Hexaghost: A9 HP; A19 Str 3, 2 Burns, Tackle 6x2, Inferno 3x6; Sear 6, Inflame block 12 unchanged.
        ("Hexaghost", {
            let mut w = vec![Hp(264, 264)];
            for mv in [3, 6, 10, 13] {
                w.extend([Num(mv, 0, 6), Hits(mv, 0, 2)]);
            }
            for mv in [8, 15] {
                w.extend([Num(mv, 0, 3), Hits(mv, 0, 6), Num(mv, 1, 3)]);
            }
            for mv in [5, 12] {
                w.extend([Num(mv, 0, 12), Num(mv, 1, 3), Applies(mv, 1, Power::Strength)]);
            }
            for mv in [2, 4, 7, 9, 11, 14] {
                w.extend([Num(mv, 0, 6), Num(mv, 1, 2)]);
            }
            w
        }),
        // TheGuardian: A19 HP 250, Mode Shift 40, Sharp Hide 4; A4 Fierce Bash 36, Roll 10.
        ("The Guardian", vec![Hp(250, 250), StartPower(Power::ModeShift, 40), Num(1, 0, 36), Num(5, 0, 10), Num(4, 0, 4),
            Num(0, 0, 9), Num(3, 0, 5), Hits(3, 0, 4), Num(6, 0, 8), Hits(6, 0, 2)]),
        // SlaverBlue: A7 HP; A2 Stab 13, Rake 8; A17 Weak 2, Rake after one blocked.
        ("gen:Blue Slaver", vec![Hp(48, 52), Num(0, 0, 13), Num(1, 0, 8), Num(1, 1, 2), Row(0, &[RollBelow(40), LastMove(1)], m(0))]),
        // SlaverRed: A7 HP; A2 Stab 14, Scrape 9; A17 Vulnerable 2, Scrape after one blocked.
        ("gen:Red Slaver", vec![Hp(48, 52), Num(0, 0, 14), Num(3, 0, 14), Num(1, 0, 9), Num(4, 0, 9), Num(1, 1, 2), Num(4, 1, 2),
            Row(6, &[LastMove(4)], m(3)), Row(9, &[RollBelow(75), LastMove(1)], m(0))]),
        // GremlinFat: A7 HP; A2 Smash 5; A17 Frail 1 after Weak 1.
        ("gen:Fat Gremlin", vec![Hp(14, 18), Num(0, 0, 5), Effects(0, 3), Num(0, 1, 1), Applies(0, 1, Power::Weak), Num(0, 2, 1), Applies(0, 2, Power::Frail)]),
        // GremlinThief: A7 HP; A2 Puncture 10.
        ("gen:Sneaky Gremlin", vec![Hp(11, 15), Num(0, 0, 10)]),
        // GremlinTsundere: A17 HP 13-17, block 11; A2 Shield Bash 8.
        ("gen:Shield Gremlin", vec![Hp(13, 17), Num(0, 0, 11), Num(1, 0, 8)]),
        // GremlinWarrior: A7 HP; A2 Scratch 5; A17 Angry 2.
        ("gen:Mad Gremlin", vec![Hp(21, 25), Num(0, 0, 5), GenStart(0, 2)]),
        // GremlinWizard: A7 HP 22-26; A2 Ultimate Blast 30; A17 blasts every turn after the first.
        ("gen:Gremlin Wizard", vec![Hp(22, 26), Num(3, 0, 30), Row(3, &[LastMove(3)], m(3))]),
    ]
}

fn check(name: &str, d: &MonsterDef, w: &Want) -> Option<String> {
    let eff = |mv: usize, i: usize| d.moves.get(mv).and_then(|m| m.effects.get(i));
    let bad = |what: String| Some(format!("{name}: {what}"));
    match *w {
        Hp(lo, hi) if (d.hp_min, d.hp_max) != (lo, hi) => bad(format!("HP {}-{}, want {lo}-{hi}", d.hp_min, d.hp_max)),
        Num(mv, i, n) => match eff(mv, i) {
            Some(e) if num(e) == n => None,
            e => bad(format!("move {mv} effect {i} is {e:?}, want the number {n}")),
        },
        Hits(mv, i, h) => match eff(mv, i) {
            Some(Effect::Damage { hits, .. }) if *hits == h => None,
            e => bad(format!("move {mv} effect {i} is {e:?}, want {h} hits")),
        },
        Applies(mv, i, p) => match eff(mv, i) {
            Some(Effect::Apply { power, .. }) if *power == p => None,
            e => bad(format!("move {mv} effect {i} is {e:?}, want {p:?}")),
        },
        Effects(mv, n) if d.moves[mv].effects.len() != n => bad(format!("move {mv} has {:?}, want {n} effects", d.moves[mv].effects)),
        StartPower(p, n) if !d.start_powers.contains(&(p, n)) => bad(format!("start powers {:?}, want {p:?} {n}", d.start_powers)),
        GenStart(i, n) if d.gen_powers.get(i).map(|g| g.1) != Some(n) => bad(format!("pack start powers {:?}, want {n}", d.gen_powers)),
        StartBlock(n) if d.start_block != n => bad(format!("start block {}, want {n}", d.start_block)),
        Rolled(lo, hi) if d.rolled_attack != Some((lo, hi)) => bad(format!("rolled attack {:?}, want {lo}-{hi}", d.rolled_attack)),
        RolledPower(p, lo, hi) if !d.rolled_powers.contains(&(p, lo, hi)) => bad(format!("rolled powers {:?}, want {p:?} {lo}-{hi}", d.rolled_powers)),
        Row(i, when, then) => match d.pattern.get(i) {
            Some(r) if r.when == when && r.then == then => None,
            r => bad(format!("pattern row {i} is {r:?}, want {when:?} -> {then:?}")),
        },
        Pattern(ref rows) => {
            let got: Vec<(&[PatCond], PatPick)> = d.pattern.iter().map(|r| (r.when, r.then)).collect();
            if got == *rows { None } else { bad(format!("pattern {got:?}, want {rows:?}")) }
        }
        _ => None,
    }
}

#[test]
fn every_act1_monster_at_a20_matches_the_research() {
    let mut errors = Vec::new();
    let t = table();
    for (name, wants) in &t {
        let k = kind(name);
        let d = k.def_at(A20);
        assert!(!std::ptr::eq(d, k.def()), "{name}: no A20 definition");
        assert!(std::ptr::eq(k.def_at(Ascension(0)), k.def()), "{name}: A0 is its own definition");
        errors.extend(wants.iter().filter_map(|w| check(name, d, w)));
    }
    // Every official Act 1 monster is in the table.
    for i in 1..sts_engine::monsters::NUM_OFFICIAL_MONSTERS {
        let n = K(i as u8).def().name;
        assert!(t.iter().any(|(x, _)| *x == n), "{n} has no row");
    }
    assert!(errors.is_empty(), "{}", errors.join("\n"));
}

#[test]
fn a_wrong_want_is_named() {
    let d = K::Cultist.def_at(A20);
    for w in [Hp(48, 54), Num(0, 0, 3), Row(0, &[], m(1)), Rolled(1, 2), StartPower(Power::Artifact, 1)] {
        assert!(check("Cultist", d, &w).is_some());
    }
}

#[test]
fn a0_keeps_the_engine_numbers() {
    // A few A0 numbers the rows change at A20.
    let d = K::GremlinNob.def_at(Ascension(0));
    assert_eq!((d.hp_min, d.hp_max, num(&d.moves[1].effects[0])), (82, 86, 14));
    let d = K::RedLouse.def();
    assert_eq!((d.rolled_attack, d.rolled_powers), (Some((5, 7)), &[(Power::CurlUp, 3, 7)][..]));
    assert_eq!(K::TheGuardian.def().start_powers, &[(Power::ModeShift, 30)]);
    // Levels between: the rows from their level up (Guardian 0/9/19).
    assert_eq!(K::TheGuardian.def_at(Ascension(9)).start_powers, &[(Power::ModeShift, 35)]);
    assert_eq!(K::TheGuardian.def_at(Ascension(18)).start_powers, &[(Power::ModeShift, 35)]);
    assert_eq!(num(&K::TheGuardian.def_at(Ascension(4)).moves[1].effects[0]), 36);
    assert_eq!(K::TheGuardian.def_at(Ascension(3)).hp_min, 240);
}

/// A fight at A20 against `names`, the player at 999 HP with the starter
/// deck, who only ends turns.
fn fight(names: &[&str], group: EncounterGroup, seed: u64) -> CombatState {
    let kinds: Vec<MonsterKind> = names.iter().map(|n| kind(n)).collect();
    let deck = Character::Ironclad.starter_deck();
    CombatState::new_with_turn1(Character::Ironclad, &deck, &Binding::default(), 999, 999, &kinds, group, &[], false, A20, None, &mut Rng::new(seed))
}

use sts_engine::monsters::EncounterGroup;

/// (move name on show, HP the player lost to the monsters' turn) for each
/// of `turns` turns of a passive player; the player's block is cleared
/// first so the losses are the moves' damage.
fn passive(s: &mut CombatState, slot: usize, turns: usize) -> Vec<(&'static str, i16)> {
    let mut out = Vec::new();
    for _ in 0..turns {
        let name = s.monsters[slot].intent_def().map_or("-", |d| d.name);
        s.player.block = 0;
        let hp = s.player.hp;
        end_turn(s);
        out.push((name, hp - s.player.hp));
    }
    out
}

#[test]
fn nob_a20_bellows_then_skull_bash_every_third_turn() {
    let mut s = fight(&["Gremlin Nob"], EncounterGroup::Elite, 3);
    assert!((85..=90).contains(&s.monsters[0].hp));
    let seen = passive(&mut s, 0, 7);
    let names: Vec<&str> = seen.iter().map(|x| x.0).collect();
    assert_eq!(names, ["Bellow", "Skull Bash", "Bull Rush", "Bull Rush", "Skull Bash", "Bull Rush", "Bull Rush"]);
    assert_eq!(s.monsters[0].powers.get(Power::Enrage), 3, "Bellow's Anger 3");
    assert_eq!(seen[1].1, 8, "Skull Bash 8");
    assert_eq!(seen[2].1, 24, "Bull Rush 16 on a Vulnerable player");
}

#[test]
fn lagavulin_a20_attacks_for_20_and_siphons_2() {
    let mut s = fight(&["Lagavulin"], EncounterGroup::Elite, 3);
    assert!((112..=115).contains(&s.monsters[0].hp));
    let seen = passive(&mut s, 0, 6);
    let names: Vec<&str> = seen.iter().map(|x| x.0).collect();
    assert_eq!(names, ["Sleep", "Sleep", "Sleep", "Attack", "Attack", "Siphon Soul"]);
    assert_eq!((seen[3].1, seen[4].1), (20, 20));
    assert_eq!((s.player.powers.get(Power::Strength), s.player.powers.get(Power::Dexterity)), (-2, -2));
}

#[test]
fn sentries_a20_add_3_dazed_and_beam_for_10() {
    let mut s = fight(&["Sentry", "Sentry", "Sentry"], EncounterGroup::Elite, 3);
    for m in &s.monsters[..3] {
        assert!((39..=45).contains(&m.hp) && m.powers.get(Power::Artifact) == 1);
    }
    let names: Vec<&str> = (0..3).map(|i| s.monsters[i].intent_def().unwrap().name).collect();
    assert_eq!(names, ["Bolt", "Beam", "Bolt"]);
    let dazed = |s: &CombatState| s.discard().count(card("Dazed")) + s.draw().count(card("Dazed")) + s.hand.count(card("Dazed"));
    s.player.block = 0;
    let hp = s.player.hp;
    end_turn(&mut s);
    assert_eq!(hp - s.player.hp, 10, "one Beam");
    assert_eq!(dazed(&s), 6, "two Bolts of 3 Dazed");
    let names: Vec<&str> = (0..3).map(|i| s.monsters[i].intent_def().unwrap().name).collect();
    assert_eq!(names, ["Beam", "Bolt", "Beam"]);
}

#[test]
fn slime_boss_a20_goops_5_slimed_and_slams_for_38() {
    let mut s = fight(&["Slime Boss"], EncounterGroup::Boss, 3);
    assert_eq!(s.monsters[0].hp, 150);
    let slimed = |s: &CombatState| s.discard().count(card("Slimed")) + s.draw().count(card("Slimed")) + s.hand.count(card("Slimed"));
    let seen = passive(&mut s, 0, 3);
    let names: Vec<&str> = seen.iter().map(|x| x.0).collect();
    assert_eq!(names, ["Goop Spray", "Preparing", "Slam"]);
    assert_eq!(slimed(&s), 5);
    assert_eq!(seen[2].1, 38);
    // Its split children are A20's large slimes.
    let mut s = fight(&["Slime Boss"], EncounterGroup::Boss, 3);
    s.hand = Hand::from_cards(&[card("Strike")]);
    s.player.energy = 1;
    s.monsters[0].hp = 80;
    play(&mut s, "Strike", Some(0));
    end_turn(&mut s);
    let kids: Vec<_> = s.monsters.iter().filter(|m| m.alive()).map(|m| (m.kind, m.def().moves[0].effects[0])).collect();
    assert_eq!(kids.len(), 2, "{kids:?}");
    assert!(kids.iter().all(|(_, e)| num(e) == 18 || num(e) == 12), "A2 numbers on the children: {kids:?}");
}

#[test]
fn hexaghost_a20_cycle() {
    let mut s = fight(&["Hexaghost"], EncounterGroup::Boss, 3);
    assert_eq!(s.monsters[0].hp, 264);
    let burns = |s: &CombatState| s.discard().count(card("Burn")) + s.draw().count(card("Burn")) + s.hand.count(card("Burn"));
    let mut names = Vec::new();
    let mut after = Vec::new();
    for _ in 0..9 {
        names.push(s.monsters[0].intent_def().unwrap().name);
        s.player.block = 0;
        // Burns in hand hurt at turn end: count only the monster's turn.
        s.hand = Hand::default();
        let (b, block) = (burns(&s), s.monsters[0].block);
        let hp = s.player.hp;
        end_turn(&mut s);
        after.push((hp - s.player.hp, burns(&s) as i16 - b as i16, s.monsters[0].block - block, s.monsters[0].powers.get(Power::Strength)));
    }
    assert_eq!(names, ["Activate", "Divider", "Sear", "Tackle", "Sear", "Inflame", "Tackle", "Sear", "Inferno"]);
    assert_eq!((after[2].0, after[2].1), (6, 2), "Sear 6 and 2 Burns");
    assert_eq!(after[3].0, 12, "Tackle 6 x2");
    assert_eq!((after[5].2, after[5].3), (12, 3), "Inflame: 12 block, Strength 3");
    assert_eq!(after[6].0, 18, "Tackle (6 + 3) x2");
    assert_eq!(after[8].0, 36, "Inferno (3 + 3) x6");
}

#[test]
fn guardian_a20_shifts_at_40_with_sharp_hide_4() {
    let mut s = fight(&["The Guardian"], EncounterGroup::Boss, 3);
    let g = s.monsters[0];
    assert_eq!((g.hp, g.powers.get(Power::ModeShift), g.rolled_damage), (250, 40, 40));
    let seen = passive(&mut s, 0, 4);
    let names: Vec<&str> = seen.iter().map(|x| x.0).collect();
    assert_eq!(names, ["Charging Up", "Fierce Bash", "Vent Steam", "Whirlwind"]);
    assert_eq!(seen[1].1, 36, "Fierce Bash 36");
    // Mode Shift fires: Defensive mode, Close Up's Sharp Hide 4, the threshold back at 50.
    let shift = threshold(&s, 0).unwrap().effects;
    assert_eq!(shift, &[Effect::Block(guardian::DEFENSIVE_BLOCK), Effect::Apply { power: Power::SharpHide, amount: 4, target: sts_engine::effects::Target::Me }]);
    s.monsters[0].powers.clear(Power::ModeShift);
    s.monsters[0].powers.add(Power::ModeShift, 1);
    s.monsters[0].block = 0;
    s.hand = Hand::from_cards(&[card("Strike")]);
    s.player.energy = 1;
    play(&mut s, "Strike", Some(0));
    assert_eq!(s.monsters[0].intent(), guardian::CLOSE_UP);
    let seen = passive(&mut s, 0, 3);
    assert_eq!(seen.iter().map(|x| x.0).collect::<Vec<_>>(), ["Close Up", "Roll Attack", "Twin Slam"]);
    assert_eq!(seen[1].1, 10, "Roll Attack 10");
    assert_eq!(s.monsters[0].powers.get(Power::ModeShift), 50, "40 + 10 after Twin Slam");
}

#[test]
fn lice_roll_a20_ranges() {
    for seed in 0..40 {
        let s = fight(&["Red Louse", "Green Louse"], EncounterGroup::Hallway, seed);
        for m in &s.monsters[..2] {
            assert!((6..=8).contains(&m.rolled_damage), "bite {}", m.rolled_damage);
            assert!((9..=12).contains(&m.powers.get(Power::CurlUp)), "Curl Up {}", m.powers.get(Power::CurlUp));
        }
    }
}

#[test]
fn run_start_and_potion_slots() {
    assert_eq!(Character::Ironclad.run_start_hp(0), (80, 80));
    assert_eq!(Character::Ironclad.run_start_hp(6), (72, 80));
    assert_eq!(Character::Ironclad.run_start_hp(20), (68, 75));
    assert_eq!(Character::Silent.run_start_hp(20), (59, 66));
    let s = fight(&["Cultist"], EncounterGroup::Hallway, 1);
    assert_eq!((s.ascension, s.potion_slots()), (A20, 2));
    assert_eq!(fresh(Encounter::Cultist, 1).potion_slots(), 3);
}

#[test]
fn codec_round_trips_a20() {
    let s = fight(&["Gremlin Nob"], EncounterGroup::Elite, 5);
    let b = encode(&s);
    let t = decode(&b);
    assert_eq!(t, s);
    assert_eq!(t.monsters[0].ascension, A20);
    assert!(std::ptr::eq(t.monsters[0].def(), K::GremlinNob.def_at(A20)));
    // A0's bytes have no level section; the same fight at A20 differs.
    let a0 = CombatState::new_with_turn1(Character::Ironclad, &Character::Ironclad.starter_deck(), &Binding::default(), 999, 999, &[K::GremlinNob], EncounterGroup::Elite, &[], false, Ascension(0), None, &mut Rng::new(5));
    assert_ne!(encode(&a0), b);
    assert_eq!(decode(&encode(&a0)).ascension, Ascension(0));
    // A level section of 0 or above 20 is no encoding.
    let n = b.len();
    assert_eq!(&b[n - 2..], &[18, 20]);
    for bad in [0, 21] {
        let mut x = b.clone();
        x[n - 1] = bad;
        assert!(sts_engine::codec::try_decode(&x).is_none(), "level {bad}");
    }
}

#[test]
fn bad_ascension_rows_are_load_errors() {
    let pack = |rows: &str| {
        format!(
            r#"{{"version": 1, "monsters": [{{"id": "Asc Bad", "hp": [5, 5], "start_block": 0, "start_powers": [],
            "moves": [{{"name": "Hit", "effects": [{{"Damage": {{"amount": 1, "hits": 1, "target": "Opponent"}}}}]}}],
            "pattern": [{{"when": [], "then": {{"Move": 0}}}}], "ascension": {rows}}}]}}"#
        )
    };
    for (rows, why) in [
        (r#"[{"from": 0, "hp": [6, 6]}]"#, "levels rise"),
        (r#"[{"from": 7, "hp": [6, 6]}, {"from": 2, "hp": [7, 7]}]"#, "levels rise"),
        (r#"[{"from": 21, "hp": [6, 6]}]"#, "levels rise"),
        (r#"[{"from": 2, "split": {"move": 0, "into": ["Cultist", "Cultist"]}}]"#, "doesn't change by level"),
        (r#"[{"from": 2, "moves": {"3": {"name": "X"}}}]"#, "item 3"),
        (r#"[{"from": 2, "moves": [{"name": "A", "effects": []}, {"name": "B", "effects": []}]}]"#, "moves count"),
    ] {
        let e = load_pack(&pack(rows)).unwrap_err();
        assert!(e.contains("ascension") && e.contains(why), "{rows}: {e}");
    }
    // A good row loads, and plays from its level.
    load_pack(&pack(r#"[{"from": 5, "moves": {"0": {"effects": {"0": {"Damage": {"amount": 4}}}}}}]"#).replace("Asc Bad", "Asc Good")).unwrap();
    let k = monster_kinds(&["gen:Asc Good"]).unwrap()[0];
    assert_eq!(num(&k.def_at(Ascension(4)).moves[0].effects[0]), 1);
    assert_eq!(num(&k.def_at(Ascension(5)).moves[0].effects[0]), 4);
}

#[test]
fn rows_with_their_keys_in_another_order_are_the_same_pack() {
    let pack = |row: &str| {
        format!(
            r#"{{"version": 1, "monsters": [{{"id": "Asc Order", "hp": [5, 5], "start_block": 0, "start_powers": [],
            "moves": [{{"name": "Hit", "effects": [{{"Damage": {{"amount": 1, "hits": 1, "target": "Opponent"}}}}]}}],
            "pattern": [{{"when": [], "then": {{"Move": 0}}}}], "ascension": [{row}]}}]}}"#
        )
    };
    load_pack(&pack(r#"{"from": 2, "hp": [6, 6]}"#)).unwrap();
    load_pack(&pack(r#"{"hp": [6, 6], "from": 2}"#)).unwrap();
    assert!(load_pack(&pack(r#"{"hp": [7, 7], "from": 2}"#)).unwrap_err().contains("redefined"));
}
