//! docs/specs/after-block.md: the four after-block replacement passes, the
//! `AtLeast` action and the `upTo` range, on test pack powers shaped as the
//! game's classes (`relics/Boot.java`, `powers/BufferPower.java`,
//! `relics/Torii.java`, `relics/TungstenRod.java`), in the order of
//! `AbstractPlayer.damage` / `AbstractMonster.damage`.

use sts_engine::registry::{bind_power, load_pack, monster_kinds, Binding};
use sts_engine::*;

const PACK: &str = r#"{"version": 2, "powers": [
{"id": "TestBuffer", "replacements": [{"event": "TakenAfterBlock", "action": "Cancel", "then": [{"ReduceSelf": 1}]}]},
{"id": "TestLift", "replacements": [{"event": "DealtAfterBlock", "action": {"AtLeast": 5}, "then": []}]},
{"id": "TestSoften", "replacements": [{"event": "AttackedAfterBlock", "upTo": 5, "action": {"Cap": 1}, "then": []}]},
{"id": "TestDull", "replacements": [{"event": "HpLossLast", "action": {"Add": -1}, "then": []}]}
], "monsters": [
{"id": "Buffered Dummy", "hp": [40, 40], "start_block": 0, "start_powers": [{"power": "TestBuffer", "amount": 1}],
 "moves": [{"name": "Wait", "effects": [{"Block": 1}]}],
 "pattern": [{"when": [], "then": {"Move": 0}}]}
]}"#;

const NAMES: [&str; 4] = ["TestBuffer", "TestLift", "TestSoften", "TestDull"];

/// The four test powers bound (none held yet).
fn bound() -> (Binding, [Power; 4]) {
    load_pack(PACK).unwrap();
    let mut b = Binding::default();
    let mut ps = [Power::Strength; 4];
    for (i, n) in NAMES.iter().enumerate() {
        let (nb, p) = bind_power(&b, n).unwrap();
        b = nb;
        ps[i] = p;
    }
    // Slots never move: each power keeps the slot it was bound at.
    for (i, n) in NAMES.iter().enumerate() {
        assert_eq!(bind_power(&b, n).unwrap().1, ps[i]);
    }
    (b, ps)
}

fn fight(enc: Encounter, b: &Binding) -> CombatState {
    CombatState::new_bound_with(Character::Ironclad, &starter_deck(), b, 50, 80, enc, &[], &mut Rng::new(11))
}

/// A Jaw Worm fight (its first move is Chomp, 11) with these test powers
/// on the player.
fn jaw_worm(held: &[usize]) -> (CombatState, [Power; 4]) {
    let (b, ps) = bound();
    let mut s = fight(Encounter::JawWorm, &b);
    for &i in held {
        s.player.powers.add(ps[i], 1);
    }
    (s, ps)
}

/// Plays `name` from hand (put there if it isn't) at monster 0.
fn play(s: &mut CombatState, name: &str) {
    let c = CardId::from_name(name).unwrap();
    if s.hand.count(c) == 0 {
        s.hand.add(c, 1);
    }
    s.player.energy = s.player.energy.max(3);
    let target = if c.def().targeted() { Some(0) } else { None };
    s.step(Action::Play { card: c, target }, &mut Rng::new(13)).unwrap();
}

/// HP monster 0 loses to `name` played at it with `block`.
fn dealt(mut s: CombatState, name: &str, block: i16) -> i16 {
    s.monsters[0].block = block;
    let before = s.monsters[0].hp;
    play(&mut s, name);
    before - s.monsters[0].hp
}

/// HP the player loses over the monsters' turn, ending it with `block`.
fn taken(mut s: CombatState, block: i16) -> i16 {
    s.player.block = block;
    let before = s.player.hp;
    let mut rng = Rng::new(12);
    s.step(Action::EndTurn, &mut rng).unwrap();
    s.advance(&mut rng);
    assert!(!s.is_over());
    before - s.player.hp
}

#[test]
fn the_binding_knows_whether_a_power_has_an_after_block_row() {
    let (b, _) = bound();
    assert!(b.has_after_block());
    assert!(!Binding::default().has_after_block());
}

