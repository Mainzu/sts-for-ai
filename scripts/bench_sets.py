"""Evaluation bench test sets (fixed, seeded, regenerated identically).

Writes combat specs (encounter, deck, start HP, seed) to data/bench/:
- standard.json: starter + 5 random cards over all encounter groups (the
  check 5/6 mix). Halves: train (training pool), held_out (>= 2 of check 6's
  or check 9's held-out cards), silent_a and silent_b (check 8's tiers).
- families.json: hand-written matchup deck families played against every
  encounter. Each family has a train and a held_out version with the same
  role: 3 role cards plus 2 shared fillers.
- tight.json: the families' specs at the start HP where search + heuristic
  wins about 50% of that (family, half, encounter), from calibration.json.
  Cells calibration can't bring near 50% are left out (listed there).
- tight2.json (docs/specs/tight-fights-v2.md): the rounds' tight fights.
  Cells of a drawn deck (varied size; held_out: at least 2 held-out cards)
  x one encounter, PER_ENC2 per encounter and half, each at the start HP
  calibrated to ~50% (calibration2.json; undrawable cells are redrawn), plus
  the families' tight cells; SEEDS2 seeds per cell, each spec carrying its
  `cell` index.
- tight_silent.json (docs/specs/warm-start.md): halves silent_a and
  silent_b, decks from check 8's tiers (transfer.deck_a / deck_b) per
  encounter, PER_ENC_S cells per encounter and half at the Silent's start
  HP calibrated to ~50% (calibration_silent.json, v2's settings), SEEDS_S
  seeds per cell, each spec carrying its `cell` index.
- tight_bosses.json (docs/specs/tight-bosses.md): halves train and
  held_out, the bosses outside Encounter::ALL (NEW_BOSSES), PER_ENC_B cells
  per boss and half at the Ironclad's start HP calibrated to ~50%
  (calibration_bosses.json, v2's settings), SEEDS_B seeds per cell.

Start HP is null (the character's starting HP) in standard and families.

    python scripts/bench_sets.py [--out data/bench]
    python scripts/bench_sets.py --recalibrate     # reruns calibration.json first
    python scripts/bench_sets.py --calibrate2      # (re)runs calibration2.json first
    python scripts/bench_sets.py --topup2          # tops up its short encounters first
    python scripts/bench_sets.py --calibrate-silent  # (re)runs calibration_silent.json first
    python scripts/bench_sets.py --calibrate-bosses  # (re)runs calibration_bosses.json first
"""

import argparse
import json
import os
import time

import numpy as np

import selfplay
import sts
import stsnet
import transfer

BENCH = os.path.join(os.path.dirname(__file__), "..", "data", "bench")
VERSION = 1
HELD_OUT_ALL = selfplay.HELD_OUT_ALL | set(sts.held_out_card_names())
STANDARD_PER_GROUP = 100
SEEDS_PER_CELL = 10
# Tight-fight calibration: bisection on start HP, each probe on BISECT_GAMES
# calibration seeds, then the two HPs around 50% on FINAL_GAMES; the closer
# one is kept if its win rate is inside CAL_BAND (stricter than the 40-60%
# fresh-seed check, so calibration noise doesn't push cells out of it).
LIMIT = selfplay.LIMIT
MAX_HP = sts.Combat(selfplay.STARTER, "cultist").player_hp()
CAL_SEED = 5_000_000
TEST_SEED = 50_000_000  # past CAL_SEED + cells * 100_000
BISECT_GAMES = 400
FINAL_GAMES = 1600
TEST_GAMES = 1600
CAL_BAND = (0.42, 0.58)
# Tight fights v2 (docs/specs/tight-fights-v2.md): PER_ENC2 calibrated cells
# per encounter and half (15 encounters: 555 per half), SEEDS2 test seeds
# per cell, and half v1's calibration games: a cell only needs its outcome
# in doubt. Calibration runs on THREADS2 threads, leaving cores free. Seed
# ranges: past every v1 range and past the seeds sts.make_specs hashes from
# small inputs (input x 1,000,003 + i: v1's standard set ~2e9, self-play's
# well under 1e12).
PER_ENC2 = 37
SEEDS2 = 20
BISECT_GAMES2 = 200
FINAL_GAMES2 = 800
THREADS2 = 8
DECK2_SEED = 77
CAL2_SEED = 10**15
TEST2_SEED = 2 * 10**15
REDRAW2 = 6  # calibration batches per half before a short encounter is left short
# Silent tight fights (warm-start): v2's calibration settings and threads,
# seed ranges past tight2's test seeds (TEST2_SEED + cells * 100_000).
PER_ENC_S = 10
SEEDS_S = 20
DECK_S_SEED = 78
CAL_S_SEED = 3 * 10**15
TEST_S_SEED = 4 * 10**15
REDRAW_S = 3
SILENT_TIERS = (("silent_a", transfer.deck_a), ("silent_b", transfer.deck_b))
# Tight boss fights (docs/specs/tight-bosses.md): the bosses outside
# Encounter::ALL, v2's settings, seed ranges past tight_silent's.
NEW_BOSSES = ("hexaghost", "the_guardian")
PER_ENC_B = 37
SEEDS_B = 20
DECK_B_SEED = 79
CAL_B_SEED = 5 * 10**15
TEST_B_SEED = 6 * 10**15
REDRAW_B = 4

