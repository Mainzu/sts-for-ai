//! Monsters: moves are effect primitives (the same ones cards use), and each
//! kind has an AI procedure that picks the next move through `Chance`.
//! Values and move rules are from slaythespire.wiki.gg (Ascension 0); a
//! monster's `ascension` rows (docs/specs/ascension.md) give the game's
//! numbers at higher levels.

use crate::effects::Effect;
use crate::powers::{Power, Powers};
use crate::rng::{Chance, Rng};
use crate::state::CombatState;

/// A monster kind: a one-byte handle. Official kinds are the consts below
/// (0 is the empty slot); a monster loaded from a content pack takes the
/// next number from `NUM_OFFICIAL_MONSTERS` in load order, for the
/// process's life (`registry::load_pack`).
#[derive(Clone, Copy, Default, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct MonsterKind(pub u8);

/// Official kinds, `MonsterKind::None` included.
pub const NUM_OFFICIAL_MONSTERS: usize = 19;

const OFFICIAL_NAMES: [&str; NUM_OFFICIAL_MONSTERS] = ["None", "Cultist", "JawWorm", "RedLouse", "GreenLouse", "AcidSlimeS", "AcidSlimeM", "AcidSlimeL", "SpikeSlimeS", "SpikeSlimeM", "SpikeSlimeL", "FungiBeast", "Looter", "GremlinNob", "Lagavulin", "Sentry", "SlimeBoss", "Hexaghost", "TheGuardian"];

#[allow(non_upper_case_globals)]
impl MonsterKind {
    /// Empty slot.
    pub const None: MonsterKind = MonsterKind(0);
    pub const Cultist: MonsterKind = MonsterKind(1);
    pub const JawWorm: MonsterKind = MonsterKind(2);
    pub const RedLouse: MonsterKind = MonsterKind(3);
    pub const GreenLouse: MonsterKind = MonsterKind(4);
    pub const AcidSlimeS: MonsterKind = MonsterKind(5);
    pub const AcidSlimeM: MonsterKind = MonsterKind(6);
    pub const AcidSlimeL: MonsterKind = MonsterKind(7);
    pub const SpikeSlimeS: MonsterKind = MonsterKind(8);
    pub const SpikeSlimeM: MonsterKind = MonsterKind(9);
    pub const SpikeSlimeL: MonsterKind = MonsterKind(10);
    pub const FungiBeast: MonsterKind = MonsterKind(11);
    pub const Looter: MonsterKind = MonsterKind(12);
    pub const GremlinNob: MonsterKind = MonsterKind(13);
    pub const Lagavulin: MonsterKind = MonsterKind(14);
    pub const Sentry: MonsterKind = MonsterKind(15);
    pub const SlimeBoss: MonsterKind = MonsterKind(16);
    pub const Hexaghost: MonsterKind = MonsterKind(17);
    pub const TheGuardian: MonsterKind = MonsterKind(18);

    /// Official (`content/monsters.json`), not loaded from a pack.
    #[inline]
    pub fn is_official(self) -> bool {
        (self.0 as usize) < NUM_OFFICIAL_MONSTERS
    }
}

impl std::fmt::Debug for MonsterKind {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match OFFICIAL_NAMES.get(self.0 as usize) {
            Some(n) => f.write_str(n),
            None => f.write_str(self.def().name),
        }
    }
}

/// The game's ascension level a combat is played at (docs/specs/ascension.md):
/// 0 to `MAX_ASCENSION`. Level 0 hashes to nothing, so every A0 state
/// hashes as it did before levels existed.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, PartialOrd, Ord)]
pub struct Ascension(pub u8);

/// The highest ascension level the game has.
pub const MAX_ASCENSION: u8 = 20;

impl std::hash::Hash for Ascension {
    fn hash<H: std::hash::Hasher>(&self, h: &mut H) {
        if self.0 != 0 {
            self.0.hash(h);
        }
    }
}

/// Index into the monster kind's move table.
pub type MoveId = u8;
pub const NO_MOVE: MoveId = u8::MAX;

#[derive(Debug)]
pub struct MoveDef {
    pub name: &'static str,
    pub effects: &'static [Effect],
}