#[test]
fn bound_but_not_held_plays_as_before() {
    let (b, _) = bound();
    let plain = fight(Encounter::JawWorm, &Binding::default());
    let with = fight(Encounter::JawWorm, &b);
    for block in [0, 3, 6] {
        assert_eq!(dealt(with.clone(), "Strike", block), dealt(plain.clone(), "Strike", block));
    }
    for block in [0, 6, 10, 11] {
        assert_eq!(taken(with.clone(), block), taken(plain.clone(), block));
    }
}

#[test]
fn dealt_after_block_raises_a_small_unblocked_attack() {
    // Boot.java `onAttackToChangeDamage`: unblocked NORMAL damage 1..4 -> 5,
    // after the monster's block (AbstractMonster.damage).
    let (s, _) = jaw_worm(&[1]);
    assert_eq!(dealt(s.clone(), "Strike", 0), 6);
    assert_eq!(dealt(s.clone(), "Strike", 3), 5, "3 past block -> 5");
    assert_eq!(dealt(s.clone(), "Strike", 5), 5, "1 past block -> 5");
    assert_eq!(dealt(s.clone(), "Strike", 6), 0, "all blocked: nothing to raise");
    assert_eq!(dealt(s.clone(), "Bash", 0), 8);
    let mut weak = s.clone();
    weak.player.powers.add(Power::Weak, 1);
    assert_eq!(dealt(weak, "Strike", 0), 5, "Weak Strike 4 -> 5");
    // The monster's Intangible caps first, then the raise: 1 -> 5.
    let mut ghost = s.clone();
    ghost.monsters[0].powers.add(Power::Intangible, 1);
    assert_eq!(dealt(ghost, "Strike", 0), 5);
    // Thorns is THORNS damage: not raised (Jaw Worm takes 3).
    let mut thorns = s.clone();
    thorns.player.powers.add(Power::Thorns, 3);
    let hp = thorns.monsters[0].hp;
    let mut rng = Rng::new(12);
    thorns.step(Action::EndTurn, &mut rng).unwrap();
    thorns.advance(&mut rng);
    assert_eq!(hp - thorns.monsters[0].hp, 3);
}

#[test]
fn dealt_after_block_is_the_attackers_not_the_targets() {
    // The player holding it doesn't raise the monster's hits on the player.
    let (s, _) = jaw_worm(&[1]);
    assert_eq!(taken(s, 8), 3);
}

#[test]
fn taken_after_block_absorbs_one_unblocked_hit_per_stack() {
    // BufferPower.java: amount > 0 -> 0 and lose a stack.
    let (s, ps) = jaw_worm(&[0]);
    let mut full = s.clone();
    full.player.block = 11;
    let hp = full.player.hp;
    let mut rng = Rng::new(12);
    full.step(Action::EndTurn, &mut rng).unwrap();
    full.advance(&mut rng);
    assert_eq!(full.player.hp, hp, "Chomp fully blocked");
    assert_eq!(full.player.powers.get(ps[0]), 1, "a blocked hit doesn't spend it");
    let mut open = s.clone();
    open.player.block = 0;
    let hp = open.player.hp;
    let mut rng = Rng::new(12);
    open.step(Action::EndTurn, &mut rng).unwrap();
    open.advance(&mut rng);
    assert_eq!(open.player.hp, hp, "Chomp absorbed");
    assert_eq!(open.player.powers.get(ps[0]), 0, "spent");
    // HP loss too (LoseHPAction calls `damage`): Bloodletting loses no HP
    // and still gives its energy; the next one loses 3.
    let mut s = s.clone();
    let hp = s.player.hp;
    play(&mut s, "Bloodletting");
    assert_eq!((s.player.hp, s.player.energy), (hp, 5), "3 energy, +2");
    play(&mut s, "Bloodletting");
    assert_eq!(s.player.hp, hp - 3);
}

