//! Content packs carry every atom (docs/specs/pack-every-atom.md): every
//! official card and power written as a pack entry loads back unchanged,
//! and generated statics, replacements, attacks and picks play.

use sts_engine::cards::CardDef;
use sts_engine::hooks::{hooks, replacements, statics};
use sts_engine::registry::{bind, card_json, load_pack, power_json};
use sts_engine::search::{search, Evaluator, SearchConfig};
use sts_engine::*;

fn same_card(a: &CardDef, b: &CardDef) {
    assert_eq!(
        (a.cost(), a.ty, a.exhaust, a.ethereal, a.retain, a.x_cost(), a.innate, a.unplayable(), a.playable_if, a.tags),
        (b.cost(), b.ty, b.exhaust, b.ethereal, b.retain, b.x_cost(), b.innate, b.unplayable(), b.playable_if, b.tags),
        "{}",
        b.name
    );
    assert_eq!(a.effects, b.effects, "{}", b.name);
    assert_eq!(a.rows.len(), b.rows.len(), "{}", b.name);
    for (x, y) in a.rows.iter().zip(b.rows) {
        assert_eq!((x.condition, x.effects), (y.condition, y.effects), "{}", b.name);
    }
    assert_eq!(a.turn_end, b.turn_end, "{}", b.name);
}

#[test]
fn every_official_card_round_trips() {
    let mut n = 0;
    for c in CardId::all() {
        let id = format!("rt_card_{}", c.0);
        let entry = card_json(&id, c.def()).expect("no monster-only effect on a card");
        load_pack(&format!("{{\"version\": 2, \"cards\": [{entry}]}}")).unwrap_or_else(|e| panic!("{}: {e}\n{entry}", c.name()));
        let (ids, b) = bind(&[&format!("gen:{id}")]).unwrap();
        same_card(b.def(ids[0]), c.def());
        n += 1;
    }
    assert_eq!(n, CardId::all().count());
}

#[test]
fn every_official_power_round_trips() {
    let mut n = 0;
    for p in Power::ALL {
        if hooks(p).is_empty() && statics(p).is_empty() && replacements(p).is_empty() {
            continue;
        }
        let id = format!("rt_pow_{p:?}");
        let pw = power_json(&id, p).unwrap();
        let card = format!(
            "{{\"id\": \"rt_powcard_{p:?}\", \"cost\": 0, \"type\": \"Skill\", \"effects\": [{{\"Apply\": {{\"power\": \"{id}\", \"amount\": 1, \"target\": \"Me\"}}}}]}}"
        );
        // Version 2: the words `power_json` writes (turn-start-draw spec).
        load_pack(&format!("{{\"version\": 2, \"powers\": [{pw}], \"cards\": [{card}]}}")).unwrap_or_else(|e| panic!("{p:?}: {e}\n{pw}"));
        let (_, b) = bind(&[&format!("gen:rt_powcard_{p:?}")]).unwrap();
        let g = Power::GEN[0];
        assert_eq!(b.hooks(g), hooks(p), "{p:?}");
        assert_eq!(b.statics(g), statics(p), "{p:?}");
        assert_eq!(b.replacements(g), replacements(p), "{p:?}");
        assert_eq!(b.rules(g), b.rules(p), "{p:?}");
        n += 1;
    }
    assert!(n >= 15, "{n}");
}

/// A combat vs a Jaw Worm (100 HP, no block) with `deck` bound, `hand` in
/// hand, 3 energy.
fn bound_combat(deck: &[&str], hand: &[usize]) -> CombatState {
    let (ids, b) = bind(deck).unwrap();
    let mut s = CombatState::new_bound(Character::Ironclad, &ids, &b, 80, 80, Encounter::JawWorm, &mut Rng::new(1));
    s.hand = Hand::from_cards(&hand.iter().map(|&i| ids[i]).collect::<Vec<_>>());
    s.set_draw(Pile::default());
    s.set_discard(Pile::default());
    s.player.energy = 3;
    s.monsters[0].hp = 100;
    s.monsters[0].max_hp = 100;
    s.monsters[0].block = 0;
    s
}

