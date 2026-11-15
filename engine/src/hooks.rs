//! Hook powers as data: each power kind maps to a const table of hooks, a
//! trigger, a condition and effect primitives. The state keeps only the
//! power's stacks; effect amounts in its hooks are per stack.

use crate::cards::{CardType, Tag};
use crate::effects::Effect;
use crate::powers::Power;

/// Whose action fires a hook, relative to the power's owner.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Side {
    Owner,
    Opponent,
}

/// What caused HP loss. As an event: `Attack` (unblocked attack damage:
/// the game's NORMAL damage with an owner), `Card` (HP loss the owner
/// causes itself, the game's `info.owner == owner`: its cards' and its own
/// powers' `LoseHp`, e.g. Bloodletting, Hemokinesis, Combust, and damage it
/// deals itself, Burn and Decay) or `Any` (anything else, such as Poison or
/// an opponent's thorns). As a hook's filter, `Any` matches every event.
/// The replacement passes see their own kinds (`Replaced`): Tungsten Rod's
/// `HpLossLast` and Buffer's `TakenAfterBlock` every loss, Torii's
/// `AttackedAfterBlock` only `Attack`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum HpLossFrom {
    Attack,
    Card,
    Any,
}

impl HpLossFrom {
    /// Whether a hook filtering on `self` fires for HP lost by `event`.
    pub fn matches(self, event: HpLossFrom) -> bool {
        self == HpLossFrom::Any || self == event
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Trigger {
    /// The owner's turn start, before the turn's draw (the game's
    /// `atStartOfTurn` / `atTurnStart`). In a version-1 content file this
    /// word means `OwnerTurnStartPostDraw` (docs/specs/turn-start-draw.md).
    OwnerTurnStart,
    /// The owner's turn start, after the turn's draw (the game's
    /// `atStartOfTurnPostDraw` / `atTurnStartPostDraw`: Demon Form,
    /// Brutality). A monster has no draw: both run in one pass.
    OwnerTurnStartPostDraw,
    OwnerTurnEnd,
    /// A card was played: a monster's hook fires before the card's effects
    /// (damage hooks after, `Hook::after_card`), the player's once the card
    /// has resolved (Rage; the game's `onUseCard` relics).
    CardPlayed { by: Side },
    /// The owner lost HP and lives.
    OwnerLostHp { from: HpLossFrom },
    /// The owner (a monster) reached 0 HP.
    OwnerDied,
    /// Once per round, after every monster's turn-end hooks: the player's,
    /// then each living monster's in slot order (debuff countdowns).
    RoundEnd,
    /// Every attack hit on the owner, blocked or not, after block and HP
    /// loss, unless the combat is over (Thorns). `Target::Attacker` is the
    /// attacker.
    OwnerAttacked,
    /// The owner plays a card, before its effects (the game's `onUseCard`
    /// timing: a power the card itself applies isn't there yet). Not for a
    /// replayed copy (Burst).
    OwnerPlaysCard,
    /// Each attack hit of the owner that made its target lose HP, unless
    /// the combat is over (Weak on hit; the game's Envenom timing). The hit
    /// target is the hook's `Target::Opponent`.
    OwnerAttackHit,
    /// The owner exhausted a card, from any pile or from play (the player
    /// only: monsters never exhaust). Fires once the card in play has been
    /// placed (or right after turn end's or turn start's hooks), once with
    /// the amounts multiplied by the number of cards exhausted since the
    /// last firing (the game queues the reaction behind the card). So its
    /// condition must be `Always` and its effects may not exhaust or pause
    /// (refused at load). A `Draw` at turn end is owed to the next turn's
    /// draw.
    CardExhausted,
    /// The owner drew a Status card (the player only, from any draw; cards
    /// put into the hand without a draw don't count). Fires once per card,
    /// where the stage machine next reaches the player's turn (the game
    /// queues the reaction at the bottom: after the draw and the card in
    /// play). Its condition must be `CardType Status` and its effects may
    /// not exhaust or pause other than `Draw` (refused at load).
    CardDrawn,
    /// The owner's HP went from above half its max HP to at most half
    /// (`2 × hp <= max_hp`), right after the HP change, before its
    /// `OwnerLostHp` reactions (the game's `onBloodied`, called where
    /// `damage` lowers HP: Red Skull). Not when the HP loss killed it.
    OwnerBloodied,
    /// A heal took the owner's HP from at most half its max HP to above
    /// (the game's `onNotBloodied`, in `heal`: Red Skull).
    OwnerUnbloodied,
    /// The player's, once, before the fight's opening draw (the game's
    /// `atBattleStartPreDraw`; docs/specs/relic-entity.md). A `Draw` joins
    /// the opening draw.
    CombatStartPreDraw,
    /// The player's, once, after the opening draw, before turn 1's
    /// post-draw and turn-start hooks (the game's `atBattleStart`).
    CombatStart,
    /// The player's, when a monster reaches 0 HP and some monster still
    /// lives, after that monster's `OwnerDied` hooks (the game's
    /// `onMonsterDeath` with `!areMonstersBasicallyDead()`: Gremlin Horn;
    /// docs/specs/fight-vocabulary.md).
    OpponentDied,
    /// The player's, once when the fight is won, before the combat-end heal
    /// (`AbstractRoom.endBattle` runs Meat on the Bone's `onTrigger` before
    /// `onVictory`; docs/specs/fight-vocabulary.md). Never on a loss or in
    /// no-death mode. Its effects heal or change a relic's counter only.
    CombatWon,
    /// The player's, when a power the player applied to another creature
    /// lands, after the replacements (Artifact's cancel means it didn't;
    /// the game's `ApplyPowerAction` with `!hasPower("Artifact")`: Champion
    /// Belt; docs/specs/act1-singles.md). `Target::Opponent` is that
    /// creature. Applications made by an `OwnerApplied` hook don't fire it
    /// again.
    OwnerApplied,
    /// The player's relics, each time the discard pile is shuffled into
    /// the draw pile (the game's `onShuffle`, called by
    /// `EmptyDeckShuffleAction`'s constructor; docs/specs/blocked-relics.md
    /// step 3): a draw that needs more cards than the draw pile holds
    /// (even with an empty discard pile), and once more when it needs more
    /// than both piles hold with a non-empty discard (the follow-up draw
    /// checks again); `PlayTop` on an empty draw pile; a non-empty
    /// `ShuffleDiscardIntoDraw` (Deep Breath). Fires at once, before the
    /// draw. Its effects are `Block`, `GainEnergy` and counter changes
    /// (checked at load: they may not draw or move cards).
    Shuffled,
    /// The player's, once a potion the player used has resolved, before
    /// its exhausts' reactions (the game's `onUsePotion`, called from
    /// `PotionPopUp` after `potion.use`: Toy Ornithopter). Not for a potion
    /// used up by a save (Fairy in a Bottle). When the potion ended the
    /// fight it still fires, after the combat-end heal (the game's
    /// `clearPostCombatActions` keeps a queued `HealAction`). Its effects
    /// heal or change a relic's counter only.
    OwnerUsedPotion,
    /// The player's (relics, then powers), once for each time damage that
    /// isn't HP loss broke a monster's block: the block was above 0 and the
    /// damage at least as much, an exact break included (the game's
    /// `brokeBlock`, called from `decrementBlock` for monsters only: Hand
    /// Drill; docs/specs/blocked-relics.md step 7). `Target::Opponent` is
    /// that monster. The game queues the reaction at the bottom, so it
    /// fires once the card or potion that dealt the damage has resolved
    /// (before its block-gain reactions and its exhausts'), else where the
    /// stage machine next settles: before the monsters' turn, after each
    /// monster's move, before the round's end, at the player's turn. Not
    /// for a monster dead by then.
    OpponentBlockBroken,
    /// The player's, whenever the player's turn settles (nothing left to
    /// resolve, no pick open, the turn not ended) with an empty hand and a
    /// card in the draw or discard pile (the game's `onRefreshHand`:
    /// Unceasing Top). It fires again each time the turn settles so, until
    /// the hand holds a card; a pass that leaves the hand empty and nothing
    /// pending settles the turn.
    OwnerHandEmpty,
    /// The player's (relics, then powers), each time the player gains
    /// block above 0, after Dexterity, Frail and the other modifiers, from
    /// any source (a card, a power's or relic's hook, a potion, Entrench's
    /// doubling), before the block is added (the game's `onGainedBlock`,
    /// called from `addBlock` for the player only: Juggernaut). Block kept
    /// at turn start isn't gained. A gain inside its own hooks doesn't
    /// fire it again.
    OwnerGainedBlock,
}

impl Trigger {
    /// Either turn-start trigger (before or after the draw).
    #[inline]
    pub fn is_turn_start(self) -> bool {
        matches!(self, Trigger::OwnerTurnStart | Trigger::OwnerTurnStartPostDraw)
    }
}

/// An event a replacement row can change (replacement-hooks spec).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Replaced {
    /// Any damage the owner takes, attack or not: after the damage
    /// pipeline, before block.
    DamageTaken,
    /// HP loss that ignores block (`LoseHp`, Poison).
    HpLoss,
    /// A debuff about to land on the owner.
    DebuffApplied,
    /// The after-block passes (docs/specs/after-block.md), in this order
    /// once block is removed, each while the amount is above 0, as the
    /// game's `damage`: the attack damage the owner deals, read from the
    /// attacker (`onAttackToChangeDamage`: The Boot).
    DealtAfterBlock,
    /// Any damage or HP loss reaching the owner (`onAttackedToChangeDamage`:
    /// Buffer).
    TakenAfterBlock,
    /// Attack damage reaching the owner (`onAttacked`: Torii).
    AttackedAfterBlock,
    /// Any damage or HP loss, last (`onLoseHpLast`: Tungsten Rod).
    HpLossLast,
    /// Cards the owner would draw, checked when the draw is requested
    /// (`DrawCardAction`'s `"No Draw"` check: Battle Trance).
    Draw,
}

impl Replaced {
    /// The after-block passes, in the order they run.
    pub const AFTER_BLOCK: [Replaced; 4] =
        [Replaced::DealtAfterBlock, Replaced::TakenAfterBlock, Replaced::AttackedAfterBlock, Replaced::HpLossLast];

