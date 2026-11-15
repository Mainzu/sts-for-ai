"""Skeptic's re-derivation of hp_coverage.py / exact_share.py headline numbers
(2026-10-30 big-picture review, questions A and B). Written independently:
reads the primary files directly, single-threaded, about a minute.

A. HP coverage
  - training caches cache/<ds>-effects_rows-v7-*/ : share of value-labelled
    (played == 1) examples at 1-8 and 1-4 HP; games' start HP.
  - the database draws (exact_drawn, 20% of value-loss weight): their rows
    are a fixed random permutation of db/train.sqlite's decision rows
    (learn.exact_order), so a random sample of decision rows with
    id <= the round's db_rows approximates their HP (dull decisions are
    skipped by the draw but not here). Read with sqlite3 mode=ro.
  - the gates: data/bench/tight2.json (rescore gate) and data/bench/tight.json
    (the gate the 10-28 night itself ran, 1160 fights); share of fights at
    1-8 HP with a 95% percentile bootstrap over cells.
B. Exact share and solve time
  - round.json rungs; solve seconds from "solve step <ds> (round k)" log
    lines keyed by dataset id (= round.json new_dataset); wall time from
    round.json mtimes (parent run's round.json for the start).

    .venv/Scripts/python scripts/analysis/check_coverage.py
"""

import glob
import gzip
import json
import os
import re
import sqlite3
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def load_rounds():
    rounds = {}
    for d in glob.glob(os.path.join(ROOT, "runs", "2026-10-2[78]-score+branch-s*")):
        r = json.load(open(os.path.join(d, "round.json"), encoding="utf-8"))
        rounds[os.path.basename(d)] = dict(r, mtime=os.path.getmtime(os.path.join(d, "round.json")))
    return rounds


def solve_seconds():
    """{dataset id: [solve seconds, ...]} from both logs (a dataset solved twice keeps both)."""
    out = {}
    for log in ("night.log", "night2.log"):
        for line in open(os.path.join(ROOT, "logs", log), encoding="utf-8"):
            m = re.match(r"solve step (\w+) \(round (\d+)\): .* (\d+)s$", line.strip())
            if m:
                out.setdefault(m.group(1), []).append((log, int(m.group(3))))
    return out


def part_b(rounds):
    solves = solve_seconds()
    s0_total = float(re.search(r"score\+branch-s0: run \S+, ([\d.]+) min",
                               open(os.path.join(ROOT, "logs", "night2.log"), encoding="utf-8").read()).group(1))
    s1_total = float(re.search(r"score\+branch-s1: run \S+, ([\d.]+) min",
                               open(os.path.join(ROOT, "logs", "night2.log"), encoding="utf-8").read()).group(1))
    by = {k: v for k, v in rounds.items()}
    s0r10 = next(v for k, v in by.items() if "-s0-r10-" in k)
    s1r10 = next(v for k, v in by.items() if "-s1-r10-" in k)
    rows = []
    for name, r in sorted(by.items(), key=lambda kv: kv[1]["mtime"]):
        if r["round"] == 0:
            continue
        g = r["rungs"]
        selfv = g["exact"] + g["search"] + g["outcome"]
        valued = selfv + g["exact_drawn"]
        sol = solves.get(r["new_dataset"], [])
        if "-s0-r6-" in name:  # crashed in night.log; redone at night2's start
            start = s0r10["mtime"] - s0_total * 60
            solve = [s for lg, s in sol if lg == "night2.log"][0]
        else:
            start = by[r["parent_run"]]["mtime"] if r["parent_run"] in by else None
            if "-s1-r1-" in name:  # parent is s0 r0; s1 started when s0 finished
                start = s0r10["mtime"]
            solve = sol[-1][1] if sol else None
        wall = r["mtime"] - start
        rows.append({"run": name, "round": r["round"], "valued": valued,
                     "exact": g["exact"], "drawn": g["exact_drawn"],
                     "count_share": (g["exact"] + g["exact_drawn"]) / valued,
                     "hit_share": g["exact"] / selfv,
                     "weight_share": 0.2 + 0.8 * g["exact"] / selfv,
                     "solve": solve, "wall": wall, "solve_share": solve / wall if solve else None,
                     "round0_in": r["window"]["round0_in"]})
    # consistency check of the s1 start: s1 total from log vs mtimes
    s1_span = (s1r10["mtime"] - s0r10["mtime"]) / 60
    return rows, {"s1_total_log_min": s1_total, "s1_span_mtime_min": s1_span}


