"""Prints bench results side by side: one row per config, metric groups
(prediction, decision quality, playing strength) as columns, each as
"value [95% interval]". Two configs differ on a metric only when their
intervals don't overlap.

    python scripts/bench_compare.py results/*.json [--set tight] [--half held_out]
    python scripts/bench_compare.py <run id> <run id> results/heuristic.json

A run id (a folder under runs/) reads that run's bench.json. A warning is
printed when the results come from different bench versions.
"""

import argparse
import glob
import json
import os

RUNS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "runs")

# (group, metric, label) per set
COLUMNS = {
    "tight": [("prediction", "mse", "mse"), ("prediction", "mse_search.contested", "mse@dec"),
              ("decisions", "regret.contested", "regret"), ("decisions", "ranking.contested", "ranking"),
              ("decisions", "ranking.uncapped", "rank(unc)"),
              ("strength", "win", "win"), ("strength", "hp_lost", "hp lost")],
    "standard": [("prediction", "mse", "mse"), ("strength", "win", "win"), ("strength", "hp_lost", "hp lost")],
    "puzzles": [("exact", "accuracy.all", "accuracy"), ("exact", "regret.all", "regret"),
                ("exact", "ranking.all", "ranking"), ("contested", "accuracy.contested", "accuracy"),
                ("contested", "regret.contested", "regret"), ("contested", "ranking.contested", "ranking"),
                ("horizon", "accuracy.h0", "acc h0"), ("horizon", "accuracy.h1", "acc h1"),
                ("horizon", "accuracy.h2+", "acc h2+")],
}


def cell(m):
    if m is None:
        return "-"
    p, lo, hi = m
    return f"{p:.3f} [{lo:.3f},{hi:.3f}]" if abs(p) < 10 else f"{p:.1f} [{lo:.1f},{hi:.1f}]"


def table(results, set_name, half):
    cols = COLUMNS[set_name]
    rows = []
    for name, r in results:
        s = r["sets"].get(set_name)  # older results have no puzzles set
        if s is None:
            metrics = {}
        else:
            metrics = s["gaps"][half[4:]] if half.startswith("gap:") else s["halves"][half]["metrics"]
        rows.append([name + (" (quick)" if r.get("quick") else "")] + [cell(metrics.get(m)) for _, m, _ in cols])
    groups = ["config"] + [g for g, _, _ in cols]
    labels = [""] + [l for _, _, l in cols]
    widths = [max(len(x[i]) for x in rows + [groups, labels]) for i in range(len(groups))]
    out = []
    for line in (groups, labels):
        out.append("  ".join(x.ljust(w) for x, w in zip(line, widths)))
    out.append("  ".join("-" * w for w in widths))
    for line in rows:
        out.append("  ".join(x.ljust(w) for x, w in zip(line, widths)))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="results JSON files (globs ok) or run ids")
    ap.add_argument("--set", choices=sorted(COLUMNS), help="only this set (default: all)")
    ap.add_argument("--half", help="only this half, or gap:<half> (default: every half and gap)")
    args = ap.parse_args(argv)
    results, warnings = load_results(args.files)
    for w in warnings:
        print(f"warning: {w}")
    for set_name in [args.set] if args.set else list(COLUMNS):
        s = next((r["sets"][set_name] for _, r in results if set_name in r["sets"]), None)
        if s is None:
            if args.set:
                print(f"note: no file has the {set_name} set")
            continue
        halves = [args.half] if args.half else list(s["halves"]) + [f"gap:{h}" for h in s["gaps"]]
        for half in halves:
            title = f"{set_name} / " + (f"gap ({half[4:]} - train)" if half.startswith("gap:") else half)
            print(f"\n{title}\n{table(results, set_name, half)}")
    if not args.set:
        print(f"\nrepresentation\n{representation_table(results)}")


def load_results(names, runs_root=RUNS):
    """[(name, result)] for results files (globs ok) and run ids, plus
    warnings (differing bench versions)."""
    items = []
    for f in names:
        run = os.path.join(runs_root, f, "bench.json")
        if os.path.exists(run):
            items.append((f, run))
        else:
            items += [(os.path.splitext(os.path.basename(p))[0], p) for p in sorted(glob.glob(f) or [f])]
    seen, results = set(), []
    for name, p in items:
        if p in seen:
            continue
        seen.add(p)
        with open(p, encoding="utf-8") as fh:
            results.append((name, json.load(fh)))
    versions = sorted({str(r.get("version")) for _, r in results})
    warnings = [] if len(versions) <= 1 else [
        "bench versions differ (" + ", ".join(f"{n}: {r.get('version')}" for n, r in results) + "); numbers may not compare"]
    return results, warnings


def representation_table(results):
    """Probe pass rate and aliased groups (effects / own features) per tight half."""
    rows = []
    for name, r in results:
        rep = r.get("representation")
        if rep is None:
            continue
        line = [name, cell(rep["probes"]["pass"])]
        for kind in ("effects", "own"):
            a = rep["aliasing"].get(kind)
            line.append("-" if a is None else " / ".join(f"{h} {x['aliased']}/{x['pairs']}" for h, x in a["halves"].items()))
        rows.append(line)
    head = ["config", "probes pass", "aliased/sibling pairs (effects)", "aliased/sibling pairs (own)"]
    widths = [max(len(x[i]) for x in rows + [head]) for i in range(len(head))]
    out = ["  ".join(x.ljust(w) for x, w in zip(head, widths)), "  ".join("-" * w for w in widths)]
    out += ["  ".join(x.ljust(w) for x, w in zip(line, widths)) for line in rows]
    return "\n".join(out)


if __name__ == "__main__":
    main()