/// Picks the next move for the monster in `slot`. Called after its current
/// move resolved, so `intent()` is the move it just used (`NO_MOVE` for a
/// monster that hasn't moved yet). It reads only its monster's kind, `slot`
/// and move history (`moves`): the heuristic caches move walks on those
/// (`heuristic::damage_rate`; tested in `ai_reads_only_moves`).
pub type Ai = fn(&CombatState, usize, &mut dyn Chance) -> MoveId;

/// A condition of a pattern row, on the monster's two-deep move history
/// (`moves[0]` the last move, or the intent on show), its slot, or the
/// lazy 0..99 roll.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PatCond {
    /// No move yet.
    FirstTurn,
    LastMove(MoveId),
    /// The last two moves were both this one.
    LastTwo(MoveId),
    /// The last move `.0`, the one before `.1` (`NO_MOVE` allowed).
    Window(MoveId, MoveId),
    Slot(u8),
    /// The 0..99 roll is below this: made once, the first time a row reads it.
    RollBelow(u8),
    /// Another monster in the fight is alive (Shield Gremlin). The move
    /// caches key on it for kinds whose pattern reads it (`allies_bit`).
    Allies,
}

/// What a pattern row picks.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum PatPick {
    Move(MoveId),
    /// One `chance(p)` call: `yes` if it comes up, else `no` (a repeat
    /// limit's alternative).
    Chance { p: f64, yes: MoveId, no: MoveId },
}

/// One pattern row: the first row whose conditions all hold (checked in
/// order, stopping at the first false one) picks the move.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct PatternRow {
    pub when: &'static [PatCond],
    pub then: PatPick,
}

use PatCond::*;

/// The allies bit of the move caches' keys: whether another monster lives,
/// for a kind whose pattern reads `Allies` (false for every other kind, so
/// their keys don't split).
pub(crate) fn allies_bit(s: &CombatState, slot: usize) -> bool {
    s.monsters[slot].def().pattern.iter().any(|r| r.when.contains(&Allies)) && allies(s, slot)
}

/// `Allies` for monster `slot`: whether another monster lived when it last
/// used its move (`CombatState::allies_at_move`; the game's count at the
/// move), or lives now before its first move.
fn allies(s: &CombatState, slot: usize) -> bool {
    if s.monsters[slot].intent() == NO_MOVE {
        s.living_slots().any(|i| i != slot)
    } else {
        s.allies_at_move & 1 << slot != 0
    }
}

/// Every monster's move selection: the first matching row of its pattern,
/// making today's random calls in today's order (the golden games check it).
pub(crate) fn pattern_ai(s: &CombatState, slot: usize, c: &mut dyn Chance) -> MoveId {
    let m = &s.monsters[slot];
    let mut roll: Option<u32> = None;
    'rows: for r in m.def().pattern {
        for &cond in r.when {
            let holds = match cond {
                FirstTurn => m.intent() == NO_MOVE,
                LastMove(x) => m.last_move(x),
                LastTwo(x) => m.last_two_moves(x),
                Window(a, b) => m.moves == [a, b],
                Slot(n) => slot == n as usize,
                RollBelow(n) => *roll.get_or_insert_with(|| c.below(100)) < n as u32,
                Allies => allies(s, slot),
            };
            if !holds {
                continue 'rows;
            }
        }
        return match r.then {
            PatPick::Move(x) => x,
            PatPick::Chance { p, yes, no } => {
                if c.chance(p) {
                    yes
                } else {
                    no
                }
            }
        };
    }
    NO_MOVE
}