# family: (train role cards, held-out role cards, shared fillers)
FAMILIES = {
    "aoe": (["Cleave", "Cleave", "Cleave+"], ["Thunderclap", "Thunderclap", "Thunderclap+"], ["Shrug It Off", "Anger"]),
    "skill_heavy": (["Shrug It Off", "Shrug It Off+", "Flex"], ["Rage", "Rage+", "Flex"], ["Defend", "Defend+"]),
    "multi_hit": (["Pummel", "Pummel+", "Sword Boomerang"], ["Twin Strike", "Twin Strike", "Twin Strike+"],
                  ["Inflame", "Defend"]),
    "setup": (["Inflame", "Inflame+", "Combust"], ["Demon Form", "Metallicize", "Metallicize+"],
              ["Shrug It Off", "Defend"]),
    "debuff": (["Clothesline", "Clothesline+", "Bash"], ["Uppercut", "Uppercut+", "Go for the Eyes"],
               ["Dropkick", "Strike+"]),
}


def encounter_groups():
    """{encounter: group} over selfplay.GROUPS."""
    out = {}
    for g in selfplay.GROUPS:
        for enc, _, _ in sts.make_specs(g, 200, extra=0, seed=0):
            out[enc] = g
    return out


def standard_held_out_deck(rng):
    """Starter + 5 cards from the whole pool (check 9's cards included), at
    least 2 of them held out by check 6 or check 9."""
    pool = sts.deck_card_names() + sts.held_out_card_names()
    while True:
        extra = list(rng.choice(pool, 5))
        if sum(c in HELD_OUT_ALL for c in extra) >= 2:
            return selfplay.STARTER + extra


def spec(enc, deck, seed, character, **extra):
    return {"encounter": enc, "deck": [str(c) for c in deck], "hp": None, "seed": int(seed),
            "character": character, **extra}


def standard_set():
    groups = encounter_groups()
    halves = {}
    for i, (half, fn, ch) in enumerate([("train", selfplay.train_deck, "ironclad"),
                                        ("held_out", standard_held_out_deck, "ironclad"),
                                        ("silent_a", transfer.deck_a, "silent"),
                                        ("silent_b", transfer.deck_b, "silent")]):
        specs, _ = selfplay.make_specs(STANDARD_PER_GROUP, 201 + i, fn, character=ch)
        halves[half] = [spec(e, d, s, ch, group=groups[e]) for e, d, s in specs]
    return halves


def families_set():
    groups = encounter_groups()
    starter = selfplay.STARTER
    halves = {"train": [], "held_out": []}
    seed = 3_000_000
    for fam, (train, held, fill) in FAMILIES.items():
        for half, role in (("train", train), ("held_out", held)):
            for enc in sts.encounter_names():
                for _ in range(SEEDS_PER_CELL):
                    halves[half].append(spec(enc, starter + role + fill, seed, "ironclad", group=groups[enc], family=fam))
                    seed += 1
    return halves


def cells():
    """Every (family, half, encounter) the tight fights calibrate, in order."""
    return [(f, h, e) for f in FAMILIES for h in ("train", "held_out") for e in sts.encounter_names()]


