//! State features for evaluators. Everything is described through effect
//! primitives except, in `ids` mode, the cards and hook powers themselves.
//!
//! A batch of states encodes as:
//! - `player`   [B, P]
//! - `monsters` [B, 5, M] (zeros for empty or dead slots)
//! - `cards`    [N, C]: one row per distinct card in a pile, with
//!   `card_count` [N], `card_pile` [N] (index into `PILES`, or into the
//!   net's own pile list, see `Encoder::set_layout`) and
//!   `card_state` [N] (index into the batch). Sum-pooling rows × count per
//!   (state, pile) gives an order-free pile encoding of any size.
//! - `rows`     [R, D] (effects mode only; empty in ids mode): hook rows,
//!   each a trigger, a condition and an effect vector. `row_card` [R] is the
//!   card entry (index into `cards`) a row belongs to, or -1; `row_entity`
//!   [R] is `state * ENTITIES + entity` (0 = player, 1 + slot = monster) for
//!   a row of a power on that entity, or -1; `row_state` [R] is the state.
//!   Rows pool into their card or entity (nested Deep Sets).
//!
//! A card's rows: one per effect row of the card (trigger "played by its
//! owner", the row's condition), then, for each hook power the card applies,
//! that power's hooks scaled by the amount and marked as granted to the
//! card's user ("me") or to its opponent. An entity's rows: the hooks of each
//! hook power it has, scaled by its stacks ("own"); for a monster also the
//! hooks of hook powers its intent applies ("me" / "opponent").
//!
//! Powers: in effects mode the built-in modifiers (Strength, Dexterity,
//! Vulnerable, Weak, Frail, Artifact) get one dimension each plus `unknown`,
//! and hook powers are rows. In ids mode every power is a dimension plus
//! `unknown`, and there are no rows.
//!
//! Vocabularies (`known_*`) fix which cards, powers, triggers, conditions and
//! effect scalars get a dimension, in the order given, so a net trained on
//! one vocabulary still encodes content added later: unknown card ids,
//! powers, triggers and conditions land in their `unknown` slot and unknown
//! effect scalars are dropped.
//!
//! Lookahead (off by default, docs/specs/monster-lookahead.md): each
//! monster also gets `LOOK_SCALARS` and the expected effect vectors of its
//! next and second-next move (`next1_*`, `next2_*`), from its AI rolled
//! forward over its move history (`agent::lookahead`), after the `intent_*`
//! block.
//!
//! Rates (off by default, docs/specs/rate-features.md): the player and each
//! monster also get the heuristic's per-turn hook sums (`agent::hook_rates`)
//! as `rate_<field>`, and `rate_strength_x_turns` / `rate_block_x_turns`
//! (each times the heuristic's rounds-left estimate); the player then gets
//! `turns_left_est` itself. In effects mode each card also gets
//! `grant_rate_<field>`: the rates of the hook powers it applies to its user,
//! at the applied amount.
//!
//! Start HP (off by default, docs/specs/start-hp.md): the player path ends
//! with `start_hp`, the HP the combat started at, so a net can tell HP lost
//! from HP it never had (the score counts HP lost from the start).

use std::sync::atomic::{AtomicBool, Ordering};

use sts_engine::agent::{hook_rates, intent_damage, intent_known, lookahead, HookRates};
use sts_engine::cards::{CardDef, CardId, CardType, Tag, NUM_CARDS};
use sts_engine::chance::ChanceEvent;
use sts_engine::effects::{Amount, Effect, PickKind, PileKind, Quantity, Target};
use sts_engine::heuristic::turns_left_estimate;
use sts_engine::hooks::{
    hooks, Condition, Hook, HpLossFrom, Modifies, Replace, Replaced, Replacement, Side, Static, StaticCondition, StaticStage, Trigger,
};
use sts_engine::monsters::NO_MOVE;
use sts_engine::powers::{Power, Powers, NUM_POWERS};
use sts_engine::registry::{self, Binding};
use sts_engine::relics::Relics;
use sts_engine::state::{attack_shape, CombatState, Pile, PileRef, Stage, Who, MAX_MONSTERS};
use sts_engine::threshold::threshold;

/// Pile names in the head's slot order (a net saves its own list).
pub const PILES: [&str; 7] = ["hand", "draw", "discard", "exhaust", "playing", "next_draw", "known_later"];
/// A pile a net doesn't list is written as its parent (spec 7 adds next
/// draw and known later → draw).
pub const PILE_PARENTS: [(&str, &str); 2] = [("next_draw", "draw"), ("known_later", "draw")];
/// Row kinds the encoder writes: card effect rows, hook rows and granted
/// rows are all `triggered`; a monster's HP threshold is `threshold`, a
/// card's held-at-turn-end effects `held` (threshold-and-held-rows spec;
/// specs 4, 5, 9 add `static`, `replacement`, `pattern`; card-rules adds
/// `rule`; relic-entity adds `relic`; potions adds `potion`).
pub const ROW_KINDS: [&str; 10] = ["triggered", "threshold", "held", "static", "countdown", "replacement", "pattern", "rule", "relic", "potion"];
const KIND_THRESHOLD: u8 = 1;
const KIND_HELD: u8 = 2;
/// A power's static modifier rows (static-modifiers spec).
const KIND_STATIC: u8 = 3;
/// Hook rows whose trigger is `RoundEnd` (the debuff countdowns).
const KIND_COUNTDOWN: u8 = 4;
/// A power's replacement rows (replacement-hooks spec).
const KIND_REPLACEMENT: u8 = 5;
/// A monster's possible next moves with their probabilities, from its
/// pattern (monster-patterns spec).
const KIND_PATTERN: u8 = 6;
/// A rule a power sets on its owner's cards: forbids, caps the cost of, or
/// exhausts cards of a type (docs/specs/card-rules.md).
const KIND_RULE: u8 = 7;
/// A held relic's hooks (docs/specs/relic-entity.md): the power row format,
/// `grant_relic`, the relic's counter and its counter effects in the
/// `RELIC_COLS`.
const KIND_RELIC: u8 = 8;
/// A held potion's effects (docs/specs/potions.md): trigger `Potion(Use)`,
/// the effects at their effective amounts, `potion_potency`.
const KIND_POTION: u8 = 9;
/// The row kinds written by default: the rest (static, countdown,
/// replacement, pattern) are opt-in (`with_extra_rows`), like lookahead and
/// rates, since they double a batch's row data (decisions "Series row
/// kinds are opt-in").
const BASE_KINDS: usize = 3;
/// The opt-in kinds, by name.
pub const EXTRA_KINDS: [&str; 7] = ["static", "countdown", "replacement", "pattern", "rule", "relic", "potion"];
/// A pattern row's "trigger" column.
pub const PATTERN_TRIGGER: &str = "Pattern(Next)";
/// A potion row's "trigger" column (using it), and Sacred Bark's relic row's.
pub const POTION_TRIGGER: &str = "Potion(Use)";
/// Entities per state in `row_entity`: the player, then the monster slots.
pub const ENTITIES: usize = 1 + MAX_MONSTERS;
/// Test only (`Encoder::inject_test`): a row kind every row is also written
/// as, and a pile (parent: draw) the draw pile's cards go to instead, so the
/// gather's row-kind and pile handling can be checked before a spec adds
/// real ones.
pub const TEST_KIND: &str = "test";
/// The card path's last columns (draw-knowledge spec item 3): a known
/// card's place in the draw pile (1 = drawn next), and a floater's cards
/// certainly above it. A layout without them gets merged entries.
const POSITION_COLS: [&str; 2] = ["draw_position", "draw_above"];
pub const TEST_PILE: &str = "test";

/// A net's own layout (the contract's gather): per path (player, monster,
/// card, row) the net's column names and the encoder column each reads
/// (`None`: the encoder has no such column, it reads 0); per encoder row
/// kind whether it is written; per encoder pile the net's slot.
#[derive(Clone, Debug)]
struct Gather {
    names: [Vec<String>; 4],
    /// Per path, the net's columns as runs: (first encoder column or `None`
    /// for zeros, length), so a gather copies slices.
    runs: [Vec<(Option<usize>, usize)>; 4],
    keep_kind: Vec<bool>,
    pile_slot: Vec<i64>,
    n_piles: usize,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CardRepr {
    Effects,
    Ids,
}

pub fn power_name(p: Power) -> String {
    format!("{p:?}")
}

/// Set once an ids-mode encoder has met generated content (warned once).
static IDS_WARNED: AtomicBool = AtomicBool::new(false);

/// A power with a hook other than a `RoundEnd` countdown, not a built-in
/// modifier: its hooks are `triggered` rows (effects mode).
pub fn is_hook_power(p: Power) -> bool {
    !is_modifier(p) && hooks(p).iter().any(|h| h.trigger != Trigger::RoundEnd)
}

/// The powers with a dimension in effects mode (a named list, so a modifier
/// that later gains hooks keeps its dimension; ids mode keeps every power).
pub const MODIFIER_POWERS: [Power; 8] = [
    Power::Strength,
    Power::Dexterity,
    Power::Vulnerable,
    Power::Weak,
    Power::Frail,
    Power::Artifact,
    Power::DamageDown,
    Power::SplitHits,
];

pub fn is_modifier(p: Power) -> bool {
    MODIFIER_POWERS.contains(&p)
}

/// Effect-primitive dimensions shared by cards, intents and hook rows.
pub const EFFECT_SCALARS: [&str; 58] = [
    "damage_single",
    "hits_single",
    "damage_all",
    "hits_all",
    "damage_random",
    "hits_random",
    "damage_from_block",
    "strength_mult_base",
    "strength_mult",
    "per_strike_base",
    "per_strike",
    "rolled_attack",
    "block",
    "draw",
    "energy",
    "lose_hp",
    "add_draw",
    "add_discard",
    "added_damage",
    "added_block",
    "added_unplayable",
    "split",
    "escape",
    "add_hand",
    "damage_plain",
    "remove_self",
    "reduce_self",
    // Plain damage to the effect's owner (Burn held at turn end).
    "damage_plain_self",
    // Amount expressions (`ScaledDamage`): the total damage resolved against
    // the state (card path only), the total as `base + k × quantity`, a
    // one-hot of the quantity, and whether it hits every enemy.
    "expr_value",
    "expr_base",
    "expr_k",
    "expr_q_block",
    "expr_q_strength",
    "expr_q_energy",
    "expr_q_strike",
    "expr_all",
    // A static modifier row: its add (amount × stacks) or its multiply's
    // factor − 1 (static-modifiers spec).
    "static_add",
    "static_mult",
    // A replacement row: cancels, caps at, adds, multiplies by (factor − 1),
    // and its power's stacks (replacement-hooks spec).
    "replace_cancel",
    "replace_cap",
    "replace_add",
    "replace_mult",
    "replace_stacks",
    // Decision points: a pick of n cards (discard from hand, return from the
    // discard pile) and a replay of the card in play (decision-points spec).
    "pick_discard",
    "pick_return",
    "replay",
    // Known top: a pick from the discard pile onto the draw pile's top.
    "pick_to_top",
    // Per-copy overrides: the copy's own damage grows by this (Rampage).
    "grow_damage",
    // Exhausting other cards (exhaust-cards spec): a pick from hand to the
    // exhaust pile and back, the whole hand (or its non-Attacks), one at
    // random, block per card counted, and a count of hand cards in an
    // amount expression.
    "pick_exhaust",
    "pick_return_exhaust",
    "exhaust_hand",
    "exhaust_random",
    "block_per_card",
    "expr_q_hand",
    // Amounts that read a quantity (quantity-amounts spec): the `k` of a
    // `BlockOf` (its `base` counts in `block`) and of an `ApplyOf` (its
    // `base` counts in its power's column).
    "block_of_k",
    "apply_of_k",
    // Upgrades in combat (card-upgrades spec): a pick of n cards in hand to
    // upgrade, and every card in hand upgraded (Armaments, Armaments+).
    "pick_upgrade",
    "upgrade_hand",
];
const APPLY_TARGETS: [&str; 3] = ["opponent", "all", "me"];
/// Whose a row is: the card's own effect or the entity's own power, or a
/// hook power the card / intent grants to its user or to its opponent.
pub const GRANTS: [&str; 4] = ["own", "me", "opponent", "relic"];
const OWN: usize = 0;
const GRANT_ME: usize = 1;
const GRANT_OPPONENT: usize = 2;
/// A held relic's own hook (relic-entity spec).
const GRANT_RELIC: usize = 3;
/// Row-only columns after the grants (relic-entity spec): a relic row's
/// counter now, whether its effects set the counter and to what, and what
/// they add to it. Zero on every other row; not effect scalars, so card
/// and intent vectors keep their width.
pub const RELIC_COLS: [&str; 4] = ["relic_counter", "counter_set", "counter_set_to", "counter_add"];
/// Row-only column after `RELIC_COLS` (potions spec): a potion row's
/// effective potency, Sacred Bark's relic row's `potion_potency`.
pub const POTION_COLS: [&str; 1] = ["potion_potency"];
/// Row-only column after `POTION_COLS` (after-block spec): a replacement
/// row's `AtLeast` value (The Boot's 5).
pub const REPLACE_COLS: [&str; 1] = ["replace_at_least"];
/// Every row-only column.
const ROW_ONLY: usize = RELIC_COLS.len() + POTION_COLS.len() + REPLACE_COLS.len();

fn scalar_index(name: &str) -> usize {
    EFFECT_SCALARS.iter().position(|&s| s == name).expect("effect dim")
}

pub const TRIGGERS: [Trigger; 21] = [
    Trigger::OwnerTurnStart,
    Trigger::OwnerTurnEnd,
    Trigger::CardPlayed { by: Side::Owner },
    Trigger::CardPlayed { by: Side::Opponent },
    Trigger::OwnerLostHp { from: HpLossFrom::Attack },
    Trigger::OwnerLostHp { from: HpLossFrom::Card },
    Trigger::OwnerLostHp { from: HpLossFrom::Any },
    Trigger::OwnerDied,
    Trigger::RoundEnd,
    Trigger::OwnerAttacked,
    Trigger::OwnerPlaysCard,
    Trigger::OwnerAttackHit,
    Trigger::CardExhausted,
    Trigger::CardDrawn,
    Trigger::OwnerBloodied,
    Trigger::OwnerUnbloodied,
    Trigger::CombatStartPreDraw,
    Trigger::CombatStart,
    Trigger::OpponentDied,
    Trigger::CombatWon,
    // Champion Belt (docs/specs/act1-singles.md).
    Trigger::OwnerApplied,
];

/// A replacement row's "trigger" column: the event it replaces.
pub const REPLACE_TRIGGERS: [&str; 7] = [
    "Replace(DamageTaken)",
    "Replace(HpLoss)",
    "Replace(DebuffApplied)",
    // The after-block passes (after-block spec).
    "Replace(DealtAfterBlock)",
    "Replace(TakenAfterBlock)",
    "Replace(AttackedAfterBlock)",
    "Replace(HpLossLast)",
];

fn replace_trigger(e: Replaced) -> &'static str {
    match e {
        Replaced::DamageTaken => REPLACE_TRIGGERS[0],
        Replaced::HpLoss => REPLACE_TRIGGERS[1],
        Replaced::DebuffApplied => REPLACE_TRIGGERS[2],
        Replaced::DealtAfterBlock => REPLACE_TRIGGERS[3],
        Replaced::TakenAfterBlock => REPLACE_TRIGGERS[4],
        Replaced::AttackedAfterBlock => REPLACE_TRIGGERS[5],
        Replaced::HpLossLast => REPLACE_TRIGGERS[6],
        Replaced::Draw => DRAW_REPLACE_TRIGGER,
    }
}

