//! Pins for docs/specs/turn-start-draw.md, written on the code before it
//! (step 1) and kept passing through every later step:
//!
//! - `v1_pack_replays_unchanged`: saved version-1 packs play as they did
//!   when `OwnerTurnStart` ran after the draw. The packs under
//!   `tests/data/v1/` are copies taken 2026-11-10 (at 3459a46): today's
//!   `content/packs/act1-ironclad.json`; the turn-start powers of
//!   `content/packs/gen-enemies-train.json` with the Cultist and Jaw Worm
//!   that start with them; and the generated pack of run
//!   `runs/2026-10-31-lean-gen16-s1-r1-18daa19` (its `gp2_008` draws a card
//!   at turn start). Each fight is played by seeded random legal actions;
//!   every state at a decision is hashed (all but its binding), and the hash,
//!   the result and the turn count are pinned.
//! - `tsl1_unchanged_on_official`: the turn-start leaf (`@tsl1`) on Demon
//!   Form and Brutality states, before the monster's roll and at the draw,
//!   and a search with it, pinned to today's values.

use sts_engine::codec::encode;
use sts_engine::registry::{bind, load_pack, monster_kinds, Binding};
use sts_engine::search::{search, Heuristic, SearchConfig};
use sts_engine::*;

const ACT1_IRONCLAD: &str = include_str!("data/v1/act1_ironclad.json");
const GEN_ENEMIES: &str = include_str!("data/v1/gen_enemies_turn_start.json");
const GENERATED: &str = include_str!("data/v1/generated_gen16_s1.json");

/// Hash of everything in `s` but its binding (the codec refuses a state
/// with generated content, and a version-1 pack's binding may name its
/// triggers differently once read; what it does is what's pinned).
fn state_hash(h: u64, s: &CombatState) -> u64 {
    let mut t = s.clone();
    t.binding = Default::default();
    fnv(h, format!("{t:?}").as_bytes())
}

/// FNV-1a over `bytes`, continuing from `h`.
fn fnv(mut h: u64, bytes: &[u8]) -> u64 {
    for &b in bytes {
        h ^= b as u64;
        h = h.wrapping_mul(0x100_0000_01b3);
    }
    h
}

const FNV0: u64 = 0xcbf2_9ce4_8422_2325;

/// Whether the player or a living monster holds a pack power.
fn holds_pack_power(s: &CombatState) -> bool {
    let official = Binding::default().powers_in_play().len();
    let pack = &s.binding.powers_in_play()[official..];
    pack.iter().any(|&p| s.player.powers.get(p) > 0 || s.monsters.iter().any(|m| m.alive() && m.powers.get(p) > 0))
}

/// Plays `s` to its end (or 400 decisions) by seeded random legal actions:
/// (hash of every decision state, won, turns, player HP, turns started
/// with a pack power held, so the pin is seen to cover turn-start hooks).
fn replay(mut s: CombatState, seed: u64) -> (u64, bool, u16, i16, u16) {
    let mut rng = Rng::new(seed);
    let mut pick = Rng::new(seed ^ 0x9e37);
    let mut h = state_hash(FNV0, &s);
    let mut held = 0;
    for _ in 0..400 {
        if s.is_over() {
            break;
        }
        let turn = s.turn;
        let acts = s.legal_actions();
        let a = acts[pick.below(acts.len() as u32) as usize];
        s.step(a, &mut rng).expect("legal");
        if s.turn != turn && holds_pack_power(&s) {
            held += 1;
        }
        h = state_hash(h, &s);
    }
    (h, s.won(), s.turn as u16, s.player.hp, held)
}

fn starter_names() -> Vec<String> {
    starter_deck().iter().map(|&c| c.def().name.to_string()).collect()
}

fn deck_with(extra: &[&str]) -> Vec<String> {
    let mut d = starter_names();
    d.extend(extra.iter().map(|s| s.to_string()));
    d
}

fn fight(cards: &[String], monsters: &[&str], seed: u64) -> CombatState {
    let refs: Vec<&str> = cards.iter().map(String::as_str).collect();
    let (ids, b) = bind(&refs).unwrap();
    let kinds: Vec<MonsterKind> = if monsters.iter().all(|m| m.starts_with("gen:")) {
        monster_kinds(monsters).unwrap()
    } else {
        assert_eq!(monsters, &["Jaw Worm"]);
        vec![MonsterKind::JawWorm]
    };
    CombatState::new_vs(Character::Ironclad, &ids, &b, 60, 80, &kinds, &mut Rng::new(seed))
}

