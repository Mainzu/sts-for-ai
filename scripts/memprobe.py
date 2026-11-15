"""Memory per phase of a real learned-play run (curriculum spec, step 7;
Amendment 1: the training set is a view over memory-mapped caches).

Runs `learn.learn` on one sweep row's config at the given sizes in its own
registry root, with every phase wrapped (self-play, dataset write, solve
step, feature-cache build or load, labelling, exact examples, the
training set (Amendment 1's view; sampling and concatenation on the in-RAM
path), normalizer, training, tight-fight and puzzle checks). A
sampler process polls this process's commit (private bytes) and working
set every 50 ms; each sample is charged to the innermost phase running.
Prints and writes (<root>/memprobe.json) each phase's peak commit and the
example counts the peak model needs, and the process's own peak commit
(GetProcessMemoryInfo) as a check that sampling saw the highest point.
The root's registry (cache, datasets, db, runs) is deleted at the end;
memprobe.json and memprobe.samples stay.

    python scripts/memprobe.py --root <tmp> --n0 2000 --n-round 300 --db db/train.sqlite
    python scripts/memprobe.py --root <tmp> --config configs/<learn config>.json --n0 40000 --db db/train.sqlite
"""

import argparse
import bisect
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time

GB = 1e9


class Counters(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
k32.OpenProcess.restype = k32.GetCurrentProcess.restype = ctypes.c_void_p
k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]


def counters(handle):
    c = Counters()
    c.cb = ctypes.sizeof(Counters)
    psapi.GetProcessMemoryInfo(handle, ctypes.byref(c), c.cb)
    return c


def sample(pid, out):
    """Sampler process: (time, commit, working set) lines until `pid` exits."""
    h = k32.OpenProcess(0x0400 | 0x0010 | 0x100000, False, pid)  # query, read, synchronize
    with open(out, "w", encoding="utf-8") as f:
        while k32.WaitForSingleObject(h, 50) == 0x102:  # WAIT_TIMEOUT
            c = counters(h)
            f.write(f"{time.time():.3f} {c.PagefileUsage} {c.WorkingSetSize}\n")
            f.flush()


class Phases:
    """Enter/exit events of wrapped functions, with sizes noted on the way."""

    def __init__(self):
        self.events, self.sizes = [], []

    def wrap(self, obj, name, label, size=None, static=False):
        fn = getattr(obj, name)

        def wrapped(*a, **kw):
            lab = label(*a, **kw) if callable(label) else label
            self.events.append((time.time(), lab, 1))
            try:
                out = fn(*a, **kw)
            finally:
                self.events.append((time.time(), lab, -1))
            if size is not None:
                self.sizes.append((lab, size(out, *a, **kw)))
            return out
        setattr(obj, name, staticmethod(wrapped) if static else wrapped)


def peaks(events, samples):
    """{phase: peak commit} charging each sample to the innermost phase."""
    out, stack, i = {}, ["(other)"], 0
    for t, commit, _ in samples:
        while i < len(events) and events[i][0] <= t:
            _, lab, d = events[i]
            if d > 0:
                stack.append(lab)
            else:
                stack.remove(lab)
            i += 1
        out[stack[-1]] = max(out.get(stack[-1], 0), commit)
    return out


def timeline(events, samples):
    """Lines per wrapped call, in order: start (s), duration, commit at
    entry, peak inside and at exit (GB), nested calls indented."""
    ts = [s[0] for s in samples]
    out, start, depth = [], {}, 0
    for t, lab, d in events:
        if d > 0:
            start[lab], depth = t, depth + 1
            continue
        depth -= 1
        a, b = bisect.bisect_left(ts, start[lab]), bisect.bisect_right(ts, t)
        seg = samples[max(a - 1, 0):max(b, a + 1)] or samples[-1:]
        out.append((start[lab], f"{start[lab] - ts[0]:7.0f}s {t - start[lab]:6.0f}s {'  ' * depth}{lab:<16} "
                                f"in {seg[0][1] / GB:5.2f}  peak {max(s[1] for s in seg) / GB:5.2f}  "
                                f"out {seg[-1][1] / GB:5.2f}"))
    return [line for _, line in sorted(out)]


