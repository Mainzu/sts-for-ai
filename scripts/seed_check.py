"""Seed check (spec folded: git show b076af5:docs/specs/seed-check.md): do the 2026-10-28 night's gate
passes hold up across training seeds?

Each round tested (default s1 r10, r7, r4, r2: the rounds whose night net
clears learned-play Amendment 5's gate on tight fights v2) is retrained at
other training seeds (`learn.fit`'s `seed`) with its own config, window and
round-0 sample (`round_window`), against the database as it was when the
round started (`cut_db`: a copy of db/train.sqlite with the states solved
later removed). r10 needs no copy and no training: the rung-4 check's arm A
(runs/rung4-nightdb) is that retrain at seeds 1, 101, 201.

Every retrain's rung counts must equal the round's own (`search`,
`outcome`, `exact`, within 1%), and the heuristic's tight fights must equal
the ones the rung-4 check stored: else the run stops. Each retrained net
plays the tight fights (every seed); per round, each fight is averaged
over the round's nets and gated against the heuristic (`learn.gate`). A
round holds up when that averaged lead's interval lies above 0 on both
halves and every seed's held-out lead is above 0; the night meets the gate
when one round holds up. The night's own net is reported beside, not
counted.

Results go to runs/seed-check/check.json after every step; a rerun skips
what is there. Retrains are registry runs `seed-check-r<k>-s<seed>`, left
unfinished, so no sweep reuses them.

    python scripts/seed_check.py [--rounds 10 7 4 2] [--seeds 1 101 201] [--out runs/seed-check]
"""
import argparse
import glob
import json
import os
import shutil
import sqlite3
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bench  # noqa: E402
import learn  # noqa: E402
import registry  # noqa: E402

ROUNDS = (10, 7, 4, 2)  # r10 first (no training), then the cuts in growing order
SEEDS = (1, 101, 201)
NIGHT = "2026-10-28-score+branch-s1-r{k}-*"  # the night's s1 rounds under runs/
SOURCE_DB = os.path.join(registry.ROOT, "db", "train.sqlite")
RUNG4 = os.path.join(registry.ROOT, "runs", "rung4-nightdb", "check.json")  # r10's retrains (arm A)
RESCORE = os.path.join(registry.ROOT, "runs", "tight2", "rescore.json")  # the night nets on tight fights v2
CHECKED = ("search", "outcome", "exact")  # rung counts that must match the round's
TOL = 0.01
CACHE_KIB = 1 << 20  # the cut's page cache, 1 GiB (idea #61: deletes are slow with a small one)


def night_run(k, root=registry.ROOT):
    """The run directory of the night's s1 round k."""
    found = glob.glob(os.path.join(root, "runs", NIGHT.format(k=k)))
    if len(found) != 1:
        raise SystemExit(f"round {k}: {len(found)} night runs match {NIGHT.format(k=k)}")
    return found[0]


def round_window(run_dir):
    """{round, cfg, parts, val, samples, db_rows, rungs} of a night round:
    what `learn.learn` trained it on (parts [(dataset, its round)] in its
    order, round 0's sample), from its round.json and config.json; stops
    when round.json lacks db_rows, window or rungs, or its sample fraction
    disagrees with `learn.d0_samples`."""
    rec = json.load(open(os.path.join(run_dir, "round.json")))
    cfg = json.load(open(os.path.join(run_dir, "config.json")))
    for key in ("db_rows", "window", "rungs"):
        if rec.get(key) is None:
            raise SystemExit(f"{run_dir}: round.json has no {key}")
    k, w = rec["round"], rec["window"]
    ds = w["datasets"]
    if len(ds) == 3 and not (w["round0_in"] and k >= 2):
        raise SystemExit(f"{run_dir}: three datasets in the window without round 0 in it")
    parts = list(zip(ds, [k, k - 1, 0][:len(ds)]))
    samples = {}
    if w["round0_sample"] is not None:
        d0 = ds[-1]  # round 0's dataset is the window's last
        samples = learn.d0_samples(cfg, k, d0)
        if d0 not in samples or samples[d0][0] != w["round0_sample"]:
            raise SystemExit(f"{run_dir}: round 0's sample {w['round0_sample']} isn't d0_samples' {samples}")
    return {"round": k, "cfg": cfg, "parts": parts, "val": rec["datasets"]["val"], "samples": samples,
            "db_rows": rec["db_rows"], "rungs": rec["rungs"]}