    /// Whether the event is one of the after-block passes.
    #[inline]
    pub fn after_block(self) -> bool {
        Replaced::AFTER_BLOCK.contains(&self)
    }
}

/// What a replacement row does to its event.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Replace {
    /// The event doesn't happen.
    Cancel,
    /// The amount becomes at most `n`.
    Cap(i16),
    /// `n` is added to the amount (no content yet).
    Add(i16),
    /// The amount is multiplied by `num / den`, rounded down (no content yet).
    Multiply(i16, i16),
    /// An amount below `n` becomes `n` (The Boot; docs/specs/after-block.md).
    AtLeast(i16),
}

/// "If X would happen to the owner, do Y instead": a replacement row.
/// `then` runs on the owner when the row applies (Artifact's `ReduceSelf`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Replacement {
    pub event: Replaced,
    /// A `DebuffApplied` replacement's filter: it acts only on this power
    /// being applied, and before every unfiltered one (the game checks
    /// Ginger and Turnip before Artifact, `ApplyPowerAction.java` ~132;
    /// docs/specs/fight-vocabulary.md). `None`: every debuff.
    pub power: Option<Power>,
    /// The row applies only to an amount of at most this (`"upTo"`: Torii's
    /// 5; docs/specs/after-block.md). `None`: any amount.
    pub up_to: Option<i16>,
    pub action: Replace,
    pub then: &'static [Effect],
}

