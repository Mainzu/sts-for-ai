//! Effect primitives shared by cards and monster moves.

use crate::cards::{CardId, CardType, Tag};
use crate::powers::Power;

/// A state number an amount can read (a closed vocabulary).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Quantity {
    /// The user's block (Body Slam).
    OwnBlock,
    /// The user's Strength stacks (Heavy Blade).
    OwnStrength,
    /// The X of the X-cost card in play: the energy it spent (Whirlwind).
    EnergySpent,
    /// Cards with the tag in hand, draw and discard, plus the card in play
    /// if it has it (Perfected Strike).
    CardsTagged(Tag),
    /// Cards in hand, or those not of type `except` (Second Wind, Fiend
    /// Fire); the card in play is not in hand.
    HandCards { except: Option<CardType> },
    /// The user's max HP (Blood Potion's heal: `k` 1/5).
    OwnMaxHp,
    /// Cards in the player's draw pile (Mind Blast); the card in play is
    /// not in it.
    DrawPileSize,
    /// Cards of the type in hand, draw and discard, plus the card in play
    /// if it is one (Du-Vu Doll's curses, read at `CombatStart`: the
    /// combat's deck; docs/specs/blocked-relics.md step 6).
    CardsOfType(CardType),
    /// The HP the user's latest damage effect took from its targets,
    /// summed over targets and hits, each hit capped at its target's HP
    /// (the game's `lastDamageTaken`: Reaper's heal).
    HpDealt,
}

/// `base + trunc(k × quantity / per)`, a constant when `of` is `None`.
/// `per` is at least 1 (1 for a whole `k`); the division truncates toward
/// zero, as the game's `(int)` cast does (docs/specs/fractional-amounts.md).
/// Debug leaves `per` out when it is 1, so dumps and fingerprints of whole
/// amounts read as before.
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
pub struct Amount {
    pub base: i16,
    pub k: i16,
    pub per: i16,
    pub of: Option<Quantity>,
}

impl Amount {
    pub const fn constant(n: i16) -> Amount {
        Amount { base: n, k: 0, per: 1, of: None }
    }

    pub const fn of(base: i16, k: i16, q: Quantity) -> Amount {
        Amount { base, k, per: 1, of: Some(q) }
    }

    /// `base + k/per × q`, the fraction in lowest terms with its sign on
    /// top; `None` if `per` is 0.
    pub fn frac(base: i16, k: i16, per: i16, q: Quantity) -> Option<Amount> {
        let (k, per) = lowest(k as i32, per as i32)?;
        Some(Amount { base, k: k as i16, per: per as i16, of: Some(q) })
    }

    /// `base` and `k` multiplied by `n`; `per` kept.
    pub const fn times(self, n: i16) -> Amount {
        Amount { base: self.base * n, k: self.k * n, per: self.per, of: self.of }
    }

    /// The value with the quantity at `q`: `base + trunc(k × q / per)`, in
    /// 32 bits.
    pub fn at(self, q: i16) -> i16 {
        self.base + ((self.k as i32 * q as i32) / self.per as i32) as i16
    }

    /// `k / per`, for estimates and net columns (exactly `k` when `per` is 1).
    pub fn kf(self) -> f32 {
        self.k as f32 / self.per as f32
    }
}

impl std::fmt::Debug for Amount {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let mut d = f.debug_struct("Amount");
        d.field("base", &self.base).field("k", &self.k);
        if self.per != 1 {
            d.field("per", &self.per);
        }
        d.field("of", &self.of).finish()
    }
}

/// `a/b` in lowest terms with the sign on top; `None` if `b` is 0.
pub fn lowest(a: i32, b: i32) -> Option<(i32, i32)> {
    if b == 0 {
        return None;
    }
    let (mut x, mut y) = (a.unsigned_abs(), b.unsigned_abs());
    while y != 0 {
        (x, y) = (y, x % y);
    }
    let g = x.max(1) as i32;
    let s = if b < 0 { -1 } else { 1 };
    Some((s * a / g, s * b / g))
}

/// Who an effect hits, relative to whoever uses it.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Target {
    /// The chosen enemy for a player card; the player for a monster move.
    Opponent,
    /// Every living enemy for a player card; the player for a monster move.
    AllOpponents,
    /// Whoever uses the effect.
    Me,
    /// The attacker, in an `OwnerAttacked` hook: the attacking monster for
    /// the player's hook, the player for a monster's.
    Attacker,
    /// One living enemy picked at random when the hit is paid, a chance
    /// event while more than one lives; the player for a monster. Only on
    /// `PlainDamage` (checked at load): the game's `DamageRandomEnemyAction`
    /// with a THORNS hit (Juggernaut; docs/specs/ironclad-last-four.md).
    RandomOpponent,
}

