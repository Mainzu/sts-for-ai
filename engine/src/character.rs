//! Playable characters: starting HP, starter deck, card pool and relic.

use crate::cards::{starter_deck, CardClass, CardId, CardKind};

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash)]
pub enum Character {
    /// Burning Blood: heal 6 HP when a combat is won.
    #[default]
    Ironclad,
    /// Ring of the Snake: draw 2 additional cards at the start of combat.
    Silent,
}

impl Character {
    pub const ALL: [Character; 2] = [Character::Ironclad, Character::Silent];

    pub fn name(self) -> &'static str {
        match self {
            Character::Ironclad => "ironclad",
            Character::Silent => "silent",
        }
    }

    pub fn from_name(name: &str) -> Option<Character> {
        Character::ALL.into_iter().find(|c| c.name() == name)
    }

    pub fn max_hp(self) -> i16 {
        match self {
            Character::Ironclad => 80,
            Character::Silent => 70,
        }
    }

    /// Max HP the game takes off a run from ascension 14 (its
    /// `getAscensionMaxHPLoss`).
    pub fn ascension_max_hp_loss(self) -> i16 {
        match self {
            Character::Ironclad => 5,
            Character::Silent => 4,
        }
    }

    /// `(hp, max_hp)` a run starts with at ascension `a`, as the game's
    /// `dungeonTransitionSetup` sets them on floor 1 (docs/specs/ascension.md):
    /// from A14 max HP less `ascension_max_hp_loss`, then from A6 HP
    /// round(0.9 x max HP) (libGDX `MathUtils.round` in f32: Ironclad A20
    /// 68 of 75); below A6 full HP.
    pub fn run_start_hp(self, a: u8) -> (i16, i16) {
        let max = self.max_hp() - if a >= 14 { self.ascension_max_hp_loss() } else { 0 };
        let hp = if a >= 6 { ((max as f32 * 0.9f32 + 16384.5f32) as i32 - 16384) as i16 } else { max };
        (hp, max)
    }

    pub fn class(self) -> CardClass {
        match self {
            Character::Ironclad => CardClass::Ironclad,
            Character::Silent => CardClass::Silent,
        }
    }

    /// Ironclad: 5 Strike, 4 Defend, Bash. Silent: 5 Strike, 6 Defend,
    /// Neutralize (the game's Survivor needs a discard choice, which is out
    /// of scope, so a Defend takes its place; Amendment 2).
    pub fn starter_deck(self) -> Vec<CardId> {
        match self {
            Character::Ironclad => starter_deck(),
            Character::Silent => {
                let mut d = vec![CardId::new(CardKind::SilentStrike, false); 5];
                d.extend([CardId::new(CardKind::SilentDefend, false); 6]);
                d.push(CardId::new(CardKind::Neutralize, false));
                d
            }
        }
    }

    /// A named starter: `"default"` (`starter_deck`) or `"game"`: the game's
    /// own (the Silent's has Survivor in place of the sixth Defend; the
    /// Ironclad's is the default). `None` for an unknown name.
    pub fn starter_deck_variant(self, variant: &str) -> Option<Vec<CardId>> {
        match (self, variant) {
            (_, "default") | (Character::Ironclad, "game") => Some(self.starter_deck()),
            (Character::Silent, "game") => {
                let mut d = self.starter_deck();
                let defend = CardId::new(CardKind::SilentDefend, false);
                let i = d.iter().position(|&c| c == defend).expect("a Defend");
                d[i] = CardId::new(CardKind::Survivor, false);
                Some(d)
            }
            _ => None,
        }
    }

    /// The starter relic, an official relic (`content/relics.json`), when
    /// it is data: the Silent's Ring of the Snake is still code
    /// (`first_turn_draw`).
    pub fn starter_relic(self) -> Option<&'static str> {
        match self {
            Character::Ironclad => Some("Burning Blood"),
            Character::Silent => None,
        }
    }

    /// HP healed when a combat is won: the starter relic's `win_heal`
    /// (Burning Blood's 6), 0 without one. A fight starts with this
    /// (`CombatState::win_heal`).
    pub fn win_heal(self) -> i16 {
        // Read once per character: the codec and every fight ask.
        static HEAL: [std::sync::OnceLock<i16>; 2] = [const { std::sync::OnceLock::new() }; 2];
        *HEAL[self as usize].get_or_init(|| {
            self.starter_relic().map_or(0, |n| {
                let (_, r) = crate::registry::official_relics().iter().find(|(i, _)| i == n).unwrap_or_else(|| panic!("starter relic {n:?} not in content/relics.json"));
                r.win_heal
            })
        })
    }

    /// Extra cards drawn on the first turn (Ring of the Snake).
    pub fn first_turn_draw(self) -> u8 {
        match self {
            Character::Ironclad => 0,
            Character::Silent => 2,
        }
    }
}