def cell_deck(family, half):
    train, held, fill = FAMILIES[family]
    return selfplay.STARTER + (train if half == "train" else held) + fill


def cell_seeds(i, base, n):
    """Seeds of cell i from a seed range (calibration or test)."""
    return [base + i * 100_000 + k for k in range(n)]


def hp_win_rates(cells, queries, n, seed_base, threads=None, character="ironclad"):
    """{(cell index, hp): search + heuristic win rate} over `cells`
    [(encounter, deck)] on the first n seeds of each cell
    (`cell_seeds(i, seed_base, n)`); one sts.run per distinct hp."""
    by_hp = {}
    for i, hp in queries:
        by_hp.setdefault(hp, []).append(i)
    out = {}
    for hp, idx in sorted(by_hp.items()):
        specs = [(cells[i][0], cells[i][1], s) for i in idx for s in cell_seeds(i, seed_base, n)]
        res = sts.run("search", specs, limit=LIMIT, hp=hp, character=character,
                      **stsnet.job_threads({"threads": threads}))
        for j, i in enumerate(idx):
            out[(i, hp)] = sum(r["won"] for r in res[j * n:(j + 1) * n]) / n
    return out


def calibrate_cells(cells, bisect_games, final_games, seed_base, band=None, threads=None, character="ironclad"):
    """Bisection on start HP per cell [(encounter, deck)], probes on
    `bisect_games` seeds, the two HPs around 50% on `final_games`; per cell
    {"hp", "win_rate"} when the closer one is inside `band` (default
    CAL_BAND), else {"reason"}. Start HP runs from 1 to the character's max."""
    band = band or CAL_BAND
    MAX_HP = selfplay.max_hp(character)  # noqa: N806 (the module's MAX_HP is the Ironclad's)
    ends = hp_win_rates(cells, [(i, hp) for i in range(len(cells)) for hp in (1, MAX_HP)], bisect_games,
                        seed_base, threads, character)
    cand, bounds = {}, {}
    for i in range(len(cells)):
        if ends[(i, 1)] >= 0.5:
            cand[i] = [1]
        elif ends[(i, MAX_HP)] < 0.5:
            cand[i] = [MAX_HP]
        else:
            bounds[i] = (1, MAX_HP)  # win rate < 0.5 at lo, >= 0.5 at hi
    while bounds:
        mids = {i: (lo + hi) // 2 for i, (lo, hi) in bounds.items()}
        wr = hp_win_rates(cells, mids.items(), bisect_games, seed_base, threads, character)
        for i, m in mids.items():
            lo, hi = bounds[i]
            bounds[i] = (m, hi) if wr[(i, m)] < 0.5 else (lo, m)
            if bounds[i][1] - bounds[i][0] == 1:
                cand[i] = list(bounds.pop(i))
    final = hp_win_rates(cells, [(i, hp) for i, hps in cand.items() for hp in hps], final_games, seed_base, threads,
                         character)
    out = []
    for i in range(len(cells)):
        rates = {hp: final[(i, hp)] for hp in cand[i]}
        hp = min(rates, key=lambda h: (abs(rates[h] - 0.5), h))
        if band[0] <= rates[hp] <= band[1]:
            out.append({"hp": hp, "win_rate": round(rates[hp], 4)})
        elif cand[i] == [1]:
            out.append({"reason": f"wins {rates[1]:.2f} at 1 HP"})
        elif cand[i] == [MAX_HP]:
            out.append({"reason": f"wins {rates[MAX_HP]:.2f} at {MAX_HP} HP (max)"})
        else:
            lo, hi = cand[i]
            out.append({"reason": f"steep: wins {rates[lo]:.2f} at {lo} HP, {rates[hi]:.2f} at {hi} HP"})
    return out


def calibrate():
    """Bisection on start HP per cell; returns the calibration dict."""
    cs = cells()
    res = calibrate_cells([(e, cell_deck(f, h)) for f, h, e in cs], BISECT_GAMES, FINAL_GAMES, CAL_SEED)
    kept, excluded = [], []
    for (fam, half, enc), r in zip(cs, res):
        cell = {"family": fam, "half": half, "encounter": enc}
        (kept if "hp" in r else excluded).append({**cell, **r})
    return {"version": VERSION, "agent": "search", "evaluator": "heuristic", "limit": LIMIT,
            "bisect_games": BISECT_GAMES, "final_games": FINAL_GAMES, "band": list(CAL_BAND),
            "seed_base": CAL_SEED, "cells": kept, "excluded": excluded}


def dump_calibration(path, cal):
    """Settings on the first line, then one cell per line."""
    head = {k: v for k, v in cal.items() if k not in ("cells", "excluded")}
    parts = [json.dumps(head, sort_keys=True)[1:-1]]
    for key in ("cells", "excluded"):
        rows = ",\n".join("  " + json.dumps(c, sort_keys=True) for c in cal[key])
        parts.append(f' "{key}": [\n{rows}\n ]')
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("{" + ",\n".join(parts) + "\n}\n")


def load_calibration(bench=BENCH):
    path = os.path.join(bench, "calibration.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} missing: run scripts/bench_sets.py --recalibrate")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def tight_set(families, cal):
    """The families' specs of every calibrated cell, at its calibrated HP."""
    hp = {(c["family"], c["half"], c["encounter"]): c["hp"] for c in cal["cells"]}
    return {half: [{**s, "hp": hp[(s["family"], half, s["encounter"])]} for s in specs
                   if (s["family"], half, s["encounter"]) in hp]
            for half, specs in families.items()}


def held_out_varied_deck(rng):
    """Starter + 3-15 cards (varied size) from the whole pool, at least 2
    of them held out by check 6 or check 9."""
    pool = sts.deck_card_names() + sts.held_out_card_names()
    lo, hi = selfplay.VARIED["extra_cards"]
    while True:
        extra = list(rng.choice(pool, int(rng.integers(lo, hi + 1))))
        if sum(c in HELD_OUT_ALL for c in extra) >= 2:
            return selfplay.STARTER + extra


def calibrate2(per_enc=PER_ENC2, bisect_games=BISECT_GAMES2, final_games=FINAL_GAMES2, threads=THREADS2,
               log=print, prev=None):
    """Tight fights v2's calibration: per half, decks drawn (DECK2_SEED) for
    each encounter that still needs cells, calibrated in batches, the
    first `per_enc` inside the band kept per encounter; up to REDRAW2
    batches, then an encounter stays short. Each tried cell gets its own
    calibration seeds (its index over all tried cells).
    `prev`: a saved calibration with short encounters, topped up: its cells
    kept, fresh decks (seed [DECK2_SEED, top-up number]) drawn for the
    short encounters only, each batch sized by the encounter's kept share
    so far (cells kept / cells recorded, at least 5%)."""
    top = prev.get("topups", 0) + 1 if prev else 0
    rng = np.random.default_rng([DECK2_SEED, top] if top else DECK2_SEED)
    encs = sts.encounter_names()
    if prev:
        per_enc = prev["per_encounter"]
        kept, excluded, short, tried = list(prev["cells"]), list(prev["excluded"]), {}, prev["tried"]
    else:
        kept, excluded, short, tried = [], [], {}, 0

    def size(half, e, n):
        if not top:
            return -(-n * 4 // 3)
        k = sum(c["half"] == half and c["encounter"] == e for c in kept)
        share = max(0.05, k / max(1, k + sum(c["half"] == half and c["encounter"] == e for c in excluded)))
        return int(np.ceil(n * 4 / 3 / share))
    for half, deck_fn in (("train", selfplay.varied_deck), ("held_out", held_out_varied_deck)):
        need = {e: prev["short"].get(half, {}).get(e, 0) if prev else per_enc for e in encs}
        for _ in range(REDRAW2):
            if not any(need.values()):
                break
            batch = [(e, deck_fn(rng)) for e in encs for _ in range(size(half, e, need[e]) if need[e] else 0)]
            t = time.time()
            # cell i of this batch gets cell_seeds(tried + i, CAL2_SEED, n): no two tried cells share seeds
            res = calibrate_cells(batch, bisect_games, final_games, CAL2_SEED + tried * 100_000, threads=threads)
            for (e, deck), r in zip(batch, res):
                cell = {"half": half, "encounter": e, "deck": [str(c) for c in deck]}
                if "hp" not in r:
                    excluded.append({**cell, **r})
                elif need[e]:
                    kept.append({**cell, **r})
                    need[e] -= 1
            tried += len(batch)
            log(f"calibration v2 {half}: {len(batch)} cells in {time.time() - t:.0f}s, "
                f"{sum(need.values())} still needed")
        if any(need.values()):
            short[half] = {e: n for e, n in need.items() if n}
    return {"version": VERSION, "agent": "search", "evaluator": "heuristic", "limit": LIMIT,
            "per_encounter": per_enc, "bisect_games": bisect_games, "final_games": final_games,
            "band": list(CAL_BAND), "seed_base": CAL2_SEED, "deck_seed": DECK2_SEED, "tried": tried,
            "topups": top, "short": short, "cells": kept, "excluded": excluded}


def load_calibration2(bench=BENCH):
    path = os.path.join(bench, "calibration2.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} missing: run scripts/bench_sets.py --calibrate2")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def tight2_set(cal2, cal, seeds=SEEDS2):
    """{half: specs}: per half the families' tight cells (v1's calibration)
    then calibration2's cells, `seeds` specs each with test seeds of their
    own (TEST2_SEED, by cell index over both halves) and the cell's index
    within its half."""
    groups = encounter_groups()
    halves = {"train": [], "held_out": []}
    for c in cal["cells"]:
        halves[c["half"]].append({"encounter": c["encounter"], "deck": cell_deck(c["family"], c["half"]),
                                  "hp": c["hp"], "family": c["family"]})
    for c in cal2["cells"]:
        halves[c["half"]].append({"encounter": c["encounter"], "deck": c["deck"], "hp": c["hp"]})
    out, j = {}, 0
    for half, cs in halves.items():
        out[half] = []
        for k, c in enumerate(cs):
            extra = {"family": c["family"]} if "family" in c else {}
            out[half] += [spec(c["encounter"], c["deck"], s, "ironclad", hp=c["hp"], cell=k,
                               group=groups[c["encounter"]], **extra) for s in cell_seeds(j, TEST2_SEED, seeds)]
            j += 1
    return out


def calibrate_silent(per_enc=PER_ENC_S, bisect_games=BISECT_GAMES2, final_games=FINAL_GAMES2, threads=THREADS2,
                     log=print):
    """The Silent tight fights' calibration: per tier, decks drawn
    (DECK_S_SEED) for each encounter that still needs cells, calibrated
    for the Silent in batches, the first `per_enc` inside the band kept per
    encounter; up to REDRAW_S batches, then an encounter stays short. An
    encounter whose batch kept no cell isn't redrawn (it is too easy or
    too hard for the Silent at any start HP, as most hallway fights are).
    Each tried cell gets its own calibration seeds (its index over all
    tried cells, from CAL_S_SEED)."""
    rng = np.random.default_rng(DECK_S_SEED)
    encs = sts.encounter_names()
    kept, excluded, short, tried = [], [], {}, 0
    for half, deck_fn in SILENT_TIERS:
        need = {e: per_enc for e in encs}
        dry = set()  # encounters whose last batch kept nothing
        for _ in range(REDRAW_S):
            if not any(n for e, n in need.items() if e not in dry):
                break
            batch = [(e, deck_fn(rng)) for e in encs if e not in dry for _ in range(-(-need[e] * 4 // 3))]
            t = time.time()
            res = calibrate_cells(batch, bisect_games, final_games, CAL_S_SEED + tried * 100_000, threads=threads,
                                  character="silent")
            before = dict(need)
            for (e, deck), r in zip(batch, res):
                cell = {"half": half, "encounter": e, "deck": [str(c) for c in deck]}
                if "hp" not in r:
                    excluded.append({**cell, **r})
                elif need[e]:
                    kept.append({**cell, **r})
                    need[e] -= 1
            dry |= {e for e in {e for e, _ in batch} if need[e] == before[e]}
            tried += len(batch)
            log(f"calibration silent {half}: {len(batch)} cells in {time.time() - t:.0f}s, "
                f"{sum(need.values())} still needed")
        if any(need.values()):
            short[half] = {e: n for e, n in need.items() if n}
    return {"version": VERSION, "agent": "search", "evaluator": "heuristic", "limit": LIMIT, "character": "silent",
            "per_encounter": per_enc, "bisect_games": bisect_games, "final_games": final_games,
            "band": list(CAL_BAND), "seed_base": CAL_S_SEED, "deck_seed": DECK_S_SEED, "tried": tried,
            "short": short, "cells": kept, "excluded": excluded}


def load_calibration_silent(bench=BENCH):
    path = os.path.join(bench, "calibration_silent.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} missing: run scripts/bench_sets.py --calibrate-silent")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def tight_silent_set(cal_s, seeds=SEEDS_S):
    """{tier: specs}: each calibrated Silent cell, `seeds` specs with test
    seeds of their own (TEST_S_SEED, by cell index over both tiers) and the
    cell's index within its tier."""
    groups = encounter_groups()
    out, j = {half: [] for half, _ in SILENT_TIERS}, 0
    for half in out:
        for k, c in enumerate(c for c in cal_s["cells"] if c["half"] == half):
            out[half] += [spec(c["encounter"], c["deck"], s, "silent", hp=c["hp"], cell=k,
                               group=groups[c["encounter"]]) for s in cell_seeds(j, TEST_S_SEED, seeds)]
            j += 1
    return out


def calibrate_bosses(per_enc=PER_ENC_B, bisect_games=BISECT_GAMES2, final_games=FINAL_GAMES2, threads=THREADS2,
                     log=print):
    """The tight boss fights' calibration: as calibrate_silent, for the
    Ironclad's train and held-out deck halves and NEW_BOSSES (from
    DECK_B_SEED and CAL_B_SEED, up to REDRAW_B batches)."""
    rng = np.random.default_rng(DECK_B_SEED)
    kept, excluded, short, tried = [], [], {}, 0
    for half, deck_fn in (("train", selfplay.varied_deck), ("held_out", held_out_varied_deck)):
        need = {e: per_enc for e in NEW_BOSSES}
        dry = set()  # encounters whose last batch kept nothing
        for _ in range(REDRAW_B):
            if not any(n for e, n in need.items() if e not in dry):
                break
            batch = [(e, deck_fn(rng)) for e in NEW_BOSSES if e not in dry for _ in range(-(-need[e] * 4 // 3))]
            t = time.time()
            res = calibrate_cells(batch, bisect_games, final_games, CAL_B_SEED + tried * 100_000, threads=threads)
            before = dict(need)
            for (e, deck), r in zip(batch, res):
                cell = {"half": half, "encounter": e, "deck": [str(c) for c in deck]}
                if "hp" not in r:
                    excluded.append({**cell, **r})
                elif need[e]:
                    kept.append({**cell, **r})
                    need[e] -= 1
            dry |= {e for e in {e for e, _ in batch} if need[e] == before[e]}
            tried += len(batch)
            log(f"calibration bosses {half}: {len(batch)} cells in {time.time() - t:.0f}s, "
                f"{sum(need.values())} still needed")
        if any(need.values()):
            short[half] = {e: n for e, n in need.items() if n}
    return {"version": VERSION, "agent": "search", "evaluator": "heuristic", "limit": LIMIT, "character": "ironclad",
            "per_encounter": per_enc, "bisect_games": bisect_games, "final_games": final_games,
            "band": list(CAL_BAND), "seed_base": CAL_B_SEED, "deck_seed": DECK_B_SEED, "tried": tried,
            "short": short, "cells": kept, "excluded": excluded}


def load_calibration_bosses(bench=BENCH):
    path = os.path.join(bench, "calibration_bosses.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} missing: run scripts/bench_sets.py --calibrate-bosses")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def tight_bosses_set(cal_b, seeds=SEEDS_B):
    """{half: specs}: each calibrated boss cell, `seeds` specs with test
    seeds of their own (TEST_B_SEED, by cell index over both halves),
    group "boss" and the cell's index within its half."""
    out, j = {"train": [], "held_out": []}, 0
    for half in out:
        for k, c in enumerate(c for c in cal_b["cells"] if c["half"] == half):
            out[half] += [spec(c["encounter"], c["deck"], s, "ironclad", hp=c["hp"], cell=k, group="boss")
                          for s in cell_seeds(j, TEST_B_SEED, seeds)]
            j += 1
    return out


def build_sets(cal=None, cal2=None, bench=BENCH, cal_s=None, cal_b=None):
    families = families_set()
    cal = cal or load_calibration(bench)
    out = {"standard": standard_set(), "families": families, "tight": tight_set(families, cal)}
    if cal2 is not None or os.path.exists(os.path.join(bench, "calibration2.json")):
        out["tight2"] = tight2_set(cal2 or load_calibration2(bench), cal)
    if cal_s is not None or os.path.exists(os.path.join(bench, "calibration_silent.json")):
        out["tight_silent"] = tight_silent_set(cal_s or load_calibration_silent(bench))
    if cal_b is not None or os.path.exists(os.path.join(bench, "calibration_bosses.json")):
        out["tight_bosses"] = tight_bosses_set(cal_b or load_calibration_bosses(bench))
    return out


def dump(path, name, halves):
    """One spec per line so diffs stay readable; byte-identical per input."""
    parts = []
    for half, specs in halves.items():
        rows = ",\n".join("  " + json.dumps(s, sort_keys=True) for s in specs)
        parts.append(f" {json.dumps(half)}: [\n{rows}\n ]")
    head = f'{{"set": {json.dumps(name)}, "version": {VERSION}, "halves": {{\n'
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(head + ",\n".join(parts) + "\n}}\n")


def write_sets(out=BENCH, cal=None, cal2=None, cal_s=None, cal_b=None):
    os.makedirs(out, exist_ok=True)
    for name, halves in build_sets(cal, cal2, cal_s=cal_s, cal_b=cal_b).items():
        dump(os.path.join(out, name + ".json"), name, halves)


def load_set(name, bench=BENCH):
    """{half: [spec dict]} of a saved set."""
    with open(os.path.join(bench, name + ".json"), encoding="utf-8") as f:
        return json.load(f)["halves"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=BENCH)
    ap.add_argument("--recalibrate", action="store_true", help="rerun tight-fight calibration first")
    ap.add_argument("--calibrate2", action="store_true", help="(re)run tight fights v2's calibration first")
    ap.add_argument("--topup2", action="store_true", help="top up calibration2.json's short encounters first")
    ap.add_argument("--calibrate-silent", action="store_true", help="(re)run the Silent tight fights' calibration first")
    ap.add_argument("--calibrate-bosses", action="store_true", help="(re)run the tight boss fights' calibration first")
    args = ap.parse_args()
    cal = cal2 = cal_s = cal_b = None
    if args.recalibrate:
        t = time.time()
        cal = calibrate()
        os.makedirs(args.out, exist_ok=True)
        dump_calibration(os.path.join(args.out, "calibration.json"), cal)
        print(f"calibrated {len(cal['cells'])} cells, excluded {len(cal['excluded'])} in {time.time() - t:.0f}s")
    if args.calibrate2 or args.topup2:
        t = time.time()
        cal2 = calibrate2(prev=load_calibration2(args.out) if args.topup2 else None)
        os.makedirs(args.out, exist_ok=True)
        dump_calibration(os.path.join(args.out, "calibration2.json"), cal2)
        print(f"calibrated v2 {len(cal2['cells'])} cells, excluded {len(cal2['excluded'])}, short {cal2['short']} "
              f"in {time.time() - t:.0f}s")
    if args.calibrate_silent:
        t = time.time()
        cal_s = calibrate_silent()
        os.makedirs(args.out, exist_ok=True)
        dump_calibration(os.path.join(args.out, "calibration_silent.json"), cal_s)
        print(f"calibrated silent {len(cal_s['cells'])} cells, excluded {len(cal_s['excluded'])}, "
              f"short {cal_s['short']} in {time.time() - t:.0f}s")
    if args.calibrate_bosses:
        t = time.time()
        cal_b = calibrate_bosses()
        os.makedirs(args.out, exist_ok=True)
        dump_calibration(os.path.join(args.out, "calibration_bosses.json"), cal_b)
        print(f"calibrated bosses {len(cal_b['cells'])} cells, excluded {len(cal_b['excluded'])}, "
              f"short {cal_b['short']} in {time.time() - t:.0f}s")
    write_sets(args.out, cal, cal2, cal_s, cal_b)
    for name in ("standard", "families", "tight", "tight2", "tight_silent", "tight_bosses"):
        if not os.path.exists(os.path.join(args.out, name + ".json")):
            continue
        halves = load_set(name, args.out)
        print(f"{name}: " + ", ".join(f"{h} {len(s)}" for h, s in halves.items()))


if __name__ == "__main__":
    main()