pub struct MonsterDef {
    pub name: &'static str,
    pub hp_min: i16,
    pub hp_max: i16,
    pub moves: &'static [MoveDef],
    /// Picks the next move: `pattern_ai`, reading `pattern`, for every monster.
    pub ai: Ai,
    /// Move selection as data (monster-patterns spec).
    pub pattern: &'static [PatternRow],
    pub start_block: i16,
    pub start_powers: &'static [(Power, i16)],
    /// Pack start powers (registry power indices), at their bound slots.
    pub gen_powers: &'static [(u16, i16)],
    /// Code run at the start of combat after the rolls (The Guardian's
    /// threshold); `no_setup` for most.
    pub setup: fn(&mut Monster, &mut Rng),
    /// `RolledAttack`'s damage range, rolled per monster at the start of
    /// combat (louse Bite); `None` for a monster without one.
    pub rolled_attack: Option<(i16, i16)>,
    /// Start powers whose amounts are rolled per monster at the start of
    /// combat, after `rolled_attack` (louse Curl Up): (power, min, max).
    pub rolled_powers: &'static [(Power, i16, i16)],
    /// This kind's definitions at higher ascension levels: (the lowest level
    /// it applies from, the definition), ascending; empty when every level
    /// plays as level 0 (`MonsterKind::def_at`).
    pub levels: &'static [(u8, &'static MonsterDef)],
    /// The `ascension` rows as the content file writes them (empty for none).
    pub ascension_rows: &'static str,
    /// For slimes: the move their intent switches to at half HP, and what
    /// they split into. `NO_MOVE` for everything else.
    pub split_move: MoveId,
    pub split_into: [MonsterKind; 2],
}

#[derive(Clone, Copy, Default, PartialEq, Eq, Hash)]
pub struct Monster {
    pub kind: MonsterKind,
    pub hp: i16,
    pub max_hp: i16,
    pub block: i16,
    pub powers: Powers,
    /// `[current intent, previous move]`.
    pub moves: [MoveId; 2],
    /// Damage rolled at the start of combat for `RolledAttack` (louse Bite).
    pub rolled_damage: i16,
    /// Left combat (Looter). An escaped monster isn't alive.
    pub escaped: bool,
    /// The combat's ascension level, which picks its definition (`def`).
    pub ascension: Ascension,
}

/// The derived layout, with `ascension` shown only above 0 (so debug text
/// reads as it did before levels).
impl std::fmt::Debug for Monster {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let mut d = f.debug_struct("Monster");
        d.field("kind", &self.kind)
            .field("hp", &self.hp)
            .field("max_hp", &self.max_hp)
            .field("block", &self.block)
            .field("powers", &self.powers)
            .field("moves", &self.moves)
            .field("rolled_damage", &self.rolled_damage)
            .field("escaped", &self.escaped);
        if self.ascension.0 != 0 {
            d.field("ascension", &self.ascension.0);
        }
        d.finish()
    }
}

impl Monster {
    /// A monster with full HP `hp`, its kind's starting block and powers, and no move yet.
    pub fn new(kind: MonsterKind, hp: i16) -> Monster {
        Monster::new_bound(kind, hp, &crate::registry::Binding::default())
    }

    /// `new` with its pack start powers at their slots in `binding`
    /// (`registry::bind_monsters`).
    pub fn new_bound(kind: MonsterKind, hp: i16, binding: &crate::registry::Binding) -> Monster {
        Monster::new_at(kind, hp, binding, Ascension(0))
    }

    /// `new_bound` at an ascension level: its definition at that level.
    pub fn new_at(kind: MonsterKind, hp: i16, binding: &crate::registry::Binding, ascension: Ascension) -> Monster {
        let d = kind.def_at(ascension);
        let mut powers = Powers::default();
        for &(p, n) in d.start_powers {
            powers.add(p, n);
        }
        for &(pi, n) in d.gen_powers {
            powers.add(binding.slot_of(pi), n);
        }
        Monster {
            kind,
            hp,
            max_hp: hp,
            block: d.start_block,
            powers,
            moves: [NO_MOVE; 2],
            rolled_damage: 0,
            escaped: false,
            ascension,
        }
    }

    /// Rolls its definition's per-monster values (`rolled_attack`, then
    /// `rolled_powers`), then runs its `setup`: at the start of combat.
    pub fn roll(&mut self, rng: &mut Rng) {
        let d = self.def();
        if let Some((lo, hi)) = d.rolled_attack {
            self.rolled_damage = lo + rng.below((hi - lo + 1) as u32) as i16;
        }
        for &(p, lo, hi) in d.rolled_powers {
            self.powers.add(p, lo + rng.below((hi - lo + 1) as u32) as i16);
        }
        (d.setup)(self, rng);
    }