/// A player pile that cards can be added to.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum PileKind {
    /// Shuffled in: the draw pile is unordered, so this is just an add.
    Draw,
    Discard,
    /// Into the hand; copies past the hand limit go to the discard pile
    /// (Blade Dance's Shivs).
    Hand,
}

/// What a pick does with the chosen card (decision-points spec): a closed,
/// engine-owned set.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum PickKind {
    /// From hand to the discard pile (Survivor).
    DiscardFromHand,
    /// From the discard pile into hand (Hologram); no pick while the hand is full.
    ReturnFromDiscard,
    /// From the discard pile onto the top of the draw pile, known (Headbutt).
    DiscardToTop,
    /// From hand to the exhaust pile (Burning Pact, True Grit+).
    ExhaustFromHand,
    /// From the exhaust pile into hand (Exhume); no pick while the hand is
    /// full, and never a card that itself returns from the exhaust pile.
    ReturnFromExhaust,
    /// Upgrade a card in hand that a general upgrade can raise (Armaments).
    UpgradeFromHand,
    /// Take one of the cards a `Discover` offers (`CombatState::offer`;
    /// docs/specs/discovery.md). Engine-internal: no content names it.
    Offered,
    /// From hand onto the top of the draw pile, known (Warcry, Thinking
    /// Ahead; the game's `PutOnDeckAction`). A card's pick of `n` with at
    /// most `n` cards of one kind in hand moves them at once.
    HandToTop,
    /// A card in hand stays and the hand gains the pick's `copies` copies
    /// of it, past the hand limit into the discard pile (Dual Wield, the
    /// game's `DualWieldAction`). One eligible card is copied at once.
    CopyInHand,
    /// From the draw pile into hand, the discard pile when the hand is full
    /// (Secret Technique, Secret Weapon: the game's
    /// `SkillFromDeckToHandAction`, `AttackFromDeckToHandAction`). Any
    /// copy of the chosen kind goes alike (`ChanceEvent::DrawInstance`).
    DrawToHand,
}

/// A set of card types: the cards a pick may take (`Effect::Pick`'s `of`).
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
pub struct Types(pub u8);

impl Types {
    pub const ALL: Types = Types(0b1_1111);

    pub fn has(self, t: CardType) -> bool {
        self.0 & 1 << t as u8 != 0
    }

    pub fn of(types: &[CardType]) -> Types {
        Types(types.iter().fold(0, |m, &t| m | 1 << t as u8))
    }

    /// The types in it, in `CardType` order.
    pub fn types(self) -> Vec<CardType> {
        [CardType::Attack, CardType::Skill, CardType::Power, CardType::Status, CardType::Curse].into_iter().filter(|&t| self.has(t)).collect()
    }
}

/// `All`, or the types it holds.
impl std::fmt::Debug for Types {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        if *self == Types::ALL { f.write_str("All") } else { self.types().fmt(f) }
    }
}

