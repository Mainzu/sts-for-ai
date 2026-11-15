//! Blocks M6 and M7's building blocks on small test packs
//! (docs/specs/m6-m7-monsters.md): the `Allies` pattern condition, the
//! `BlockAlly` move effect and a pack power that forbids a card type.

mod common;

use common::vs;
use sts_engine::registry::{load_pack, monster_kinds, Binding};
use sts_engine::chance::{ChanceEvent, ChanceOutcomes};
use sts_engine::monsters::NO_MOVE;
use sts_engine::cards::CardType;
use sts_engine::*;

const PACK: &str = r#"{"version": 1, "powers": [
  {"id": "Tangled", "debuff": true, "forbids": "Attack",
   "hooks": [{"trigger": "OwnerTurnEnd", "condition": "Always", "effects": ["RemoveSelf"]}], "statics": [], "replacements": []}
], "monsters": [
  {"id": "Tangler", "hp": [30, 30], "start_block": 0, "start_powers": [],
   "moves": [{"name": "Tangle", "effects": [{"Apply": {"power": "Tangled", "amount": 1, "target": "Opponent"}}]},
             {"name": "Poke", "effects": [{"Damage": {"amount": 1, "hits": 1, "target": "Opponent"}}]}],
   "pattern": [{"when": ["FirstTurn"], "then": {"Move": 0}}, {"when": [], "then": {"Move": 1}}]},
  {"id": "Ally Watcher", "hp": [20, 20], "start_block": 0, "start_powers": [],
   "moves": [{"name": "Guard", "effects": [{"Damage": {"amount": 1, "hits": 1, "target": "Opponent"}}]},
             {"name": "Alone", "effects": [{"Damage": {"amount": 2, "hits": 1, "target": "Opponent"}}]}],
   "pattern": [{"when": ["Allies"], "then": {"Move": 0}}, {"when": [], "then": {"Move": 1}}]},
  {"id": "Protector", "hp": [12, 12], "start_block": 0, "start_powers": [],
   "moves": [{"name": "Protect", "effects": [{"BlockAlly": 7}]}],
   "pattern": [{"when": [], "then": {"Move": 0}}]},
  {"id": "Tsundere", "hp": [12, 12], "start_block": 0, "start_powers": [],
   "moves": [{"name": "Protect", "effects": [{"BlockAlly": 7}]},
             {"name": "Bash", "effects": [{"Damage": {"amount": 6, "hits": 1, "target": "Opponent"}}]}],
   "pattern": [{"when": ["FirstTurn"], "then": {"Move": 0}}, {"when": [{"LastMove": 1}], "then": {"Move": 1}},
               {"when": ["Allies"], "then": {"Move": 0}}, {"when": [], "then": {"Move": 1}}]}
]}"#;

fn kind(id: &str) -> MonsterKind {
    load_pack(PACK).unwrap();
    monster_kinds(&[&format!("gen:{id}")]).unwrap()[0]
}

#[test]
fn allies_condition() {
    let w = kind("Ally Watcher");
    let mut s = vs(&[w, MonsterKind::Cultist], &[], None);
    assert_eq!(s.move_distribution(0), vec![(0, 1.0)], "an ally lives: Guard");
    // Same kind, slot and move history: only the ally's death differs, so
    // the cache must not hand back the first answer.
    s.monsters[1].hp = 0;
    assert_eq!(s.move_distribution(0), vec![(1, 1.0)], "alone: Alone");
    let alone = vs(&[w], &[], None);
    assert_eq!(alone.move_distribution(0), vec![(1, 1.0)]);
}

/// A Protector in slot 0 and `allies` Ally Watchers, every one with a move
/// on show, after the player ends the turn (chance not resolved).
fn protect_turn(allies: usize) -> CombatState {
    let mut kinds = vec![kind("Protector")];
    kinds.extend(std::iter::repeat(kind("Ally Watcher")).take(allies));
    lineup_turn(&kinds, 0)
}