def rounds(events, samples, sizes):
    """Per round: its training set's examples, its peak outside the solve
    step (from its solve step's end to the next one's start, or the end) and
    its solve step's peak."""
    solves, start = [], None
    for t, lab, d in events:
        if lab == "solve step":
            if d > 0:
                start = t
            else:
                solves.append((start, t))
    trained = [s["examples"] for lab, s in sizes if lab == "training"]
    out = []
    for k, (a, b) in enumerate(solves):
        end = solves[k + 1][0] if k + 1 < len(solves) else float("inf")
        out.append({"round": k, "examples": trained[k] if k < len(trained) else None,
                    "peak_gb": max(c for t, c, _ in samples if b <= t < end) / GB,
                    "solve_gb": max(c for t, c, _ in samples if a <= t <= b) / GB})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", help="a fresh registry root (feature caches get built)")
    ap.add_argument("--n0", type=int, default=2000, help="round 0's pool, games per group")
    ap.add_argument("--n-round", type=int, default=300, help="games per group of rounds >= 1")
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--solve", type=int, default=20, help="games per solve step")
    ap.add_argument("--threads", type=int, default=2, help="solve-step threads (the sweep's solve_threads)")
    ap.add_argument("--db", help="a solved-position database copied into the root first (exact examples)")
    ap.add_argument("--config", help="instead of a sweep row: this learn config's round 0 only (its pool of "
                                     "--n0 games per group, labels, training set and --epochs of training)")
    ap.add_argument("--epochs", type=int, default=1, help="with --config: training epochs")
    ap.add_argument("--sample", nargs=2, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.sample:
        sample(int(args.sample[0]), args.sample[1])
        return
    if not args.root:
        ap.error("--root is required")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import learn
    import registry
    import stsnet
    import sweep
    import train

    if os.path.exists(args.root) and os.path.samefile(args.root, registry.ROOT):  # any spelling or case
        ap.error("--root must be a fresh folder, not the main checkout (its registry is deleted at the end)")
    os.makedirs(os.path.join(args.root, "db"), exist_ok=True)
    if args.db and not os.path.exists(learn.db_path(args.root)):
        shutil.copy(args.db, learn.db_path(args.root))
    p = Phases()
    p.wrap(registry, "selfplay", "dataset (play + write)")
    p.wrap(registry, "play", "self-play", lambda out, specs, *a, **kw: {"games": len(specs)})
    p.wrap(registry, "write_dataset", "dataset write")
    p.wrap(learn, "solve_step", "solve step")
    p.wrap(registry, "examples", lambda ds, mode, root=None, **kw: "cache load" if os.path.exists(
        registry.cache_path(ds, mode, root, kw.get("labels"))) else "cache build",
        lambda out, *a, **kw: {"examples": len(out)})
    p.wrap(learn, "ladder", "labels (ladder)")
    p.wrap(learn, "exact_examples", "exact examples", lambda res, *a, **kw: {"examples": 0 if res is None else len(res)})
    p.wrap(stsnet.Dataset, "take", "sample (take)", static=False)
    p.wrap(stsnet.Dataset, "concat", "concatenate", lambda out, parts: {"examples": len(out)}, static=True)
    p.wrap(learn, "training_set", "training set", lambda out, *a, **kw: {"examples": len(out[0])})
    p.wrap(stsnet.Normalizer, "fit", "normalizer", static=True)
    p.wrap(train, "train", "training", lambda out, mode, ds, *a, **kw: {"examples": len(ds)})
    p.wrap(learn, "tight_results", "tight fights")
    p.wrap(learn, "trusted_zone", "puzzles")

    out = os.path.join(args.root, "memprobe.samples")
    sampler = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--sample", str(os.getpid()), out])
    t0 = time.time()
    if args.config:  # learn.learn's round 0, cut to --epochs (lane learn-memory)
        with open(args.config, encoding="utf-8") as f:
            cfg = {**json.load(f), "n_train": args.n0}
        cfg = {**cfg, **learn.label_settings(cfg)}
        train.EPOCHS = args.epochs
        val = learn.dataset(cfg, "val", args.root)
        d0 = learn.dataset(cfg, "train", args.root)
        learn.solve_step(cfg, d0, 0, args.root)
        learn.fit(cfg, f"{cfg['name']}-r0", [(d0, 0)], val, args.root, finish=False,
                  samples=learn.d0_samples(cfg, 0, d0), seed=cfg.get("round0_seed", cfg.get("seed", 0)))
    else:
        cfg = sweep.config("score+branch-s0", False, True, 0, args.n0, args.n_round, args.n_round,
                           rounds=(args.rounds, args.rounds), solve=args.solve, threads=args.threads)
        cfg["rounds"]["every"] = sweep.mono_every()
        learn.learn(cfg, root=args.root)
    time.sleep(0.2)
    own = counters(k32.GetCurrentProcess())
    p.events.append((time.time(), "(end)", 1))
    time.sleep(0.2)
    sampler.terminate()
    sampler.wait()
    with open(out, encoding="utf-8") as f:
        samples = [tuple(float(x) for x in line.split()) for line in f if line.count(" ") == 2]
    pk = peaks(p.events, samples)
    result = {"n0": args.n0, "n_round": args.n_round, "rounds": args.rounds, "solve": args.solve,
              "threads": args.threads, "rounds_peak": rounds(p.events, samples, p.sizes),
              "minutes": (time.time() - t0) / 60, "peak_commit_gb": own.PeakPagefileUsage / GB,
              "sampled_peak_gb": max(s[1] for s in samples) / GB,
              "phases": {k: v / GB for k, v in sorted(pk.items(), key=lambda kv: -kv[1])}, "sizes": p.sizes,
              "timeline": timeline(p.events[:-1], samples)}
    with open(os.path.join(args.root, "memprobe.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    for d in ("cache", "datasets", "db", "runs"):  # the probe's own registry (GBs), not its result
        shutil.rmtree(os.path.join(args.root, d), ignore_errors=True)
    print(f"peak commit {result['peak_commit_gb']:.2f} GB (sampled {result['sampled_peak_gb']:.2f}), "
          f"{result['minutes']:.1f} min")
    for k, v in result["phases"].items():
        print(f"  {k:<18} {v:6.2f} GB")
    for lab, s in p.sizes:
        print(f"  {lab}: {s}")
    print("\n".join(result["timeline"]))
    for r in result["rounds_peak"]:
        print(f"round {r['round']}: {r['examples']} training examples, peak {r['peak_gb']:.2f} GB outside the "
              f"solve step, solve step {r['solve_gb']:.2f} GB")


if __name__ == "__main__":
    main()