#[test]
fn taken_after_block_on_a_monster() {
    let (b, ps) = bound();
    let mut s = fight(Encounter::JawWorm, &b);
    s.monsters[0].powers.add(ps[0], 1);
    assert_eq!(dealt(s.clone(), "Twin Strike", 0), 5, "the first hit absorbed, the second lands");
    s.monsters[0].powers.add(ps[0], 1);
    assert_eq!(dealt(s.clone(), "Twin Strike", 0), 0, "two stacks, two hits");
    // The attacker's pass runs first (Boot before the monster's Buffer).
    let mut lift = s.clone();
    lift.monsters[0].powers.add(ps[0], -1);
    lift.player.powers.add(ps[1], 1);
    lift.monsters[0].block = 3;
    let hp = lift.monsters[0].hp;
    play(&mut lift, "Strike");
    assert_eq!(lift.monsters[0].hp, hp);
    assert_eq!(lift.monsters[0].powers.get(ps[0]), 0);
}

#[test]
fn attacked_after_block_caps_small_unblocked_attacks() {
    // Torii.java `onAttacked`: unblocked NORMAL damage 2..5 -> 1.
    let (s, _) = jaw_worm(&[2]);
    assert_eq!(taken(s.clone(), 6), 1, "5 -> 1");
    assert_eq!(taken(s.clone(), 9), 1, "2 -> 1");
    assert_eq!(taken(s.clone(), 10), 1, "1 stays 1");
    assert_eq!(taken(s.clone(), 5), 6, "6 is above the range");
    assert_eq!(taken(s.clone(), 11), 0);
    // Not THORNS or HP_LOSS: Bloodletting's 3 stays 3.
    let mut s = s.clone();
    let hp = s.player.hp;
    play(&mut s, "Bloodletting");
    assert_eq!(s.player.hp, hp - 3);
}

#[test]
fn hp_loss_last_takes_one_off_every_loss() {
    // TungstenRod.java `onLoseHpLast`: amount > 0 -> amount - 1, every type.
    let (s, _) = jaw_worm(&[3]);
    assert_eq!(taken(s.clone(), 5), 5, "6 -> 5");
    assert_eq!(taken(s.clone(), 10), 0, "1 -> 0");
    assert_eq!(taken(s.clone(), 11), 0);
    let mut b = s.clone();
    let hp = b.player.hp;
    play(&mut b, "Bloodletting");
    assert_eq!(b.player.hp, hp - 2, "HP loss 3 -> 2");
    // With the attacked pass first: 5 -> 1 -> 0.
    let (s, _) = jaw_worm(&[2, 3]);
    assert_eq!(taken(s.clone(), 6), 0);
    // With Intangible: 11 -> 1 -> 0.
    let (mut s, _) = jaw_worm(&[3]);
    s.player.powers.add(Power::Intangible, 1);
    assert_eq!(taken(s, 0), 0);
}

#[test]
fn hp_loss_last_on_a_cards_own_hp_cost_run_23() {
    // Run 23, floor 12: Hemokinesis with Tungsten Rod at 63 HP; the game
    // took 1 (LoseHPAction -> damage -> onLoseHpLast), so 62.
    let (mut s, _) = jaw_worm(&[3]);
    s.player.hp = 63;
    play(&mut s, "Hemokinesis");
    assert_eq!(s.player.hp, 62);
    // Unheld, the card's 2.
    let (mut s, _) = jaw_worm(&[]);
    s.player.hp = 63;
    play(&mut s, "Hemokinesis");
    assert_eq!(s.player.hp, 61);
}

#[test]
fn rupture_counts_the_players_own_burn() {
    // RupturePower.wasHPLost: `info.owner == owner`. Burn's and Decay's
    // turn-end damage is the player's own (DamageInfo(player, 2, THORNS)),
    // so Rupture gains Strength; the Cultist doesn't attack on turn 1.
    // (Decay's is the same `PlainDamage` on `Me`.)
    let (b, _) = bound();
    for status in ["Burn"] {
        let c = CardId::from_name(status).unwrap();
        let mut s = fight(Encounter::Cultist, &b);
        s.player.powers.add(Power::Rupture, 1);
        s.hand.add(c, 1);
        assert_eq!(taken(s.clone(), 0), 2, "{status}");
        let mut rng = Rng::new(12);
        s.step(Action::EndTurn, &mut rng).unwrap();
        s.advance(&mut rng);
        assert_eq!(s.player.powers.get(Power::Strength), 1, "{status}: Rupture's Strength");
    }
}

