//! Monster values and move rules from the StS wiki (slaythespire.wiki.gg).

mod common;
use common::*;
use sts_engine::monsters::*;
use sts_engine::*;

/// A state whose player just ends turns: no cards, lots of HP.
fn idle(enc: Encounter) -> CombatState {
    let mut s = with_hand(enc, &[], 40);
    s.player.hp = 500;
    s.player.max_hp = 500;
    s
}

fn hp_loss_on_end_turn(s: &mut CombatState) -> i16 {
    let before = s.player.hp;
    end_turn(s);
    before - s.player.hp
}

#[test]
fn hp_ranges() {
    for seed in 0..500 {
        let c = fresh(Encounter::Cultist, seed).monsters[0].hp;
        assert!((48..=54).contains(&c), "cultist hp {c}");
        let j = fresh(Encounter::JawWorm, seed).monsters[0].hp;
        assert!((40..=44).contains(&j), "jaw worm hp {j}");
    }
}

#[test]
fn cultist_incantation_then_dark_strike_growing_by_ritual() {
    let mut s = idle(Encounter::Cultist);
    assert_eq!(s.monsters[0].intent(), INCANTATION);
    assert_eq!(hp_loss_on_end_turn(&mut s), 0);
    assert_eq!(s.monsters[0].powers.get(Power::Ritual), 3);
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 0); // Ritual skips the turn it's gained
    assert_eq!(s.monsters[0].intent(), DARK_STRIKE);
    assert_eq!(hp_loss_on_end_turn(&mut s), 6);
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 3);
    assert_eq!(hp_loss_on_end_turn(&mut s), 9);
    assert_eq!(hp_loss_on_end_turn(&mut s), 12);
    assert_eq!(s.monsters[0].intent(), DARK_STRIKE);
}

#[test]
fn jaw_worm_always_starts_with_chomp_for_11() {
    for seed in 0..50 {
        let s = fresh(Encounter::JawWorm, seed);
        assert_eq!(s.monsters[0].intent(), CHOMP);
    }
    let mut s = idle(Encounter::JawWorm);
    assert_eq!(hp_loss_on_end_turn(&mut s), 11);
}

fn jaw_worm_doing(m: MoveId) -> CombatState {
    let mut s = idle(Encounter::JawWorm);
    s.monsters[0].moves = [m, CHOMP];
    s
}

#[test]
fn jaw_worm_thrash_deals_7_and_blocks_5() {
    let mut s = jaw_worm_doing(THRASH);
    assert_eq!(hp_loss_on_end_turn(&mut s), 7);
    assert_eq!(s.monsters[0].block, 5);
}

#[test]
fn jaw_worm_bellow_gains_3_strength_and_6_block() {
    let mut s = jaw_worm_doing(BELLOW);
    assert_eq!(hp_loss_on_end_turn(&mut s), 0);
    assert_eq!(s.monsters[0].powers.get(Power::Strength), 3);
    assert_eq!(s.monsters[0].block, 6);
    // Strength boosts the next attack.
    s.monsters[0].moves = [CHOMP, BELLOW];
    assert_eq!(hp_loss_on_end_turn(&mut s), 14);
}

#[test]
fn monster_block_lasts_until_its_next_turn() {
    let mut s = jaw_worm_doing(THRASH);
    end_turn(&mut s);
    assert_eq!(s.monsters[0].block, 5); // still up during the player's turn
    s.monsters[0].moves = [CHOMP, THRASH];
    end_turn(&mut s);
    assert_eq!(s.monsters[0].block, 0);
}

#[test]
fn player_block_resets_at_turn_start() {
    let mut s = idle(Encounter::JawWorm);
    s.player.block = 20;
    assert_eq!(hp_loss_on_end_turn(&mut s), 0); // Chomp 11 absorbed
    assert_eq!(s.player.block, 0);
    assert_eq!(s.player.energy, 3);
}

fn dist(history: [MoveId; 2]) -> Vec<(MoveId, f64)> {
    let mut s = idle(Encounter::JawWorm);
    s.monsters[0].moves = history;
    let mut d = s.move_distribution(0);
    d.sort_by_key(|&(m, _)| m);
    d
}

fn approx(d: &[(MoveId, f64)], expect: &[(MoveId, f64)]) {
    assert_eq!(d.len(), expect.len(), "{d:?}");
    for ((m, p), (em, ep)) in d.iter().zip(expect) {
        assert_eq!(m, em);
        assert!((p - ep).abs() < 1e-9, "{d:?} vs {expect:?}");
    }
    let total: f64 = d.iter().map(|x| x.1).sum();
    assert!((total - 1.0).abs() < 1e-12);
}