/// Which cards a `RandomizeCost` rolls.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum CostRoll {
    Hand,
    Drawn,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Effect {
    /// Attack damage: Strength, Weak and Vulnerable apply; block absorbs it.
    Damage { amount: i16, hits: u8, target: Target },
    /// Non-attack damage (Combust): Strength, Weak and Vulnerable don't
    /// apply; block absorbs it.
    PlainDamage { amount: i16, target: Target },
    /// An attack whose amount or hit count reads the state (Body Slam,
    /// Heavy Blade, Perfected Strike, Whirlwind); resolved when it runs,
    /// then dealt like `Damage`. At most one of the two reads a quantity.
    ScaledDamage { amount: Amount, hits: Amount, target: Target },
    /// `hits` attacks, each on a random living enemy (Sword Boomerang).
    /// Each hit is a chance event while more than one enemy lives.
    RandomDamage { amount: i16, hits: u8 },
    /// `hits` applications of a power, each on a random living enemy
    /// (Bouncing Flask). Each is a chance event while more than one enemy lives.
    RandomApply { power: Power, amount: i16, hits: u8 },
    /// Monster attack whose damage was rolled at the start of combat (louse Bite).
    RolledAttack,
    /// Block for the user (Dexterity and Frail apply for the player).
    Block(i16),
    /// Monster moves only (Shield Gremlin's Protect): block for a uniformly
    /// random other living monster not showing an Escape move, the user
    /// itself when there is none (the game's `GainBlockRandomMonsterAction`).
    /// It lands when the move runs, before any later monster acts; two or
    /// more candidates pause the monsters' turn on the pick
    /// (`Stage::MonsterActing`, `ChanceEvent::AllyBlock`).
    BlockAlly(i16),
    /// Block by an amount read when it runs (Entrench), gained as is:
    /// no Dexterity or Frail; nothing when it resolves to 0 or less.
    BlockOf(Amount),
    /// `amount` block gained `times` times, each like `Block` (Second Wind).
    ScaledBlock { amount: i16, times: Amount },
    /// Every card in the player's hand, or every one not of type `except`,
    /// goes to the exhaust pile (Second Wind, Sever Soul, Fiend Fire).
    ExhaustHand { except: Option<CardType> },
    /// One uniformly random card in hand (by copies) goes to the exhaust
    /// pile (True Grit): a chance event while the hand holds two distinct cards.
    ExhaustRandom,
    /// One uniformly random card in hand (by copies) costing above 0 this
    /// turn, else one costing above 0 for the combat, costs 0 for the
    /// combat and loses its this-turn mark (Madness, the game's
    /// `MadnessAction`): a chance event while two distinct cards qualify.
    ZeroCostRandom,
    /// Player draws cards (a chance event when the result is uncertain).
    Draw(u8),
    /// Each card in hand (`Hand`: Snecko Oil) or the card just drawn
    /// (`Drawn`, only in a `CardDrawn` hook with condition `Always`:
    /// Confused) whose cost is 0 or more gets a random cost 0-3 for the
    /// combat, one chance event per card (the game's
    /// `RandomizeHandCostAction` and `ConfusionPower.onCardDraw`;
    /// docs/specs/sparse-piles.md). A roll equal to its cost changes nothing.
    RandomizeCost(CostRoll),
    GainEnergy(i8),
    /// HP loss that ignores block.
    LoseHp(i16),
    /// `LoseHp` by an amount read when it runs (Regret: the hand's cards);
    /// nothing when it resolves to 0 or less.
    LoseHpOf(Amount),
    /// HP gained by its user, never above max HP.
    Heal(i16),
    /// `Heal` by an amount read when it runs (Blood Potion: 1/5 of
    /// `OwnMaxHp`); nothing when it resolves to 0 or less.
    HealOf(Amount),
    /// Raises the player's combat-end heal (`CombatState::win_heal`) by
    /// this many HP: Self Repair, combat-end healing relics. From a monster
    /// it does nothing.
    WinHeal(i16),
    /// Each target's HP becomes at most `amount` + max HP x `num` / `den`
    /// (rounded down), by a direct write: no HP-loss hooks, no bloodied,
    /// no block (the game's `currentHealth` field write: Preserved Insect
    /// 0 + 3/4, Neow's Lament 1 + 0/1). Never below 1.
    CapHp { amount: i16, num: i16, den: i16, target: Target },
    /// Raises the user's max HP and HP by this many (the game's
    /// `increaseMaxHp(n, true)`: Fruit Juice; docs/specs/fight-vocabulary.md).
    GainMaxHp(i16),
    /// Draws as many cards as the `Pick` just before it in the same row
    /// took (Gambler's Brew, Gambling Chip; docs/specs/fight-vocabulary.md):
    /// the chosen cards are discarded first, then all drawn in one draw.
    /// The count is the stage's `hit` at this effect.
    DrawPicked,
    Apply { power: Power, amount: i16, target: Target },
    /// `Apply` of a pack power by registry index, bound to the fight's slot
    /// when it runs (a pack monster's move: Red Slaver's Entangle).
    ApplyPack { power: u16, amount: i16, target: Target },
    /// `Apply` by an amount read when it runs (Limit Break); nothing when
    /// it resolves to 0.
    ApplyOf { power: Power, amount: Amount, target: Target },
    /// `Apply` as a monster's application: a power new on its target skips
    /// the end of the round it lands in, as `skips_first_round` lets a
    /// monster's debuff (the game's `isSourceMonster` flag: Doubt's Weak,
    /// Shame's Frail at the player's turn end; a Vulnerable or NoBlock
    /// applied there ticks, as the player's turn hasn't ended).
    ApplyAsMonster { power: Power, amount: i16, target: Target },
    /// Adds `n` copies of a card to a player pile; to the draw pile each at
    /// a random spot under the top card (the game's `addToRandomSpot`).
    AddCard { card: CardId, n: u8, pile: PileKind },
    /// `AddCard` of the card it is on, at its level (Necronomicurse's copy
    /// on exhaust): only in a card's `exhausted`.
    AddCopy { n: u8, pile: PileKind },
    /// The monster disappears and its kind's two children appear with its
    /// current HP (slimes).
    Split,
    /// The monster leaves combat (Looter).
    Escape,
    /// Removes the power whose hook this is.
    RemoveSelf,
    /// Lowers the stacks of the power whose hook this is (Poison's countdown).
    ReduceSelf(i16),
    /// The card pauses for the player to pick `n` cards (`exact`: the pick
    /// ends by itself after `n`; otherwise `Done` is offered at every step).
    /// Skipped when there is nothing to pick. `free`: each card it puts
    /// into the hand costs 0 this turn (`free_this_turn`; Liquid Memories,
    /// docs/specs/act1-singles.md). `of`: only cards of these types can
    /// be picked (Dual Wield: Attacks and Powers). `copies`: a
    /// `CopyInHand` pick's copies per card (0 for every other kind).
    Pick { kind: PickKind, n: u8, exact: bool, free: bool, of: Types, copies: u8 },
    /// Takes the top `n` cards of the draw pile (reshuffling the discard
    /// pile in when it runs out), each with a random living enemy as its
    /// target, and plays them once the card or potion in play has finished:
    /// free, counted as played, an X-cost card at the energy when taken; a
    /// card that can't be played then goes to the discard pile unplayed.
    /// `exhaust`: each exhausts instead (Havoc). The game's
    /// `PlayTopCardAction` (Distilled Chaos, Havoc;
    /// docs/specs/act1-singles.md).
    PlayTop { n: u8, exhaust: bool },
    /// In a hook: the card in play is played once more after it resolves
    /// (Burst).
    ReplayCard,
    /// The card in play's own damage grows by this, for the combat
    /// (Rampage): it becomes a variant of its card.
    GrowDamage(i16),
    /// Every card in hand that a general upgrade can raise is upgraded,
    /// once each (Armaments+).
    UpgradeHand,
    /// Every card in hand, draw, discard and exhaust pile that a general
    /// upgrade can raise is upgraded, once each; the card in play is in
    /// none of them; known-top and floater ids follow (Apotheosis, the
    /// game's `ApotheosisAction`).
    UpgradeAll,
    /// With a non-empty discard pile: it joins the draw pile, which is
    /// reshuffled whole, so the known top and floaters are forgotten
    /// (Deep Breath: `EmptyDeckShuffleAction` then `ShuffleAction`).
    /// Nothing with an empty discard pile. A non-empty one fires the
    /// relics' `Trigger::Shuffled` (the game's `onShuffle`).
    ShuffleDiscardIntoDraw,
    /// Every power the actor holds that is a debuff at its stacks
    /// (`PowerRules::is_debuff`, the test `apply_power` uses) is removed
    /// (Orange Pellets: the game's `RemoveDebuffsAction`, every power of
    /// type `DEBUFF`; removing Flex's LoseStrength keeps the Strength).
    RemoveDebuffs,
    /// In a relic's hook: its own counter becomes `n`
    /// (docs/specs/relic-entity.md; a load error anywhere else).
    SetCounter(i16),
    /// In a relic's hook: `n` is added to its own counter (scaled like any
    /// amount, e.g. per card a `CardExhausted` pass counts).
    AddCounter(i16),
    /// `offer` different random cards of pool `pool` (`registry::pool_def`),
    /// only those of type `ty` when given, as a chance event; the player
    /// takes one (or none, `Done`, when `skip`) and `copies` copies go into
    /// hand, past the hand limit into the discard pile, costing 0 this turn
    /// when `free` (Attack Potion, Infernal Blade; docs/specs/discovery.md).
    Discover { pool: u8, ty: Option<CardType>, offer: u8, copies: u8, free: bool, skip: bool },
    /// `n` independent uniform rolls of pool `pool` (only type `ty` when
    /// given; repeats allowed), each a chance event, run only by a card in
    /// play (docs/specs/colorless-cards.md step 3). Each card goes to
    /// `pile`: the hand (past the hand limit the discard pile), or the draw
    /// pile at a random spot that is never the top (the game's
    /// `addToRandomSpot`: under the top card whenever the pile held any,
    /// known or not). `zero_cost`: costs 0 for the combat when its
    /// cost is above 0 (Chrysalis); `free`: costs 0 this turn
    /// (Transmutation); `match_level`: upgraded when the card in play is.
    MakeRandom { pool: u8, ty: Option<CardType>, n: Amount, pile: PileKind, zero_cost: bool, free: bool, match_level: bool },
    /// In a potion: one random potion of potion pool `pool`
    /// (`potions::potion_pool`) per empty potion slot, each a chance event
    /// (Entropic Brew; docs/specs/act1-singles.md section 5).
    ObtainRandomPotions { pool: u8 },
    /// One uniformly random card in hand (by copies) costing above 0 this
    /// turn and not marked costs 0 this turn (Mummified Hand, the game's
    /// `setCostForTurn(0)` on a card with `cost > 0`, `costForTurn > 0`);
    /// nothing when none qualifies: a chance event while two distinct
    /// cards qualify (docs/specs/blocked-relics.md step 5).
    ZeroCostRandomTurn,
    /// One uniformly random card in hand (by copies) that a general upgrade
    /// can raise is upgraded for the combat (Warped Tongs, the game's
    /// `UpgradeRandomCardAction`); nothing when none can be: a chance event
    /// while two distinct copies (a mark tells copies apart) qualify.
    UpgradeRandom,
    /// Every card in hand (not X-cost or unplayable) that costs more than
    /// `cost` this turn costs `cost` this turn (Enlightenment, the game's
    /// `EnlightenmentAction`: `costForTurn` capped); with `combat`, every
    /// one whose own cost is above `cost` costs `cost` for the combat too,
    /// keeping its mark. No chance.
    CostAtMost { cost: i8, combat: bool },
    /// Up to `n` random draw pile cards of type `ty` leave it (every copy
    /// alike, without replacement): the first ones for the hand while it has
    /// room, the rest for the discard pile (Violence, the game's
    /// `DrawPileToHandAction`). A chance event while the result is not one
    /// state.
    TakeRandomFromDraw { ty: CardType, n: u8 },
}