def boot(cells, stat, n=2000, seed=11):
    rng = np.random.default_rng(seed)
    k = len(cells)
    v = [stat(np.concatenate([cells[i] for i in rng.integers(0, k, k)])) for _ in range(n)]
    return [round(float(np.percentile(v, 2.5)), 3), round(float(np.percentile(v, 97.5)), 3)]


def low(x):
    return float(((x >= 1) & (x <= 8)).mean())


def gate(path):
    t = json.load(open(path, encoding="utf-8"))
    res = {}
    for half, specs in t["halves"].items():
        cells = {}
        for s in specs:
            key = s["cell"] if "cell" in s else (s["encounter"], tuple(s["deck"]), s["hp"])  # tight.json: no cell id
            cells.setdefault(key, []).append(s)
        r = {"fights": len(specs), "cells": len(cells)}
        for grp in ("hallway", "elite", "boss", "all"):
            cs = [c for c in cells.values() if grp == "all" or c[0]["group"] == grp]
            pc = [np.array([s["hp"] for s in c], float) for c in cs]
            allhp = np.concatenate(pc)
            # per-cell HP is constant? (then cell share = fight share within a cell)
            const = all(len(set(x.tolist())) == 1 for x in pc)
            r[grp] = {"cells": len(cs), "fight_frac": round(len(allhp) / len(specs), 3),
                      "share_1_8": round(low(allhp), 3), "ci": boot(pc, low),
                      "cell_share_1_8": round(float(np.mean([low(x) for x in pc])), 3),
                      "median_hp": float(np.median(allhp)), "hp_const_per_cell": const}
        res[half] = r
    return res


def caches(rounds):
    night_ds = {r["new_dataset"]: (k, r["round"]) for k, r in rounds.items()}
    out = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "cache", "*-effects_rows-v7*"))):
        ds = os.path.basename(path)[:12]
        man = json.load(open(os.path.join(ROOT, "datasets", ds, "manifest.json"), encoding="utf-8"))
        if man["config"].get("set") != "train":
            continue
        hp = np.load(os.path.join(path, "hp.npy")).astype(float)
        st = np.load(os.path.join(path, "start_hp.npy")).astype(float)
        mx = np.load(os.path.join(path, "max_hp.npy")).astype(float)
        played = np.load(os.path.join(path, "played.npy")) == 1
        oc = np.load(os.path.join(path, "outcome.npy"))
        v = played
        lowv = v & (hp >= 1) & (hp <= 8)
        out[ds] = {"made_in": night_ds.get(ds, ("round-0 pool", 0)), "n_valued": int(v.sum()),
                   "valued_low_1_8": round(float(lowv.sum() / v.sum()), 4),
                   "valued_low_1_4": round(float((v & (hp >= 1) & (hp <= 4)).sum() / v.sum()), 4),
                   "hp_le_0_valued": int((v & (hp <= 0)).sum()),
                   "hp_gt_start": int((hp > st).sum()), "hp_gt_max": int((hp > mx).sum()),
                   "low_from_start_gt8": round(float((st[lowv] > 8).mean()), 4),
                   "low_start_median": float(np.median(st[lowv])),
                   "low_win": round(float((oc[lowv] > 0).mean()), 3), "all_win": round(float((oc[v] > 0).mean()), 3),
                   "low_count": int(lowv.sum()), "self_valued": int(v.sum())}
    return out


def start_hp_games(rounds):
    out = {}
    for k, r in rounds.items():
        ds = r["new_dataset"]
        p = os.path.join(ROOT, "datasets", ds, "games.jsonl.gz")
        if r["round"] == 0 or not os.path.exists(p):
            continue
        hps = []
        with gzip.open(p, "rt", encoding="utf-8") as f:
            for line in f:
                g = json.loads(line)
                if "branch_at" not in g:
                    hps.append(g["hp"])
        hps = np.array(hps)
        out[ds] = {"games": len(hps), "min": int(hps.min()), "share_eq_8": round(float((hps == 8).mean()), 4)}
    return out


