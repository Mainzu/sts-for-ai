"""Teacher sizing (learned-play step 1): search + heuristic at several depths
on the bench's saved decisions (regret, ranking against the cached
reference) and tight fights (win rate, HP lost), with the compute each
costs. Writes results/teacher_sizing.json and prints a Markdown table.

    python scripts/teacher_sizing.py
"""

import json
import os
import time

import bench
import bench_decisions
import bench_sets

# The agents' one-turn search first; then sampling at random events and a
# second turn. Limit stays the agents'. A second turn only takes effect with
# sample_k > 0 (the next turn's draw is a large random event), and at one
# turn sampling only reaches large in-turn events.
SETTINGS = [
    {"limit": bench.LIMIT, "sample_k": 0, "turns": 1},
    {"limit": bench.LIMIT, "sample_k": 2, "turns": 1},
    {"limit": bench.LIMIT, "sample_k": 4, "turns": 1},
    {"limit": bench.LIMIT, "sample_k": 8, "turns": 1},
    {"limit": bench.LIMIT, "sample_k": 0, "turns": 2},
    {"limit": bench.LIMIT, "sample_k": 1, "turns": 2},
    {"limit": bench.LIMIT, "sample_k": 2, "turns": 2},
    {"limit": bench.LIMIT, "sample_k": 4, "turns": 2},
]
OUT = os.path.join(os.path.dirname(__file__), "..", "results", "teacher_sizing.json")


def name(s):
    return f"turns {s['turns']}, sample_k {s['sample_k']}"


def size(search):
    ev = bench.load_evaluator("heuristic")
    decisions = bench_decisions.load_decisions()
    reference = bench_decisions.load_reference()
    tight = bench_sets.load_set("tight")
    out = {"settings": search, "halves": {}}
    t_dec = t_games = 0.0
    n_dec = n_games = 0
    for half, rows in reference["halves"].items():
        t = time.time()
        picks, values, _ = bench.search_decisions(ev, [decisions[half][r["index"]] for r in rows], rows, search)
        t_dec += time.time() - t
        n_dec += len(rows)
        hs = bench.decision_halves(rows, picks, values, [None] * len(rows), [None] * len(rows))
        m = {f"{k}.{sub}": v for sub in ("all", "contested") for k, v in hs[sub].metrics.items()}
        t = time.time()
        res = bench.run_specs(tight[half], search=search)
        t_games += time.time() - t
        n_games += len(res)
        h = bench.Half()
        h.rate("win", [r["won"] for r in res])
        h.mean("hp_lost", [r["hp_start"] - r["hp_end"] for r in res])
        m.update(h.metrics)
        out["halves"][half] = m
    out["ms_per_decision"] = round(1000 * t_dec / n_dec, 2)  # one thread
    out["games_per_s"] = round(n_games / t_games, 1)  # all threads
    return out


def fmt(m):
    return f"{m[0]:.3f} [{m[1]:.3f}, {m[2]:.3f}]"


def main():
    results = []
    for s in SETTINGS:
        r = size(s)
        results.append(r)
        print(name(s), r["ms_per_decision"], "ms/decision", r["games_per_s"], "games/s", flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(results, f, indent=1)
    print("\n| Half | Search | regret (contested) | ranking (contested) | win | ms / decision | games / s |")
    print("|---|---|---|---|---|---|---|")
    for half in ("train", "held_out"):
        for r in results:
            m = r["halves"][half]
            print(f"| {half} | {name(r['settings'])} | {fmt(m['regret.contested'])} | {fmt(m['ranking.contested'])} "
                  f"| {fmt(m['win'])} | {r['ms_per_decision']} | {r['games_per_s']} |")


if __name__ == "__main__":
    main()