#[test]
fn v1_pack_replays_unchanged() {
    load_pack(ACT1_IRONCLAD).unwrap();
    load_pack(GEN_ENEMIES).unwrap();
    load_pack(GENERATED).unwrap();
    let ironclad = deck_with(&["gen:Berserk", "gen:Flame Barrier", "gen:Flame Barrier", "gen:Dark Embrace", "gen:Evolve"]);
    let generated = deck_with(&["gen:gc2_008", "gen:gc2_008", "gen:gc2_008"]);
    let cases: Vec<(&str, Vec<String>, Vec<&str>)> = vec![
        ("act1-ironclad", ironclad, vec!["Jaw Worm"]),
        ("gen-enemies", starter_names(), vec!["gen:Cultist GE-TurnStart-Strength", "gen:Jaw Worm GE-TurnStart-Damage"]),
        ("gen-enemies weak", starter_names(), vec!["gen:Jaw Worm GE-TurnStart-Weak", "gen:Cultist GE-TurnStart-Block"]),
        ("generated draw", generated, vec!["Jaw Worm"]),
    ];
    let mut got = Vec::new();
    for (name, deck, monsters) in &cases {
        for seed in 0..4u64 {
            got.push((*name, seed, replay(fight(deck, monsters, seed), seed)));
        }
    }
    // Today's values (2026-11-10, 3459a46).
    let want: &[(&str, u64, (u64, bool, u16, i16, u16))] = &[
        ("act1-ironclad", 0, (851161198614358347, false, 13, 0, 11)),
        ("act1-ironclad", 1, (17227370777573702714, true, 8, 25, 7)),
        ("act1-ironclad", 2, (17672056480155032515, false, 8, 0, 6)),
        ("act1-ironclad", 3, (7464476972538781600, false, 9, 0, 0)),
        ("gen-enemies", 0, (12642419523441898119, false, 4, 0, 3)),
        ("gen-enemies", 1, (14780755071947868196, false, 3, 0, 2)),
        ("gen-enemies", 2, (15018546104595569192, false, 3, 0, 2)),
        ("gen-enemies", 3, (6477181667747167468, false, 3, 0, 2)),
        ("gen-enemies weak", 0, (9682870029494678632, false, 5, 0, 4)),
        ("gen-enemies weak", 1, (2647576199834082418, false, 4, 0, 3)),
        ("gen-enemies weak", 2, (4684266554827581027, false, 5, 0, 4)),
        ("gen-enemies weak", 3, (14615960228322672628, false, 5, 0, 4)),
        ("generated draw", 0, (3882389484953480017, false, 11, 0, 8)),
        ("generated draw", 1, (8710677175777579315, true, 8, 23, 3)),
        ("generated draw", 2, (10790959694230419914, false, 9, 0, 8)),
        ("generated draw", 3, (9432289177293501118, true, 7, 24, 5)),
    ];
    assert_eq!(got.as_slice(), want);
}

/// A Jaw Worm (its next move is a roll) at 100 HP, the starter deck in the
/// draw pile (so the turn's draw is a chance event), `hand`, and the player holding `powers`.
fn official(hand: &[&str], powers: &[(Power, i16)]) -> CombatState {
    let deck = starter_deck();
    let mut s = CombatState::new_vs(Character::Ironclad, &deck, &Default::default(), 60, 80, &[MonsterKind::JawWorm], &mut Rng::new(4));
    s.monsters[0].hp = 100;
    s.monsters[0].max_hp = 100;
    s.hand = Hand::from_cards(&hand.iter().map(|n| CardId::from_name(n).unwrap()).collect::<Vec<_>>());
    s.set_draw(Pile::from_cards(&deck));
    s.set_discard(Pile::default());
    s.player.energy = 3;
    for &(p, n) in powers {
        s.player.powers.add(p, n);
    }
    s
}

/// (hash of the leaf's encoding, player HP, Strength, hand, draw pile)
/// of `@tsl1` at `s`, or `None`.
fn leaf(s: &CombatState) -> Option<(u64, i16, i16, usize, usize)> {
    s.turn_start_leaf()
        .map(|t| (fnv(FNV0, &encode(&t)), t.player.hp, t.player.powers.get(Power::Strength), t.hand.len(), t.draw().len()))
}

#[test]
fn tsl1_unchanged_on_official() {
    let mut got = Vec::new();
    for powers in [&[(Power::DemonForm, 2)][..], &[(Power::Brutality, 1)], &[(Power::DemonForm, 3), (Power::Brutality, 1)]] {
        let s = official(&["Strike", "Defend", "Bash"], powers);
        // A search with the leaf on, from the player's decision.
        let r = search(&s, &mut Heuristic, &SearchConfig { turn_start_leaf: true, ..SearchConfig::default() });
        let best = r.options.iter().map(|o| o.value).fold(f32::MIN, f32::max);
        let line_hash = fnv(FNV0, format!("{:?}", r.line).as_bytes());
        // Paused after EndTurn: the monster's roll pending, then at the draw.
        let mut t = s.clone();
        t.apply_action(Action::EndTurn).unwrap();
        let at_roll = (format!("{:?}", t.stage), leaf(&t));
        let mut rng = Rng::new(9);
        let mut guard = 0;
        while !(t.stage == Stage::TurnStarted && t.pending.is_some()) {
            t.resolve_chance(&mut rng);
            guard += 1;
            assert!(guard < 10 && !t.is_over(), "reaches the draw");
        }
        let at_draw = leaf(&t);
        got.push((r.nodes, r.leaves, best.to_bits(), line_hash, at_roll, at_draw));
    }
    let want: &[(usize, usize, u32, u64, (String, Option<(u64, i16, i16, usize, usize)>), Option<(u64, i16, i16, usize, usize)>)] = &[
        // Today's values (2026-11-10, 3459a46): Demon Form 2, Brutality 1, both.
        (15, 8, 1072900731, 6366289202657690734, ("MonsterRolls { next: 1 }".into(), Some((1840191909954164367, 49, 2, 0, 10))), Some((9488766891187505861, 49, 2, 0, 10))),
        (15, 8, 1069635981, 6366289202657690734, ("MonsterRolls { next: 1 }".into(), Some((16469820079336855514, 48, 0, 0, 10))), Some((4711681428527598130, 48, 0, 0, 10))),
        (15, 8, 1072586777, 6366289202657690734, ("MonsterRolls { next: 1 }".into(), Some((12119199469004265525, 48, 3, 0, 10))), Some((13377040536559367727, 48, 3, 0, 10))),
    ];
    assert_eq!(got.as_slice(), want);
}