/// A static row's "trigger" column: the number it modifies.
pub const STATIC_TRIGGERS: [&str; 3] = ["Static(DamageDealt)", "Static(DamageTaken)", "Static(BlockGained)"];

fn static_trigger(m: Modifies) -> &'static str {
    match m {
        Modifies::DamageDealt => STATIC_TRIGGERS[0],
        Modifies::DamageTaken => STATIC_TRIGGERS[1],
        Modifies::BlockGained => STATIC_TRIGGERS[2],
    }
}

/// A rule row's "trigger" column: which rule (docs/specs/card-rules.md);
/// its condition column is the card type it acts on.
pub const RULE_TRIGGERS: [&str; 4] = ["Rule(Forbids)", "Rule(SetsCost)", "Rule(ExhaustsPlayed)", "Rule(PlayableIf)"];
/// The rule letting unplayable cards of a type be played (Blue Candle,
/// Medical Kit; docs/specs/blocked-relics.md step 6): last in the default
/// vocabulary, so earlier columns keep their places.
pub const PLAYS_UNPLAYABLE_TRIGGER: &str = "Rule(PlaysUnplayable)";
/// The replaced draw (No Draw; docs/specs/ironclad-last-four.md step 1):
/// after it, so earlier columns keep their places.
pub const DRAW_REPLACE_TRIGGER: &str = "Replace(Draw)";
/// The block-gain hook (Juggernaut; docs/specs/ironclad-last-four.md step
/// 4): after it, so earlier columns keep their places.
pub const GAINED_BLOCK_TRIGGER: &str = "OwnerGainedBlock";

/// The default trigger vocabulary: every hook trigger, then the static
/// rows' modified numbers, the replaced events, the pattern, the rules and
/// a potion's use.
pub fn default_trigger_names() -> Vec<String> {
    TRIGGERS
        .iter()
        .map(|&t| trigger_name(t))
        .chain(STATIC_TRIGGERS.iter().map(|s| s.to_string()))
        .chain(REPLACE_TRIGGERS.iter().map(|s| s.to_string()))
        .chain(std::iter::once(PATTERN_TRIGGER.to_string()))
        .chain(RULE_TRIGGERS.iter().map(|s| s.to_string()))
        .chain(std::iter::once(POTION_TRIGGER.to_string()))
        .chain(std::iter::once(PLAYS_UNPLAYABLE_TRIGGER.to_string()))
        .chain(std::iter::once(DRAW_REPLACE_TRIGGER.to_string()))
        .chain(std::iter::once(GAINED_BLOCK_TRIGGER.to_string()))
        .collect()
}

/// A hook trigger's column name. Both turn starts write the one
/// `OwnerTurnStart` column (docs/specs/turn-start-draw.md: one net column).
pub fn trigger_name(t: Trigger) -> String {
    match t {
        Trigger::OwnerTurnStartPostDraw => "OwnerTurnStart".to_string(),
        Trigger::CardPlayed { by } => format!("CardPlayed({by:?})"),
        Trigger::OwnerLostHp { from } => format!("OwnerLostHp({from:?})"),
        t => format!("{t:?}"),
    }
}

/// Condition vocabulary: categorical parameters are part of the name
/// (`CardType(Attack)`, `TargetHas(Vulnerable)`); a numeric one goes in the
/// row's `condition_param` (`CardsPlayedThisTurnBelow`).
pub fn condition_names() -> Vec<String> {
    let mut v = vec!["Always".to_string()];
    for t in ["Attack", "Skill", "Power", "Status"] {
        v.push(format!("CardType({t})"));
    }
    v.push("TargetIntendsAttack".into());
    v.extend(Power::ALL.iter().map(|&p| format!("TargetHas({})", power_name(p))));
    v.push("CardsPlayedThisTurnBelow".into());
    // Threshold rows: fires once the owner has lost `condition_param` more HP.
    v.push(HP_LOST_REACHES.into());
    // Static rows' conditions.
    v.extend(Tag::ALL.iter().map(|t| format!("CardInPlayTagged({t:?})")));
    v.push("OwnerHpAtMostHalf".into());
    // A card's play condition (card-rules spec: Clash).
    for t in ["Attack", "Skill", "Power", "Status"] {
        v.push(format!("HandAll({t})"));
    }
    // A relic's counter test (relic-entity spec), its value in `condition_param`.
    v.push("CounterIs".into());
    // The owner's block (fight-vocabulary spec: Orichalcum), in `condition_param`.
    v.push("OwnerBlockIs".into());
    // A `DebuffApplied` replacement's filter: the power being applied
    // (fight-vocabulary spec: Ginger, Turnip).
    v.extend(Power::ALL.iter().map(|&p| format!("Applying({})", power_name(p))));
    // A replacement row's range (after-block spec: Torii's `upTo` 5), its
    // value in `condition_param`.
    v.push("AmountAtMost".into());
    // Colorless cards (docs/specs/colorless-cards.md step 2).
    for t in ["Attack", "Skill", "Power", "Status"] {
        v.push(format!("HandNone({t})"));
    }
    v.extend(Power::ALL.iter().map(|&p| format!("TargetLacks({})", power_name(p))));
    v.push("ApplyingDebuff".into());
    // A static row's held power (docs/specs/blocked-relics.md step 2).
    for side in ["Owner", "Opponent"] {
        v.extend(Power::ALL.iter().map(|&p| format!("{side}Holds({})", power_name(p))));
    }
    // The Curse type (docs/specs/blocked-relics.md step 6: Blue Candle's
    // hook and rule), last so earlier columns keep their places.
    v.push("CardType(Curse)".into());
    // The on-kill test (Feed), last for the same reason.
    v.push("TargetDied".into());
    // Pocketwatch's tests, last for the same reason: a relic's counter at
    // most `condition_param`, and not the combat's first turn.
    v.push("CounterAtMost".into());
    v.push("NotFirstTurn".into());
    v
}

fn static_condition_name(c: StaticCondition) -> String {
    match c {
        StaticCondition::Always => "Always".into(),
        StaticCondition::CardInPlayTagged(t) => format!("CardInPlayTagged({t:?})"),
        StaticCondition::OwnerHpAtMostHalf => "OwnerHpAtMostHalf".into(),
        StaticCondition::Holds { side, power } => format!("{side:?}Holds({})", power_name(power)),
    }
}

const HP_LOST_REACHES: &str = "HpLostReaches";

fn condition_key(c: Condition) -> (String, f32) {
    match c {
        Condition::Always => ("Always".into(), 0.0),
        Condition::CardType(t) => (format!("CardType({t:?})"), 0.0),
        Condition::TargetIntendsAttack => ("TargetIntendsAttack".into(), 0.0),
        Condition::TargetHas(p) => (format!("TargetHas({})", power_name(p)), 0.0),
        Condition::CardsPlayedThisTurnBelow(n) => ("CardsPlayedThisTurnBelow".into(), n as f32),
        Condition::HandAll(t) => (format!("HandAll({t:?})"), 0.0),
        Condition::OwnerHpAtMostHalf => ("OwnerHpAtMostHalf".into(), 0.0),
        // A relic's counter test (relic-entity spec).
        Condition::CounterIs(n) => ("CounterIs".into(), n as f32),
        Condition::OwnerBlockIs(n) => ("OwnerBlockIs".into(), n as f32),
        // The replacement filter's column (fight-vocabulary spec).
        Condition::Applying(p) => (format!("Applying({})", power_name(p)), 0.0),
        Condition::HandNone(t) => (format!("HandNone({t:?})"), 0.0),
        Condition::TargetLacks(p) => (format!("TargetLacks({})", power_name(p)), 0.0),
        Condition::ApplyingDebuff => ("ApplyingDebuff".into(), 0.0),
        Condition::TargetDied => ("TargetDied".into(), 0.0),
        Condition::CounterAtMost(n) => ("CounterAtMost".into(), n as f32),
        Condition::NotFirstTurn => ("NotFirstTurn".into(), 0.0),
    }
}

/// Card columns; `only_attacks_in_hand` (index `LEGACY_CLASH`) only for a
/// net whose layout names it (card-rules spec: a legacy read of Clash's
/// `playable_if`).
const CARD_PROPS: [&str; 14] = [
    "cost",
    "type_attack",
    "type_skill",
    "type_power",
    "type_status",
    "unplayable",
    "exhaust",
    "ethereal",
    "targeted",
    "only_attacks_in_hand",
    "is_strike",
    "x_cost",
    "retain",
    "cost_less_per_hp_loss",
];
const LEGACY_CLASH: usize = 9;

const PLAYER_SCALARS: [&str; 26] = [
    "hp",
    "max_hp",
    "block",
    "energy",
    "turn",
    "hand_size",
    "draw_size",
    "discard_size",
    "exhaust_size",
    "awaiting_action",
    "won",
    "lost",
    "pending_draw",
    "pending_monster_move",
    "pending_random_hit",
    // The pick the card in play waits on (decision-points spec): its kind
    // as a one-hot, and the picks left.
    "pick_discard_from_hand",
    "pick_return_from_discard",
    "pick_left",
    "pick_discard_to_top",
    // Known top (known-top spec): next turn's draw size and how many cards
    // on top are known. `next_draw_size` is the least the next turn's start
    // draws (`CombatState::next_draw`; the name kept so older nets read it),
    // `next_draw_max` the most (draw-knowledge spec item 3).
    "next_draw_size",
    "known_top",
    "next_draw_max",
    // Exhausting other cards (exhaust-cards spec): the two new pick kinds
    // and the random-exhaust chance event.
    "pick_exhaust_from_hand",
    "pick_return_from_exhaust",
    "pending_random_exhaust",
    // Upgrades in combat (card-upgrades spec): the upgrade pick.
    "pick_upgrade_from_hand",
];

const MONSTER_SCALARS: [&str; 7] = ["alive", "hp", "max_hp", "block", "can_split", "escaped", "intent_damage"];
/// Lookahead's scalars per monster: shown intent still to roll, then the
/// 4-move (damage, hits) rate.
pub const LOOK_SCALARS: [&str; 3] = ["intent_pending", "look_rate_damage", "look_rate_hits"];

/// Rates' products with the rounds-left estimate, after the `rate_*` block.
const RATE_PRODUCTS: [&str; 2] = ["rate_strength_x_turns", "rate_block_x_turns"];
/// Rates' state column (on the player path).
pub const TURNS_LEFT: &str = "turns_left_est";

