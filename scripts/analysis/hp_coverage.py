"""Question A of the 2026-10-30 big-picture review: do the nets' training
games cover the low-HP states that dominate the tight-fight gate?

Training side (no engine needed):
- The feature caches of the 2026-10-28 night's self-play datasets still on
  disk (cache/<dataset>-effects_rows-v7-<labels>/): per training example the
  player's HP at that state (`hp.npy`, the engine's player.hp), `max_hp`,
  `start_hp`, `group` (0 hallway, 1 elite, 2 boss), `option` (-1 = a
  decision state, >= 0 = an option's afterstate) and `played` (1 = on the
  played line: the examples with a value label; 0 = ranking only).
  Which datasets: their manifests (datasets/<id>/manifest.json) give round
  and parent; the s0 datasets of that night have no cache left, so for them
  only the games' start HP (datasets/<id>/games.jsonl.gz "hp") is read.
- Self-play start HP is VARIED["hp"] = [0.1, 1.0] of max HP
  (scripts/selfplay.py varied_hp): ceil(0.1 x 80) = 8 HP at least for the
  Ironclad.

Gate side:
- data/bench/tight2.json: each fight's start HP; the HP is fixed per cell.
- In-fight states: `--replay K` plays K fights per tight2 cell with the
  heuristic agent (search + hand-written evaluator, limit 16, one thread)
  and records the player's HP at every recorded state. The nets' own lines
  differ, but the start HP bounds both from above (no in-combat healing in
  these decks short of Reaper/Feed, which the replay would show).

Shares over cells come with a 95% percentile bootstrap over cells (fights
cluster by cell); training shares are over examples (clustered by game, but
~6,000 games per dataset, so the clustering widens them little).

    .venv/Scripts/python scripts/analysis/hp_coverage.py [--replay 2]
"""

import argparse
import glob
import gzip
import json
import os
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(HERE, "out")
GROUPS = ["hallway", "elite", "boss"]
LOW = 8  # "low HP": 1-8 HP (8 = the lowest self-play start HP for the Ironclad)
BINS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 16, 20, 30, 40, 60, 81]
FRAC_BINS = [0, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0001]