/// Checked when a hook fires or a card effect row is reached.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Condition {
    Always,
    /// The played card is of this type.
    CardType(CardType),
    TargetIntendsAttack,
    TargetHas(Power),
    CardsPlayedThisTurnBelow(u8),
    /// Every card in the player's hand is of this type (a card's
    /// `playable_if`: Clash, docs/specs/card-rules.md).
    HandAll(CardType),
    /// The hook's owner has at most half its max HP (`2 × hp <= max_hp`;
    /// Red Skull's start check, docs/specs/red-skull-strength.md).
    OwnerHpAtMostHalf,
    /// The hook's relic's counter is `n` (docs/specs/relic-entity.md);
    /// false in a power's hook or a card row.
    CounterIs(i16),
    /// The hook's owner has exactly `n` block (Orichalcum,
    /// docs/specs/fight-vocabulary.md).
    OwnerBlockIs(i16),
    /// The power being applied is this one (an `OwnerApplied` hook's only;
    /// refused at load anywhere else: docs/specs/act1-singles.md).
    Applying(Power),
    /// No card of this type is in the player's hand, the card in play
    /// already gone from it (Impatience; the game's `ConditionalDrawAction`).
    HandNone(CardType),
    /// The chosen target holds none of this power (Dark Shackles: Artifact).
    TargetLacks(Power),
    /// The power being applied is a debuff, or a `debuff_if_negative` one
    /// with a negative amount (an `OwnerApplied` hook's only: Sadistic
    /// Nature, docs/specs/colorless-cards.md).
    ApplyingDebuff,
    /// The chosen target is dead, killed by the card or potion in play,
    /// and was not a minion or half dead (the game's on-kill actions
    /// `FeedAction`, `GreedAction`, `RitualDaggerAction`,
    /// `LessonLearnedAction`: `isDying || currentHealth <= 0`, `!halfDead`,
    /// no `Minion` power; Defect's `SunderAction` skips the last two and
    /// would need its own condition). An escaped monster isn't dead. The engine
    /// summons no minions and has no half-dead monsters (no revive), so
    /// every dead target counts; a summon or revive must fail it here.
    TargetDied,
    /// The hook's relic's counter is at most `n` (Pocketwatch's 3 cards
    /// played); false in a power's hook or a card row.
    CounterAtMost(i16),
    /// It isn't the combat's first turn (`turn > 1`; Pocketwatch's
    /// `firstTurn`, cleared at the first turn's post-draw).
    NotFirstTurn,
}