/// These monsters (Watchers at 20 HP, the rest at 12), every one showing
/// its move 0, after the player with Thorns `thorns` ends the turn (chance
/// not resolved).
fn lineup_turn(kinds: &[MonsterKind], thorns: i16) -> CombatState {
    let watcher = kind("Ally Watcher");
    let mut s = vs(kinds, &[], Some(12));
    for m in s.monsters.iter_mut().filter(|m| m.alive()) {
        if m.kind == watcher {
            (m.hp, m.max_hp) = (20, 20);
        }
        m.set_move(0);
    }
    s.player.powers.add(Power::Thorns, thorns);
    s.apply_action(Action::EndTurn).unwrap();
    s
}

#[test]
fn ally_block_lands_before_later_attackers() {
    // The game's GainBlockRandomMonsterAction resolves before the next
    // monster's move: the Watcher's Guard meets Thorns with 7 block.
    let (p, w) = (kind("Protector"), kind("Ally Watcher"));
    let s = lineup_turn(&[p, w], 3);
    assert_eq!((s.monsters[1].hp, s.monsters[1].block), (20, 4));
    // A Watcher before the Protector takes Thorns first, then the block.
    let s = lineup_turn(&[w, p], 3);
    assert_eq!((s.monsters[0].hp, s.monsters[0].block), (17, 7));
}

#[test]
fn ally_block_pick_pauses_the_monsters_turn() {
    let (p, w) = (kind("Protector"), kind("Ally Watcher"));
    let s = lineup_turn(&[p, w, w], 3);
    assert_eq!(s.pending, Some(ChanceEvent::AllyBlock { slot: 0 }));
    assert_eq!(s.stage, Stage::MonsterActing { slot: 0, next: 1 });
    assert!(!s.turn_has_ended(), "at rest while paused");
    let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(16) else { panic!("listed outcomes") };
    assert_eq!(v.len(), 2);
    for (k, (pr, t)) in v.iter().enumerate() {
        assert!((pr - 0.5).abs() < 1e-12);
        let (on, off) = (1 + k, 2 - k);
        assert_eq!((t.monsters[on].hp, t.monsters[on].block), (20, 4), "outcome {k}");
        assert_eq!((t.monsters[off].hp, t.monsters[off].block), (17, 0), "outcome {k}");
        assert_eq!(t.stage, Stage::PlayerTurn);
    }
}

#[test]
fn allies_counted_at_the_move() {
    // The Watcher (2 HP) is the Tsundere's only candidate: its 7 block and
    // 2 HP fall to Thorns 10 on its Guard. The game counted it alive at
    // the Protect, so the Tsundere protects again.
    let (t, w) = (kind("Tsundere"), kind("Ally Watcher"));
    let mut s = vs(&[t, w], &[], Some(12));
    s.monsters[1].hp = 2;
    for m in s.monsters.iter_mut().filter(|m| m.alive()) {
        m.set_move(0);
    }
    s.player.powers.add(Power::Thorns, 10);
    let mut rng = Rng::new(4);
    s.step(Action::EndTurn, &mut rng).unwrap();
    assert!(!s.monsters[1].alive());
    assert_eq!(s.monsters[0].intent(), 0, "Protect again (counted at the move)");
    // Alone now: it protects itself, then bashes.
    s.step(Action::EndTurn, &mut rng).unwrap();
    assert_eq!((s.monsters[0].block, s.monsters[0].intent()), (7, 1));
}