def db_draw_hp(max_ids, n=8000, seed=5):
    """HP and turn of random decision rows of db/train.sqlite with id <= each bound."""
    import sts
    con = sqlite3.connect(f"file:{os.path.join(ROOT, 'db', 'train.sqlite')}?mode=ro", uri=True)
    top = max(max_ids)
    ids = sorted(set(np.random.default_rng(seed).integers(1, top + 1, n).tolist()))
    rows = []
    for i in range(0, len(ids), 500):
        ch = ids[i:i + 500]
        rows += con.execute("select id, state, turns_left from states where options is not null and id in (%s)"
                            % ",".join(map(str, ch))).fetchall()
    con.close()
    rid = np.array([r[0] for r in rows])
    hp = np.array([sts.Combat.decode(r[1]).player_hp() for r in rows], float)
    turn = np.array([sts.Combat.decode(r[1]).turn() for r in rows], float)
    tl = np.array([r[2] for r in rows])
    res = {}
    for b in max_ids:
        s = rid <= b
        res[int(b)] = {"n": int(s.sum()), "low_1_8": round(low(hp[s]), 3),
                       "low_1_4": round(float(((hp[s] >= 1) & (hp[s] <= 4)).mean()), 3),
                       "median_hp": float(np.median(hp[s])),
                       "turn_median": float(np.median(turn[s])), "turn_le_1": round(float((turn[s] <= 1).mean()), 3),
                       "low_turn_le_1": round(float((turn[s & (hp >= 1) & (hp <= 8)] <= 1).mean()), 3),
                       "turns_left_median": float(np.median(tl[s]))}
    return res


def main():
    rounds = load_rounds()
    rows, chk = part_b(rounds)
    res = {"B": {"rows": rows, "check": chk}}
    sel = [x for x in rows if x["run"].startswith("2026-10-28")]
    cs = np.array([x["count_share"] for x in sel])
    ss = np.array([x["solve_share"] for x in sel])
    ws = np.array([x["weight_share"] for x in sel])
    res["B"]["summary_10_28"] = {
        "n": len(sel), "count_share_mean": cs.mean(), "count_share_min": cs.min(), "count_share_max": cs.max(),
        "weight_share_mean": ws.mean(),
        "solve_share_mean": ss.mean(), "solve_share_median": float(np.median(ss)),
        "solve_share_min": ss.min(), "solve_share_max": ss.max(),
        "pooled": sum(x["solve"] for x in sel) / sum(x["wall"] for x in sel),
        "pooled_solve_s": sum(x["solve"] for x in sel), "pooled_wall_s": sum(x["wall"] for x in sel),
        "solve_share_excl_s0r6": float(np.mean([x["solve_share"] for x in sel if "-s0-r6-" not in x["run"]])),
        "count_share_round0_in": [round(x["count_share"], 4) for x in sel if x["round0_in"]]}
    res["B"]["summary_all20"] = sum(x["solve"] for x in rows) / sum(x["wall"] for x in rows)

    res["A"] = {"caches": caches(rounds), "start_hp": start_hp_games(rounds),
                "gate_tight2": gate(os.path.join(ROOT, "data", "bench", "tight2.json")),
                "gate_tight_night": gate(os.path.join(ROOT, "data", "bench", "tight.json"))}
    # DB draw HP at the s1 rounds whose window is fully cached
    s1 = {r["round"]: (k, r) for k, r in rounds.items() if "-s1-" in k}
    bounds = sorted({s1[k][1]["db_rows"] for k in (3, 4, 7)})
    res["A"]["db_draws"] = db_draw_hp(bounds)
    # Low-HP share of value-loss weight for s1 r3, r4, r7 (both window datasets cached).
    # round.json db_rows may be after the round's own solve; the draw happens
    # after the solve too, so it is the right bound.
    comb = {}
    for k in (3, 4, 7):
        name, r = s1[k]
        win = r["datasets"]["train"]
        c = [res["A"]["caches"].get(ds) for ds in win]
        if any(x is None for x in c):
            continue
        low_self = sum(x["low_count"] for x in c) / sum(x["self_valued"] for x in c)
        dbl = res["A"]["db_draws"][r["db_rows"]]["low_1_8"]
        comb[k] = {"window": win, "self_low_1_8": round(low_self, 4), "db_low_1_8": dbl,
                   "weight_low_1_8": round(0.8 * low_self + 0.2 * dbl, 4),
                   "count_low_1_8": None}
        g = r["rungs"]
        selfv = g["exact"] + g["search"] + g["outcome"]
        comb[k]["count_low_1_8"] = round((low_self * selfv + dbl * g["exact_drawn"]) / (selfv + g["exact_drawn"]), 4)
    res["A"]["combined"] = comb

    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, "check_coverage.json"), "w", encoding="utf-8"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=lambda x: round(float(x), 4)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