#[test]
fn plain_damage_runs_only_the_every_kind_passes() {
    // Burn at turn end is THORNS damage to the player: the Cultist doesn't
    // attack on turn 1, so the turn's loss is Burn's 2.
    let (b, ps) = bound();
    let burn = |held: &[usize]| {
        let mut s = fight(Encounter::Cultist, &b);
        for &i in held {
            s.player.powers.add(ps[i], 1);
        }
        s.hand.add(CardId::from_name("Burn").unwrap(), 1);
        taken(s, 0)
    };
    assert_eq!(burn(&[]), 2);
    assert_eq!(burn(&[2]), 2, "Torii: not an attack");
    assert_eq!(burn(&[3]), 1, "Tungsten Rod: 2 -> 1");
    assert_eq!(burn(&[0]), 0, "Buffer: absorbed");
}

#[test]
fn load_errors() {
    let bad = |rep: &str| {
        let pack = format!(r#"{{"version": 2, "powers": [{{"id": "BadAfterBlock", "replacements": [{rep}]}}]}}"#);
        load_pack(&pack).unwrap_err()
    };
    assert!(bad(r#"{"event": "DealtAfterBlock", "action": {"AtLeast": 0}, "then": []}"#).contains("AtLeast"));
    assert!(bad(r#"{"event": "AttackedAfterBlock", "upTo": -1, "action": {"Cap": 1}, "then": []}"#).contains("upTo"));
    assert!(bad(r#"{"event": "AttackedAfterBlock", "upTo": "five", "action": {"Cap": 1}, "then": []}"#).contains("upTo"));
    assert!(bad(r#"{"event": "AfterBlock", "action": "Cancel", "then": []}"#).contains("event"));
}

#[test]
fn taken_after_block_on_a_pack_monsters_start_power() {
    // A pack monster starting with the power: `bind_monsters` binds it and
    // sets the binding's flag from a deck binding without it.
    load_pack(PACK).unwrap();
    let k = monster_kinds(&["gen:Buffered Dummy"]).unwrap()[0];
    let s = CombatState::new_vs(Character::Ironclad, &starter_deck(), &Binding::default(), 50, 80, &[k], &mut Rng::new(11));
    assert!(s.binding.has_after_block());
    let buffer = bind_power(&s.binding, "TestBuffer").unwrap().1;
    assert_eq!(s.monsters[0].powers.get(buffer), 1);
    let mut t = s.clone();
    t.monsters[0].block = 3;
    let hp = t.monsters[0].hp;
    play(&mut t, "Strike");
    assert_eq!((t.monsters[0].hp, t.monsters[0].powers.get(buffer)), (hp, 0), "3 past block absorbed");
    play(&mut t, "Strike");
    assert_eq!(t.monsters[0].hp, hp - 6, "the next lands");
    // With the player's DealtAfterBlock power bound and held: it runs first
    // (3 -> 5), then the monster's absorbs.
    let (b, lift) = bind_power(&s.binding, "TestLift").unwrap();
    let mut u = CombatState::new_vs(Character::Ironclad, &starter_deck(), &b, 50, 80, &[k], &mut Rng::new(11));
    u.player.powers.add(lift, 1);
    u.monsters[0].block = 3;
    play(&mut u, "Strike");
    assert_eq!((u.monsters[0].hp, u.monsters[0].powers.get(buffer)), (hp, 0));
    play(&mut u, "Strike");
    assert_eq!(u.monsters[0].hp, hp - 6);
    u.monsters[0].block = 3;
    play(&mut u, "Strike");
    assert_eq!(u.monsters[0].hp, hp - 11, "3 past block -> 5");
}