const PACK: &str = r#"{"version": 1,
 "powers": [
  {"id": "pk_acc", "statics": [{"modifies": "DamageDealt", "stage": "Add", "amount": 1, "condition": {"CardInPlayTagged": "Shiv"}}]},
  {"id": "pk_int", "hooks": [{"trigger": "RoundEnd", "effects": [{"ReduceSelf": 1}]}],
   "replacements": [{"event": "DamageTaken", "action": {"Cap": 1}}, {"event": "HpLoss", "action": {"Cap": 1}}]}
 ],
 "cards": [
  {"id": "pk_acc_card", "cost": 1, "type": "Power", "effects": [{"Apply": {"power": "pk_acc", "amount": 4, "target": "Me"}}]},
  {"id": "pk_int_card", "cost": 1, "type": "Skill", "effects": [{"Apply": {"power": "pk_int", "amount": 2, "target": "Me"}}]},
  {"id": "pk_slam", "cost": 1, "type": "Attack", "tags": ["Strike"],
   "effects": [{"ScaledDamage": {"amount": {"base": 2, "k": 1, "of": "OwnBlock"}, "target": "Opponent"}}]},
  {"id": "pk_survive", "cost": 1, "type": "Skill", "retain": true,
   "effects": [{"Block": 4}, {"Pick": {"kind": "DiscardFromHand", "n": 1}}]}
 ]}"#;

#[test]
fn generated_static_and_replacement_apply() {
    load_pack(PACK).unwrap();
    // Accuracy-like: Shivs +4, a Strike not.
    let deck = ["gen:pk_acc_card", "Shiv", "Strike"];
    let acc = bind(&deck).unwrap().0[0];
    let mut s = bound_combat(&deck, &[0, 1, 2]);
    s.apply_action(Action::Play { card: acc, target: None }).unwrap();
    let gen = Power::GEN[0];
    assert_eq!(s.player.powers.get(gen), 4);
    s.apply_action(Action::Play { card: CardId::from_name("Shiv").unwrap(), target: Some(0) }).unwrap();
    assert_eq!(s.monsters[0].hp, 92);
    s.apply_action(Action::Play { card: CardId::from_name("Strike").unwrap(), target: Some(0) }).unwrap();
    assert_eq!(s.monsters[0].hp, 86);
    // Intangible-like: a Chomp (11) through it is 1.
    let card = bind(&["gen:pk_int_card"]).unwrap().0[0];
    let mut s = bound_combat(&["gen:pk_int_card"], &[0]);
    s.apply_action(Action::Play { card, target: None }).unwrap();
    let hp = s.player.hp;
    s.step(Action::EndTurn, &mut Rng::new(7)).unwrap();
    assert_eq!(s.player.hp, hp - 1);
    assert_eq!(s.player.powers.get(Power::GEN[0]), 1, "its RoundEnd countdown ran");
}

#[test]
fn generated_attack_and_pick_play() {
    load_pack(PACK).unwrap();
    let (ids, b) = bind(&["gen:pk_slam", "gen:pk_survive", "Strike"]).unwrap();
    let (slam, survive) = (ids[0], ids[1]);
    assert!(b.def(slam).is_strike());
    let mut s = bound_combat(&["gen:pk_slam", "gen:pk_survive", "Strike"], &[0, 1, 2]);
    s.player.block = 5;
    s.apply_action(Action::Play { card: slam, target: Some(0) }).unwrap();
    assert_eq!(s.monsters[0].hp, 93, "2 + 1 x block 5");
    s.apply_action(Action::Play { card: survive, target: None }).unwrap();
    assert_eq!(s.legal_actions(), vec![Action::Choose(CardId::from_name("Strike").unwrap())]);
    s.apply_action(Action::Choose(CardId::from_name("Strike").unwrap())).unwrap();
    assert_eq!((s.player.block, s.hand.len()), (9, 0));
}