impl Effect {
    /// The effect with its amounts multiplied by `k` (a power's stacks).
    pub fn scaled(self, k: i16) -> Effect {
        match self {
            Effect::Damage { amount, hits, target } => Effect::Damage { amount: amount * k, hits, target },
            Effect::PlainDamage { amount, target } => Effect::PlainDamage { amount: amount * k, target },
            Effect::Block(n) => Effect::Block(n * k),
            Effect::ScaledBlock { amount, times } => Effect::ScaledBlock { amount: amount * k, times },
            Effect::Draw(n) => Effect::Draw(n * k as u8),
            Effect::GainEnergy(n) => Effect::GainEnergy(n * k as i8),
            Effect::LoseHp(n) => Effect::LoseHp(n * k),
            Effect::Heal(n) => Effect::Heal(n * k),
            Effect::WinHeal(n) => Effect::WinHeal(n * k),
            Effect::GainMaxHp(n) => Effect::GainMaxHp(n * k),
            Effect::AddCounter(n) => Effect::AddCounter(n * k),
            Effect::Discover { pool, ty, offer, copies, free, skip } => Effect::Discover { pool, ty, offer, copies: copies * k as u8, free, skip },
            Effect::Apply { power, amount, target } => Effect::Apply { power, amount: amount * k, target },
            Effect::ApplyAsMonster { power, amount, target } => Effect::ApplyAsMonster { power, amount: amount * k, target },
            Effect::LoseHpOf(a) => Effect::LoseHpOf(a.times(k)),
            Effect::BlockOf(a) => Effect::BlockOf(a.times(k)),
            Effect::HealOf(a) => Effect::HealOf(a.times(k)),
            Effect::ApplyOf { power, amount, target } => Effect::ApplyOf { power, amount: amount.times(k), target },
            e => e,
        }
    }

    pub fn target(&self) -> Option<Target> {
        match *self {
            Effect::Damage { target, .. }
            | Effect::PlainDamage { target, .. }
            | Effect::Apply { target, .. }
            | Effect::ApplyAsMonster { target, .. }
            | Effect::ApplyOf { target, .. }
            | Effect::ScaledDamage { target, .. }
            | Effect::CapHp { target, .. } => Some(target),
            Effect::RolledAttack => Some(Target::Opponent),
            _ => None,
        }
    }
}