/// Start HP's player column (`with_start_hp`), last on the player path.
pub const START_HP: &str = "start_hp";

/// `<prefix><field>` for every `HookRates` field.
fn rate_names(prefix: &str) -> impl Iterator<Item = String> + '_ {
    HookRates::NAMES.iter().map(move |f| format!("{prefix}{f}"))
}

/// Whether player column names include the rate columns (a net trained with them).
pub fn has_rates(player_names: &[String]) -> bool {
    player_names.iter().any(|n| n == TURNS_LEFT || n.starts_with("rate_"))
}

/// Whether player column names include `start_hp` (a net trained with it).
pub fn has_start_hp(player_names: &[String]) -> bool {
    player_names.iter().any(|n| n == START_HP)
}

/// Whether monster column names include lookahead's (a net trained with it).
pub fn has_lookahead(monster_names: &[String]) -> bool {
    monster_names.iter().any(|n| LOOK_SCALARS.contains(&n.as_str()) || n.starts_with("next1_") || n.starts_with("next2_"))
}

/// Which names have a dimension, in order. `None` in a `known_*` list means
/// every name of that vocabulary in engine order.
#[derive(Clone, Debug, Default)]
pub struct Vocab {
    pub cards: Option<Vec<CardId>>,
    pub powers: Option<Vec<Power>>,
    pub triggers: Option<Vec<String>>,
    pub conditions: Option<Vec<String>>,
    pub effects: Option<Vec<String>>,
}

#[derive(Clone, Debug)]
pub struct Encoder {
    pub repr: CardRepr,
    /// Card id → its ids dimension (`card_ids.len()` = unknown).
    card_index: [usize; NUM_CARDS],
    card_ids: Vec<CardId>,
    /// Power → its dimension in a power block (`powers.len()` = unknown).
    power_index: [usize; NUM_POWERS],
    powers: Vec<Power>,
    triggers: Vec<String>,
    conditions: Vec<String>,
    /// Effect scalar → its dimension, or `None` (dropped).
    scalar_dim: [Option<usize>; EFFECT_SCALARS.len()],
    scalars: Vec<&'static str>,
    /// Precomputed per card id: its card vector, and its hook rows flat.
    card_vecs: Vec<Vec<f32>>,
    card_rows: Vec<Vec<f32>>,
    card_held: Vec<Vec<f32>>,
    /// Per card id: its rows of the newer kinds (flat) and their kinds.
    card_kind_rows: Vec<(Vec<f32>, Vec<u8>)>,
    /// The net's layout, when it differs from the full one (`set_layout`).
    gather: Option<Gather>,
    test_inject: bool,
    /// The opt-in row kinds on (`with_extra_rows`).
    extra_rows: bool,
    /// Lookahead columns on (`with_lookahead`).
    lookahead: bool,
    /// Rate columns on (`with_rates`).
    rates: bool,
    /// Start-HP column on (`with_start_hp`).
    start_hp: bool,
    /// Card damage and block as the game shows them (`with_shown_numbers`).
    shown_numbers: bool,
    /// Exhaust pile counts written as 0 (`with_exhaust_hidden`).
    exhaust_hidden: bool,
    /// The legacy `only_attacks_in_hand` card column on (a layout names it).
    legacy_clash: bool,
    /// Known cards and floaters as entries of their own with their
    /// `POSITION_COLS` (off for a layout without them).
    positions: bool,
}