const FIX_PACK: &str = r#"{"version": 1,
 "powers": [
  {"id": "fx_might", "can_go_negative": true, "statics": [{"modifies": "DamageDealt", "stage": "Add", "amount": 1}]},
  {"id": "fx_half_block", "debuff": true, "statics": [{"modifies": "BlockGained", "stage": "Multiply", "num": 1, "den": 2}]},
  {"id": "fx_double_tap", "hooks": [{"trigger": "OwnerPlaysCard", "condition": {"CardType": "Attack"}, "effects": ["ReplayCard", {"ReduceSelf": 1}]}]},
  {"id": "fx_soften", "replacements": [{"event": "DebuffApplied", "action": {"Cap": 1}}]},
  {"id": "fx_numb", "replacements": [{"event": "HpLoss", "action": {"Add": -5}}]},
  {"id": "fx_shrug", "replacements": [{"event": "DebuffApplied", "action": {"Add": -3}}]}
 ],
 "cards": [
  {"id": "fx_might_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "fx_might", "amount": -3, "target": "Opponent"}}]},
  {"id": "fx_half_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "fx_half_block", "amount": 1, "target": "Me"}}]},
  {"id": "fx_dt_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "fx_double_tap", "amount": 1, "target": "Me"}}]},
  {"id": "fx_soften_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "fx_soften", "amount": 1, "target": "Opponent"}}]},
  {"id": "fx_numb_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "fx_numb", "amount": 1, "target": "Me"}}]},
  {"id": "fx_shrug_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "fx_shrug", "amount": 1, "target": "Opponent"}}]},
  {"id": "fx_sap_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "Strength", "amount": -4, "target": "Opponent"}}]}
 ]}"#;

/// Plays the generated card `id` (cost 0) from a combat bound to `deck`
/// (which must start with it), with `hand` (names) in hand afterwards.
fn with_power(deck: &[&str], hand: &[&str]) -> CombatState {
    load_pack(FIX_PACK).unwrap();
    let ids = bind(deck).unwrap().0;
    let mut s = bound_combat(deck, &[0]);
    let target = if s.binding.def(ids[0]).targeted() { Some(0) } else { None };
    s.apply_action(Action::Play { card: ids[0], target }).unwrap();
    s.hand = Hand::from_cards(&hand.iter().map(|n| CardId::from_name(n).unwrap()).collect::<Vec<_>>());
    s.player.energy = 3;
    s
}

#[test]
fn negative_generated_add_static_counts() {
    let s = with_power(&["gen:fx_might_card"], &[]);
    let g = Power::GEN[0];
    assert_eq!(s.monsters[0].powers.get(g), -3);
    assert_eq!(s.attack_damage(sts_engine::state::Who::Monster(0), sts_engine::state::Who::Player, 11), 8);
    assert_eq!(s.attack_damage(sts_engine::state::Who::Monster(0), sts_engine::state::Who::Player, 11),
               s.interpret_attack_damage(sts_engine::state::Who::Monster(0), sts_engine::state::Who::Player, 11));
}

/// A pack power without `can_go_negative` floors at 0 on a negative
/// application, as an official one does (the game's `ReducePowerAction`):
/// nothing when not held, never below 0, no debuff (Artifact keeps its
/// stack) and no `OwnerApplied` hooks.
#[test]
fn a_pack_power_without_can_go_negative_floors_at_0() {
    load_pack(
        r#"{"version": 2, "powers": [
          {"id": "fl_plate", "statics": [{"modifies": "DamageDealt", "stage": "Add", "amount": 1}]},
          {"id": "fl_watch", "hooks": [{"trigger": "OwnerApplied", "effects": [{"Block": 1}]}]}],
         "cards": [
          {"id": "fl_minus", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "fl_plate", "amount": -2, "target": "Opponent"}}]},
          {"id": "fl_plus", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "fl_plate", "amount": 3, "target": "Opponent"}}]},
          {"id": "fl_watch_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "fl_watch", "amount": 1, "target": "Me"}}]}]}"#,
    )
    .unwrap();
    let deck = ["gen:fl_watch_card", "gen:fl_minus", "gen:fl_plus", "gen:fl_minus", "gen:fl_minus"];
    let (ids, b) = bind(&deck).unwrap();
    let pl = sts_engine::registry::bind_power(&b, "fl_plate").unwrap().1;
    assert!(!b.rules(pl).can_go_negative);
    let mut s = bound_combat(&deck, &[0, 1, 2]);
    s.monsters[0].powers.add(Power::Artifact, 1);
    s.apply_action(Action::Play { card: ids[0], target: None }).unwrap();
    s.player.block = 0;
    let plate = |s: &CombatState| s.monsters[0].powers.get(pl);
    s.apply_action(Action::Play { card: ids[1], target: Some(0) }).unwrap();
    assert_eq!((plate(&s), s.player.block), (0, 0), "not held: nothing, no OwnerApplied hook");
    assert_eq!(s.monsters[0].powers.get(Power::Artifact), 1, "not a debuff");
    s.apply_action(Action::Play { card: ids[2], target: Some(0) }).unwrap();
    assert_eq!((plate(&s), s.player.block), (3, 1), "a positive apply fires the hook");
    s.hand = Hand::from_cards(&[ids[1], ids[1]]);
    s.apply_action(Action::Play { card: ids[1], target: Some(0) }).unwrap();
    assert_eq!((plate(&s), s.player.block), (1, 1));
    s.apply_action(Action::Play { card: ids[1], target: Some(0) }).unwrap();
    assert_eq!((plate(&s), s.player.block), (0, 1), "floored at 0, not -1");
    assert_eq!(s.monsters[0].powers.get(Power::Artifact), 1);
}

#[test]
fn generated_block_multiply_rounds_once_with_frail() {
    let mut s = with_power(&["gen:fx_half_card"], &["Shrug It Off+"]);
    s.player.powers.add(Power::Frail, 1);
    s.player.block = 0;
    s.apply_action(Action::Play { card: CardId::from_name("Shrug It Off+").unwrap(), target: None }).unwrap();
    assert_eq!(s.player.block, 4, "11 x 3/4 x 1/2 rounded once");
}

#[test]
fn a_replayed_copys_grown_variant_is_dropped() {
    let mut s = with_power(&["gen:fx_dt_card"], &["Rampage"]);
    s.apply_action(Action::Play { card: CardId::from_name("Rampage").unwrap(), target: Some(0) }).unwrap();
    assert_eq!(s.monsters[0].hp, 100 - 8 - 13, "the copy plays at 13");
    // The original's 13 is in the discard pile; the copy's 18 went nowhere.
    assert_eq!(sts_engine::codec::changed_ranks(&s).len(), 1);
}

#[test]
fn debuff_replacement_acts_on_the_size() {
    load_pack(FIX_PACK).unwrap();
    let deck = ["gen:fx_shrug_card", "gen:fx_sap_card", "Bash"];
    let ids = bind(&deck).unwrap().0;
    let mut s = bound_combat(&deck, &[0, 1, 2]);
    for &card in &ids[..2] {
        let target = if s.binding.def(card).targeted() { Some(0) } else { None };
        s.apply_action(Action::Play { card, target }).unwrap();
    }
    assert_eq!(s.monsters[0].powers.get(Power::Strength), -1, "a Strength loss of 4 softened by 3");
    s.apply_action(Action::Play { card: ids[2], target: Some(0) }).unwrap();
    assert_eq!(s.monsters[0].powers.get(Power::Vulnerable), 0, "Bash's 2 - 3 cancels (no -1 left behind)");
    assert_eq!(s.monsters[0].powers, {
        let mut p = s.monsters[0].powers;
        p.clear_round_flags();
        p
    }, "no round flag on a power it doesn't hold");
}

#[test]
fn debuff_replacement_changes_the_amount() {
    let mut s = with_power(&["gen:fx_soften_card"], &["Bash"]);
    s.apply_action(Action::Play { card: CardId::from_name("Bash").unwrap(), target: Some(0) }).unwrap();
    assert_eq!(s.monsters[0].powers.get(Power::Vulnerable), 1, "Bash's 2 capped at 1");
}

#[test]
fn a_replaced_hp_loss_never_heals() {
    let mut s = with_power(&["gen:fx_numb_card"], &["Bloodletting"]);
    let hp = s.player.hp;
    s.apply_action(Action::Play { card: CardId::from_name("Bloodletting").unwrap(), target: None }).unwrap();
    assert_eq!(s.player.hp, hp, "3 - 5 is 0, not a heal");
}

/// The power fields load into `PowerRules` for a pack power as for an
/// official one, and a hook's `hp_loss_source` into the hook.
#[test]
fn pack_power_fields_load() {
    load_pack(
        r#"{"version": 2, "powers": [{"id": "fx_fields", "debuff": false, "debuff_if_negative": true,
          "skips_first_round": {"from_monster": true, "on_monster": true},
          "hooks": [{"trigger": "OwnerTurnStart", "hp_loss_source": "Any", "effects": [{"LoseHp": 1}]}]}],
         "cards": [{"id": "fx_fields_card", "cost": 0, "type": "Skill", "effects": [{"Apply": {"power": "fx_fields", "amount": 1, "target": "Me"}}]}]}"#,
    )
    .unwrap();
    let (_, b) = bind(&["gen:fx_fields_card"]).unwrap();
    let g = Power::GEN[0];
    let r = b.rules(g);
    assert!(r.debuff_if_negative && !r.debuff && r.skips_first_round.from_monster && r.skips_first_round.on_monster);
    assert!(b.is_debuff(g, -1) && !b.is_debuff(g, 1));
    assert_eq!(b.hooks(g)[0].hp_loss, sts_engine::hooks::HpLossFrom::Any);
    // Official rows read the same way: Poison's loss is `Any`, Split Hits splits.
    assert_eq!(hooks(Power::Poison)[0].hp_loss, sts_engine::hooks::HpLossFrom::Any);
    assert_eq!(b.rules(Power::SplitHits).attack_shape, Some(2));
    assert!(b.rules(Power::Weak).skips_first_round.from_monster && b.rules(Power::Ritual).skips_first_round.on_monster);
    assert!(b.is_debuff(Power::Strength, -1) && !b.is_debuff(Power::Strength, 1));
    // The engine's amount can go negative: Strength, Dexterity. The game's canGoNegative
    // also has Focus (no engine power) and Wraith Form (stored with the opposite sign).
    for p in Power::ALL {
        assert_eq!(b.rules(p).can_go_negative, matches!(p, Power::Strength | Power::Dexterity), "{p:?}");
    }
}