def cut_db(src, dst, db_rows):
    """Copies database `src` (only read) to `dst` and deletes there the
    states with id above `db_rows` and the positions pointing at them;
    `trivial` is kept whole. A `dst` already there is replaced. Stops,
    keeping the copy, when the copy's largest state id isn't `db_rows`."""
    for f in (dst, dst + "-wal", dst + "-shm", dst + "-journal"):
        if os.path.exists(f):
            os.remove(f)
    s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    d = sqlite3.connect(dst)
    try:
        s.backup(d)
    finally:
        s.close()
    try:
        d.execute(f"pragma cache_size = -{CACHE_KIB}")
        d.execute("delete from positions where state > ?", (db_rows,))
        d.execute("delete from states where id > ?", (db_rows,))
        d.commit()
        (top,), = d.execute("select max(id) from states")
    finally:
        d.close()
    if top != db_rows:
        raise SystemExit(f"{dst}: largest state id {top} after the cut, not db_rows {db_rows} (copy kept)")


def rung_mismatch(got, want, tol=TOL):
    """The CHECKED rung counts of `got` off from `want` by more than `tol`
    of `want`: {name: (got, want)}."""
    return {n: (got[n], want[n]) for n in CHECKED if abs(got[n] - want[n]) > tol * max(want[n], 1)}


def enc(results):
    return {h: "".join(map(str, x)) for h, x in results.items()}


def dec(fights):
    return {h: [int(c) for c in x] for h, x in fights.items()}


def averaged(per_seed):
    """{half: per-fight results averaged over seeds} of a list of
    `tight_results`."""
    return {h: np.mean([np.array(r[h], float) for r in per_seed], axis=0) for h in per_seed[0]}


def holds_up(seed_leads, avg_gate):
    """The round's verdict: `avg_gate` (`learn.gate` of the seed-averaged
    fights) above 0 on both halves, and every seed's held-out lead point
    (`seed_leads` {seed: {half: [mean, lo, hi]}}) above 0."""
    v = {"averaged_above": all(h["lead"][1] > 0 for h in avg_gate["halves"].values()),
         "every_seed_held_out_above": all(s["held_out"][0] > 0 for s in seed_leads.values())}
    v["holds"] = all(v.values())
    return v


def summarize(rnd, heur, cells, night_lead):
    """A round's summary over its seeds (`rnd["seeds"]`, each with fights):
    the averaged gate, the per-seed leads' spread, the night net's lead and
    the verdict."""
    seeds = rnd["seeds"]
    leads = {s: {h: v["lead"] for h, v in r["gate"]["halves"].items()} for s, r in seeds.items()}
    avg = learn.gate(averaged([dec(r["fights"]) for r in seeds.values()]), heur, cells)

    def spread(x):
        return float(np.std(x, ddof=1)) if len(x) > 1 else 0.0
    return {"averaged": avg, "spread": {h: spread([v[h][0] for v in leads.values()]) for h in cells},
            "night": night_lead, "verdict": holds_up(leads, avg)}


def file_stamp(path):
    st = os.stat(path)
    return {"size": st.st_size, "mtime_ns": st.st_mtime_ns}