def manifest(ds):
    with open(os.path.join(ROOT, "datasets", ds, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def night_datasets():
    """[(dataset id, run label, round)] of the 10-28 night's training sets
    (round.json of every 10-27/10-28 score+branch round names its window)."""
    out = {}
    for d in sorted(glob.glob(os.path.join(ROOT, "runs", "2026-10-2[78]-score+branch-s*"))):
        with open(os.path.join(d, "round.json"), encoding="utf-8") as f:
            r = json.load(f)
        for ds in r["datasets"]["train"]:
            if ds not in out:
                m = manifest(ds)
                out[ds] = (m["parent_model"] or "round-0 pool", m["config"].get("round", 0))
    return out


def hist(vals, bins):
    h, _ = np.histogram(vals, bins=bins)
    return (h / max(len(vals), 1)).round(4).tolist()


def boot_cells(cell_vals, stat, n=2000, seed=0):
    """95% percentile bootstrap of `stat` over resampled cells; `cell_vals`
    is a list of per-cell arrays."""
    rng = np.random.default_rng(seed)
    k = len(cell_vals)
    out = []
    for _ in range(n):
        pick = rng.integers(0, k, k)
        out.append(stat(np.concatenate([cell_vals[i] for i in pick])))
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]


def training_side():
    res = {"caches": {}, "start_hp_only": {}}
    night = night_datasets()
    for path in sorted(glob.glob(os.path.join(ROOT, "cache", "*-effects_rows-v7*"))):
        ds = os.path.basename(path)[:12]
        m = manifest(ds)
        if m["config"].get("set") != "train":
            continue
        a = {k: np.load(os.path.join(path, k + ".npy"), mmap_mode="r") for k in
             ("hp", "max_hp", "start_hp", "group", "option", "played")}
        hp = np.asarray(a["hp"], np.float64)
        frac = hp / np.asarray(a["max_hp"], np.float64)
        grp = np.asarray(a["group"])
        dec = np.asarray(a["option"]) == -1
        val = np.asarray(a["played"]) == 1
        entry = {"round": m["config"].get("round", 0), "parent": m["parent_model"], "n_games": m["n_games"],
                 "in_night_window": ds in night, "n_examples": int(len(hp))}
        for name, sel in (("all", np.ones(len(hp), bool)), ("valued", val), ("decision", dec),
                          ("hallway_valued", val & (grp == 0))):
            h = hp[sel]
            entry[name] = {
                "n": int(sel.sum()),
                "share_hp_1_8": float(((h >= 1) & (h <= LOW)).mean()),
                "share_hp_1_4": float(((h >= 1) & (h <= 4)).mean()),
                "share_hp_le0": float((h <= 0).mean()),
                "share_frac_le_0.1": float((frac[sel] <= 0.1).mean()),
                "quantiles_hp_5_25_50": np.percentile(h, [5, 25, 50]).tolist(),
                "hist_hp": hist(h, BINS),
                "hist_frac": hist(frac[sel], FRAC_BINS),
            }
        sh = np.asarray(a["start_hp"], np.float64)[dec]
        entry["start_hp_min"] = float(sh.min())
        # The low-HP training states: how far below their game's start HP
        # they are (the gate's low HP is the fight's start, full enemy HP).
        lowv = val & (hp >= 1) & (hp <= LOW)
        st_low = np.asarray(a["start_hp"], np.float64)[lowv]
        entry["low_valued_start_hp_quantiles_25_50_75"] = np.percentile(st_low, [25, 50, 75]).tolist()
        entry["low_valued_share_at_start_hp"] = float((st_low == hp[lowv]).mean())
        # Their real outcome (score; 0 = the game was lost): the gate's cells
        # are calibrated to ~50% heuristic wins.
        outc = np.load(os.path.join(path, "outcome.npy"), mmap_mode="r")
        entry["low_valued_win_share"] = float((np.asarray(outc)[lowv] > 0).mean())
        entry["valued_win_share"] = float((np.asarray(outc)[val] > 0).mean())
        entry["start_hp_share_le_8"] = float((sh <= LOW).mean())
        res["caches"][ds] = entry
    # Start HP of the night's game records (every dataset, cache or not).
    for ds, (parent, rnd) in sorted(night.items(), key=lambda x: x[1][1]):
        hps, n_branch = [], 0
        with gzip.open(os.path.join(ROOT, "datasets", ds, "games.jsonl.gz"), "rt", encoding="utf-8") as f:
            for line in f:
                g = json.loads(line)
                if "branch_at" in g:
                    n_branch += 1
                    continue
                hps.append(g["hp"])
        hps = np.asarray(hps)
        res["start_hp_only"][ds] = {"parent": parent, "round": rnd, "games": int(len(hps)), "branch_games": n_branch,
                                    "min": int(hps.min()), "share_le_8": float((hps <= LOW).mean()),
                                    "share_le_12": float((hps <= 12).mean())}
    return res


def gate_side(replay_k, budget_s):
    with open(os.path.join(ROOT, "data", "bench", "tight2.json"), encoding="utf-8") as f:
        t2 = json.load(f)
    res = {}
    for half, specs in t2["halves"].items():
        cells = {}
        for s in specs:
            cells.setdefault(s["cell"], []).append(s)
        r = {"fights": len(specs), "cells": len(cells)}
        for gname in GROUPS + ["all"]:
            cs = [c for c in cells.values() if gname == "all" or c[0]["group"] == gname]
            hp = np.array([s["hp"] for c in cs for s in c], np.float64)
            per_cell = [np.array([s["hp"] for s in c], np.float64) for c in cs]
            low = lambda x: float(((x >= 1) & (x <= LOW)).mean())  # noqa: E731
            r[gname] = {"cells": len(cs), "fights": int(len(hp)), "fight_share": len(hp) / len(specs),
                        "start_share_hp_1_8": low(hp), "start_share_hp_1_8_ci": boot_cells(per_cell, low),
                        "start_hp_quantiles_25_50_75": np.percentile(hp, [25, 50, 75]).tolist(),
                        "start_frac_le_0.1": float((hp / 80 <= 0.1).mean()),
                        "hist_start_hp": hist(hp, BINS)}
        res[half] = r
    if replay_k:
        import sts
        t0 = time.perf_counter()
        for half, specs in t2["halves"].items():
            t_half = time.perf_counter()
            cells = {}
            for s in specs:
                cells.setdefault(s["cell"], []).append(s)
            per_cell, per_cell_g, n_done, healed = [], [], 0, 0
            # cells in a fixed shuffled order, so a budget cut keeps a random subset of every group
            order = np.random.default_rng(1).permutation(sorted(cells))
            for cid in order:
                c = cells[int(cid)]
                if time.perf_counter() - t_half > budget_s / 2:
                    break
                pick = c[:replay_k]
                out = sts.run("search", [(s["encounter"], s["deck"], s["seed"]) for s in pick], hp=pick[0]["hp"],
                              character=pick[0]["character"], record=True, threads=1, limit=16)
                hps = []
                for s, o in zip(pick, out):
                    h = [st.player_hp() for st in o["states"]]
                    healed += int(max(h) > s["hp"])
                    hps += h
                per_cell.append(np.asarray(hps, np.float64))
                per_cell_g.append(pick[0]["group"])
                n_done += len(pick)
            low = lambda x: float(((x >= 1) & (x <= LOW)).mean())  # noqa: E731
            r = {"cells_replayed": len(per_cell), "fights_replayed": n_done, "fights_with_hp_above_start": healed}
            for gname in GROUPS + ["all"]:
                cv = [v for v, g in zip(per_cell, per_cell_g) if gname == "all" or g == gname]
                if not cv:
                    continue
                allv = np.concatenate(cv)
                r[gname] = {"cells": len(cv), "states": int(len(allv)), "state_share_hp_1_8": low(allv),
                            "state_share_hp_1_8_ci": boot_cells(cv, low, n=1000),
                            "state_hp_quantiles_25_50_75": np.percentile(allv, [25, 50, 75]).tolist(),
                            "hist_state_hp": hist(allv, BINS)}
            res[half]["replay"] = r
        res["replay_seconds"] = time.perf_counter() - t0
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", type=int, default=0, help="fights per tight2 cell to replay for in-fight HP (0: none)")
    ap.add_argument("--budget", type=float, default=90.0, help="seconds for the replay, split between the halves (cells beyond it are skipped)")
    args = ap.parse_args()
    tr = training_side()
    gate = gate_side(args.replay, args.budget)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "hp_coverage.json"), "w", encoding="utf-8") as f:
        json.dump({"bins_hp": BINS, "bins_frac": FRAC_BINS, "training": tr, "gate": gate}, f, indent=1)

    print(f"HP bins (left edges): {BINS[:-1]}")
    print("\n== training caches (10-28 night self-play + round-0 pool); share of examples at 1-8 HP")
    print(f"{'dataset':12} {'rnd':>3} {'window':>6} {'n_ex':>7} {'all':>6} {'valued':>6} {'decis':>6} "
          f"{'hallV':>6} {'<=4':>6} {'frac<=.1':>8} {'p5 p25 p50 (valued)':>22} {'minStart':>8}")
    for ds, e in tr["caches"].items():
        v = e["valued"]
        print(f"{ds:12} {e['round']:>3} {str(e['in_night_window']):>6} {e['n_examples']:>7} "
              f"{e['all']['share_hp_1_8']:6.3f} {v['share_hp_1_8']:6.3f} {e['decision']['share_hp_1_8']:6.3f} "
              f"{e['hallway_valued']['share_hp_1_8']:6.3f} {v['share_hp_1_4']:6.3f} {v['share_frac_le_0.1']:8.3f} "
              f"{str([round(x) for x in v['quantiles_hp_5_25_50']]):>22} {e['start_hp_min']:8.0f}")
    for ds, e in tr["caches"].items():
        print(f"  {ds}: valued examples at 1-8 HP: their game's start HP q25/50/75 "
              f"{e['low_valued_start_hp_quantiles_25_50_75']}, share still at start HP {e['low_valued_share_at_start_hp']:.3f}, "
              f"won {e['low_valued_win_share']:.3f} (all valued: {e['valued_win_share']:.3f})")
    print("  valued hist:", {ds: e["valued"]["hist_hp"][:9] for ds, e in list(tr["caches"].items())[:2]})
    print("\n== start HP of the night's self-play games (non-branch games)")
    for ds, e in tr["start_hp_only"].items():
        print(f"{ds} round {e['round']:>2} parent {e['parent']}: {e['games']} games, min {e['min']}, "
              f"share <=8 {e['share_le_8']:.3f}, <=12 {e['share_le_12']:.3f}")
    print("\n== tight2 gate: start HP (per fight; CI over cells)")
    for half in ("train", "held_out"):
        g = gate[half]
        for gname in GROUPS + ["all"]:
            x = g[gname]
            ci = x["start_share_hp_1_8_ci"]
            print(f"{half:8} {gname:7} cells {x['cells']:>3} fights {x['fights']:>5} ({x['fight_share']:.2f} of gate) "
                  f"share 1-8 HP {x['start_share_hp_1_8']:.3f} [{ci[0]:.3f}, {ci[1]:.3f}] "
                  f"q25/50/75 {x['start_hp_quantiles_25_50_75']}")
        if "replay" in g:
            r = g["replay"]
            print(f"  replay: {r['cells_replayed']} cells, {r['fights_replayed']} fights, "
                  f"{r['fights_with_hp_above_start']} fights ever above start HP")
            for gname in GROUPS + ["all"]:
                if gname in r:
                    x = r[gname]
                    ci = x["state_share_hp_1_8_ci"]
                    print(f"  {gname:7} states {x['states']:>6}: share 1-8 HP {x['state_share_hp_1_8']:.3f} "
                          f"[{ci[0]:.3f}, {ci[1]:.3f}] q25/50/75 {x['state_hp_quantiles_25_50_75']}")
    if "replay_seconds" in gate:
        print(f"replay seconds: {gate['replay_seconds']:.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
