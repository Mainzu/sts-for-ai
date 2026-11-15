"""The run value as the choosers' unit (docs/specs/run-value-chooser.md):
V(h, j, boss, deck) = P(reach the boss at h' | HP h at the start of floor
j) x P(win the boss | h', deck), the first from a fit set of gauntlet
sequences (neighbours by HP at floor j), the second from the boss's causal
curve shifted to the deck's own level.

    .venv/Scripts/python scripts/run_value_unit.py pickrate results/gauntlet/<vrun file>.json
"""

import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import gauntlet  # noqa: E402

# P(win | entry HP) per boss, one-turn causal replays of the headline decks
# (b39d1, 2026-11-02; results doc "Boss replays: the boss curve is causal").
CURVE_HP = (30, 40, 50, 60, 70, 80)
BOSS_CURVE = {
    "slime_boss": (0.62, 0.83, 0.92, 0.97, 0.98, 0.99),
    "hexaghost": (0.33, 0.45, 0.59, 0.72, 0.86, 0.90),
    "the_guardian": (0.07, 0.25, 0.49, 0.71, 0.88, 0.95),
}
P_CLIP = (0.02, 0.98)
NEAR_HP = 5
NEAR_MIN = 20
BOSS_FLOOR = len(gauntlet.SHAPE) - 1


def logit(p):
    p = min(max(p, P_CLIP[0]), P_CLIP[1])
    return math.log(p / (1 - p))


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def curve(boss, h, table=BOSS_CURVE):
    """The boss's causal P(win | entry HP), linear between grid points,
    clipped to the grid's ends."""
    ys = table[boss]
    return float(np.interp(h, CURVE_HP, ys))


class RunValue:
    def __init__(self, fit_rows, table=BOSS_CURVE):
        self.table = table
        # per floor j: arrays of (HP at the start of j, HP at the boss after the rest or -1 if died before it)
        self.by_floor = {}
        for j in range(BOSS_FLOOR):
            hp, boss_hp = [], []
            for r in fit_rows:
                if len(r["floors"]) > j:
                    hp.append(r["floors"][j]["hp_start"])
                    boss_hp.append(r["floors"][BOSS_FLOOR]["hp_start"] if len(r["floors"]) > BOSS_FLOOR else -1)
            self.by_floor[j] = (np.array(hp, float), np.array(boss_hp, float))

    def pwin(self, boss, h, delta=0.0):
        return sigmoid(logit(curve(boss, h, self.table)) + delta)

    def delta(self, boss, hp_now, boss_fights, max_hp=gauntlet.MAX_HP):
        """The deck's shift: its 8 boss fights at rest(hp_now) against the curve there."""
        p = (sum(bool(r["won"]) for r in boss_fights) + 0.5) / (len(boss_fights) + 1)
        return logit(p) - logit(curve(boss, gauntlet.rest(hp_now, max_hp), self.table))

    def neighbours(self, j, h):
        hp, boss_hp = self.by_floor[j]
        if len(hp) == 0:
            return boss_hp
        order = np.argsort(np.abs(hp - h), kind="stable")
        n = max(NEAR_MIN, int(np.sum(np.abs(hp - h) <= NEAR_HP)))
        return boss_hp[order[:n]]

    def value(self, h, j, boss, delta, max_hp=gauntlet.MAX_HP):
        """V(h, j, boss, deck): HP h at the start of floor j (before the rest
        if j is the boss floor)."""
        if j >= BOSS_FLOOR:
            return self.pwin(boss, gauntlet.rest(h, max_hp), delta)
        nb = self.neighbours(j, h)
        if len(nb) == 0:
            return 0.0
        return float(np.mean([self.pwin(boss, b, delta) if b >= 0 else 0.0 for b in nb]))

    def score(self, k, hp_now, boss, parts, max_hp=gauntlet.MAX_HP):
        """An option's score after winning floor k at HP hp_now: `parts` =
        [next-floor fights, boss fights] ({won, hp_end} each), or just the
        boss fights at the floor before the boss."""
        nxt = parts[0]
        if k + 1 >= BOSS_FLOOR:
            return float(np.mean([bool(r["won"]) for r in nxt]))
        d = self.delta(boss, hp_now, parts[1], max_hp)
        vals = [self.value(min(max_hp, int(r["hp_end"])), k + 2, boss, d, max_hp) if r["won"] else 0.0 for r in nxt]
        return float(np.mean(vals))


def load_fit(path, first, n):
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)["sequences"]
    return [r for r in rows if first <= r["i"] < first + n]


def pickrate(path):
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)["sequences"]
    by = {}
    for r in rows:
        for k, fl in enumerate(r["floors"]):
            if "took_sim" in fl:
                by.setdefault(k + 1, []).append(fl["took"] != fl["took_sim"])
    allv = [x for v in by.values() for x in v]
    print(f"{path}: {len(allv)} reward rows, pick changed {np.mean(allv):.3f}" if allv else f"{path}: no took_sim rows")
    for k, v in sorted(by.items()):
        print(f"  floor {k:2d} n {len(v):4d} changed {np.mean(v):.3f}")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("pickrate",))
    ap.add_argument("file")
    args = ap.parse_args(argv)
    pickrate(args.file)


if __name__ == "__main__":
    main()