impl Encoder {
    pub fn new(repr: CardRepr, vocab: &Vocab) -> Encoder {
        let card_ids = vocab.cards.clone().unwrap_or_else(|| CardId::all().collect());
        let mut card_index = [card_ids.len(); NUM_CARDS];
        for (i, c) in card_ids.iter().enumerate() {
            card_index[c.0 as usize] = i;
        }
        // Effects mode: modifier powers only; the rest are rows.
        let powers: Vec<Power> = vocab
            .powers
            .clone()
            .unwrap_or_else(|| Power::ALL.to_vec())
            .into_iter()
            .filter(|&p| repr == CardRepr::Ids || is_modifier(p))
            .collect();
        let mut power_index = [powers.len(); NUM_POWERS];
        for (i, &p) in powers.iter().enumerate() {
            power_index[p as usize] = i;
        }
        let triggers = vocab.triggers.clone().unwrap_or_else(default_trigger_names);
        let conditions = vocab.conditions.clone().unwrap_or_else(condition_names);
        let scalars: Vec<&'static str> = match &vocab.effects {
            None => EFFECT_SCALARS.to_vec(),
            Some(names) => names.iter().filter_map(|n| EFFECT_SCALARS.iter().find(|&&s| s == n).copied()).collect(),
        };
        let mut scalar_dim = [None; EFFECT_SCALARS.len()];
        for (i, s) in scalars.iter().enumerate() {
            scalar_dim[scalar_index(s)] = Some(i);
        }
        let mut e = Encoder {
            repr,
            card_index,
            card_ids,
            power_index,
            powers,
            triggers,
            conditions,
            scalar_dim,
            scalars,
            card_vecs: Vec::new(),
            card_rows: Vec::new(),
            card_held: Vec::new(),
            card_kind_rows: Vec::new(),
            gather: None,
            test_inject: false,
            extra_rows: false,
            lookahead: false,
            rates: false,
            start_hp: false,
            shown_numbers: false,
            exhaust_hidden: false,
            legacy_clash: false,
            positions: true,
        };
        e.cache_cards();
        e
    }

    /// Precomputes every official card's vector and rows.
    fn cache_cards(&mut self) {
        let (e, repr) = (&*self, self.repr);
        let official = Binding::default();
        let card_vecs = CardId::all().map(|c| e.card_vec(c, c.def(), &official)).collect();
        let card_rows = CardId::all()
            .map(|c| if repr == CardRepr::Effects { e.card_hook_rows(c.def(), &official).concat() } else { Vec::new() })
            .collect();
        let card_held = CardId::all().map(|c| if repr == CardRepr::Effects { e.card_held_rows(c.def()) } else { Vec::new() }).collect();
        let card_kind_rows = CardId::all()
            .map(|c| if repr == CardRepr::Effects { e.card_kind_rows(c.def(), &official) } else { Default::default() })
            .collect();
        (self.card_vecs, self.card_rows, self.card_held, self.card_kind_rows) = (card_vecs, card_rows, card_held, card_kind_rows);
    }

    /// Turns the lookahead columns on or off. Call before `set_layout`.
    pub fn with_lookahead(mut self, on: bool) -> Encoder {
        self.lookahead = on;
        self
    }

    pub fn lookahead(&self) -> bool {
        self.lookahead
    }

    /// Turns the rate columns on or off. Call before `set_layout`.
    pub fn with_rates(mut self, on: bool) -> Encoder {
        if on != self.rates {
            self.rates = on;
            self.cache_cards(); // card vectors gain or lose `grant_rate_*`
        }
        self
    }

    pub fn rates(&self) -> bool {
        self.rates
    }

    /// Turns the start-HP column on or off. Call before `set_layout`.
    pub fn with_start_hp(mut self, on: bool) -> Encoder {
        self.start_hp = on;
        self
    }

    pub fn start_hp(&self) -> bool {
        self.start_hp
    }

    /// Writes each card's damage and block as the game shows them: damage
    /// + the player's Strength x hits, x0.75 rounded down under Weak; block
    /// + Dexterity, x0.75 under Frail (docs/specs/shown-card-numbers.md).
    /// Effects mode only; the layout is unchanged.
    pub fn with_shown_numbers(mut self, on: bool) -> Encoder {
        self.shown_numbers = on;
        self
    }

    pub fn shown_numbers(&self) -> bool {
        self.shown_numbers
    }

    /// Writes the exhaust pile's card counts as 0; the layout is unchanged.
    pub fn with_exhaust_hidden(mut self, on: bool) -> Encoder {
        self.exhaust_hidden = on;
        self
    }

    pub fn exhaust_hidden(&self) -> bool {
        self.exhaust_hidden
    }

    /// The card property columns (`only_attacks_in_hand` only when on).
    fn card_props(&self) -> impl Iterator<Item = &'static str> + '_ {
        CARD_PROPS.iter().enumerate().filter(|&(i, _)| i != LEGACY_CLASH || self.legacy_clash).map(|(_, &s)| s)
    }

    /// The full-layout card columns `shown_numbers` rewrites: (damage, hits)
    /// pairs, then block; `None` for a column the vocabulary drops.
    fn shown_cols(&self) -> ([(Option<usize>, Option<usize>); 3], Option<usize>) {
        let col = |n: &str| self.scalar_dim[scalar_index(n)].map(|i| self.card_props().count() + i);
        let pair = |d: &str, h: &str| (col(d), col(h));
        ([pair("damage_single", "hits_single"), pair("damage_all", "hits_all"), pair("damage_random", "hits_random")], col("block"))
    }

    /// Rewrites one card vector's damage and block as the game shows them
    /// (see `with_shown_numbers`): each attack effect through the engine's
    /// `shown_damage` (per hit), each block effect through `shown_block`,
    /// over the effects the cached vector was built from.
    fn show_numbers(&self, s: &CombatState, d: &CardDef, card: &mut [f32]) {
        let ([single, all, random], blk) = self.shown_cols();
        let (mut dmg, mut block) = ([0f32; 3], 0f32);
        for e in d.all_effects().chain(d.turn_end).chain(d.exhausted) {
            match *e {
                Effect::Damage { amount, hits, target } => {
                    dmg[if target == Target::AllOpponents { 1 } else { 0 }] += s.shown_damage(amount, hits) as f32;
                }
                Effect::RandomDamage { amount, hits } => dmg[2] += s.shown_damage(amount, hits) as f32,
                Effect::Block(n) => block += s.shown_block(n) as f32,
                Effect::BlockOf(a) => block += a.base as f32,
                Effect::ScaledBlock { amount, times } if times.of.is_none() => block += (s.shown_block(amount) * times.base) as f32,
                _ => {}
            }
        }
        for ((dc, hc), v) in [single, all, random].into_iter().zip(dmg) {
            if let (Some(dc), Some(hc)) = (dc, hc) {
                if card[hc] > 0.0 {
                    card[dc] = v;
                }
            }
        }
        if let Some(b) = blk {
            if card[b] > 0.0 {
                card[b] = block;
            }
        }
    }

    /// An entity's rate columns from its powers `pw`: `rate_*`, then the
    /// products with `turns`.
    fn rate_cols(&self, pw: &Powers, bd: &Binding, turns: f32, out: &mut Vec<f32>) {
        let r = hook_rates(pw, bd);
        out.extend(r.values());
        out.extend([r.strength * turns, r.block * turns]);
    }

    /// A card's `grant_rate_*`: the rates of the hook powers it applies to
    /// its user, at the applied amount.
    fn grant_rate_cols(&self, d: &CardDef, bd: &Binding, out: &mut Vec<f32>) {
        let mut pw = Powers::default();
        for e in d.all_effects() {
            if let Effect::Apply { power, amount, target: Target::Me } = *e {
                if !bd.hooks(power).is_empty() {
                    pw.add(power, amount);
                }
            }
        }
        out.extend(hook_rates(&pw, bd).values());
    }

    /// The vocabularies in use, as names (what a net's meta saves).
    pub fn vocab_names(&self) -> Vec<(&'static str, Vec<String>)> {
        vec![
            ("cards", self.card_ids.iter().map(|c| c.name().to_string()).collect()),
            ("powers", self.powers.iter().map(|&p| power_name(p)).collect()),
            ("triggers", self.triggers.clone()),
            ("conditions", self.conditions.clone()),
            ("effects", self.scalars.iter().map(|s| s.to_string()).collect()),
        ]
    }

    /// Test only: write the `TEST_KIND` rows and the `TEST_PILE` pile (see
    /// there). Call before `set_layout`.
    pub fn inject_test(&mut self) {
        self.test_inject = true;
    }

    /// Turns the opt-in row kinds (`EXTRA_KINDS`) on or off. Call before
    /// `set_layout`.
    pub fn with_extra_rows(mut self, on: bool) -> Encoder {
        self.extra_rows = on;
        self
    }

    pub fn extra_rows(&self) -> bool {
        self.extra_rows
    }

    /// Row kinds this encoder writes: the base ones, the opt-in ones when on.
    pub fn row_kinds(&self) -> Vec<&'static str> {
        ROW_KINDS[..self.n_kinds()].iter().copied().chain(self.test_inject.then_some(TEST_KIND)).collect()
    }

    /// How many of `ROW_KINDS` this encoder writes (the test kind follows).
    fn n_kinds(&self) -> usize {
        if self.extra_rows { ROW_KINDS.len() } else { BASE_KINDS }
    }

    /// Piles this encoder writes, in `card_pile` order before any gather.
    pub fn piles(&self) -> Vec<&'static str> {
        PILES.iter().copied().chain(self.test_inject.then_some(TEST_PILE)).collect()
    }

    fn pile_parent(&self, p: &str) -> Option<&'static str> {
        if self.test_inject && p == TEST_PILE {
            return Some("draw");
        }
        PILE_PARENTS.iter().find(|(c, _)| *c == p).map(|&(_, parent)| parent)
    }

    /// Full-layout column names per path: player, monster, card, row.
    fn full_names(&self) -> [Vec<String>; 4] {
        [self.player_names(), self.monster_names(), self.card_names(), self.row_names()]
    }

    /// Writes every batch in a net's own layout (the contract's gather):
    /// `columns` per path in the net's order (a column the encoder lacks
    /// reads 0, one the net lacks is left out), only rows of `row_kinds`,
    /// and each card's pile as its index in `piles` (an unlisted pile as its
    /// parent's). `None` keeps that part as the encoder has it. A layout
    /// equal to the full one costs nothing.
    pub fn set_layout(
        &mut self,
        columns: Option<[Vec<String>; 4]>,
        row_kinds: Option<Vec<String>>,
        piles: Option<Vec<String>>,
    ) -> Result<(), String> {
        // A net trained with Clash's old column reads it (card-rules spec).
        if let Some(c) = &columns {
            let legacy = self.repr == CardRepr::Effects && c[2].iter().any(|n| n == CARD_PROPS[LEGACY_CLASH]);
            if legacy != self.legacy_clash {
                self.legacy_clash = legacy;
                self.cache_cards();
            }
        }
        let full = self.full_names();
        for (k, path) in full.iter().enumerate() {
            let mut seen = std::collections::HashSet::new();
            if let Some(n) = path.iter().find(|n| !seen.insert(n.as_str())) {
                return Err(format!("column {n:?} appears twice in path {k}; columns are matched by name"));
            }
        }
        self.positions = columns.as_ref().is_none_or(|c| c[2].iter().any(|n| POSITION_COLS.contains(&n.as_str())));
        let names = columns.unwrap_or_else(|| full.clone());
        let cols: [Vec<Option<usize>>; 4] = std::array::from_fn(|k| {
            let at: std::collections::HashMap<&str, usize> =
                full[k].iter().enumerate().map(|(i, n)| (n.as_str(), i)).collect();
            names[k].iter().map(|n| at.get(n.as_str()).copied()).collect()
        });
        let kinds = self.row_kinds();
        let keep_kind: Vec<bool> =
            kinds.iter().map(|k| row_kinds.as_ref().is_none_or(|l| l.iter().any(|x| x == k))).collect();
        let own = self.piles();
        let net_piles: Vec<String> = piles.unwrap_or_else(|| own.iter().map(|p| p.to_string()).collect());
        let mut pile_slot = Vec::with_capacity(own.len());
        for &p in &own {
            let mut q = Some(p);
            let slot = loop {
                match q {
                    Some(name) => match net_piles.iter().position(|x| x == name) {
                        Some(i) => break i as i64,
                        None => q = self.pile_parent(name),
                    },
                    None => return Err(format!("pile {p:?} is not in the net's piles {net_piles:?} and has no parent there")),
                }
            };
            pile_slot.push(slot);
        }
        let identity = (0..4).all(|k| cols[k].len() == full[k].len() && cols[k].iter().enumerate().all(|(i, &c)| c == Some(i)))
            && keep_kind.iter().all(|&k| k)
            && net_piles.len() == own.len()
            && pile_slot.iter().enumerate().all(|(i, &s)| s == i as i64);
        let runs = cols.map(|c| {
            let mut v: Vec<(Option<usize>, usize)> = Vec::new();
            for x in c {
                match v.last_mut() {
                    Some((Some(s), n)) if x == Some(*s + *n) => *n += 1,
                    Some((None, n)) if x.is_none() => *n += 1,
                    _ => v.push((x, 1)),
                }
            }
            v
        });
        self.gather = (!identity).then_some(Gather { names, runs, keep_kind, pile_slot, n_piles: net_piles.len() });
        Ok(())
    }

    /// Column names per path (player, monster, card, row) as batches carry
    /// them: the net's layout, else the full one.
    pub fn layout_names(&self) -> [Vec<String>; 4] {
        match &self.gather {
            Some(g) => g.names.clone(),
            None => self.full_names(),
        }
    }

    /// Batch widths per path (player, monster, card, row).
    pub fn layout_dims(&self) -> [usize; 4] {
        match &self.gather {
            Some(g) => std::array::from_fn(|k| g.runs[k].iter().map(|&(_, n)| n).sum()),
            None => [self.player_dim(), self.monster_dim(), self.card_dim(), self.row_dim()],
        }
    }

    /// Pile slots in batches (`card_pile` ranges over them).
    pub fn n_piles(&self) -> usize {
        self.gather.as_ref().map_or(self.piles().len(), |g| g.n_piles)
    }

    /// Power dimensions: one per vocabulary power, then `unknown`.
    fn power_dims(&self) -> usize {
        self.powers.len() + 1
    }

    fn power_dim_names(&self, prefix: &str) -> Vec<String> {
        self.powers.iter().map(|&p| format!("{prefix}{}", power_name(p))).chain([format!("{prefix}unknown")]).collect()
    }

    fn effect_dim_names(&self) -> Vec<String> {
        let mut v: Vec<String> = self.scalars.iter().map(|s| s.to_string()).collect();
        for t in APPLY_TARGETS {
            v.extend(self.power_dim_names(&format!("apply_{t}_")));
        }
        v
    }

    fn effect_dim(&self) -> usize {
        self.scalars.len() + APPLY_TARGETS.len() * self.power_dims()
    }

    pub fn player_names(&self) -> Vec<String> {
        let mut v: Vec<String> = PLAYER_SCALARS.iter().map(|s| s.to_string()).collect();
        v.extend(self.power_dim_names("power_"));
        if self.rates {
            v.extend(rate_names("rate_").chain(RATE_PRODUCTS.iter().map(|s| s.to_string())));
            v.push(TURNS_LEFT.to_string());
        }
        if self.start_hp {
            v.push(START_HP.to_string());
        }
        if self.relic_ids() {
            v.extend(registry::official_relics().iter().map(|(n, _)| format!("relic_{n}")));
            v.push("relic_unknown".to_string());
            v.extend(registry::official_potions().iter().map(|(n, _)| format!("potion_{n}")));
            v.push("potion_unknown".to_string());
        }
        v
    }

    pub fn monster_names(&self) -> Vec<String> {
        let mut v: Vec<String> = MONSTER_SCALARS.iter().map(|s| s.to_string()).collect();
        v.extend(self.power_dim_names("power_"));
        v.extend(self.effect_dim_names().into_iter().map(|n| format!("intent_{n}")));
        if self.lookahead {
            v.extend(LOOK_SCALARS.iter().map(|s| s.to_string()));
            for step in ["next1", "next2"] {
                v.extend(self.effect_dim_names().into_iter().map(|n| format!("{step}_{n}")));
            }
        }
        if self.rates {
            v.extend(rate_names("rate_").chain(RATE_PRODUCTS.iter().map(|s| s.to_string())));
        }
        v
    }

    pub fn card_names(&self) -> Vec<String> {
        match self.repr {
            CardRepr::Effects => {
                let rates = self.rates.then(|| rate_names("grant_rate_")).into_iter().flatten();
                self.card_props().map(|s| s.to_string()).chain(self.effect_dim_names()).chain(rates).chain(POSITION_COLS.map(String::from)).collect()
            }
            CardRepr::Ids => {
                // A status card's upgraded slot shares its name: it is `<name>+`.
                let mut seen = std::collections::HashSet::new();
                let mut v: Vec<String> = Vec::with_capacity(self.card_ids.len() + 1);
                for c in &self.card_ids {
                    let n = format!("id_{}", c.name());
                    v.push(if seen.insert(n.clone()) { n } else { format!("{n}+") });
                }
                v.push("id_unknown".to_string());
                v.extend(POSITION_COLS.map(String::from));
                v
            }
        }
    }

    pub fn row_names(&self) -> Vec<String> {
        let mut v: Vec<String> = self.triggers.iter().map(|t| format!("trigger_{t}")).collect();
        v.push("trigger_unknown".into());
        v.extend(self.conditions.iter().map(|c| format!("condition_{c}")));
        v.push("condition_unknown".into());
        v.push("condition_param".into());
        v.extend(GRANTS.iter().map(|g| format!("grant_{g}")));
        v.extend(RELIC_COLS.iter().chain(&POTION_COLS).chain(&REPLACE_COLS).map(|s| s.to_string()));
        v.extend(self.effect_dim_names());
        v
    }

    fn powers(&self, p: &Powers, bd: &Binding, out: &mut Vec<f32>) {
        let mut v = vec![0f32; self.power_dims()];
        for &k in bd.powers_in_play() {
            if self.repr == CardRepr::Effects && !is_modifier(k) {
                continue;
            }
            v[self.power_index[k as usize]] += p.get(k) as f32;
        }
        out.extend(v);
    }

    /// Effect-primitive vector of a list of effects. `rolled` is the damage
    /// of a `RolledAttack` (monster intents only). In effects mode a hook
    /// power's `Apply` has no dimension: its hooks are rows instead.
    fn effects<'a>(&self, effects: impl IntoIterator<Item = &'a Effect>, rolled: i16, out: &mut Vec<f32>) {
        let scalars = self.scalars.len();
        let power_dims = self.power_dims();
        let mut v = vec![0f32; self.effect_dim()];
        let rows_for_hooks = self.repr == CardRepr::Effects;
        for e in effects {
            let mut add = |name: &str, x: f32| {
                if let Some(i) = self.scalar_dim[scalar_index(name)] {
                    v[i] += x;
                }
            };
            match *e {
                Effect::Damage { amount, hits, target } => {
                    let (d, h) = if target == Target::AllOpponents { ("damage_all", "hits_all") } else { ("damage_single", "hits_single") };
                    add(d, amount as f32 * hits as f32);
                    add(h, hits as f32);
                }
                Effect::PlainDamage { amount, target: Target::Me } => add("damage_plain_self", amount as f32),
                Effect::PlainDamage { amount, .. } => add("damage_plain", amount as f32),
                Effect::ScaledDamage { amount, hits, target } => {
                    // The columns of the primitives this replaced, so old nets read
                    // Body Slam, Heavy Blade and Perfected Strike as before.
                    if hits == Amount::constant(1) {
                        match amount.of {
                            Some(Quantity::OwnBlock) => add("damage_from_block", amount.kf()),
                            Some(Quantity::OwnStrength) => {
                                add("strength_mult_base", amount.base as f32);
                                add("strength_mult", amount.kf() + 1.0);
                            }
                            Some(Quantity::CardsTagged(Tag::Strike)) => {
                                add("per_strike_base", amount.base as f32);
                                add("per_strike", amount.kf());
                            }
                            _ => {}
                        }
                    }
                    // The total, amount × hits, as `base + k × quantity` (one side is constant).
                    let (base, k, q) = match (amount.of, hits.of) {
                        (q @ Some(_), _) => (amount.base * hits.base, amount.kf() * hits.base as f32, q),
                        (None, q) => (amount.base * hits.base, amount.base as f32 * hits.kf(), q),
                    };
                    add("expr_base", base as f32);
                    add("expr_k", k);
                    match q {
                        Some(Quantity::OwnBlock) => add("expr_q_block", 1.0),
                        Some(Quantity::OwnStrength) => add("expr_q_strength", 1.0),
                        Some(Quantity::EnergySpent) => add("expr_q_energy", 1.0),
                        Some(Quantity::CardsTagged(Tag::Strike)) => add("expr_q_strike", 1.0),
                        Some(Quantity::HandCards { .. }) => add("expr_q_hand", 1.0),
                        // No content counts another tag yet, and none puts max
                        // HP in damage (fractional-amounts spec): no column;
                        // nor the draw pile (Mind Blast; colorless-cards spec).
                        // Nor a count of a card type (Du-Vu Doll's curses: a relic's).
                        Some(Quantity::CardsTagged(_)) | Some(Quantity::OwnMaxHp) | Some(Quantity::DrawPileSize) | Some(Quantity::CardsOfType(_)) | Some(Quantity::HpDealt) | None => {}
                    }
                    if target == Target::AllOpponents {
                        add("expr_all", 1.0);
                    }
                }
                Effect::RandomDamage { amount, hits } => {
                    add("damage_random", amount as f32 * hits as f32);
                    add("hits_random", hits as f32);
                }
                Effect::RolledAttack => add("rolled_attack", rolled as f32),
                Effect::Block(n) => add("block", n as f32),
                // Pack monsters' block for an ally and pack-power applies
                // (Shield Gremlin, Red Slaver): no column, the layout stays.
                // Heal and HealOf: no column either (the 10-29 layout stays).
                // Counter effects are a relic's (relic-entity spec step 5 reads them).
                Effect::BlockAlly(_) | Effect::ApplyPack { .. } | Effect::Heal(_) | Effect::HealOf(_) | Effect::CapHp { .. } | Effect::WinHeal(_) | Effect::GainMaxHp(_) | Effect::DrawPicked | Effect::PlayTop { .. } | Effect::SetCounter(_) | Effect::AddCounter(_) | Effect::RandomizeCost(_) => {}
                // A discovery: no column (docs/specs/discovery.md); the net reads the card taken.
                Effect::Discover { .. } => {}
                // Random cards made: no column (colorless-cards spec step 3).
                Effect::MakeRandom { .. } => {}
                // Random potions: no column (docs/specs/act1-singles.md "The net").
                Effect::ObtainRandomPotions { .. } => {}
                Effect::BlockOf(a) => {
                    add("block", a.base as f32);
                    add("block_of_k", a.kf());
                }
                Effect::ScaledBlock { amount, times } => match times.of {
                    None => add("block", (amount * times.base) as f32),
                    Some(_) => add("block_per_card", amount as f32 * times.kf()),
                },
                // Every card in hand: 1; every non-Attack: 0.5.
                Effect::ExhaustHand { except } => add("exhaust_hand", if except.is_some() { 0.5 } else { 1.0 }),
                Effect::ExhaustRandom => add("exhaust_random", 1.0),
                Effect::Draw(n) => add("draw", n as f32),
                Effect::GainEnergy(n) => add("energy", n as f32),
                Effect::LoseHp(n) => add("lose_hp", n as f32),
                // Regret's HP loss by the hand: its base in the same column (no new column).
                Effect::LoseHpOf(a) => add("lose_hp", a.base as f32),
                // A copy of the card it is on (Necronomicurse): counted as added.
                Effect::AddCopy { n, pile } => add(
                    match pile {
                        PileKind::Draw => "add_draw",
                        PileKind::Discard => "add_discard",
                        PileKind::Hand => "add_hand",
                    },
                    n as f32,
                ),
                Effect::AddCard { card, n, pile } => {
                    let n = n as f32;
                    add(
                        match pile {
                            PileKind::Draw => "add_draw",
                            PileKind::Discard => "add_discard",
                            PileKind::Hand => "add_hand",
                        },
                        n,
                    );
                    let d = card.def();
                    for e in d.all_effects() {
                        match *e {
                            Effect::Damage { amount, hits, .. } => add("added_damage", n * amount as f32 * hits as f32),
                            Effect::Block(b) => add("added_block", n * b as f32),
                            _ => {}
                        }
                    }
                    if d.unplayable() {
                        add("added_unplayable", n);
                    }
                }
                Effect::Split => add("split", 1.0),
                Effect::Escape => add("escape", 1.0),
                Effect::RemoveSelf => add("remove_self", 1.0),
                Effect::ReduceSelf(n) => add("reduce_self", n as f32),
                Effect::Pick { kind: PickKind::DiscardFromHand, n, .. } => add("pick_discard", n as f32),
                Effect::Pick { kind: PickKind::ReturnFromDiscard, n, .. } => add("pick_return", n as f32),
                Effect::Pick { kind: PickKind::DiscardToTop, n, .. } => add("pick_to_top", n as f32),
                Effect::Pick { kind: PickKind::ExhaustFromHand, n, .. } => add("pick_exhaust", n as f32),
                Effect::Pick { kind: PickKind::ReturnFromExhaust, n, .. } => add("pick_return_exhaust", n as f32),
                Effect::Pick { kind: PickKind::UpgradeFromHand, n, .. } => add("pick_upgrade", n as f32),
                // Engine-internal: no content effect holds it.
                Effect::Pick { kind: PickKind::Offered, .. } => {}
                // No column yet (colorless-cards spec step 4), as below.
                Effect::Pick { kind: PickKind::HandToTop, .. } => {}
                // No column yet (ironclad-last-four spec step 3), as HandToTop.
                Effect::Pick { kind: PickKind::CopyInHand, .. } => {}
                Effect::UpgradeHand => add("upgrade_hand", 1.0),
                // No column yet (colorless-cards spec step 4): a new column
                // changes the layout.
                Effect::UpgradeAll | Effect::ShuffleDiscardIntoDraw | Effect::ZeroCostRandom => {}
                // Random hand work (blocked-relics spec step 5): no column,
                // as ZeroCostRandom; the net reads the hand it leaves.
                Effect::ZeroCostRandomTurn | Effect::UpgradeRandom => {}
                // Debuffs removed: no column (blocked-relics spec step 4).
                Effect::RemoveDebuffs => {}
                Effect::ReplayCard => add("replay", 1.0),
                Effect::GrowDamage(k) => add("grow_damage", k as f32),
                Effect::ApplyOf { power, amount, .. } if rows_for_hooks && !is_modifier(power) => add("apply_of_k", amount.kf()),
                Effect::Apply { power, .. } | Effect::ApplyAsMonster { power, .. } | Effect::RandomApply { power, .. } if rows_for_hooks && !is_modifier(power) => {}
                // As a monster's (Doubt, Shame): the same columns as Apply.
                Effect::Apply { power, amount, target } | Effect::ApplyAsMonster { power, amount, target } => {
                    let t = match target {
                        Target::Opponent => 0,
                        Target::AllOpponents => 1,
                        Target::Me => 2,
                        // Only hooks fired by an attack name the attacker: an opponent.
                        Target::Attacker | Target::RandomOpponent => 0,
                    };
                    v[scalars + t * power_dims + self.power_index[power as usize]] += amount as f32;
                }
                Effect::ApplyOf { power, amount, target } => {
                    let t = match target {
                        Target::Opponent | Target::Attacker | Target::RandomOpponent => 0,
                        Target::AllOpponents => 1,
                        Target::Me => 2,
                    };
                    add("apply_of_k", amount.kf());
                    v[scalars + t * power_dims + self.power_index[power as usize]] += amount.base as f32;
                }
                // Random enemies: counted, in total, as applied to an opponent.
                Effect::RandomApply { power, amount, hits } => {
                    v[scalars + self.power_index[power as usize]] += amount as f32 * hits as f32;
                }
            }
        }
        out.extend(v);
    }

    /// One hook row: trigger, condition, grant, then the effect vector.
    fn row<'a>(&self, trigger: Trigger, condition: Condition, grant: usize, effects: impl IntoIterator<Item = &'a Effect>, out: &mut Vec<f32>) {
        let (cn, param) = condition_key(condition);
        self.row_named(trigger, &cn, param, grant, effects, out);
    }

    /// A hook's row (`row`), its second condition's column set too and its
    /// number, if it has one, in `condition_param` (fight-vocabulary spec:
    /// at most one of the two carries a number).
    fn hook_row<'a>(&self, h: &Hook, grant: usize, effects: impl IntoIterator<Item = &'a Effect>, out: &mut Vec<f32>) {
        let at = out.len();
        self.row(h.trigger, h.condition, grant, effects, out);
        if h.also != Condition::Always {
            let (cn, param) = condition_key(h.also);
            let nc = self.conditions.len();
            let c0 = at + self.triggers.len() + 1;
            out[c0 + self.conditions.iter().position(|x| *x == cn).unwrap_or(nc)] = 1.0;
            if sts_engine::registry::condition_has_number(h.also) {
                out[c0 + nc + 1] = param;
            }
        }
    }

    /// `row` with the condition as its vocabulary name and parameter.
    fn row_named<'a>(&self, trigger: Trigger, cn: &str, param: f32, grant: usize, effects: impl IntoIterator<Item = &'a Effect>, out: &mut Vec<f32>) {
        self.row_of(&trigger_name(trigger), cn, param, grant, effects, out);
    }

    /// `row_named` with the trigger as its column name (a pseudo-trigger
    /// such as `POTION_TRIGGER`).
    fn row_of<'a>(&self, tn: &str, cn: &str, param: f32, grant: usize, effects: impl IntoIterator<Item = &'a Effect>, out: &mut Vec<f32>) {
        let nt = self.triggers.len();
        let mut t = vec![0f32; nt + 1];
        t[self.triggers.iter().position(|x| *x == tn).unwrap_or(nt)] = 1.0;
        out.extend(t);
        let nc = self.conditions.len();
        let mut c = vec![0f32; nc + 1];
        c[self.conditions.iter().position(|x| *x == cn).unwrap_or(nc)] = 1.0;
        out.extend(c);
        out.push(param);
        let mut g = [0f32; GRANTS.len()];
        g[grant] = 1.0;
        out.extend(g);
        out.extend([0f32; ROW_ONLY]);
        self.effects(effects, 0, out);
    }

    /// The rows of a hook power with `stacks`, appended to `out`; returns
    /// how many.
    /// With `cond` (name, parameter), every row takes that condition
    /// instead of the hook's own (a threshold's granted rows).
    fn power_rows(&self, p: Power, stacks: i16, grant: usize, cond: Option<(&str, f32)>, bd: &Binding, out: &mut Vec<f32>) -> usize {
        // `RoundEnd` hooks are `countdown` rows (`power_kind_rows`).
        let hs: Vec<_> = bd.hooks(p).iter().filter(|h| h.trigger != Trigger::RoundEnd).collect();
        for h in &hs {
            let scaled: Vec<Effect> = h.effects.iter().map(|e| e.scaled(stacks)).collect();
            match cond {
                Some((cn, param)) => self.row_named(h.trigger, cn, param, grant, &scaled, out),
                None => self.hook_row(h, grant, &scaled, out),
            }
        }
        hs.len()
    }

    /// A power's rows of the newer kinds, appended to `rows` with each one's
    /// kind in `kinds`: its `RoundEnd` hooks (`countdown`), then its static
    /// rows (`static`), scaled by `stacks`.
    /// `all`: every kind, for a card's cached rows (the write decides);
    /// otherwise only kinds that are on and reach the net.
    #[allow(clippy::too_many_arguments)]
    fn power_kind_rows(&self, p: Power, stacks: i16, grant: usize, bd: &Binding, all: bool, rows: &mut Vec<f32>, kinds: &mut Vec<u8>) {
        let keeps = |k: u8| all || self.keeps(k);
        // Kinds the net's layout drops aren't written at all (older nets).
        for h in bd.hooks(p).iter().filter(|h| h.trigger == Trigger::RoundEnd && keeps(KIND_COUNTDOWN)) {
            let scaled: Vec<Effect> = h.effects.iter().map(|e| e.scaled(stacks)).collect();
            self.hook_row(h, grant, &scaled, rows);
            kinds.push(KIND_COUNTDOWN);
        }
        for st in bd.statics(p).iter().filter(|_| keeps(KIND_STATIC)) {
            self.static_row(st, stacks, grant, rows);
            kinds.push(KIND_STATIC);
        }
        for r in bd.replacements(p).iter().filter(|_| keeps(KIND_REPLACEMENT)) {
            self.replacement_row(r, stacks, grant, rows);
            kinds.push(KIND_REPLACEMENT);
        }
        if keeps(KIND_RULE) {
            let rules = [
                bd.forbids(p).map(|ty| (RULE_TRIGGERS[0], ty, None)),
                bd.sets_cost(p).map(|(ty, cost)| (RULE_TRIGGERS[1], ty, Some(cost))),
                bd.exhausts_played(p).map(|ty| (RULE_TRIGGERS[2], ty, None)),
                bd.plays_unplayable(p).map(|ty| (PLAYS_UNPLAYABLE_TRIGGER, ty, None)),
            ];
            for (trigger, ty, cost) in rules.into_iter().flatten() {
                self.rule_row(trigger, &format!("CardType({ty:?})"), cost, grant, rows);
                kinds.push(KIND_RULE);
            }
        }
    }

    /// One rule row: the rule as its trigger, the card type (or the card's
    /// play condition) as its condition, and a cost cap's cost in
    /// `condition_param` (no effect scalar: card and intent vectors keep
    /// their width).
    fn rule_row(&self, trigger: &str, condition: &str, cost: Option<i8>, grant: usize, out: &mut Vec<f32>) {
        let nt = self.triggers.len();
        let mut t = vec![0f32; nt + 1];
        t[self.triggers.iter().position(|x| x == trigger).unwrap_or(nt)] = 1.0;
        out.extend(t);
        let nc = self.conditions.len();
        let mut c = vec![0f32; nc + 1];
        c[self.conditions.iter().position(|x| x == condition).unwrap_or(nc)] = 1.0;
        out.extend(c);
        out.push(cost.map_or(0.0, |c| c as f32));
        let mut g = [0f32; GRANTS.len()];
        g[grant] = 1.0;
        out.extend(g);
        out.extend([0f32; ROW_ONLY]);
        self.effects(&[], 0, out);
    }

    /// Whether rows of `kind` are written (an opt-in kind only when on) and
    /// reach the net (its layout may drop the kind).
    fn keeps(&self, kind: u8) -> bool {
        ((kind as usize) < BASE_KINDS || self.extra_rows) && self.gather.as_ref().is_none_or(|g| g.keep_kind[kind as usize])
    }

    /// A monster's `pattern` rows: one per possible next move (after the
    /// intent on show), `condition_param` its probability, the move's
    /// effect vector. Returns how many.
    fn pattern_rows(&self, s: &CombatState, slot: usize, out: &mut Vec<f32>) -> usize {
        let m = &s.monsters[slot];
        let moves = m.def().moves;
        let dist = s.move_distribution(slot);
        let nt = self.triggers.len();
        let nc = self.conditions.len();
        let mut n = 0;
        for (mv, p) in dist {
            let Some(d) = moves.get(mv as usize) else { continue };
            let mut t = vec![0f32; nt + 1];
            t[self.triggers.iter().position(|x| x == PATTERN_TRIGGER).unwrap_or(nt)] = 1.0;
            out.extend(t);
            let mut c = vec![0f32; nc + 1];
            c[self.conditions.iter().position(|x| x == "Always").unwrap_or(nc)] = 1.0;
            out.extend(c);
            out.push(p as f32);
            let mut g = [0f32; GRANTS.len()];
            g[OWN] = 1.0;
            out.extend(g);
        out.extend([0f32; ROW_ONLY]);
            self.effects(d.effects, m.rolled_damage, out);
            n += 1;
        }
        n
    }

    /// One replacement row: the replaced event as its trigger, `Always`,
    /// the action's scalar, the power's stacks and its `then` effects.
    fn replacement_row(&self, r: &Replacement, stacks: i16, grant: usize, out: &mut Vec<f32>) {
        let nt = self.triggers.len();
        let mut t = vec![0f32; nt + 1];
        let tn = replace_trigger(r.event);
        t[self.triggers.iter().position(|x| x == tn).unwrap_or(nt)] = 1.0;
        out.extend(t);
        let nc = self.conditions.len();
        let mut c = vec![0f32; nc + 1];
        // The filter and the range each set their column (as a hook's two
        // conditions); neither: `Always`.
        let mut names = Vec::new();
        if let Some(p) = r.power {
            names.push(format!("Applying({})", power_name(p)));
        }
        if r.up_to.is_some() {
            names.push("AmountAtMost".to_string());
        }
        if names.is_empty() {
            names.push("Always".to_string());
        }
        for cn in &names {
            c[self.conditions.iter().position(|x| x == cn).unwrap_or(nc)] = 1.0;
        }
        out.extend(c);
        out.push(r.up_to.unwrap_or(0) as f32);
        let mut g = [0f32; GRANTS.len()];
        g[grant] = 1.0;
        out.extend(g);
        let mut row_only = [0f32; ROW_ONLY];
        if let Replace::AtLeast(n) = r.action {
            row_only[RELIC_COLS.len() + POTION_COLS.len()] = n as f32;
        }
        out.extend(row_only);
        let at = out.len();
        self.effects(r.then, 0, out);
        let (name, x) = match r.action {
            Replace::Cancel => ("replace_cancel", 1.0),
            Replace::Cap(n) => ("replace_cap", n as f32),
            Replace::Add(n) => ("replace_add", n as f32),
            Replace::Multiply(num, den) => ("replace_mult", num as f32 / den as f32 - 1.0),
            // Its value is the row-only `replace_at_least`; no effect scalar.
            Replace::AtLeast(_) => ("", 0.0),
        };
        for (name, x) in [(name, x), ("replace_stacks", stacks as f32)].into_iter().filter(|(n, _)| !n.is_empty()) {
            if let Some(i) = self.scalar_dim[scalar_index(name)] {
                out[at + i] = x;
            }
        }
    }

    /// One static row: the modified number as its trigger, its condition,
    /// and `static_add` (amount × stacks) or `static_mult` (factor − 1).
    fn static_row(&self, st: &Static, stacks: i16, grant: usize, out: &mut Vec<f32>) {
        let nt = self.triggers.len();
        let mut t = vec![0f32; nt + 1];
        let tn = static_trigger(st.modifies);
        t[self.triggers.iter().position(|x| x == tn).unwrap_or(nt)] = 1.0;
        out.extend(t);
        let nc = self.conditions.len();
        let mut c = vec![0f32; nc + 1];
        let cn = static_condition_name(st.condition);
        c[self.conditions.iter().position(|x| *x == cn).unwrap_or(nc)] = 1.0;
        out.extend(c);
        out.push(0.0);
        let mut g = [0f32; GRANTS.len()];
        g[grant] = 1.0;
        out.extend(g);
        out.extend([0f32; ROW_ONLY]);
        let at = out.len();
        self.effects(&[], 0, out);
        let (name, x) = match st.stage {
            StaticStage::Add => ("static_add", (st.amount * stacks) as f32),
            StaticStage::Multiply => ("static_mult", if stacks > 0 { st.num as f32 / st.den as f32 - 1.0 } else { 0.0 }),
        };
        if let Some(i) = self.scalar_dim[scalar_index(name)] {
            out[at + i] = x;
        }
    }

    /// The newer-kind rows granted by the applies in `effects` (a card's or
    /// an intent's), scaled by the applied amount; kinds in `kinds`.
    fn granted_kind_rows(&self, effects: &[Effect], bd: &Binding, all: bool, rows: &mut Vec<f32>, kinds: &mut Vec<u8>) {
        for e in effects {
            let (power, amount, grant) = match *e {
                Effect::Apply { power, amount, target } => (power, amount, if target == Target::Me { GRANT_ME } else { GRANT_OPPONENT }),
                Effect::RandomApply { power, amount, hits } => (power, amount * hits as i16, GRANT_OPPONENT),
                _ => continue,
            };
            self.power_kind_rows(power, amount, grant, bd, all, rows, kinds);
        }
    }

    /// Rows granted by the hook-power applies in `effects` (a card's or an
    /// intent's), scaled by the applied amount.
    fn granted_rows(&self, effects: &[Effect], bd: &Binding, out: &mut Vec<f32>) -> usize {
        self.granted_rows_if(effects, None, bd, out)
    }

    /// `granted_rows`, every row under `cond` when given (see `power_rows`).
    fn granted_rows_if(&self, effects: &[Effect], cond: Option<(&str, f32)>, bd: &Binding, out: &mut Vec<f32>) -> usize {
        let mut n = 0;
        for e in effects {
            let (power, amount, grant) = match *e {
                Effect::Apply { power, amount, target } => (power, amount, if target == Target::Me { GRANT_ME } else { GRANT_OPPONENT }),
                Effect::RandomApply { power, amount, hits } => (power, amount * hits as i16, GRANT_OPPONENT),
                _ => continue,
            };
            if !bd.hooks(power).is_empty() {
                n += self.power_rows(power, amount, grant, cond, bd, out);
            }
        }
        n
    }

    /// A card's rows of the newer kinds (`granted_kind_rows` over every row's
    /// effects), flat, and their kinds.
    fn card_kind_rows(&self, d: &CardDef, bd: &Binding) -> (Vec<f32>, Vec<u8>) {
        let (mut rows, mut kinds) = (Vec::new(), Vec::new());
        for (_, effects) in d.rows() {
            self.granted_kind_rows(effects, bd, true, &mut rows, &mut kinds);
        }
        // Its play condition (Clash: `HandAll(Attack)`).
        if let Some(c) = d.playable_if {
            self.rule_row(RULE_TRIGGERS[3], &condition_key(c).0, None, OWN, &mut rows);
            kinds.push(KIND_RULE);
        }
        (rows, kinds)
    }

    /// A card's rows, each its own vector: its effect rows, then the hooks
    /// of the hook powers it applies.
    fn card_hook_rows(&self, d: &CardDef, bd: &Binding) -> Vec<Vec<f32>> {
        let mut rows = Vec::new();
        for (cond, effects) in d.rows() {
            if effects.is_empty() {
                continue;
            }
            let mut v = Vec::new();
            self.row(Trigger::CardPlayed { by: Side::Owner }, cond, OWN, effects, &mut v);
            rows.push(v);
        }
        for (_, effects) in d.rows() {
            let mut v = Vec::new();
            self.granted_rows(effects, bd, &mut v);
            rows.extend(v.chunks(self.row_dim()).map(|r| r.to_vec()));
        }
        rows
    }

    /// A card's `held` rows, the effects it has outside play: while held at
    /// its owner's turn end (Burn), then when it is exhausted (Sentinel);
    /// the trigger column says which.
    fn card_held_rows(&self, d: &CardDef) -> Vec<f32> {
        let mut v = Vec::new();
        if !d.turn_end.is_empty() {
            self.row(Trigger::OwnerTurnEnd, Condition::Always, OWN, d.turn_end, &mut v);
        }
        if !d.exhausted.is_empty() {
            self.row(Trigger::CardExhausted, Condition::Always, OWN, d.exhausted, &mut v);
        }
        v
    }

    /// A monster's `threshold` rows: the threshold's effects, then the
    /// hooks of hook powers they apply, all under `HpLostReaches`.
    fn threshold_rows(&self, s: &CombatState, slot: usize, out: &mut Vec<f32>) -> usize {
        let Some(t) = threshold(s, slot) else { return 0 };
        let cond = (HP_LOST_REACHES, t.hp_to_go as f32);
        self.row_named(Trigger::OwnerLostHp { from: HpLossFrom::Any }, cond.0, cond.1, OWN, t.effects, out);
        1 + self.granted_rows_if(t.effects, Some(cond), &s.binding, out)
    }

    /// `d` is `c`'s definition (through the combat's binding `bd` for a
    /// generated slot).
    fn card_vec(&self, c: CardId, d: &CardDef, bd: &Binding) -> Vec<f32> {
        match self.repr {
            CardRepr::Ids => {
                let n = self.card_ids.len();
                let mut v = vec![0f32; n + 1 + POSITION_COLS.len()];
                v[self.card_index.get(c.0 as usize).copied().unwrap_or(n)] = 1.0;
                v
            }
            CardRepr::Effects => {
                let b = |x: bool| x as u8 as f32;
                let mut v = vec![
                    d.cost() as f32,
                    b(d.ty == CardType::Attack),
                    b(d.ty == CardType::Skill),
                    b(d.ty == CardType::Power),
                    b(d.ty == CardType::Status),
                    b(d.unplayable()),
                    b(d.exhaust),
                    b(d.ethereal),
                    b(d.targeted()),
                    b(d.playable_if == Some(Condition::HandAll(CardType::Attack))),
                    b(d.is_strike()),
                    b(d.x_cost()),
                    b(d.retain),
                    b(d.cost_less_per_hp_loss),
                ];
                if !self.legacy_clash {
                    v.remove(LEGACY_CLASH);
                }
                // Every effect, conditional, held and exhausted rows included; the rows say when.
                // A Curse has no type column: all four type bits 0 tell it apart.
                self.effects(d.all_effects().chain(d.turn_end).chain(d.exhausted).chain(d.other_played), 0, &mut v);
                if self.rates {
                    self.grant_rate_cols(d, bd, &mut v);
                }
                v.extend([0.0; POSITION_COLS.len()]);
                v
            }
        }
    }

    /// Columns of an entity's rate block.
    fn rate_dim(&self) -> usize {
        if self.rates { HookRates::NAMES.len() + RATE_PRODUCTS.len() } else { 0 }
    }

    pub fn player_dim(&self) -> usize {
        PLAYER_SCALARS.len() + self.power_dims() + self.rate_dim() + self.rates as usize + self.start_hp as usize + self.relic_id_dims()
    }

    /// Whether the player path carries `relic_<name>` columns: ids mode
    /// with the opt-in kinds on (relic-entity spec; effects mode reads
    /// relics as `relic` rows instead).
    fn relic_ids(&self) -> bool {
        self.repr == CardRepr::Ids && self.extra_rows
    }

    /// The `relic_<name>` columns: one per official relic, then `unknown`;
    /// then the `potion_<name>` columns the same way (potions spec).
    fn relic_id_dims(&self) -> usize {
        if self.relic_ids() { registry::official_relics().len() + 1 + registry::official_potions().len() + 1 } else { 0 }
    }

    /// Ids mode: how many of each official relic the player holds, then the
    /// rest (pack relics) in `relic_unknown`.
    fn relic_id_cols(&self, relics: &Relics, out: &mut Vec<f32>) {
        let official = registry::official_relics();
        let at = out.len();
        out.resize(at + official.len() + 1, 0.0);
        for (id, _) in relics.iter() {
            let i = official.iter().position(|(n, _)| n == id.name()).unwrap_or(official.len());
            out[at + i] += 1.0;
        }
    }

    /// The `relic` rows of the player's relics: each relic's hooks in the
    /// power row format at one stack, `grant_relic`, the counter and the
    /// hook's counter effects in `RELIC_COLS`.
    fn relic_rows(&self, relics: &Relics, entity: i64, state: usize, b: &mut Batch) {
        let dr = self.row_dim();
        let cols = self.triggers.len() + 1 + self.conditions.len() + 1 + 1 + GRANTS.len();
        for (id, counter) in relics.iter() {
            for h in id.hooks() {
                let at = b.rows.len();
                self.hook_row(h, GRANT_RELIC, h.effects, &mut b.rows);
                debug_assert_eq!(b.rows.len(), at + dr);
                let (mut set, mut set_to, mut add) = (0f32, 0f32, 0f32);
                for e in h.effects {
                    match *e {
                        Effect::SetCounter(n) => (set, set_to) = (1.0, n as f32),
                        Effect::AddCounter(n) => add += n as f32,
                        _ => {}
                    }
                }
                b.rows[at + cols..at + cols + RELIC_COLS.len()].copy_from_slice(&[counter as f32, set, set_to, add]);
                b.push_row_ids_kind(1, -1, entity, state, KIND_RELIC);
            }
            // Sacred Bark (potions spec): one row on a potion's use, its
            // `potion_potency`.
            let k = id.potion_potency();
            if k != 1 {
                let at = b.rows.len();
                self.row_of(POTION_TRIGGER, "Always", 0.0, GRANT_RELIC, &[], &mut b.rows);
                b.rows[at + cols] = counter as f32;
                b.rows[at + cols + RELIC_COLS.len()] = k as f32;
                b.push_row_ids_kind(1, -1, entity, state, KIND_RELIC);
            }
        }
    }

    /// Ids mode: how many of each official potion the player holds, then
    /// the rest (pack potions) in `potion_unknown`.
    fn potion_id_cols(&self, potions: &sts_engine::potions::Potions, out: &mut Vec<f32>) {
        let official = registry::official_potions();
        let at = out.len();
        out.resize(at + official.len() + 1, 0.0);
        for id in potions.iter() {
            let i = official.iter().position(|(n, _)| n == id.name()).unwrap_or(official.len());
            out[at + i] += 1.0;
        }
    }

    /// The `potion` rows of the player's held potions (potions spec): per
    /// potion, each of its rows with trigger `Potion(Use)` (or the potion's
    /// own trigger: Fairy in a Bottle's `OwnerDied`), its condition,
    /// `grant_own`, its effects at their effective amounts (Sacred Bark's
    /// multiple) and `potion_potency` its effective potency.
    fn potion_rows(&self, s: &CombatState, entity: i64, state: usize, b: &mut Batch) {
        let dr = self.row_dim();
        let at_potency = self.triggers.len() + 1 + self.conditions.len() + 1 + 1 + GRANTS.len() + RELIC_COLS.len();
        for id in s.player.potions.iter() {
            let spec = id.spec().expect("a held potion is loaded");
            let k = s.potion_scale(id);
            let tn = spec.trigger.map_or(POTION_TRIGGER.to_string(), trigger_name);
            for (condition, effects) in &spec.rows {
                let scaled: Vec<Effect> = effects.iter().map(|&e| sts_engine::potions::scaled_effect(e, k)).collect();
                let (cn, param) = condition_key(*condition);
                let at = b.rows.len();
                self.row_of(&tn, &cn, param, OWN, &scaled, &mut b.rows);
                debug_assert_eq!(b.rows.len(), at + dr);
                b.rows[at + at_potency] = (spec.potency * k) as f32;
                b.push_row_ids_kind(1, -1, entity, state, KIND_POTION);
            }
        }
    }

    pub fn monster_dim(&self) -> usize {
        let look = if self.lookahead { LOOK_SCALARS.len() + 2 * self.effect_dim() } else { 0 };
        MONSTER_SCALARS.len() + self.power_dims() + self.effect_dim() + look + self.rate_dim()
    }

    /// Lookahead's columns of a live monster: `LOOK_SCALARS`, then the
    /// probability-weighted effect vectors of step 1 and step 2.
    fn lookahead_cols(&self, s: &CombatState, slot: usize, out: &mut Vec<f32>) {
        let m = &s.monsters[slot];
        let l = lookahead(s, slot);
        out.extend([(!intent_known(s, slot)) as u8 as f32, l.rate_damage, l.rate_hits]);
        let moves = m.def().moves;
        let mut one = Vec::with_capacity(self.effect_dim());
        for step in [&l.next1, &l.next2] {
            let at = out.len();
            out.resize(at + self.effect_dim(), 0.0);
            for &(mv, p) in step {
                one.clear();
                self.effects(moves.get(mv as usize).map_or(&[][..], |d| d.effects), m.rolled_damage, &mut one);
                for (o, x) in out[at..].iter_mut().zip(&one) {
                    *o += p * x;
                }
            }
        }
    }

    pub fn card_dim(&self) -> usize {
        self.card_vecs[0].len()
    }

    /// `expr_value`'s column on the card path (effects mode), if the
    /// vocabulary has it.
    fn expr_value_col(&self) -> Option<usize> {
        if self.repr != CardRepr::Effects {
            return None;
        }
        self.scalar_dim[scalar_index("expr_value")].map(|i| self.card_props().count() + i)
    }

    pub fn row_dim(&self) -> usize {
        self.triggers.len() + 1 + self.conditions.len() + 1 + 1 + GRANTS.len() + ROW_ONLY + self.effect_dim()
    }

    /// Encodes a batch into flat buffers (shapes in the module docs).
    pub fn encode(&self, states: &[&CombatState]) -> Batch {
        let mut b = Batch::default();
        for (i, s) in states.iter().enumerate() {
            self.encode_one(i, s, &mut b);
            if i == 0 {
                // Growing the buffers one doubling at a time was ~15% of a
                // net-leaf search (docs/specs/net-leaf-cache.md).
                b.reserve_like_first(states.len());
            }
        }
        match &self.gather {
            Some(g) => self.gathered(g, b),
            None => b,
        }
    }

    /// A full-layout batch in the net's layout.
    fn gathered(&self, g: &Gather, b: Batch) -> Batch {
        let pick = |src: &[f32], dim: usize, runs: &[(Option<usize>, usize)], out: &mut Vec<f32>| {
            for r in src.chunks(dim) {
                for &(at, n) in runs {
                    match at {
                        Some(i) => out.extend_from_slice(&r[i..i + n]),
                        None => out.resize(out.len() + n, 0.0),
                    }
                }
            }
        };
        let mut o = Batch { n: b.n, ..Batch::default() };
        pick(&b.player, self.player_dim(), &g.runs[0], &mut o.player);
        pick(&b.monsters, self.monster_dim(), &g.runs[1], &mut o.monsters);
        pick(&b.cards, self.card_dim(), &g.runs[2], &mut o.cards);
        o.card_count = b.card_count;
        o.card_pile = b.card_pile.iter().map(|&p| g.pile_slot[p as usize]).collect();
        o.card_state = b.card_state;
        let dr = self.row_dim();
        for r in 0..b.row_card.len() {
            if !g.keep_kind[b.row_kind[r] as usize] {
                continue;
            }
            pick(&b.rows[r * dr..(r + 1) * dr], dr, &g.runs[3], &mut o.rows);
            o.row_card.push(b.row_card[r]);
            o.row_entity.push(b.row_entity[r]);
            o.row_state.push(b.row_state[r]);
            o.row_kind.push(b.row_kind[r]);
        }
        o
    }

    fn encode_one(&self, i: usize, s: &CombatState, b: &mut Batch) {
        let rows_start = b.row_card.len();
        let p = &s.player;
        let over = |won: bool| (s.stage == Stage::Over { won }) as u8 as f32;
        let (draw, mmove, hit) = match s.pending {
            Some(ChanceEvent::Draw { n }) => (n as f32, 0.0, 0.0),
            Some(ChanceEvent::MonsterMove { .. } | ChanceEvent::AllyBlock { .. }) => (0.0, 1.0, 0.0),
            Some(ChanceEvent::RandomTarget { amount } | ChanceEvent::PlainHit { amount }) => (0.0, 0.0, amount as f32),
            Some(ChanceEvent::RandomExhaust | ChanceEvent::TakeTop { .. } | ChanceEvent::Offer { .. } | ChanceEvent::MakeRandom { .. } | ChanceEvent::RandomPotion { .. } | ChanceEvent::RandomCost | ChanceEvent::RandomZeroCost | ChanceEvent::RandomFreeTurn | ChanceEvent::RandomUpgrade | ChanceEvent::ExhaustSave { .. }) | None => (0.0, 0.0, 0.0),
        };
        b.player.extend([
            p.hp as f32,
            p.max_hp as f32,
            p.block as f32,
            p.energy as f32,
            s.turn as f32,
            s.hand.len() as f32,
            s.draw().len() as f32,
            s.discard().len() as f32,
            s.exhaust().len() as f32,
            s.awaiting_action() as u8 as f32,
            over(true),
            over(false),
            draw,
            mmove,
            hit,
        ]);
        let pick = s.pick();
        let (next_min, next_max) = s.next_draw();
        b.player.extend([
            pick.is_some_and(|p| p.kind == PickKind::DiscardFromHand) as u8 as f32,
            pick.is_some_and(|p| p.kind == PickKind::ReturnFromDiscard) as u8 as f32,
            pick.map_or(0.0, |p| p.left as f32),
            pick.is_some_and(|p| p.kind == PickKind::DiscardToTop) as u8 as f32,
            next_min as f32,
            s.top.n_known() as f32,
            next_max as f32,
            pick.is_some_and(|p| p.kind == PickKind::ExhaustFromHand) as u8 as f32,
            pick.is_some_and(|p| p.kind == PickKind::ReturnFromExhaust) as u8 as f32,
            (s.pending == Some(ChanceEvent::RandomExhaust)) as u8 as f32,
            pick.is_some_and(|p| p.kind == PickKind::UpgradeFromHand) as u8 as f32,
        ]);
        let bd = &s.binding;
        if !bd.is_empty() && self.repr == CardRepr::Ids && !IDS_WARNED.swap(true, Ordering::Relaxed) {
            eprintln!("sts: ids-mode features see generated cards and powers as unknown");
        }
        self.powers(&p.powers, bd, &mut b.player);
        let turns = if self.rates { turns_left_estimate(s) } else { 0.0 };
        if self.rates {
            self.rate_cols(&p.powers, bd, turns, &mut b.player);
            b.player.push(turns);
        }
        if self.start_hp {
            b.player.push(s.start_hp as f32);
        }
        if self.relic_ids() {
            self.relic_id_cols(&p.relics, &mut b.player);
            self.potion_id_cols(&p.potions, &mut b.player);
        }
        let rows = self.repr == CardRepr::Effects;
        let entity_base = (i * ENTITIES) as i64;
        if rows {
            self.entity_power_rows(&p.powers, bd, entity_base, i, b);
            if !p.relics.is_empty() && self.keeps(KIND_RELIC) {
                self.relic_rows(&p.relics, entity_base, i, b);
            }
            if !p.potions.is_empty() && self.keeps(KIND_POTION) {
                self.potion_rows(s, entity_base, i, b);
            }
        }

        for slot in 0..MAX_MONSTERS {
            let m = &s.monsters[slot];
            if !m.alive() {
                b.monsters.extend(std::iter::repeat_n(0.0, self.monster_dim()));
                continue;
            }
            b.monsters.extend([
                1.0,
                m.hp as f32,
                m.max_hp as f32,
                m.block as f32,
                (m.def().split_move != NO_MOVE) as u8 as f32,
                m.escaped as u8 as f32,
                intent_damage(s, slot) as f32,
            ]);
            self.powers(&m.powers, bd, &mut b.monsters);
            let effects = m.intent_def().map_or(&[][..], |mv| mv.effects);
            // The intent as it lands (an `attack_shape` power, Split Hits:
            // twice the hits at half the base).
            let split: Vec<Effect>;
            let shown = if sts_engine::registry::official().shape_powers.iter().any(|&(p, _)| m.powers.get(p) > 0) {
                split = effects.iter().map(|&e| split_effect(&m.powers, slot, e, m.rolled_damage)).collect();
                &split[..]
            } else {
                effects
            };
            self.effects(shown, m.rolled_damage, &mut b.monsters);
            if self.lookahead {
                self.lookahead_cols(s, slot, &mut b.monsters);
            }
            if self.rates {
                self.rate_cols(&m.powers, bd, turns, &mut b.monsters);
            }
            if rows {
                let entity = entity_base + 1 + slot as i64;
                self.entity_power_rows(&m.powers, bd, entity, i, b);
                let n = self.granted_rows(effects, bd, &mut b.rows);
                b.push_row_ids(n, -1, entity, i);
                let n = self.threshold_rows(s, slot, &mut b.rows);
                b.push_row_ids_kind(n, -1, entity, i, KIND_THRESHOLD);
                let mut kinds = Vec::new();
                self.granted_kind_rows(effects, bd, false, &mut b.rows, &mut kinds);
                b.push_row_ids_kinds(&kinds, -1, entity, i);
                // Skipped when the net's layout drops the kind (older nets).
                if self.keeps(KIND_PATTERN) {
                    let n = self.pattern_rows(s, slot, &mut b.rows);
                    b.push_row_ids_kind(n, -1, entity, i, KIND_PATTERN);
                }
            }
        }

        let pos_col = self.card_dim() - POSITION_COLS.len();
        let mut pile = |k: usize, entries: &mut dyn Iterator<Item = (CardId, u8, f32, f32)>| {
            for (c, n, pos, above) in entries {
                // A generated slot's encodings come from its bound definition.
                let generated = (!c.is_official()).then(|| {
                    let d = bd.def(c);
                    let effects = self.repr == CardRepr::Effects;
                    (
                        self.card_vec(c, d, bd),
                        if effects { self.card_hook_rows(d, bd).concat() } else { Vec::new() },
                        if effects { self.card_held_rows(d) } else { Vec::new() },
                        if effects { self.card_kind_rows(d, bd) } else { Default::default() },
                    )
                });
                let (v, r, h, kr) = match &generated {
                    Some((v, r, h, kr)) => (v, r, h, kr),
                    None => (
                        &self.card_vecs[c.0 as usize],
                        &self.card_rows[c.0 as usize],
                        &self.card_held[c.0 as usize],
                        &self.card_kind_rows[c.0 as usize],
                    ),
                };
                let card_entry = b.card_count.len() as i64;
                let at = b.cards.len();
                b.cards.extend_from_slice(v);
                if let Some(col) = self.expr_value_col() {
                    let x = if k == 4 { s.stage_x() } else { s.player.energy.max(0) as i16 };
                    let value = expr_value(s, bd.def(c), x);
                    if value != 0.0 {
                        b.cards[at + col] = value;
                    }
                }
                if self.shown_numbers && self.repr == CardRepr::Effects {
                    self.show_numbers(s, bd.def(c), &mut b.cards[at..]);
                }
                b.cards[at + pos_col] = pos;
                b.cards[at + pos_col + 1] = above;
                b.card_count.push(if k == 3 && self.exhaust_hidden { 0.0 } else { n as f32 });
                b.card_pile.push(k as i64);
                b.card_state.push(i as i64);
                if !r.is_empty() {
                    b.rows.extend_from_slice(r);
                    b.push_row_ids(r.len() / self.row_dim(), card_entry, -1, i);
                }
                if !h.is_empty() {
                    b.rows.extend_from_slice(h);
                    b.push_row_ids_kind(h.len() / self.row_dim(), card_entry, -1, i, KIND_HELD);
                }
                if self.extra_rows && !kr.1.is_empty() {
                    b.rows.extend_from_slice(&kr.0);
                    b.push_row_ids_kinds(&kr.1, card_entry, -1, i);
                }
            }
        };
        let plain = |p: PileRef<'_>| p.iter().map(|(c, n)| (c, n, 0.0, 0.0)).collect::<Vec<_>>();
        pile(0, &mut plain(s.hand.view()).into_iter());
        // The draw pile less its known top, which goes to `next_draw` (the
        // least the next turn's start draws) and `known_later` (piles a net
        // may not list: they fold into `draw`). With position columns each
        // known card is its own entry at its place, and each floater with
        // cards certainly above it its own entry; without, merged entries.
        let mut unknown = s.draw().to_pile();
        let (mut next, mut later) = (Vec::new(), Vec::new());
        let mut floaters = Vec::new();
        for (i, c) in s.top.known().enumerate() {
            unknown.remove(c, 1);
            let to = if i < next_min as usize { &mut next } else { &mut later };
            let pos = if self.positions { i as f32 + 1.0 } else { 0.0 };
            match to.iter_mut().find(|e: &&mut (CardId, u8, f32, f32)| !self.positions && e.0 == c) {
                Some(e) => e.1 += 1,
                None => to.push((c, 1, pos, 0.0)),
            }
        }
        if self.positions {
            for (c, above, k) in s.top.floater_entries() {
                if above > 0 {
                    unknown.remove(c, k);
                    floaters.push((c, k, 0.0, above as f32));
                }
            }
        }
        if !self.positions {
            // Merged in card order, as a pile lists them.
            next = plain(Pile::from_cards(&next.iter().flat_map(|e| std::iter::repeat_n(e.0, e.1 as usize)).collect::<Vec<_>>()).view());
            later = plain(Pile::from_cards(&later.iter().flat_map(|e| std::iter::repeat_n(e.0, e.1 as usize)).collect::<Vec<_>>()).view());
        }
        let draw_slot = if self.test_inject { PILES.len() } else { 1 };
        pile(draw_slot, &mut plain(unknown.view()).into_iter().chain(floaters));
        pile(2, &mut plain(s.discard()).into_iter());
        pile(3, &mut plain(s.exhaust()).into_iter());
        // The card in play, and the cards `PlayTop` took waiting to play.
        let mut playing = Pile::from_cards(&s.top_queue.iter().map(|q| q.card).collect::<Vec<_>>());
        if let Stage::PlayingCard { card, .. } = s.stage {
            playing.add(card, 1);
        }
        pile(4, &mut plain(playing.view()).into_iter());
        pile(5, &mut next.into_iter());
        pile(6, &mut later.into_iter());
        if self.test_inject {
            // Every row of this state again, as a test-kind row.
            let (dr, n_rows) = (self.row_dim(), b.row_card.len());
            for r in rows_start..n_rows {
                b.rows.extend_from_within(r * dr..(r + 1) * dr);
                b.row_card.push(b.row_card[r]);
                b.row_entity.push(b.row_entity[r]);
                b.row_state.push(b.row_state[r]);
                b.row_kind.push(self.n_kinds() as u8);
            }
        }
        b.n += 1;
    }

    fn entity_power_rows(&self, powers: &Powers, bd: &Binding, entity: i64, state: usize, b: &mut Batch) {
        let mut kinds = Vec::new();
        for &p in bd.powers_in_play() {
            let stacks = powers.get(p);
            if stacks == 0 {
                continue;
            }
            if !bd.hooks(p).is_empty() {
                let n = self.power_rows(p, stacks, OWN, None, bd, &mut b.rows);
                b.push_row_ids(n, -1, entity, state);
            }
            kinds.clear();
            self.power_kind_rows(p, stacks, OWN, bd, false, &mut b.rows, &mut kinds);
            b.push_row_ids_kinds(&kinds, -1, entity, state);
        }
    }
}

