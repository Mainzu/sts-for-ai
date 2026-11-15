"""Check 5: strength table. Random, greedy and search (heuristic evaluator)
play the same seeded combats per encounter group: the starter deck and the
starter + 5 random cards. Exits 1 if the pass bar isn't met.

    python scripts/eval.py [--n 500] [--sample-k 0] [--turns 1]
"""

import argparse
import sys
import time

import sts

GROUPS = ["hallway", "elite", "boss"]
AGENTS = ["random", "greedy", "search"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=500, help="combats per group")
    ap.add_argument("--sample-k", type=int, default=0)
    ap.add_argument("--turns", type=int, default=1)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    print(f"{args.n} combats per group")
    print(f"{'group':<8} {'agent':<8} {'win %':>8} {'HP lost':>9} {'secs':>7}")
    table = {}
    for g in GROUPS:
        specs = sts.make_specs(g, args.n, extra=5, seed=args.seed)
        for a in AGENTS:
            t = time.perf_counter()
            res = sts.run(a, specs, sample_k=args.sample_k, turns=args.turns)
            win = sum(r["won"] for r in res) / len(res)
            lost = sum(r["hp_start"] - r["hp_end"] for r in res) / len(res)
            table[g, a] = (win, lost)
            print(f"{g:<8} {a:<8} {win * 100:>8.1f} {lost:>9.1f} {time.perf_counter() - t:>7.1f}")

    fails = []
    for g in GROUPS:
        (gw, gl), (rw, rl) = table[g, "greedy"], table[g, "random"]
        if not (gw > rw or (gw == rw and gl < rl)):
            fails.append(f"greedy doesn't beat random on {g}")
    margin = (table["boss", "search"][0] - table["boss", "greedy"][0]) * 100
    if margin < 15:
        fails.append(f"search beats greedy on boss win rate by {margin:.1f} points (need 15)")
    sl, gl = table["hallway", "search"][1], table["hallway", "greedy"][1]
    if sl > 0.8 * gl:
        fails.append(f"search hallway HP lost {sl:.1f} vs greedy {gl:.1f} (need <= {0.8 * gl:.1f})")
    for f in fails:
        print("FAIL:", f)
    print("check 5:", "FAIL" if fails else "pass")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
