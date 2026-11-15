//! Hexaghost, The Guardian and their mechanics (Burn, Mode Shift, Sharp
//! Hide), from slaythespire.wiki.gg (Ascension 0). docs/specs/act1-bosses.md.

mod common;
use common::*;
use sts_engine::*;

#[test]
fn burn_hurts_at_turn_end_while_held() {
    // Cultist opens with Incantation: no attack this turn.
    let mut s = with_hand(Encounter::Cultist, &["Burn", "Burn", "Burn+"], 40);
    s.player.block = 3;
    let hp = s.player.hp;
    assert!(!s.legal_actions().iter().any(|a| matches!(a, Action::Play { .. })), "Burn is unplayable");
    end_turn(&mut s);
    assert_eq!(hp - s.player.hp, 2 + 2 + 4 - 3);
    assert_eq!(s.discard().count(card("Burn")) + s.hand.count(card("Burn")) + s.draw().count(card("Burn")), 2);
}

#[test]
fn burn_can_kill() {
    let mut s = with_hand(Encounter::Cultist, &["Burn+"], 40);
    s.player.hp = 4;
    end_turn(&mut s);
    assert!(s.is_over() && !s.won());
}

// ---- Hexaghost ----

use sts_engine::monsters::{hexaghost, MonsterKind as K};

#[test]
fn hexaghost_activate_divider_cycle() {
    let mut s = fresh(Encounter::Hexaghost, 1);
    assert_eq!(s.monsters[0].kind, K::Hexaghost);
    assert_eq!(s.monsters[0].hp, 250);
    s.player.hp = 900;
    s.player.max_hp = 900;
    let mut seen = vec![s.monsters[0].intent()];
    for _ in 0..17 {
        end_turn(&mut s);
        seen.push(s.monsters[0].intent());
    }
    let c = hexaghost::CYCLE;
    let u = hexaghost::CYCLE_UP;
    let mut want = vec![hexaghost::ACTIVATE, hexaghost::DIVIDER];
    want.extend(c..c + 7);
    want.extend(u..u + 7);
    want.extend([u, u + 1]);
    assert_eq!(seen, want);
    let names: Vec<&str> = (c..c + 7).map(|m| s.monsters[0].def().moves[m as usize].name).collect();
    assert_eq!(names, ["Sear", "Tackle", "Sear", "Inflame", "Tackle", "Sear", "Inferno"]);
}

#[test]
fn divider_hits_six_times_for_hp_over_12_plus_1() {
    let mut s = fresh(Encounter::Hexaghost, 1);
    end_turn(&mut s); // Activate; Divider chosen at 80 HP: 7 per hit
    assert_eq!(s.monsters[0].intent(), hexaghost::DIVIDER);
    assert_eq!(s.monsters[0].rolled_damage, 7);
    s.player.hp = 30; // fixed when chosen: losing HP since doesn't change it
    s.hand = Hand::default();
    end_turn(&mut s);
    assert!(s.is_over() && !s.won(), "42 damage kills a player at 30 HP");
}

#[test]
fn sear_adds_burn_and_inferno_upgrades_every_burn() {
    let mut s = fresh(Encounter::Hexaghost, 1);
    s.player.hp = 900;
    s.player.max_hp = 900;
    s.monsters[0].moves = [hexaghost::CYCLE, hexaghost::DIVIDER]; // Sear next
    s.hand = Hand::from_cards(&[card("Burn")]);
    s.set_draw(Pile::from_cards(&[card("Burn"); 5])); // the next hand: 5 Burns, nothing to play
    s.set_discard(Pile::default());
    end_turn(&mut s);
    let burns = |s: &CombatState, up: bool| {
        let c = card(if up { "Burn+" } else { "Burn" });
        s.hand.count(c) + s.draw().count(c) + s.discard().count(c)
    };
    assert_eq!((burns(&s, false), burns(&s, true)), (7, 0), "Sear added one Burn");
    s.monsters[0].moves = [hexaghost::INFERNO, hexaghost::CYCLE + 5];
    end_turn(&mut s);
    assert_eq!((burns(&s, false), burns(&s, true)), (0, 7 + 3));
    assert_eq!(s.monsters[0].intent(), hexaghost::CYCLE_UP);
    end_turn(&mut s); // upgraded Sear
    assert_eq!((burns(&s, false), burns(&s, true)), (0, 11));
}

// ---- The Guardian ----

use sts_engine::monsters::guardian;

fn guardian_fight(hand: &[&str]) -> CombatState {
    let mut s = with_hand(Encounter::Cultist, hand, 240);
    s.monsters[0] = sts_engine::monsters::Monster::new(K::TheGuardian, 240);
    s.monsters[0].rolled_damage = 30;
    s.monsters[0].set_move(guardian::CHARGING_UP);
    s.player.hp = 900;
    s.player.max_hp = 900;
    s
}

#[test]
fn guardian_starts_with_mode_shift_and_cycles_offensive() {
    let mut s = fresh(Encounter::TheGuardian, 3);
    let g = &s.monsters[0];
    assert_eq!((g.kind, g.hp, g.powers.get(Power::ModeShift)), (K::TheGuardian, 240, 30));
    s.player.hp = 900;
    s.player.max_hp = 900;
    let mut seen = vec![s.monsters[0].intent()];
    for _ in 0..5 {
        s.hand = Hand::default();
        end_turn(&mut s);
        seen.push(s.monsters[0].intent());
    }
    use guardian::*;
    assert_eq!(seen, [CHARGING_UP, FIERCE_BASH, VENT_STEAM, WHIRLWIND, CHARGING_UP, FIERCE_BASH]);
}