def run(args):
    t0 = time.perf_counter()
    os.makedirs(args.out, exist_ok=True)
    res_path = os.path.join(args.out, "check.json")
    res = json.load(open(res_path)) if os.path.exists(res_path) else {}

    def save():
        with open(res_path, "w") as f:
            json.dump(res, f, indent=1)

    stamp = file_stamp(SOURCE_DB)
    res.setdefault("source", stamp)
    if res["source"] != stamp:
        raise SystemExit(f"{SOURCE_DB} changed since the check started: {res['source']} -> {stamp}")
    agent = {"limit": bench.LIMIT}
    cells = learn.tight_cells(1)
    rung4 = json.load(open(RUNG4))
    if "heuristic_fights" not in res:
        fights = enc(learn.tight_results("heuristic", agent, 1))
        if fights != rung4["heuristic_fights"]:
            raise SystemExit("the heuristic's tight fights differ from the rung-4 check's stored ones")
        res["heuristic_fights"] = fights
        save()
    heur = dec(res["heuristic_fights"])
    night = json.load(open(RESCORE))["nets"]
    rounds = res.setdefault("rounds", {})
    saved_db = learn.db_path
    for k in args.rounds:
        run_dir = night_run(k)
        w = round_window(run_dir)
        rnd = rounds.setdefault(str(k), {"run": os.path.basename(run_dir), "db_rows": w["db_rows"],
                                         "rungs": w["rungs"], "seeds": {}})
        seeds = rnd["seeds"]
        todo = [s for s in args.seeds if str(s) not in seeds]
        if k == 10:  # the rung-4 check's arm A: same config, parts and database
            for s in todo:
                a = rung4["seeds"][str(s)]
                arm = a["arms"]["A"]
                off = rung_mismatch(arm["rungs"], w["rungs"])
                if off:
                    raise SystemExit(f"r10's reused seed {s}: rung counts off {off}")
                seeds[str(s)] = {**arm, "fights": a["fights"]["A"], "reused": RUNG4}
                save()
            todo = []
        copy = os.path.join(registry.ROOT, "db", f"seed-check-r{k}.sqlite")
        if todo:
            if not rnd.get("cut"):
                t = time.perf_counter()
                print(f"r{k}: cutting {copy} at db_rows {w['db_rows']}", flush=True)
                cut_db(SOURCE_DB, copy, w["db_rows"])
                rnd["cut"] = {"path": copy, "minutes": (time.perf_counter() - t) / 60}
                save()
            learn.db_path = lambda root=registry.ROOT: copy
            try:
                for s in todo:
                    name = f"seed-check-r{k}-s{s}"
                    print(f"r{k}: training {name}", flush=True)
                    t = time.perf_counter()
                    r, val_mse, _, counts = learn.fit({**w["cfg"], "name": name}, name, w["parts"], w["val"],
                                                      finish=False, samples=w["samples"], seed=s)
                    rec = {"model": r.model_path, "val_mse": val_mse, "rungs": counts,
                           "train_min": (time.perf_counter() - t) / 60}
                    off = rung_mismatch(counts, w["rungs"])
                    if off:
                        rnd["stopped"] = {"seed": s, **rec, "off": off}
                        save()
                        raise SystemExit(f"r{k} seed {s}: rung counts off the round's {off}: the copy "
                                         f"doesn't rebuild its labels (copy kept: {copy})")
                    rec["fights"] = enc(learn.tight_results(r.model_path, agent, 1))
                    seeds[str(s)] = rec
                    save()
            finally:
                learn.db_path = saved_db
        if rnd.get("cut") and not rnd.get("copy_deleted") and all(str(s) in seeds for s in args.seeds):
            if os.path.exists(copy):
                os.remove(copy)
            rnd["copy_deleted"] = True
            save()
        for r in seeds.values():
            r.setdefault("gate", learn.gate(dec(r["fights"]), heur, cells))
        rnd.update(summarize({"seeds": {str(s): seeds[str(s)] for s in args.seeds}}, heur, cells,
                             night[f"s1 r{k}"]["lead"]))
        rnd["seeds_used"] = list(args.seeds)
        save()

    if file_stamp(SOURCE_DB) != stamp:
        raise SystemExit(f"{SOURCE_DB} changed during the check")
    held = [k for k in args.rounds if rounds[str(k)]["verdict"]["holds"]]
    res["verdict"] = {"rounds": list(args.rounds), "holding": held, "meets_gate": bool(held)}
    res["minutes"] = res.get("minutes", 0) + (time.perf_counter() - t0) / 60
    save()
    print(report(res))


def report(res):
    """The check as markdown: a row per round and seed, then per round the
    averaged gate, the spread, the night net's lead and the verdict, then
    the overall answer."""
    def f(b):
        return f"{b[0]:+.4f} [{b[1]:+.4f}, {b[2]:+.4f}]"
    out = ["Seed check: the night's rounds retrained at other training seeds", "",
           "| round | seed | val MSE | training | rungs search / outcome / exact | lead train | lead held-out |",
           "|---|---|---|---|---|---|---|"]
    for k, rnd in res["rounds"].items():
        for s in rnd["seeds_used"]:
            r = rnd["seeds"][str(s)]
            g = r["gate"]["halves"]
            n = r["rungs"]
            out.append(f"| r{k} | {s} | {r['val_mse']:.4f} | {r['train_min']:.0f} min | "
                       f"{n['search']} / {n['outcome']} / {n['exact']} | {f(g['train']['lead'])} | "
                       f"{f(g['held_out']['lead'])} |")
    out += ["", "| round | averaged lead train | averaged lead held-out | sd train / held-out | "
                "night net train / held-out | holds up |", "|---|---|---|---|---|---|"]
    for k, rnd in res["rounds"].items():
        a = rnd["averaged"]["halves"]
        out.append(f"| r{k} | {f(a['train']['lead'])} | {f(a['held_out']['lead'])} | "
                   f"{rnd['spread']['train']:.4f} / {rnd['spread']['held_out']:.4f} | "
                   f"{rnd['night']['train'][0]:+.4f} / {rnd['night']['held_out'][0]:+.4f} | "
                   f"{'yes' if rnd['verdict']['holds'] else 'no'} |")
    v = res["verdict"]
    out += ["", f"verdict: the night {'meets' if v['meets_gate'] else 'does not meet'} the gate "
                f"(rounds holding up: {', '.join(f'r{k}' for k in v['holding']) or 'none'} of "
                f"{len(v['rounds'])}); {res['minutes']:.0f} min"]
    if len(v["holding"]) == 1 and len(v["rounds"]) > 1:
        out.append(f"With {len(v['rounds'])} rounds tested, one round holding by luck is likelier than "
                   "one test's 5%.")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rounds", type=int, nargs="+", default=list(ROUNDS))
    ap.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS))
    ap.add_argument("--out", default=os.path.join("runs", "seed-check"))
    run(ap.parse_args(argv))


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    main()