    pub fn alive(&self) -> bool {
        self.kind != MonsterKind::None && self.hp > 0 && !self.escaped
    }

    /// Its kind's definition at its combat's ascension level.
    #[inline]
    pub fn def(&self) -> &'static MonsterDef {
        self.kind.def_at(self.ascension)
    }

    pub fn intent(&self) -> MoveId {
        self.moves[0]
    }

    pub fn intent_def(&self) -> Option<&'static MoveDef> {
        self.def().moves.get(self.intent() as usize)
    }

    pub fn set_move(&mut self, m: MoveId) {
        self.moves = [m, self.moves[0]];
    }

    pub fn last_move(&self, m: MoveId) -> bool {
        self.moves[0] == m
    }

    pub fn last_two_moves(&self, m: MoveId) -> bool {
        self.moves == [m, m]
    }
}

pub(crate) fn no_setup(_: &mut Monster, _: &mut Rng) {}


// Cultist: Incantation, then Dark Strike every turn.
pub const INCANTATION: MoveId = 0;
pub const DARK_STRIKE: MoveId = 1;

// Jaw Worm: Chomp first, then a 0..99 roll with repeat limits.
pub const CHOMP: MoveId = 0;
pub const THRASH: MoveId = 1;
pub const BELLOW: MoveId = 2;

/// Lice: Bite (damage rolled per louse: `rolled_attack`) 75%, the other
/// move 25%; no move three times in a row. Curl Up rolled per louse
/// (`rolled_powers`).
pub mod louse {
    use super::*;
    pub const BITE: MoveId = 0;
    /// Grow (red) or Spit Web (green).
    pub const OTHER: MoveId = 1;
}

/// Acid Slimes (M) and (L): 30% Corrosive Spit, 40% Tackle, 30% Lick; no
/// Tackle twice in a row, no other move three times in a row.
pub mod acid_slime {
    use super::*;
    pub const CORROSIVE_SPIT: MoveId = 0;
    pub const TACKLE: MoveId = 1;
    pub const LICK: MoveId = 2;
    pub const SPLIT: MoveId = 3;

    /// Acid Slime (S): Lick or Tackle at random first, then alternates.
    pub const S_LICK: MoveId = 0;
    pub const S_TACKLE: MoveId = 1;

}

/// Spike Slimes (M) and (L): 30% Flame Tackle, 70% Lick; no move three times
/// in a row. Spike Slime (S) only Tackles.
pub mod spike_slime {
    use super::*;
    pub const FLAME_TACKLE: MoveId = 0;
    pub const LICK: MoveId = 1;
    pub const SPLIT: MoveId = 2;
    pub const S_TACKLE: MoveId = 0;

}

/// Fungi Beast: 60% Bite, 40% Grow; no Bite three times or Grow twice in a row.
pub mod fungi_beast {
    use super::*;
    pub const BITE: MoveId = 0;
    pub const GROW: MoveId = 1;

}

/// Looter: Mug twice, then 50% Lunge (then Smoke Bomb) or Smoke Bomb, then Escape.
pub mod looter {
    use super::*;
    pub const MUG: MoveId = 0;
    pub const LUNGE: MoveId = 1;
    pub const SMOKE_BOMB: MoveId = 2;
    pub const ESCAPE: MoveId = 3;

}

/// Gremlin Nob: Bellow first, then 33% Skull Bash, 67% Bull Rush; no Bull
/// Rush three times in a row.
pub mod gremlin_nob {
    use super::*;
    pub const BELLOW: MoveId = 0;
    pub const BULL_RUSH: MoveId = 1;
    pub const SKULL_BASH: MoveId = 2;

}

