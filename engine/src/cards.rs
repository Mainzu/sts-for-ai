//! Cards as data: a cost, a few flags and a list of effect primitives.
//! An upgrade is a second definition, not code.

use crate::effects::{Effect, Target};
use crate::hooks::Condition;
use crate::upgrade::{Keyword, Parts, Upgrade};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
#[repr(u8)]
pub enum CardKind {
    Strike,
    Defend,
    Bash,
    ShrugItOff,
    Wound,
    Anger,
    BodySlam,
    Clash,
    Cleave,
    Clothesline,
    IronWave,
    PommelStrike,
    Thunderclap,
    TwinStrike,
    WildStrike,
    HeavyBlade,
    PerfectedStrike,
    SwordBoomerang,
    Bloodletting,
    Hemokinesis,
    Pummel,
    Uppercut,
    Inflame,
    Flex,
    Carnage,
    Slimed,
    Dazed,
    // The Silent's cards (Amendment 2), after every Ironclad one so the
    // earlier card ids keep their numbers.
    SilentStrike,
    SilentDefend,
    Neutralize,
    SuckerPunch,
    LegSweep,
    QuickSlash,
    Backflip,
    Deflect,
    Slice,
    DaggerSpray,
    BladeDance,
    CloakAndDagger,
    Shiv,
    DeadlyPoison,
    PoisonedStab,
    BouncingFlask,
    // Triggers and conditions: conditional cards, after every earlier one.
    SpotWeakness,
    Dropkick,
    GoForTheEyes,
    Ftl,
    // Triggers and conditions: power cards built from hooks.
    Combust,
    Brutality,
    Rupture,
    Metallicize,
    DemonForm,
    Rage,
    // Act-1 bosses: Hexaghost's status card.
    Burn,
    // Rules-engine proving content (the `proving` card set), after every earlier one.
    Whirlwind,
    Accuracy,
    WraithForm,
    Caltrops,
    Survivor,
    Burst,
    Hologram,
    Headbutt,
    Rampage,
    Protect,
}

impl CardKind {
    pub const ALL: [CardKind; 64] = [
        CardKind::Strike,
        CardKind::Defend,
        CardKind::Bash,
        CardKind::ShrugItOff,
        CardKind::Wound,
        CardKind::Anger,
        CardKind::BodySlam,
        CardKind::Clash,
        CardKind::Cleave,
        CardKind::Clothesline,
        CardKind::IronWave,
        CardKind::PommelStrike,
        CardKind::Thunderclap,
        CardKind::TwinStrike,
        CardKind::WildStrike,
        CardKind::HeavyBlade,
        CardKind::PerfectedStrike,
        CardKind::SwordBoomerang,
        CardKind::Bloodletting,
        CardKind::Hemokinesis,
        CardKind::Pummel,
        CardKind::Uppercut,
        CardKind::Inflame,
        CardKind::Flex,
        CardKind::Carnage,
        CardKind::Slimed,
        CardKind::Dazed,
        CardKind::SilentStrike,
        CardKind::SilentDefend,
        CardKind::Neutralize,
        CardKind::SuckerPunch,
        CardKind::LegSweep,
        CardKind::QuickSlash,
        CardKind::Backflip,
        CardKind::Deflect,
        CardKind::Slice,
        CardKind::DaggerSpray,
        CardKind::BladeDance,
        CardKind::CloakAndDagger,
        CardKind::Shiv,
        CardKind::DeadlyPoison,
        CardKind::PoisonedStab,
        CardKind::BouncingFlask,
        CardKind::SpotWeakness,
        CardKind::Dropkick,
        CardKind::GoForTheEyes,
        CardKind::Ftl,
        CardKind::Combust,
        CardKind::Brutality,
        CardKind::Rupture,
        CardKind::Metallicize,
        CardKind::DemonForm,
        CardKind::Rage,
        CardKind::Burn,
        CardKind::Whirlwind,
        CardKind::Accuracy,
        CardKind::WraithForm,
        CardKind::Caltrops,
        CardKind::Survivor,
        CardKind::Burst,
        CardKind::Hologram,
        CardKind::Headbutt,
        CardKind::Rampage,
        CardKind::Protect,
    ];
}