#[test]
fn packs_refuse_what_play_cant_run() {
    for (what, pack) in [
        ("a pick in a hook", r#"{"version": 1, "powers": [{"id": "bad1", "hooks": [{"trigger": "OwnerTurnEnd", "effects": [{"Pick": {"kind": "DiscardFromHand", "n": 1}}]}]}]}"#),
        ("random hits at turn end", r#"{"version": 1, "cards": [{"id": "bad2", "cost": 0, "type": "Status", "turn_end": [{"RandomDamage": {"amount": 1, "hits": 2}}]}]}"#),
        ("a zero den", r#"{"version": 1, "powers": [{"id": "bad3", "statics": [{"modifies": "DamageDealt", "stage": "Multiply", "num": 1, "den": 0}]}]}"#),
        ("a pack attack_shape", r#"{"version": 2, "powers": [{"id": "bad4", "attack_shape": {"split": 2}}]}"#),
        ("hp_loss_source without LoseHp", r#"{"version": 2, "powers": [{"id": "bad5", "hooks": [{"trigger": "OwnerTurnEnd", "hp_loss_source": "Any", "effects": [{"Block": 1}]}]}]}"#),
        ("a skips_first_round typo", r#"{"version": 2, "powers": [{"id": "bad6", "skips_first_round": {"from_monsters": true}}]}"#),
    ] {
        assert!(load_pack(pack).is_err(), "{what} was accepted");
    }
}

/// Asserts it is never asked to score a state paused at a pick.
struct NoPickLeaves;

impl Evaluator for NoPickLeaves {
    fn evaluate(&mut self, states: &[CombatState]) -> Vec<f32> {
        assert!(states.iter().all(|s| s.pick().is_none()), "a pick became a leaf");
        vec![0.0; states.len()]
    }
}

/// Searches `s` with a 1,000-node cap; returns the node count after
/// checking the chosen action is legal.
fn capped_nodes(s: &CombatState, what: &str) -> usize {
    let r = search(s, &mut NoPickLeaves, &SearchConfig { max_nodes: 1_000, ..SearchConfig::default() });
    eprintln!("{what}: {} nodes, {} leaves, {} cuts", r.nodes, r.leaves, r.cuts);
    assert!(s.is_legal(r.action));
    r.nodes
}

const D1_DECK: [&str; 10] = ["Strike", "Defend", "Bash", "Anger", "Clash", "Cleave", "Flex", "Inflame", "Pommel Strike", "Twin Strike"];

/// The pick card `card` and ten distinct official cards.
fn d1_deck(card: &str) -> Vec<String> {
    std::iter::once(format!("gen:{card}")).chain(D1_DECK.iter().map(|c| c.to_string())).collect()
}

#[test]
fn a_long_pick_stays_within_the_node_cap() {
    // Past the cap a pick follows its first option only (draw-knowledge
    // item 4), so 10*9*8*7*6 orders onto the known top stay unexplored.
    load_pack(r#"{"version": 1, "cards": [{"id": "d1_top5", "cost": 0, "type": "Skill", "effects": [{"Pick": {"kind": "DiscardToTop", "n": 5}}]}]}"#).unwrap();
    let deck = d1_deck("d1_top5");
    let deck: Vec<&str> = deck.iter().map(|c| c.as_str()).collect();
    let mut s = bound_combat(&deck, &[0]);
    let (ids, _) = bind(&deck).unwrap();
    s.set_discard(Pile::from_cards(&ids[1..]));
    assert!(capped_nodes(&s, "DiscardToTop 5 of 10") <= 2_000);
}

#[test]
fn a_long_hand_to_top_pick_stays_within_the_node_cap() {
    load_pack(r#"{"version": 1, "cards": [{"id": "d1_hand5", "cost": 0, "type": "Skill", "effects": [{"Pick": {"kind": "HandToTop", "n": 5}}]}]}"#).unwrap();
    let deck = d1_deck("d1_hand5");
    let deck: Vec<&str> = deck.iter().map(|c| c.as_str()).collect();
    // The pick card and 9 distinct cards: a full hand.
    let s = bound_combat(&deck, &(0..10).collect::<Vec<_>>());
    assert!(capped_nodes(&s, "HandToTop 5 of 9") <= 2_000);
}

#[test]
fn an_any_number_pick_stays_within_the_node_cap() {
    load_pack(r#"{"version": 1, "cards": [{"id": "d1_any", "cost": 0, "type": "Skill", "effects": [{"Pick": {"kind": "DiscardToTop", "n": 99, "exact": false}}]}]}"#).unwrap();
    let deck = d1_deck("d1_any");
    let deck: Vec<&str> = deck.iter().map(|c| c.as_str()).collect();
    let mut s = bound_combat(&deck, &[0]);
    let (ids, _) = bind(&deck).unwrap();
    s.set_discard(Pile::from_cards(&ids[1..8]));
    assert!(capped_nodes(&s, "DiscardToTop any of 7") <= 2_000);
}