#[derive(Default)]
pub struct Batch {
    pub n: usize,
    pub player: Vec<f32>,
    pub monsters: Vec<f32>,
    pub cards: Vec<f32>,
    pub card_count: Vec<f32>,
    pub card_pile: Vec<i64>,
    pub card_state: Vec<i64>,
    pub rows: Vec<f32>,
    pub row_card: Vec<i64>,
    pub row_entity: Vec<i64>,
    pub row_state: Vec<i64>,
    /// Each row's kind (index into the encoder's `row_kinds`); not a feature.
    pub row_kind: Vec<u8>,
}

impl Batch {
    /// Room for `n` states the size of the one encoded so far (a guess:
    /// states differ, and the buffers still grow past it).
    fn reserve_like_first(&mut self, n: usize) {
        let more = n.saturating_sub(1);
        self.player.reserve(self.player.len() * more);
        self.monsters.reserve(self.monsters.len() * more);
        self.cards.reserve(self.cards.len() * more);
        self.card_count.reserve(self.card_count.len() * more);
        self.card_pile.reserve(self.card_pile.len() * more);
        self.card_state.reserve(self.card_state.len() * more);
        self.rows.reserve(self.rows.len() * more);
        self.row_card.reserve(self.row_card.len() * more);
        self.row_entity.reserve(self.row_entity.len() * more);
        self.row_state.reserve(self.row_state.len() * more);
        self.row_kind.reserve(self.row_kind.len() * more);
    }