/// The number a static modifier changes, from its owner's side.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Modifies {
    /// The owner's attack damage.
    DamageDealt,
    /// Attack damage the owner takes.
    DamageTaken,
    /// Block the owner gains from cards (Dexterity, Frail; the player only).
    BlockGained,
}

/// Where a static sits in the damage pipeline: base, adds, multiplies,
/// round down once (spec 5 adds replacements, then block).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum StaticStage {
    /// `amount` per stack.
    Add,
    /// `num / den`, while the power has stacks.
    Multiply,
}

/// When a static applies.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum StaticCondition {
    Always,
    /// The attack comes from a card in play carrying the tag (Accuracy: Shivs).
    CardInPlayTagged(Tag),
    /// The owner's HP is at most half its max HP (Red Skull).
    OwnerHpAtMostHalf,
    /// The owner (`Owner`) or the other creature of the attack (`Opponent`:
    /// the target of a `DamageDealt` row, the attacker of a `DamageTaken`
    /// row) holds `power` with stacks above 0 (Paper Phrog, Odd Mushroom:
    /// Vulnerable). `Opponent` is false with no other creature (shown
    /// damage, block).
    Holds { side: Side, power: Power },
}

/// "While the power exists, change this number": a static modifier row.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Static {
    pub modifies: Modifies,
    pub stage: StaticStage,
    pub amount: i16,
    pub num: i16,
    pub den: i16,
    pub condition: StaticCondition,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Hook {
    pub trigger: Trigger,
    pub condition: Condition,
    /// A second condition that must hold too (`Always` for a hook written
    /// with one; docs/specs/fight-vocabulary.md: Pen Nib).
    pub also: Condition,
    /// `Me` is the power's owner. Effects run in their written order, each
    /// multiplied by the power's stacks at that moment (after any earlier
    /// `ReduceSelf`); `RemoveSelf` and `ReduceSelf` act on that power, and
    /// once it is gone the rest of its hooks do nothing this pass.
    /// On the player's powers, `Block` is raw block (the game's
    /// GainBlockAction): Dexterity and Frail don't apply.
    pub effects: &'static [Effect],
    /// The source of the HP its `LoseHp` effects take (`hp_loss_source`):
    /// `Card` by default (the owner's own loss: Combust, Brutality), `Any`
    /// for a loss someone else caused (Poison).
    pub hp_loss: HpLossFrom,
    /// `acts_first`: on a hook the game queues in one pass with others
    /// (`OwnerTurnEnd`, `RoundEnd`; checked at load), the hook acts before
    /// the hooks its pass ran earlier (the game's `addToTop`: Regeneration
    /// heals before Combust's HP loss). Such hooks act last-called first,
    /// then the rest in order. The game's passes: the player's two End
    /// Turn passes (`before_hand`), each its relics' hooks then its
    /// powers'; every monster's `OwnerTurnEnd` with the round's `RoundEnd`
    /// (the player's, then the monsters').
    pub first: bool,
    /// `before_hand`: on the player's `OwnerTurnEnd` hooks, the stage of
    /// End Turn the hook acts in (checked at load: `OwnerTurnEnd` only).
    /// The game's End Turn: the relics' `onPlayerEndTurn` and the powers'
    /// `atEndOfTurnPreEndTurnCards` (Metallicize, Plated Armor) in one
    /// queued pass (`before_hand`), then the hand's turn-end cards (Burn,
    /// Decay, Regret), then the powers' `atEndOfTurn` (Combust,
    /// Regeneration) in a second pass, then the discard. A relic's
    /// `OwnerTurnEnd` hook is `before_hand` unless its row says otherwise
    /// (`onPlayerEndTurn` is a relic's only turn-end call); a power's is
    /// not. A monster's powers call both in one pass, so it has no effect
    /// there.
    pub before_hand: bool,
}

