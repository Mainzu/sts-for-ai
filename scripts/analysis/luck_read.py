"""Step 1b of lane luck-corrected-labels (docs/specs/luck-corrected-labels.md):
how much the luck correction narrows a paired gauntlet read.

Plays the first N one-turn cell sequences (gauntlet.run, the cell
gauntlet's default settings) for two players with each fight's luck logged
by the unpriced luck net (sts.run luck=, the same settings as step 1a),
checks the raw floors equal the players' gauntlet files (luck logging leaves
the games unchanged), and reports the paired sd of the sequences' end HP,
raw and corrected: corrected end HP = end HP - 100 x the sequence's summed
luck (one score unit is 100 HP of a won fight). ratio = corrected sd / raw
sd, its se by bootstrap over sequences. Pass (the lane's go): ratio <= 0.75.
Also, descriptive: each player's unpaired end-HP sd, raw and corrected.

    python scripts/analysis/luck_read.py [--sequences 100] [--threads 4] [--out results/luck/luck-read-cells.json]
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import bench  # noqa: E402
import gauntlet  # noqa: E402
import gauntlet_protocol as gp  # noqa: E402
import two_turn_games  # noqa: E402

NET = "runs/2026-10-29-seed-check-r2-s1-1a789b2/model.pt"
FILES = ("results/gauntlet/net1029-hpb0.01.json", "results/gauntlet/net1029-hpb0.01-tsl1.json")
BAR = 0.75
BOOT = 2000


def play_with_luck(player, luck, threads):
    """A gauntlet `play` for one-turn `player` that also returns each spec's
    summed luck, keyed by its seed."""
    ev = bench.load_evaluator(player)
    lucks = {}
    search = {"limit": bench.LIMIT, "threads": threads, "luck": luck,
              "luck_limit": two_turn_games.LUCK["limit"], "luck_samples": two_turn_games.LUCK["samples"]}

    def play(specs):
        res = bench.run_specs(specs, ev=ev, search=search)
        for s, r in zip(specs, res):
            lucks[s["seed"]] = float(np.sum(r["luck"]))
        return [{"won": bool(r["won"]), "hp_start": r["hp_start"], "hp_end": r["hp_end"]} for r in res]
    return play, lucks


def sd(x):
    return float(np.std(x, ddof=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sequences", type=int, default=100)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--net", default=NET, help="the luck net (a plain net path)")
    ap.add_argument("--out", default="results/luck/luck-read-cells.json")
    args = ap.parse_args()
    luck = two_turn_games.luck_net(args.net)
    seqs = gauntlet.sequences(args.sequences, 0)
    sides = []
    for path in FILES:
        with open(path, encoding="utf-8") as f:
            file = json.load(f)
        st = file["settings"]
        if st.get("two_turn") or st["shape"] != list(gauntlet.SHAPE) or st["seed"] != gauntlet.GAUNTLET_SEED:
            raise SystemExit(f"{path}: not a one-turn cell gauntlet file of today's shape and seed")
        play, lucks = play_with_luck(st["player"], luck, args.threads)
        played = {r["i"]: r for r in gauntlet.run(seqs, play)}
        old = {r["i"]: r for r in file["sequences"]}
        rows = []
        for s in seqs:
            fl = played[s["i"]]["floors"]
            if fl != [{k: x[k] for k in ("encounter", "hp_start", "hp_end", "won")} for x in old[s["i"]]["floors"]]:
                raise SystemExit(f"{path}: sequence {s['i']} plays differently with luck logged")
            r = played[s["i"]]
            L = sum(lucks[s["fights"][k]["seed"]] for k in range(len(fl)))
            rows.append({"i": s["i"], "end_hp": gp.end_hp(r), "luck_hp": 100.0 * L, "cleared": r["cleared"]})
        sides.append({"player": st["player"], "rows": rows})
        print(f"{st['player']}: {len(rows)} sequences, clears {np.mean([r['cleared'] for r in rows]):.3f}", flush=True)
    a, b = (np.array([[r["end_hp"], r["luck_hp"]] for r in s["rows"]]) for s in sides)
    d_raw = a[:, 0] - b[:, 0]
    d_cor = (a[:, 0] - a[:, 1]) - (b[:, 0] - b[:, 1])
    rng = np.random.default_rng(20261111)
    boots = []
    for _ in range(BOOT):
        j = rng.integers(len(d_raw), size=len(d_raw))
        if sd(d_raw[j]) > 0:
            boots.append(sd(d_cor[j]) / sd(d_raw[j]))
    ratio = sd(d_cor) / sd(d_raw)
    died = (a[:, 0] == 0) | (b[:, 0] == 0)
    by = {}
    for name, m in (("one died", died), ("both cleared", ~died)):
        if m.sum() > 1:
            by[name] = {"n": int(m.sum()), "sd_raw": sd(d_raw[m]), "sd_corrected": sd(d_cor[m])}
    res = {"players": [s["player"] for s in sides], "luck_net": args.net, "sequences": len(d_raw),
           "mean_raw": float(d_raw.mean()), "mean_corrected": float(d_cor.mean()),
           "sd_raw": sd(d_raw), "sd_corrected": sd(d_cor), "ratio": ratio, "ratio_se": float(np.std(boots)),
           "luck_sd_hp": [sd(a[:, 1]), sd(b[:, 1])],
           "unpaired": [{"sd_raw": sd(x[:, 0]), "sd_corrected": sd(x[:, 0] - x[:, 1])} for x in (a, b)], "by": by, "bar": BAR, "pass": bool(ratio <= BAR),
           "sides": sides}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print(f"paired end HP over {len(d_raw)} sequences: mean raw {d_raw.mean():+.2f}, corrected {d_cor.mean():+.2f}; "
          f"sd raw {sd(d_raw):.2f}, corrected {sd(d_cor):.2f}; ratio {ratio:.3f} (se {np.std(boots):.3f}); "
          f"ratio <= {BAR}: {'PASS' if ratio <= BAR else 'FAIL'}")
    for p, x in zip(res["players"], res["unpaired"]):
        print(f"  unpaired {p}: sd raw {x['sd_raw']:.2f}, corrected {x['sd_corrected']:.2f} (descriptive)")
    for name, v in by.items():
        print(f"  {name}: n {v['n']}, sd raw {v['sd_raw']:.2f}, corrected {v['sd_corrected']:.2f}")


if __name__ == "__main__":
    main()
