"""Net search speed, Python vs Rust inference (docs/specs/rust-inference.md):
games per second of the learned-play sweep's net workloads, both inference
paths on the same specs. Machine load varies, so each figure is the median
of interleaved repeats (Python, Rust, Python, Rust, ...).

- self-play: a self-play round's games (`registry.play` with
  learn.SELFPLAY_SEARCH and the sweep's temperature, mixed encounters at
  full HP, train decks): sweep.RATES[("net", False)]; with an HP net,
  no-death mode: RATES[("net", True)].
- tight: the bench's tight fights (every `--every`-th), as the monotone and
  bench runs play them: sweep.TIGHT_RATE_NET.

Python runs use stsnet.NET_THREADS search threads, Rust runs every core,
as the call sites do.

    python scripts/inference_speed.py [--net models/value_effects.pt] [--hp-net RUN/model.pt]
"""

import argparse
import os
import statistics
import time

import bench
import bench_sets
import learn
import registry
import selfplay
import stsnet
import sweep


def timed(fn, n):
    t = time.perf_counter()
    fn()
    return n / (time.perf_counter() - t)


def workloads(args):
    """[(name, sweep rate it sets, {inference: fn}, games)]."""
    out = []
    specs, _ = selfplay.make_specs(args.n_selfplay, 7, selfplay.train_deck)
    tight = [s for half in bench_sets.load_set("tight").values() for s in bench.every(half, args.every)]
    for path, hp in ((args.net, False), (args.hp_net, True)):
        if not path:
            continue
        model, norm, meta = stsnet.load(path)
        if getattr(model, "hp_loss", False) != hp:
            raise SystemExit(f"{path}: expected {'an HP-histogram' if hp else 'a score'} net")
        feats = stsnet.features_for(meta)
        evs = {"python": stsnet.Evaluator(model, norm), "rust": stsnet.rust_evaluator(model, norm, meta)}
        config = {"search": learn.SELFPLAY_SEARCH, "explore": sweep.TEMPERATURE, "no_death": hp}
        out.append((f"self-play ({'hp, no-death' if hp else 'score'})", f"RATES[('net', {hp})]",
                    {k: (lambda e=e: registry.play(specs, config, evaluator=e, features=feats)) for k, e in evs.items()},
                    len(specs)))
        if not hp:
            bevs = {k: bench.Evaluator(path, e, feats, evs["python"]) for k, e in evs.items()}
            out.append(("tight fights (score)", "TIGHT_RATE_NET",
                        {k: (lambda e=e: bench.run_specs(tight, e)) for k, e in bevs.items()}, len(tight)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--net", default=os.path.join(os.path.dirname(__file__), "..", "models", "value_effects.pt"),
                    help="score net")
    ap.add_argument("--hp-net", help="HP-histogram net (no-death self-play rate)")
    ap.add_argument("--n-selfplay", type=int, default=60, help="self-play games per encounter group")
    ap.add_argument("--every", type=int, default=4, help="every n-th tight fight")
    ap.add_argument("--repeats", type=int, default=3)
    args = ap.parse_args(argv)
    print(f"{os.cpu_count()} cores; Python inference on {stsnet.NET_THREADS} search threads, Rust on all")
    print(f"{'workload':<26} {'games':>5} {'python g/s':>11} {'rust g/s':>9} {'speed-up':>8}  sets")
    for name, rate, fns, n in workloads(args):
        got = {k: [] for k in fns}
        for _ in range(args.repeats):
            for k, fn in fns.items():
                got[k].append(timed(fn, n))
        py, rs = (statistics.median(got[k]) for k in ("python", "rust"))
        print(f"{name:<26} {n:>5} {py:>11.1f} {rs:>9.1f} {rs / py:>7.1f}x  {rate}"
              f"   (runs: py {', '.join(f'{x:.1f}' for x in got['python'])}; rs {', '.join(f'{x:.1f}' for x in got['rust'])})")


if __name__ == "__main__":
    main()