#[test]
fn jaw_worm_move_odds_match_wiki() {
    // Wiki: after Chomp 59% Bellow / 41% Thrash.
    approx(&dist([CHOMP, NO_MOVE]), &[(THRASH, 0.409375), (BELLOW, 0.590625)]);
    // After Bellow 56% Thrash / 44% Chomp.
    approx(&dist([BELLOW, CHOMP]), &[(CHOMP, 0.25 + 0.45 * 0.416), (THRASH, 0.30 + 0.45 * 0.584)]);
    // After one Thrash 45% Bellow / 30% Thrash / 25% Chomp.
    approx(&dist([THRASH, CHOMP]), &[(CHOMP, 0.25), (THRASH, 0.30), (BELLOW, 0.45)]);
    // After two Thrashes 64% Bellow / 36% Chomp (no third Thrash).
    approx(&dist([THRASH, THRASH]), &[(CHOMP, 0.25 + 0.30 * 0.357), (BELLOW, 0.45 + 0.30 * 0.643)]);
    // Rounded, these are the wiki's percentages.
    let pct = |h, m| (dist(h).iter().find(|x| x.0 == m).unwrap().1 * 100.0).round();
    assert_eq!(pct([CHOMP, NO_MOVE], BELLOW), 59.0);
    assert_eq!(pct([BELLOW, CHOMP], THRASH), 56.0);
    assert_eq!(pct([THRASH, THRASH], BELLOW), 64.0);
}

#[test]
fn jaw_worm_roll_is_a_chance_node() {
    let mut s = idle(Encounter::JawWorm);
    s.apply_action(Action::EndTurn).unwrap();
    assert_eq!(s.pending, Some(ChanceEvent::MonsterMove { slot: 0 }));
    let Some(ChanceOutcomes::Listed(v)) = s.chance_outcomes(16) else { panic!() };
    assert_eq!(v.len(), 2); // Thrash or Bellow after Chomp
    assert!(matches!(s.chance_outcomes(1), Some(ChanceOutcomes::Large)));
}

#[test]
fn vulnerable_from_bash_lasts_two_player_turns() {
    let mut s = with_hand(Encounter::Cultist, &["Bash"], 100);
    s.player.hp = 500;
    s.player.max_hp = 500;
    play(&mut s, "Bash", Some(0));
    end_turn(&mut s);
    assert_eq!(s.monsters[0].powers.get(Power::Vulnerable), 1);
    end_turn(&mut s);
    assert_eq!(s.monsters[0].powers.get(Power::Vulnerable), 0);
}

/// `monsters::Ai`'s rule, which `heuristic::damage_rate` caches on: an AI
/// reads only its monster's kind, slot and move history. Every kind, slot
/// and move pair gives the same distribution when everything else changes.
#[test]
fn ai_reads_only_moves() {
    use sts_engine::state::MAX_MONSTERS;
    const KINDS: [MonsterKind; 18] = [
        MonsterKind::Cultist,
        MonsterKind::JawWorm,
        MonsterKind::RedLouse,
        MonsterKind::GreenLouse,
        MonsterKind::AcidSlimeS,
        MonsterKind::AcidSlimeM,
        MonsterKind::AcidSlimeL,
        MonsterKind::SpikeSlimeS,
        MonsterKind::SpikeSlimeM,
        MonsterKind::SpikeSlimeL,
        MonsterKind::FungiBeast,
        MonsterKind::Looter,
        MonsterKind::GremlinNob,
        MonsterKind::Lagavulin,
        MonsterKind::Sentry,
        MonsterKind::SlimeBoss,
        MonsterKind::Hexaghost,
        MonsterKind::TheGuardian,
    ];
    let base = fresh(Encounter::Cultist, 1);
    let mut checked = 0;
    for kind in KINDS {
        let n = kind.def().moves.len() as MoveId;
        let ids: Vec<MoveId> = std::iter::once(NO_MOVE).chain(0..n).collect();
        for slot in 0..MAX_MONSTERS {
            for &a in &ids {
                for &b in &ids {
                    let mut s = base.clone();
                    s.monsters = Default::default();
                    s.monsters[slot] = Monster::new(kind, 40);
                    s.monsters[slot].moves = [a, b];
                    let mut t = s.clone();
                    let m = &mut t.monsters[slot];
                    m.hp = 7;
                    m.max_hp = 90;
                    m.block = 12;
                    m.rolled_damage = 6;
                    m.powers.add(Power::Strength, 3);
                    m.powers.add(Power::Weak, 2);
                    m.powers.add(Power::Vulnerable, 1);
                    for other in (0..MAX_MONSTERS).filter(|&o| o != slot) {
                        t.monsters[other] = Monster::new(MonsterKind::JawWorm, 30 + other as i16);
                    }
                    t.turn += 5;
                    t.player.hp -= 20;
                    t.player.block = 9;
                    t.player.powers.add(Power::Strength, 2);
                    assert_eq!(s.move_distribution(slot), t.move_distribution(slot), "{kind:?} slot {slot} moves {:?}", [a, b]);
                    checked += 1;
                }
            }
        }
    }
    assert!(checked > 1000);
}

#[test]
fn monster_debuff_on_player_skips_its_first_round() {
    // The countdown is a `RoundEnd` hook, which skips `just_applied` powers.
    let mut s = vs(&[MonsterKind::JawWorm], &[], Some(100));
    s.player.powers.add(Power::Weak, 1);
    s.player.powers.set_just_applied(Power::Weak);
    end_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Weak), 1);
    assert!(!s.player.powers.just_applied(Power::Weak));
    end_turn(&mut s);
    assert_eq!(s.player.powers.get(Power::Weak), 0);
}
