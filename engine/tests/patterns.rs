//! Monster patterns (docs/specs/monster-patterns.md): every pattern table
//! gives exactly what the hand-written AI it replaced gave, over every
//! two-deep move history and slot, random calls included: each run records
//! its calls (`below(n)` / `chance(p)`), and `enumerate` lists (move, calls)
//! per path, so equal lists mean the same calls in the same order.

use sts_engine::codec::MONSTER_KINDS;
use sts_engine::monsters::*;
use sts_engine::rng::{enumerate, Chance};
use sts_engine::*;

fn me(s: &CombatState, slot: usize) -> &Monster {
    &s.monsters[slot]
}

type Old = fn(&CombatState, usize, &mut dyn Chance) -> MoveId;

/// Passes calls on, recording each: `(n, 0)` for `below(n)`, `(0, p bits)`
/// for `chance(p)`.
struct Rec<'a>(&'a mut dyn Chance, Vec<(u32, u64)>);

impl Chance for Rec<'_> {
    fn below(&mut self, n: u32) -> u32 {
        self.1.push((n, 0));
        self.0.below(n)
    }

    fn chance(&mut self, p: f64) -> bool {
        self.1.push((0, p.to_bits()));
        self.0.chance(p)
    }
}

/// `f`'s outcomes on `s`, each with the calls that led to it.
fn traced(f: Old, s: &CombatState, slot: usize) -> Vec<((MoveId, Vec<(u32, u64)>), f64)> {
    enumerate(|c| {
        let mut r = Rec(c, Vec::new());
        let m = f(s, slot, &mut r);
        (m, r.1)
    })
}

fn old_cultist_ai(s: &CombatState, slot: usize, _: &mut dyn Chance) -> MoveId {
    if me(s, slot).intent() == NO_MOVE {
        INCANTATION
    } else {
        DARK_STRIKE
    }
}

fn old_jaw_worm_ai(s: &CombatState, slot: usize, c: &mut dyn Chance) -> MoveId {
    let m = me(s, slot);
    if m.intent() == NO_MOVE {
        return CHOMP;
    }
    let num = c.below(100);
    if num < 25 {
        if m.last_move(CHOMP) {
            if c.chance(0.5625) { BELLOW } else { THRASH }
        } else {
            CHOMP
        }
    } else if num < 55 {
        if m.last_two_moves(THRASH) {
            if c.chance(0.357) { CHOMP } else { BELLOW }
        } else {
            THRASH
        }
    } else if m.last_move(BELLOW) {
        if c.chance(0.416) { CHOMP } else { THRASH }
    } else {
        BELLOW
    }
}

fn old_louse_ai(s: &CombatState, slot: usize, c: &mut dyn Chance) -> MoveId {
    let m = me(s, slot);
    if c.below(100) < 25 {
        if m.last_two_moves(louse::OTHER) { louse::BITE } else { louse::OTHER }
    } else if m.last_two_moves(louse::BITE) {
        louse::OTHER
    } else {
        louse::BITE
    }
}

fn old_acid_slime_ai(s: &CombatState, slot: usize, c: &mut dyn Chance) -> MoveId {
    let m = me(s, slot);
    let num = c.below(100);
    if num < 30 {
        if m.last_two_moves(acid_slime::CORROSIVE_SPIT) {
            if c.chance(0.5) { acid_slime::TACKLE } else { acid_slime::LICK }
        } else {
            acid_slime::CORROSIVE_SPIT
        }
    } else if num < 70 {
        if m.last_move(acid_slime::TACKLE) {
            if c.chance(0.5) { acid_slime::CORROSIVE_SPIT } else { acid_slime::LICK }
        } else {
            acid_slime::TACKLE
        }
    } else if m.last_two_moves(acid_slime::LICK) {
        if c.chance(0.4) { acid_slime::CORROSIVE_SPIT } else { acid_slime::TACKLE }
    } else {
        acid_slime::LICK
    }
}

fn old_acid_slime_small_ai(s: &CombatState, slot: usize, c: &mut dyn Chance) -> MoveId {
    match me(s, slot).intent() {
        NO_MOVE => {
            if c.chance(0.5) { acid_slime::S_TACKLE } else { acid_slime::S_LICK }
        }
        acid_slime::S_TACKLE => acid_slime::S_LICK,
        _ => acid_slime::S_TACKLE,
    }
}

fn old_spike_slime_ai(s: &CombatState, slot: usize, c: &mut dyn Chance) -> MoveId {
    let m = me(s, slot);
    if c.below(100) < 30 {
        if m.last_two_moves(spike_slime::FLAME_TACKLE) { spike_slime::LICK } else { spike_slime::FLAME_TACKLE }
    } else if m.last_two_moves(spike_slime::LICK) {
        spike_slime::FLAME_TACKLE
    } else {
        spike_slime::LICK
    }
}

fn old_spike_slime_small_ai(_: &CombatState, _: usize, _: &mut dyn Chance) -> MoveId {
    spike_slime::S_TACKLE
}

fn old_fungi_beast_ai(s: &CombatState, slot: usize, c: &mut dyn Chance) -> MoveId {
    let m = me(s, slot);
    if c.below(100) < 60 {
        if m.last_two_moves(fungi_beast::BITE) { fungi_beast::GROW } else { fungi_beast::BITE }
    } else if m.last_move(fungi_beast::GROW) {
        fungi_beast::BITE
    } else {
        fungi_beast::GROW
    }
}