#[test]
fn block_ally_outcomes() {
    let s = protect_turn(3);
    assert_eq!(s.pending, Some(ChanceEvent::AllyBlock { slot: 0 }));
    assert_eq!(s.monsters[0].block + s.monsters[1].block + s.monsters[2].block + s.monsters[3].block, 0, "no block before the pick");
    let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(16) else { panic!("listed outcomes") };
    assert_eq!(v.len(), 3);
    let mut got: Vec<usize> = v
        .iter()
        .map(|(p, t)| {
            assert!((p - 1.0 / 3.0).abs() < 1e-12);
            assert_eq!(t.monsters[0].block, 0, "the Protector keeps none");
            assert_ne!(t.monsters[0].intent(), NO_MOVE, "then it rolls");
            let on: Vec<usize> = (1..4).filter(|&i| t.monsters[i].block == 7).collect();
            assert_eq!(on.len(), 1);
            assert_eq!((1..4).map(|i| t.monsters[i].block).sum::<i16>(), 7);
            on[0]
        })
        .collect();
    got.sort_unstable();
    assert_eq!(got, [1, 2, 3]);
    // Sampling gives one of the listed states.
    let mut t = s.clone();
    t.advance(&mut Rng::new(3));
    assert_eq!((1..4).map(|i| t.monsters[i].block).sum::<i16>(), 7);

    let one = protect_turn(1);
    assert_ne!(one.pending, Some(ChanceEvent::AllyBlock { slot: 0 }), "one ally: no pick");
    assert_eq!((one.monsters[0].block, one.monsters[1].block), (0, 7));
    let alone = protect_turn(0);
    assert_eq!(alone.monsters[0].block, 7, "no ally: itself");
}

/// Whether any Attack card is among the legal plays.
fn attack_legal(s: &CombatState) -> bool {
    s.legal_actions().iter().any(|a| matches!(a, Action::Play { card, .. } if s.binding.def(*card).ty == CardType::Attack))
}

#[test]
fn entangled_forbids_attacks() {
    let k = kind("Tangler");
    let mut rng = Rng::new(1);
    let deck = Character::Ironclad.starter_deck();
    let mut s = CombatState::new_vs(Character::Ironclad, &deck, &Binding::default(), 80, 80, &[k], &mut rng);
    assert!(attack_legal(&s), "turn 1: Strikes playable");
    s.step(Action::EndTurn, &mut rng).unwrap();
    let tangled = s.player.powers.iter().filter(|&(p, n)| n != 0 && s.binding.power_id(p) == Some("Tangled")).count();
    assert_eq!(tangled, 1, "Tangle applied the pack power to the player");
    assert!(!attack_legal(&s), "turn 2: no Attack playable while Tangled");
    assert!(s.legal_actions().iter().any(|a| matches!(a, Action::Play { .. })), "Skills stay playable");
    s.step(Action::EndTurn, &mut rng).unwrap();
    assert!(attack_legal(&s), "turn 3: removed at the player's turn end");
}

#[test]
fn forbids_unknown_type_is_a_load_error() {
    let bad = r#"{"version": 1, "powers": [{"id": "Bad Forbid", "forbids": "Blessing", "hooks": [], "statics": [], "replacements": []}]}"#;
    assert!(load_pack(bad).unwrap_err().contains("forbids"));
}

#[test]
fn allies_with_a_value_is_a_load_error() {
    let bad = r#"{"version": 1, "monsters": [{"id": "Bad Allies", "hp": [5, 5], "start_block": 0, "start_powers": [],
      "moves": [{"name": "Hit", "effects": [{"Damage": {"amount": 1, "hits": 1, "target": "Opponent"}}]}],
      "pattern": [{"when": [{"Allies": 3}], "then": {"Move": 0}}, {"when": [], "then": {"Move": 0}}]}]}"#;
    assert!(load_pack(bad).unwrap_err().contains("Allies takes no value"));
}

#[test]
fn allies_at_move_is_never_encoded() {
    // Only a pack monster whose pattern reads `Allies` sets it, and the
    // codec refuses states with pack content: an encoded state holds 0.
    let (p, w) = (kind("Tsundere"), kind("Ally Watcher"));
    let s = lineup_turn(&[p, w], 0);
    assert_ne!(s.allies_at_move, 0);
    assert!(s.has_generated());
    let r = std::panic::catch_unwind(|| sts_engine::codec::encode(&s));
    assert!(r.is_err(), "the codec refuses a pack-monster state");
    // Official monsters never set it.
    let mut o = CombatState::new(&starter_deck(), 80, 80, Encounter::GremlinNob, &mut Rng::new(2));
    o.step(Action::EndTurn, &mut Rng::new(3)).unwrap();
    assert_eq!(o.allies_at_move, 0);
}