/// Lagavulin: asleep for 3 turns (the third wakes it and takes 8 off its
/// Metallicize), or stunned for a turn when HP damage wakes it (the same 8
/// off); then Attack, Attack,
/// Siphon Soul, repeating.
pub mod lagavulin {
    use super::*;
    pub const SLEEP: MoveId = 0;
    /// The third turn asleep: it wakes at the end of it.
    pub const WAKE: MoveId = 1;
    pub const STUNNED: MoveId = 2;
    pub const ATTACK: MoveId = 3;
    pub const SIPHON_SOUL: MoveId = 4;
    /// The Metallicize waking takes off (`changeState("OPEN")`'s
    /// `ReducePowerAction`), whatever it holds: more stays.
    pub const OPEN_METALLICIZE: i16 = 8;

    pub fn asleep(m: &Monster) -> bool {
        matches!(m.intent(), SLEEP | WAKE)
    }
}

/// Sentries alternate Bolt and Beam; the middle one starts with Beam.
pub mod sentry {
    use super::*;
    pub const BOLT: MoveId = 0;
    pub const BEAM: MoveId = 1;

}

/// Slime Boss: Goop Spray, Preparing, Slam, repeating; splits at half HP.
pub mod slime_boss {
    use super::*;
    pub const GOOP_SPRAY: MoveId = 0;
    pub const PREPARING: MoveId = 1;
    pub const SLAM: MoveId = 2;
    pub const SPLIT: MoveId = 3;

}

/// Hexaghost: Activate, then Divider (6 hits of the player's HP / 12 + 1,
/// fixed when chosen: `CombatState::set_monster_move`), then Sear, Tackle,
/// Sear, Inflame, Tackle, Sear, Inferno, repeating. The first Inferno
/// upgrades every Burn (`CombatState::after_move`) and from then on Sear
/// adds Burn+: the cycle after it is a second set of move ids, so the move
/// history stays the whole state.
pub mod hexaghost {
    use super::*;
    pub const ACTIVATE: MoveId = 0;
    pub const DIVIDER: MoveId = 1;
    /// First move of the cycle (Sear); the cycle is 7 moves long.
    pub const CYCLE: MoveId = 2;
    pub const INFERNO: MoveId = CYCLE + 6;
    /// The cycle once Burns are upgraded.
    pub const CYCLE_UP: MoveId = 9;
    pub const INFERNO_UP: MoveId = CYCLE_UP + 6;

    /// Divider's damage per hit for a player at `hp`.
    pub fn divider_damage(hp: i16) -> i16 {
        hp.max(0) / 12 + 1
    }
}

/// The Guardian: Offensive mode cycles Charging Up, Fierce Bash, Vent
/// Steam, Whirlwind. Losing Mode Shift's HP switches it to Defensive mode
/// (`CombatState::lost_hp`): 20 block and Close Up, then Roll Attack, then
/// Twin Slam, which returns it to Offensive mode (`CombatState::after_move`)
/// with Whirlwind next. `rolled_damage` holds the threshold Mode Shift
/// returns with (its start Mode Shift, +10 per switch).
pub mod guardian {
    use super::*;
    pub const CHARGING_UP: MoveId = 0;
    pub const FIERCE_BASH: MoveId = 1;
    pub const VENT_STEAM: MoveId = 2;
    pub const WHIRLWIND: MoveId = 3;
    pub const CLOSE_UP: MoveId = 4;
    pub const ROLL_ATTACK: MoveId = 5;
    pub const TWIN_SLAM: MoveId = 6;
    pub const THRESHOLD_STEP: i16 = 10;
    pub const DEFENSIVE_BLOCK: i16 = 20;

    /// The threshold starts at its start Mode Shift (the definition's, so
    /// one number per level).
    pub(super) fn setup(m: &mut Monster, _: &mut Rng) {
        m.rolled_damage = m.powers.get(Power::ModeShift);
    }
}

/// The `code` name an official code-backed kind carries in
/// `content/monsters.json` (`None` for the others).
pub fn code_name(k: MonsterKind) -> Option<&'static str> {
    Some(match k {
        MonsterKind::RedLouse | MonsterKind::GreenLouse => "louse",
        MonsterKind::Lagavulin => "lagavulin",
        MonsterKind::Hexaghost => "hexaghost",
        MonsterKind::TheGuardian => "guardian",
        _ => return None,
    })
}

/// The setup function a `code` name attaches (`no_setup` for none).
pub fn setup_for(code: Option<&str>) -> fn(&mut Monster, &mut Rng) {
    match code {
        Some("guardian") => guardian::setup,
        _ => no_setup,
    }
}