    fn push_row_ids(&mut self, n: usize, card: i64, entity: i64, state: usize) {
        self.push_row_ids_kind(n, card, entity, state, 0);
    }

    fn push_row_ids_kinds(&mut self, kinds: &[u8], card: i64, entity: i64, state: usize) {
        for &k in kinds {
            self.push_row_ids_kind(1, card, entity, state, k);
        }
    }

    fn push_row_ids_kind(&mut self, n: usize, card: i64, entity: i64, state: usize, kind: u8) {
        for _ in 0..n {
            self.row_card.push(card);
            self.row_entity.push(entity);
            self.row_state.push(state as i64);
            self.row_kind.push(kind);
        }
    }
}

/// A card's `ScaledDamage` total damage (amount × hits) resolved against
/// the state now, with `x` as the energy an X-cost card would spend (the
/// current energy, or the card in play's X).
fn expr_value(s: &CombatState, d: &CardDef, x: i16) -> f32 {
    let mut total = 0f32;
    for e in d.all_effects() {
        if let Effect::ScaledDamage { amount, hits, .. } = *e {
            let value = |a: Amount| match a.of {
                Some(Quantity::EnergySpent) => a.at(x),
                _ => s.resolve(Who::Player, a),
            };
            total += value(amount) as f32 * value(hits).max(0) as f32;
        }
    }
    total
}

