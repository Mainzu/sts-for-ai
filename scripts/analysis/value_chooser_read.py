"""Read a value-chooser gauntlet file against its control (docs/specs/value-chooser.md):
paired end-HP and clears with se, on all sequences and on those where neither
file took Demon Form; each file's Demon Form take rate; pick agreement (floors
both reached with the same offer: share with the same `took`); wall time of
the two jobs when --jobs names their records.

    .venv/Scripts/python scripts/analysis/value_chooser_read.py <run.json> <control.json> [--jobs jobs/done/<a>.json,jobs/done/<b>.json]
"""

import argparse
import json
import os
import sys
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import gauntlet_protocol as gp  # noqa: E402

CARD = "Demon Form"


def took_card(r, card=CARD):
    return any(f.get("took") == card for f in r["floors"])


def paired(a, b, keys):
    dh = np.array([gp.end_hp(a[k]) - gp.end_hp(b[k]) for k in keys], float)
    dc = np.array([float(a[k]["cleared"]) - float(b[k]["cleared"]) for k in keys], float)
    se = (lambda d: float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else 0.0)
    return {"n": len(keys), "end_hp": float(dh.mean()) if len(keys) else 0.0, "end_hp_se": se(dh),
            "clears": float(dc.mean()) if len(keys) else 0.0, "clears_se": se(dc),
            "clear_a": float(np.mean([a[k]["cleared"] for k in keys])) if keys else 0.0,
            "clear_b": float(np.mean([b[k]["cleared"] for k in keys])) if keys else 0.0}


def agreement(a, b, keys):
    same = n = 0
    for k in keys:
        for fa, fb in zip(a[k]["floors"], b[k]["floors"]):
            if "offer" in fa and "offer" in fb and fa["offer"] == fb["offer"]:
                n += 1
                same += fa["took"] == fb["took"]
    return {"floors": n, "share": same / n if n else None}


def read(run, control):
    a = {r["i"]: r for r in run["sequences"]}
    b = {r["i"]: r for r in control["sequences"]}
    keys = sorted(k for k in set(a) & set(b) if a[k]["cell"] == b[k]["cell"])
    plain = [k for k in keys if not took_card(a[k]) and not took_card(b[k])]
    return {"all": paired(a, b, keys), "no_demon_form": paired(a, b, plain),
            "demon_form_take": {"a": float(np.mean([took_card(a[k]) for k in keys])) if keys else 0.0,
                                "b": float(np.mean([took_card(b[k]) for k in keys])) if keys else 0.0},
            "agreement": agreement(a, b, keys), "agreement_first_pick": agreement(
                {k: {"floors": a[k]["floors"][:1]} for k in keys}, {k: {"floors": b[k]["floors"][:1]} for k in keys}, keys)}


def wall_min(path):
    with open(path, encoding="utf-8") as f:
        j = json.load(f)
    return (datetime.fromisoformat(j["ended"]) - datetime.fromisoformat(j["started"])).total_seconds() / 60


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("control")
    ap.add_argument("--jobs", default=None, help="job records of the run and the control, comma-separated")
    args = ap.parse_args(argv)
    with open(args.run, encoding="utf-8") as f:
        run = json.load(f)
    with open(args.control, encoding="utf-8") as f:
        control = json.load(f)
    out = read(run, control)
    if args.jobs:
        ja, jb = args.jobs.split(",")
        out["wall_min"] = {"a": wall_min(ja), "b": wall_min(jb)}
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    main()