/// Official kinds whose behaviour is partly code (setup rolls, special
/// cases in `CombatState`): they stay official-only, with no pack form.
pub fn has_code(k: MonsterKind) -> bool {
    matches!(k, MonsterKind::RedLouse | MonsterKind::GreenLouse | MonsterKind::Lagavulin | MonsterKind::Hexaghost | MonsterKind::TheGuardian)
}

/// Monster kinds in a `boss`-group encounter, one bit per kind: the
/// official ones on first use, a pack's as it loads (`mark_boss_kinds`).
static BOSS_KINDS: [std::sync::atomic::AtomicU64; 4] = [const { std::sync::atomic::AtomicU64::new(0) }; 4];

/// Marks every kind an encounter can roll as a boss when it is in the
/// `boss` group (docs/specs/act1-singles.md).
pub fn mark_boss_kinds(e: &EncounterDef) {
    fn walk(slots: &[EncounterSlot]) {
        for s in slots {
            match s {
                EncounterSlot::Monster(k) => mark(*k),
                EncounterSlot::OneOf(opts) => opts.iter().for_each(|o| walk(o)),
                EncounterSlot::Draw { from, .. } => from.iter().for_each(|&k| mark(k)),
            }
        }
    }
    fn mark(k: MonsterKind) {
        BOSS_KINDS[k.0 as usize / 64].fetch_or(1 << (k.0 % 64), std::sync::atomic::Ordering::Relaxed);
    }
    if e.group == EncounterGroup::Boss {
        walk(&e.slots);
    }
}

impl MonsterKind {
    /// In a `boss`-group encounter, official or a loaded pack's.
    pub fn is_boss(self) -> bool {
        static OFFICIAL: std::sync::OnceLock<()> = std::sync::OnceLock::new();
        OFFICIAL.get_or_init(|| crate::registry::official().encounters.iter().for_each(mark_boss_kinds));
        BOSS_KINDS[self.0 as usize / 64].load(std::sync::atomic::Ordering::Relaxed) & 1 << (self.0 % 64) != 0
    }
}

/// Monster slots a kind can fill over a combat: its split children's (the
/// first takes its own slot; dead monsters keep theirs), else 1.
pub fn slots_needed(k: MonsterKind) -> usize {
    let d = k.def();
    if d.split_move == NO_MOVE {
        1
    } else {
        slots_needed(d.split_into[0]) + slots_needed(d.split_into[1])
    }
}

impl MonsterKind {
    #[inline]
    pub fn def(self) -> &'static MonsterDef {
        match crate::registry::official().monsters.get(self.0 as usize) {
            Some(d) => d,
            None => crate::registry::monster_def(self),
        }
    }

    /// Its definition at ascension level `a`: the last of its `levels`
    /// that applies from `a` or below, else level 0's.
    #[inline]
    pub fn def_at(self, a: Ascension) -> &'static MonsterDef {
        let d = self.def();
        if a.0 == 0 {
            return d;
        }
        d.levels.iter().rev().find(|(from, _)| *from <= a.0).map_or(d, |(_, l)| l)
    }

}

/// The burning elite's buff (the map's emerald-key elite;
/// `MonsterRoomElite.applyEmeraldEliteBuff`): the game picks one of four
/// from the map's RNG and gives it to every monster of the fight before
/// the player's start-of-combat relics act. In act `n`: Strength n+1, max
/// HP +25% (rounded, healed by as much), Metallicize 2n+2, or Regenerate
/// 2n+1. Regenerate (`RegenerateMonsterPower`: heal its amount at the end
/// of the monster's turn) is the pack power `Regenerate` of
/// `content/packs/act1-monsters.json`, bound into the fight only when it
/// is the buff (`bind`), so that pack must be loaded for it.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum EliteBuff {
    Strength,
    MaxHp,
    Metallicize,
    Regenerate,
}