#[test]
fn guardian_shifts_after_30_hp_with_block_after_the_card() {
    // Twin Strike+: 7 + 7; Heavy Blade: 14; Pummel: 2 x 4.
    let mut s = guardian_fight(&["Twin Strike+", "Heavy Blade"]);
    play(&mut s, "Twin Strike+", Some(0));
    assert_eq!(s.monsters[0].powers.get(Power::ModeShift), 16);
    play(&mut s, "Heavy Blade", Some(0));
    let g = &s.monsters[0];
    assert_eq!((g.powers.get(Power::ModeShift), g.hp, g.block), (2, 240 - 28, 0));
    let mut s = guardian_fight(&["Pummel+", "Heavy Blade", "Twin Strike"]);
    s.player.energy = 4;
    play(&mut s, "Heavy Blade", Some(0));
    play(&mut s, "Twin Strike", Some(0)); // 24 lost
    play(&mut s, "Pummel+", Some(0)); // 5 hits of 2: shifts on the third, block after all five
    let g = &s.monsters[0];
    assert_eq!(g.hp, 240 - 24 - 10);
    assert_eq!((g.powers.get(Power::ModeShift), g.block, g.intent()), (0, 20, guardian::CLOSE_UP));
    assert_eq!(g.rolled_damage, 40);
}

/// Mode Shift broken while the turn ends (`TheGuardian.damage` queues
/// `ChangeStateAction`, which queues its `GainBlockAction`): the game's turn
/// end has already queued `MonsterStartTurnAction` ahead of that block, so
/// the Guardian loses no block and keeps its 20 into the player's next turn
/// (live run 8, turn 7). Broken during the player's turn, the block lands
/// after the card and is lost when the monsters' turn starts.
#[test]
fn guardian_shift_at_turn_end_keeps_its_block() {
    let mut s = guardian_fight(&[]);
    s.player.powers.add(Power::Combust, 1);
    s.player.powers.add(Power::CombustDamage, 5);
    s.monsters[0].powers.add(Power::ModeShift, 3 - 30);
    end_turn(&mut s);
    let g = &s.monsters[0];
    assert_eq!((g.powers.get(Power::ModeShift), g.hp, g.block), (0, 240 - 5, 20));
    assert_eq!((g.powers.get(Power::SharpHide), g.intent()), (3, guardian::ROLL_ATTACK), "Close Up was its move");
    assert_eq!(s.stage, Stage::PlayerTurn);
    // Broken by an attack mid-turn: the 20 block goes at the turn change.
    let mut s = guardian_fight(&["Heavy Blade"]);
    s.monsters[0].powers.add(Power::ModeShift, 3 - 30);
    play(&mut s, "Heavy Blade", Some(0));
    assert_eq!((s.monsters[0].powers.get(Power::ModeShift), s.monsters[0].block), (0, 20));
    end_turn(&mut s);
    assert_eq!((s.monsters[0].block, s.monsters[0].intent()), (0, guardian::ROLL_ATTACK));
}

#[test]
fn guardian_defensive_mode_then_back_with_a_higher_threshold() {
    let mut s = guardian_fight(&[]);
    s.monsters[0].powers.clear(Power::ModeShift);
    s.monsters[0].rolled_damage = 40;
    s.monsters[0].set_move(guardian::CLOSE_UP);
    end_turn(&mut s);
    assert_eq!(s.monsters[0].powers.get(Power::SharpHide), 3);
    assert_eq!(s.monsters[0].intent(), guardian::ROLL_ATTACK);
    s.hand = Hand::default();
    end_turn(&mut s);
    assert_eq!(s.monsters[0].intent(), guardian::TWIN_SLAM);
    s.hand = Hand::default();
    end_turn(&mut s);
    let g = &s.monsters[0];
    assert_eq!((g.powers.get(Power::SharpHide), g.powers.get(Power::ModeShift), g.intent()), (0, 40, guardian::WHIRLWIND));
}

#[test]
fn sharp_hide_hits_after_the_card_for_attacks_only() {
    let mut s = guardian_fight(&["Iron Wave", "Strike", "Defend"]);
    s.monsters[0].powers.add(Power::SharpHide, 3);
    let hp = s.player.hp;
    play(&mut s, "Iron Wave", Some(0)); // 5 block first, then 3 thorns
    assert_eq!((s.player.hp, s.player.block), (hp, 2));
    play(&mut s, "Defend", None);
    assert_eq!((s.player.hp, s.player.block), (hp, 7));
    play(&mut s, "Strike", Some(0));
    assert_eq!((s.player.hp, s.player.block), (hp, 4));
}

#[test]
fn sharp_hide_spares_a_card_that_kills_its_owner() {
    let mut s = guardian_fight(&["Strike"]);
    s.monsters[0].powers.add(Power::SharpHide, 3);
    s.monsters[0].hp = 5;
    s.player.hp = 2;
    play(&mut s, "Strike", Some(0));
    assert!(s.won());
}

#[test]
fn new_bosses_are_by_name_only() {
    for (name, enc) in [("hexaghost", Encounter::Hexaghost), ("the_guardian", Encounter::TheGuardian)] {
        assert_eq!(Encounter::from_name(name), Some(enc));
        assert!(!Encounter::ALL.contains(&enc));
        assert_eq!(enc.group(), sts_engine::monsters::EncounterGroup::Boss);
    }
    assert_eq!(Encounter::ALL.len(), 15);
}