/// A monster intent's attack effect in its `attack_shape` (a rolled attack
/// as a plain one); other effects unchanged.
fn split_effect(p: &Powers, slot: usize, e: Effect, rolled: i16) -> Effect {
    let who = Who::Monster(slot as u8);
    match e {
        Effect::Damage { amount, hits, target } => {
            let (amount, hits) = attack_shape(p, who, amount, hits);
            Effect::Damage { amount, hits, target }
        }
        Effect::RolledAttack => {
            let (amount, hits) = attack_shape(p, who, rolled, 1);
            Effect::Damage { amount, hits, target: Target::Opponent }
        }
        e => e,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Cards `PlayTop` took are written in the `playing` slot beside the
    /// card in play (docs/specs/act1-singles.md); with no queue the slot
    /// holds only the card in play, as before.
    #[test]
    fn queued_cards_are_playing() {
        use sts_engine::state::Queued;
        use sts_engine::{Encounter, Rng};
        let survivor = CardId::from_name("Survivor").unwrap();
        let mut s = CombatState::new(&sts_engine::starter_deck(), 80, 80, Encounter::JawWorm, &mut Rng::new(1));
        let e = Encoder::new(CardRepr::Effects, &Vocab::default());
        let playing = |b: &Batch| -> Vec<f32> { (0..b.card_pile.len()).filter(|&i| b.card_pile[i] == 4).map(|i| b.card_count[i]).collect() };
        assert!(playing(&e.encode(&[&s])).is_empty());
        s.top_queue.push(Queued { card: survivor, target: None, x: 0, exhaust: false });
        s.top_queue.push(Queued { card: survivor, target: None, x: 0, exhaust: true });
        assert_eq!(playing(&e.encode(&[&s])), vec![2.0]);
    }

    const FILE: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/data/card_vectors.txt");
    const ACT1: &str = include_str!("../../content/packs/act1-ironclad.json");

    /// One line per row: the non-zero columns by name.
    fn line(names: &[String], v: &[f32]) -> String {
        let cols: Vec<String> = v.iter().enumerate().filter(|(_, x)| **x != 0.0).map(|(i, x)| format!("{}={x}", names[i])).collect();
        cols.join(" ")
    }

    /// Every official card's and every Act 1 pack card's (and its
    /// upgrade's) effects-mode vector, hook rows and held rows, as text.
    fn dump() -> String {
        registry::load_pack(ACT1).unwrap();
        let e = Encoder::new(CardRepr::Effects, &Vocab::default());
        let (cn, rn) = (e.card_names(), e.row_names());
        let mut out = String::new();
        let mut card = |name: &str, c: CardId, d: &CardDef, bd: &Binding| {
            out.push_str(&format!("{name}\n  card {}\n", line(&cn, &e.card_vec(c, d, bd))));
            for r in e.card_hook_rows(d, bd) {
                out.push_str(&format!("  row {}\n", line(&rn, &r)));
            }
            for r in e.card_held_rows(d).chunks(e.row_dim()) {
                out.push_str(&format!("  held {}\n", line(&rn, r)));
            }
        };
        let official = Binding::default();
        for c in CardId::all() {
            card(c.name(), c, c.def(), &official);
        }
        let cards = &ACT1[ACT1.find("\"cards\": [").unwrap()..];
        let mut names: Vec<String> = cards.split("{\"id\": \"").skip(1).map(|s| format!("gen:{}", &s[..s.find('"').unwrap()])).collect();
        for n in names.clone() {
            if let Some(up) = registry::upgrade_name(&n).unwrap() {
                if !names.contains(&up) {
                    names.push(up);
                }
            }
        }
        for n in &names {
            let (ids, bd) = registry::bind(&[n.as_str()]).unwrap();
            card(n, ids[0], bd.def(ids[0]), &bd);
        }
        out
    }

    /// Pins every card's features (docs/specs/fractional-amounts.md step
    /// 1): an amount change must leave today's cards byte-identical.
    /// Re-record (only on unchanged features):
    /// `CARD_VECTORS_RECORD=1 cargo test -p sts-py card_vectors`.
    #[test]
    fn card_vectors_pinned() {
        let got = dump();
        if std::env::var("CARD_VECTORS_RECORD").is_ok() {
            std::fs::write(FILE, &got).unwrap();
        }
        let want = std::fs::read_to_string(FILE).expect("record with CARD_VECTORS_RECORD=1").replace("\r\n", "\n");
        assert!(got == want, "card features changed; first differing line: {:?}", got.lines().zip(want.lines()).find(|(a, b)| a != b));
    }
}