impl EliteBuff {
    pub const ALL: [EliteBuff; 4] = [EliteBuff::Strength, EliteBuff::MaxHp, EliteBuff::Metallicize, EliteBuff::Regenerate];
    /// The pack power id Regenerate gives (the game's `POWER_ID` too).
    pub const REGENERATE: &'static str = "Regenerate";

    pub fn name(self) -> &'static str {
        match self {
            EliteBuff::Strength => "strength",
            EliteBuff::MaxHp => "max_hp",
            EliteBuff::Metallicize => "metallicize",
            EliteBuff::Regenerate => "regenerate",
        }
    }

    pub fn from_name(s: &str) -> Option<EliteBuff> {
        EliteBuff::ALL.into_iter().find(|b| b.name() == s)
    }

    /// `b` with the pack power this buff gives bound (Regenerate's; the
    /// others give official powers, so `b` itself). An error when that
    /// pack power isn't loaded or no slot is free.
    pub fn bind(self, b: &crate::registry::Binding) -> Result<crate::registry::Binding, String> {
        match self {
            EliteBuff::Regenerate => crate::registry::bind_power(b, EliteBuff::REGENERATE)
                .map(|(nb, _)| nb)
                .map_err(|e| format!("elite buff regenerate (load content/packs/act1-monsters.json): {e}")),
            _ => Ok(*b),
        }
    }

    /// Gives it to `m` in act `act` (1 for Act 1), in a fight bound by
    /// `binding` (`bind`'s).
    pub fn apply(self, m: &mut Monster, act: u8, binding: &crate::registry::Binding) {
        let act = act as i16;
        match self {
            EliteBuff::Strength => m.powers.add(Power::Strength, act + 1),
            EliteBuff::Metallicize => m.powers.add(Power::Metallicize, 2 * act + 2),
            EliteBuff::Regenerate => {
                let (_, p) = crate::registry::bind_power(binding, EliteBuff::REGENERATE).unwrap_or_else(|e| panic!("{e}"));
                m.powers.add(p, 2 * act + 1)
            }
            EliteBuff::MaxHp => {
                // `IncreaseMaxHpAction(m, 0.25f, true)`: MathUtils.round of a
                // quarter, then `increaseMaxHp` heals as much.
                let n = (m.max_hp + 2) / 4;
                m.max_hp += n;
                m.hp = (m.hp + n).min(m.max_hp);
            }
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum EncounterGroup {
    Hallway,
    Elite,
    Boss,
}

/// An encounter: a one-byte handle. Official encounters are the consts below,
/// numbered in `content/encounters.json`'s order; an encounter loaded from a
/// content pack takes the next number from `NUM_OFFICIAL_ENCOUNTERS` in load
/// order, for the process's life (`registry::load_pack`).
#[derive(Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct Encounter(pub u8);

/// Official encounters (`ALL`, then `ADDED`).
pub const NUM_OFFICIAL_ENCOUNTERS: usize = 17;

const OFFICIAL_ENCOUNTER_NAMES: [&str; NUM_OFFICIAL_ENCOUNTERS] = [
    "Cultist", "JawWorm", "TwoLouse", "SmallSlimes", "LargeSlime", "LotsOfSlimes", "ThreeLouse", "TwoFungiBeasts", "Looter",
    "ExordiumThugs", "ExordiumWildlife", "GremlinNob", "Lagavulin", "ThreeSentries", "SlimeBoss", "Hexaghost", "TheGuardian",
];

/// One slot of an encounter's roll; slots expand left to right, depth first.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum EncounterSlot {
    /// One monster.
    Monster(MonsterKind),
    /// `rng.below(n)` picks one of the n lists, which expands in place.
    OneOf(Vec<Vec<EncounterSlot>>),
    /// `k` monsters without replacement: each `rng.below(remaining)` over
    /// the remaining list in order, the pick removed.
    Draw { k: u8, from: Vec<MonsterKind> },
}

/// An encounter's definition (`content/encounters.json`, or a pack entry).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EncounterDef {
    pub name: &'static str,
    pub group: EncounterGroup,
    pub slots: Vec<EncounterSlot>,
}