/// Whose card pool a card belongs to. Colorless cards (statuses, Shiv) are
/// never picked for decks.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum CardClass {
    Ironclad,
    Silent,
    Colorless,
}

/// Card kind plus upgraded flag: `kind * 2 + upgraded`. Official cards only:
/// the official cards (`content/cards.json`), `CardId::all()`, the codec and every name list.
pub const NUM_OFFICIAL_CARDS: usize = CardKind::ALL.len() * 2;
/// Official cards plus the reserved generated-card slots (registry-lite; a
/// slot's `+` twin plays as its base): the pile size.
pub const NUM_CARDS: usize = crate::registry::NUM_CARD_IDS;

/// A label a card carries as data, which amounts and conditions can count
/// (never a name): `CardDef::tags` is a bit set of these.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
#[repr(u8)]
pub enum Tag {
    /// The game's STRIKE tag (Perfected Strike counts it).
    Strike,
    /// Shivs (Accuracy adds to them).
    Shiv,
}

impl Tag {
    pub const ALL: [Tag; 2] = [Tag::Strike, Tag::Shiv];

    pub const fn bit(self) -> u8 {
        1 << self as u8
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum CardType {
    Attack,
    Skill,
    Power,
    Status,
    /// The game's curses (docs/specs/blocked-relics.md step 6): never
    /// chosen for decks or upgraded, as statuses.
    Curse,
}

#[derive(Debug)]
pub struct CardDef {
    pub name: &'static str,
    pub class: CardClass,
    /// The energy cost, or `X_COST` / `UNPLAYABLE` (as the game encodes
    /// them): read through `cost()`, `x_cost()` and `unplayable()`.
    pub(crate) cost_code: i8,
    pub ty: CardType,
    pub exhaust: bool,
    pub ethereal: bool,
    /// Playable only while this holds (Clash: `HandAll(Attack)`;
    /// docs/specs/card-rules.md).
    pub playable_if: Option<Condition>,
    /// Starts in the opening hand (Brutality+).
    pub innate: bool,
    /// `Tag` bits.
    pub tags: u8,
    /// Stays in hand at the end of the turn (Protect).
    pub retain: bool,
    /// Costs 1 less for each time the player lost HP this combat, floored
    /// at 0 (Blood for Blood; `CombatState::cost_of`).
    pub cost_less_per_hp_loss: bool,
    /// The on-play row: (CardPlayed by Owner, Always, effects).
    pub effects: &'static [Effect],
    /// Conditional rows, run after `effects` in order; each row's condition
    /// is checked when the row is reached.
    pub rows: &'static [Row],
    /// Run at the end of the player's turn for each copy in hand, after the
    /// player's turn-end powers and before the hand is discarded (Burn).
    pub turn_end: &'static [Effect],
    /// Run each time a copy of this card is exhausted, as it lands in the
    /// exhaust pile (Sentinel; Necronomicurse's `AddCopy`): `GainEnergy`,
    /// `Block`, `AddCard` and `AddCopy` only.
    pub exhausted: &'static [Effect],
    /// Run for each copy in hand each time the player plays another card
    /// (Pain's `triggerOnOtherCardPlayed`), before the played card's own
    /// effects; not for the turn-end plays of `turn_end` cards.
    pub other_played: &'static [Effect],
    /// While a copy is in hand, no card is playable once this many were
    /// played this turn (Normality's 3; 0 for no limit).
    pub plays_per_turn: u8,
    /// Its level: 0, 1 (the id pair's second id), 2 and up (a per-copy
    /// variant).
    pub level: u8,
    /// The highest level a general upgrade raises the card to (0 for none,
    /// `upgrade::LEVEL_CAP` for no limit).
    pub max_level: u8,
    /// What each upgrade changes; empty for a card without one or a unique
    /// upgrade (a separate `X+` entry).
    pub upgrade: &'static Upgrade,
}

/// The upgrade of a card that has none.
pub static NO_UPGRADE: Upgrade = Upgrade { changes: Vec::new(), match_level: Vec::new() };

/// A conditional part of a card: its effects run only if `condition` holds
/// for the played card and its target when the row is reached.
#[derive(Debug)]
pub struct Row {
    pub condition: Condition,
    pub effects: &'static [Effect],
}

/// Effect `i` of a card, counting through its rows in order.
#[derive(Clone, Copy, Debug)]
pub struct EffectAt {
    pub effect: Effect,
    pub condition: Condition,
    /// The first effect of its row, where the condition is checked.
    pub row_start: bool,
    /// The index just past its row.
    pub row_end: usize,
}

/// `CardDef::cost_code` of an X-cost card: playing it spends all current
/// energy, which is X (`Quantity::EnergySpent`).
pub const X_COST: i8 = -1;
/// `CardDef::cost_code` of a card that can't be played (statuses).
pub const UNPLAYABLE: i8 = -2;

impl CardDef {
    /// The energy playing it costs before any change in combat: 0 for an
    /// X-cost or unplayable card.
    #[inline]
    pub fn cost(&self) -> i8 {
        self.cost_code.max(0)
    }

    /// X cost: playing it spends all current energy.
    #[inline]
    pub fn x_cost(&self) -> bool {
        self.cost_code == X_COST
    }

    /// It can't be played.
    #[inline]
    pub fn unplayable(&self) -> bool {
        self.cost_code == UNPLAYABLE
    }

    /// A targeted card needs a chosen enemy.
    pub fn targeted(&self) -> bool {
        self.rows().any(|(c, effects)| {
            matches!(c, Condition::TargetIntendsAttack | Condition::TargetHas(_) | Condition::TargetLacks(_) | Condition::TargetDied)
                || effects.iter().any(|e| e.target() == Some(Target::Opponent))
        })
    }

    /// The on-play row (`Always`), then the conditional rows.
    pub fn rows(&self) -> impl Iterator<Item = (Condition, &'static [Effect])> + '_ {
        std::iter::once((Condition::Always, self.effects)).chain(self.rows.iter().map(|r| (r.condition, r.effects)))
    }

    /// Every effect in every row, conditions ignored.
    pub fn all_effects(&self) -> impl Iterator<Item = &'static Effect> + '_ {
        self.rows().flat_map(|(_, e)| e.iter())
    }

    /// Effect `i` counting through every row, or `None` past the last.
    pub fn effect_at(&self, i: usize) -> Option<EffectAt> {
        let mut start = 0;
        for (condition, effects) in self.rows() {
            let end = start + effects.len();
            if i < end {
                return Some(EffectAt { effect: effects[i - start], condition, row_start: i == start, row_end: end });
            }
            start = end;
        }
        None
    }

    /// The parts an upgrade changes.
    pub fn parts(&self) -> Parts {
        let k = |k: Keyword| match k {
            Keyword::Exhaust => self.exhaust,
            Keyword::Ethereal => self.ethereal,
            Keyword::Innate => self.innate,
            Keyword::Retain => self.retain,
        };
        Parts {
            cost: self.cost_code,
            keywords: Keyword::ALL.map(k),
            rows: self.rows().map(|(_, e)| e.to_vec()).collect(),
            turn_end: self.turn_end.to_vec(),
            exhausted: self.exhausted.to_vec(),
        }
    }

    /// This card with parts `p` (as `parts` gives them), named `name`, at
    /// `level` (leaked: definitions live for the process).
    pub fn with_parts(&self, p: &Parts, name: &'static str, level: u8) -> CardDef {
        let leak = |v: &Vec<Effect>| -> &'static [Effect] { Box::leak(v.clone().into_boxed_slice()) };
        let rows: Vec<Row> = self.rows.iter().zip(&p.rows[1..]).map(|(r, e)| Row { condition: r.condition, effects: leak(e) }).collect();
        CardDef {
            name,
            cost_code: p.cost,
            exhaust: p.keyword(Keyword::Exhaust),
            ethereal: p.keyword(Keyword::Ethereal),
            innate: p.keyword(Keyword::Innate),
            retain: p.keyword(Keyword::Retain),
            effects: leak(&p.rows[0]),
            rows: Box::leak(rows.into_boxed_slice()),
            turn_end: leak(&p.turn_end),
            exhausted: leak(&p.exhausted),
            level,
            ..*self
        }
    }

    pub fn has_tag(&self, t: Tag) -> bool {
        self.tags & t.bit() != 0
    }

    /// Tagged Strike (counts for Perfected Strike).
    pub fn is_strike(&self) -> bool {
        self.has_tag(Tag::Strike)
    }
}


#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct CardId(pub u16);

impl CardId {
    pub const fn new(kind: CardKind, upgraded: bool) -> CardId {
        CardId(kind as u16 * 2 + upgraded as u16)
    }

    pub fn kind(self) -> CardKind {
        CardKind::ALL[(self.0 / 2) as usize]
    }

    pub fn upgraded(self) -> bool {
        self.0 % 2 == 1
    }

    /// An official card's definition. A generated slot's needs the combat's
    /// binding (`registry::Binding::def`); asking here panics.
    pub fn def(self) -> &'static CardDef {
        // A slot id is past the loaded cards: the index check panics.
        &crate::registry::official().cards[self.0 as usize]
    }

    /// An official card (`content/cards.json`), not a reserved generated slot.
    pub fn is_official(self) -> bool {
        (self.0 as usize) < NUM_OFFICIAL_CARDS
    }

    pub fn name(self) -> &'static str {
        if self.is_official() { self.def().name } else { "<generated>" }
    }

    /// "Bash" or "Bash+".
    pub fn from_name(name: &str) -> Option<CardId> {
        crate::registry::official_card_names().iter().position(|n| n == name).map(|i| CardId(i as u16))
    }

    pub fn all() -> impl Iterator<Item = CardId> {
        (0..NUM_OFFICIAL_CARDS as u16).map(CardId)
    }

    /// Status cards (Wound, Slimed, Dazed) can't be upgraded and aren't
    /// chosen for decks.
    pub fn is_status(self) -> bool {
        self.def().ty == CardType::Status
    }
}

impl CardDef {
    /// A Status or a Curse: never chosen for decks or upgraded.
    pub fn is_status_or_curse(&self) -> bool {
        matches!(self.ty, CardType::Status | CardType::Curse)
    }
}

/// Ironclad's starting deck: 5 Strike, 4 Defend, 1 Bash.
pub fn starter_deck() -> Vec<CardId> {
    let mut d = vec![CardId::new(CardKind::Strike, false); 5];
    d.extend([CardId::new(CardKind::Defend, false); 4]);
    d.push(CardId::new(CardKind::Bash, false));
    d
}

/// The `ironclad` card set, base and upgraded: what Ironclad decks are
/// built from.
pub fn deck_cards() -> impl Iterator<Item = CardId> {
    class_cards(CardClass::Ironclad)
}

/// The card set named after the class in lower case (`configs/card-sets.json`),
/// base and upgraded in card order, or nothing if the file has none.
pub fn class_cards(class: CardClass) -> impl Iterator<Item = CardId> {
    let name = format!("{class:?}").to_lowercase();
    crate::card_sets::get(&name).unwrap_or(&[]).iter().copied()
}

/// The `check9` card set: the cards held out of every training pool,
/// base and upgraded.
pub fn held_out_cards() -> impl Iterator<Item = CardId> {
    crate::card_sets::get("check9").unwrap_or(&[]).iter().copied()
}