fn old_looter_ai(s: &CombatState, slot: usize, c: &mut dyn Chance) -> MoveId {
    match me(s, slot).moves {
        [NO_MOVE, _] | [looter::MUG, NO_MOVE] => looter::MUG,
        [looter::MUG, _] => {
            if c.chance(0.5) { looter::LUNGE } else { looter::SMOKE_BOMB }
        }
        [looter::LUNGE, _] => looter::SMOKE_BOMB,
        _ => looter::ESCAPE,
    }
}

fn old_gremlin_nob_ai(s: &CombatState, slot: usize, c: &mut dyn Chance) -> MoveId {
    let m = me(s, slot);
    if m.intent() == NO_MOVE {
        return gremlin_nob::BELLOW;
    }
    if c.below(100) < 33 || m.last_two_moves(gremlin_nob::BULL_RUSH) {
        gremlin_nob::SKULL_BASH
    } else {
        gremlin_nob::BULL_RUSH
    }
}

fn old_lagavulin_ai(s: &CombatState, slot: usize, _: &mut dyn Chance) -> MoveId {
    match me(s, slot).moves {
        [NO_MOVE, _] | [lagavulin::SLEEP, NO_MOVE] => lagavulin::SLEEP,
        [lagavulin::SLEEP, _] => lagavulin::WAKE,
        [lagavulin::ATTACK, lagavulin::ATTACK] => lagavulin::SIPHON_SOUL,
        _ => lagavulin::ATTACK,
    }
}

fn old_sentry_ai(s: &CombatState, slot: usize, _: &mut dyn Chance) -> MoveId {
    match me(s, slot).intent() {
        NO_MOVE if slot == 1 => sentry::BEAM,
        NO_MOVE | sentry::BEAM => sentry::BOLT,
        _ => sentry::BEAM,
    }
}

fn old_slime_boss_ai(s: &CombatState, slot: usize, _: &mut dyn Chance) -> MoveId {
    match me(s, slot).intent() {
        slime_boss::GOOP_SPRAY => slime_boss::PREPARING,
        slime_boss::PREPARING => slime_boss::SLAM,
        _ => slime_boss::GOOP_SPRAY,
    }
}

fn old_hexaghost_ai(s: &CombatState, slot: usize, _: &mut dyn Chance) -> MoveId {
    match me(s, slot).intent() {
        NO_MOVE => hexaghost::ACTIVATE,
        hexaghost::ACTIVATE => hexaghost::DIVIDER,
        hexaghost::DIVIDER => hexaghost::CYCLE,
        hexaghost::INFERNO | hexaghost::INFERNO_UP => hexaghost::CYCLE_UP,
        m => m + 1,
    }
}

fn old_guardian_ai(s: &CombatState, slot: usize, _: &mut dyn Chance) -> MoveId {
    match me(s, slot).intent() {
        guardian::CHARGING_UP => guardian::FIERCE_BASH,
        guardian::FIERCE_BASH => guardian::VENT_STEAM,
        guardian::VENT_STEAM => guardian::WHIRLWIND,
        guardian::CLOSE_UP => guardian::ROLL_ATTACK,
        guardian::ROLL_ATTACK => guardian::TWIN_SLAM,
        guardian::TWIN_SLAM => guardian::WHIRLWIND,
        _ => guardian::CHARGING_UP,
    }
}


fn old_none(_: &CombatState, _: usize, _: &mut dyn Chance) -> MoveId {
    NO_MOVE
}

/// The old AI of each kind, by name.
fn old_ai(k: MonsterKind) -> Old {
    match k.def().name {
        "None" => old_none,
        "Cultist" => old_cultist_ai,
        "Jaw Worm" => old_jaw_worm_ai,
        "Red Louse" | "Green Louse" => old_louse_ai,
        "Acid Slime (S)" => old_acid_slime_small_ai,
        "Acid Slime (M)" | "Acid Slime (L)" => old_acid_slime_ai,
        "Spike Slime (S)" => old_spike_slime_small_ai,
        "Spike Slime (M)" | "Spike Slime (L)" => old_spike_slime_ai,
        "Fungi Beast" => old_fungi_beast_ai,
        "Looter" => old_looter_ai,
        "Gremlin Nob" => old_gremlin_nob_ai,
        "Lagavulin" => old_lagavulin_ai,
        "Sentry" => old_sentry_ai,
        "Slime Boss" => old_slime_boss_ai,
        "Hexaghost" => old_hexaghost_ai,
        "The Guardian" => old_guardian_ai,
        n => panic!("no reference AI for {n}"),
    }
}

#[test]
fn tables_match_old_ais() {
    let mut checked = 0;
    for &k in MONSTER_KINDS.iter() {
        let n = k.def().moves.len() as MoveId;
        let ids: Vec<MoveId> = std::iter::once(NO_MOVE).chain(0..n).collect();
        for slot in 0..5usize {
            for &a in &ids {
                for &b in &ids {
                    let mut s = CombatState::new(&starter_deck(), 80, 80, Encounter::JawWorm, &mut Rng::new(1));
                    s.monsters[slot] = Monster::new(k, 20);
                    s.monsters[slot].moves = [a, b];
                    let old = traced(old_ai(k), &s, slot);
                    let new = traced(k.def().ai, &s, slot);
                    assert_eq!(old, new, "{} slot {slot} moves [{a}, {b}]", k.def().name);
                    checked += 1;
                }
            }
        }
    }
    assert!(checked > 1000, "{checked}");
}