fn roll_slots(slots: &[EncounterSlot], rng: &mut Rng, out: &mut Vec<MonsterKind>) {
    for s in slots {
        match s {
            EncounterSlot::Monster(k) => out.push(*k),
            EncounterSlot::OneOf(opts) => {
                let i = rng.below(opts.len() as u32) as usize;
                roll_slots(&opts[i], rng, out);
            }
            EncounterSlot::Draw { k, from } => {
                let mut left = from.clone();
                for _ in 0..*k {
                    let i = rng.below(left.len() as u32) as usize;
                    out.push(left.remove(i));
                }
            }
        }
    }
}

#[allow(non_upper_case_globals)]
impl Encounter {
    pub const Cultist: Encounter = Encounter(0);
    pub const JawWorm: Encounter = Encounter(1);
    pub const TwoLouse: Encounter = Encounter(2);
    pub const SmallSlimes: Encounter = Encounter(3);
    pub const LargeSlime: Encounter = Encounter(4);
    pub const LotsOfSlimes: Encounter = Encounter(5);
    pub const ThreeLouse: Encounter = Encounter(6);
    pub const TwoFungiBeasts: Encounter = Encounter(7);
    pub const Looter: Encounter = Encounter(8);
    pub const ExordiumThugs: Encounter = Encounter(9);
    pub const ExordiumWildlife: Encounter = Encounter(10);
    pub const GremlinNob: Encounter = Encounter(11);
    pub const Lagavulin: Encounter = Encounter(12);
    pub const ThreeSentries: Encounter = Encounter(13);
    pub const SlimeBoss: Encounter = Encounter(14);
    pub const Hexaghost: Encounter = Encounter(15);
    pub const TheGuardian: Encounter = Encounter(16);

    pub const ALL: [Encounter; 15] = [
        Encounter::Cultist,
        Encounter::JawWorm,
        Encounter::TwoLouse,
        Encounter::SmallSlimes,
        Encounter::LargeSlime,
        Encounter::LotsOfSlimes,
        Encounter::ThreeLouse,
        Encounter::TwoFungiBeasts,
        Encounter::Looter,
        Encounter::ExordiumThugs,
        Encounter::ExordiumWildlife,
        Encounter::GremlinNob,
        Encounter::Lagavulin,
        Encounter::ThreeSentries,
        Encounter::SlimeBoss,
    ];

    /// Encounters added after the bench sets were drawn (2026-10-30). Not in
    /// `ALL`, so spec generators by group, `encounter_names()`, golden games
    /// and every bench set keep their 15 encounters; reachable by name.
    pub const ADDED: [Encounter; 2] = [Encounter::Hexaghost, Encounter::TheGuardian];

    /// `ALL`, then `ADDED`.
    pub fn every() -> impl Iterator<Item = Encounter> {
        Encounter::ALL.into_iter().chain(Encounter::ADDED)
    }

    /// Official (`content/encounters.json`), not loaded from a pack.
    #[inline]
    pub fn is_official(self) -> bool {
        (self.0 as usize) < NUM_OFFICIAL_ENCOUNTERS
    }

    pub fn def(self) -> &'static EncounterDef {
        match crate::registry::official().encounters.get(self.0 as usize) {
            Some(d) => d,
            None => crate::registry::encounter_def(self),
        }
    }

    pub fn name(self) -> &'static str {
        self.def().name
    }

    /// An official encounter's name, or `gen:<id>` of a loaded pack's.
    pub fn from_name(name: &str) -> Option<Encounter> {
        match name.strip_prefix("gen:") {
            Some(_) => crate::registry::pack_encounter(name),
            None => Encounter::every().find(|e| e.name() == name),
        }
    }

    pub fn group(self) -> EncounterGroup {
        self.def().group
    }

    /// Monster kinds by slot, rolling any random choice from `rng`.
    pub fn roll_monsters(self, rng: &mut Rng) -> Vec<MonsterKind> {
        let mut out = Vec::new();
        roll_slots(&self.def().slots, rng, &mut out);
        out
    }
}

impl std::fmt::Debug for Encounter {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match OFFICIAL_ENCOUNTER_NAMES.get(self.0 as usize) {
            Some(n) => f.write_str(n),
            None => f.write_str(self.name()),
        }
    }
}