use Trigger::*;

impl Hook {
    /// A monster's `CardPlayed by Opponent` hook that deals damage fires
    /// once the card has resolved, not before it (Sharp Hide: the game
    /// queues it behind the card, so Iron Wave's block comes first and a
    /// card that kills the owner takes no damage back).
    pub fn after_card(&self) -> bool {
        self.trigger == CardPlayed { by: Side::Opponent }
            && self.effects.iter().any(|e| matches!(e, Effect::Damage { .. } | Effect::PlainDamage { .. }))
    }
}

/// The hooks of a power kind; for built-in modifiers at most their
/// `RoundEnd` countdown.
#[inline]
pub fn hooks(p: Power) -> &'static [Hook] {
    crate::registry::official().powers.get(p as usize).map_or(&[], |o| o.hooks)
}

/// The official powers with a `RoundEnd` hook (a test checks the list), so
/// the round's end skips entities holding none of them.
pub const ROUND_END_POWERS: [Power; 4] = [Power::Vulnerable, Power::Weak, Power::Frail, Power::Intangible];

/// The official powers with an `OwnerAttacked` hook (a test checks the
/// list), so an attack hit skips the hook scan when the target holds none.
pub const ATTACKED_POWERS: [Power; 1] = [Power::Thorns];

/// The official powers with an `OwnerAttackHit` hook (a test checks the
/// list), so a hit skips the attacker's hook scan when it holds none.
pub const ATTACK_HIT_POWERS: [Power; 1] = [Power::WeakOnHit];

/// The powers with replacement rows, which the engine reads at play time.
pub const REPLACEMENT_POWERS: [Power; 2] = [Power::Artifact, Power::Intangible];

/// The replacement rows of a power kind; empty for most.
#[inline]
pub fn replacements(p: Power) -> &'static [Replacement] {
    crate::registry::official().powers.get(p as usize).map_or(&[], |o| o.replacements)
}


/// The powers whose statics the engine reads from these rows at play
/// time; the built-in modifiers' statics are hard-coded in
/// `attack_damage` / `gain_block` (a test checks the code equals the rows).
pub const GENERIC_STATICS: [Power; 2] = [Power::Accuracy, Power::DamageDown];

/// The static modifier rows of a power kind; empty for most.
#[inline]
pub fn statics(p: Power) -> &'static [Static] {
    crate::registry::official().powers.get(p as usize).map_or(&[], |o| o.statics)
}
