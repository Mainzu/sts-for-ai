"""Loads real-game decisions joined to runs (numbered 1-90 as all_runs) and fights."""
import json, os, sys
ROOT = "."
sys.path.insert(0, ROOT + "/scripts")
import real_game_report as R

def runs():
    """List of runs: dict(n, asc, rules, guard, fights[list], decisions[list])."""
    out, n = [], 0
    for name in sorted(os.listdir(R.RECORDS)):
        folder = os.path.join(R.RECORDS, name)
        if not (os.path.isdir(folder) and name[:1].isdigit()):
            continue
        rs = R.runs_of(folder)
        kept = [r for r in rs if r["fights"] or r["end"]]
        with_fights = [r for r in rs if r["combat"]]
        # decisions split: floor goes back down = new run
        dsplit, prev = [], None
        p = os.path.join(folder, "decisions.jsonl")
        with open(p, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                d = json.loads(line)
                fl = d.get("floor", 0)
                if prev is None or fl < prev:
                    dsplit.append([])
                prev = fl
                dsplit[-1].append(d)
        # align decision runs to with_fights runs by order
        dmap = {id(r): (dsplit[i] if i < len(dsplit) else []) for i, r in enumerate(with_fights)}
        for r in kept:
            n += 1
            out.append(dict(n=n, asc=R.asc(r), rules=r.get("run_rules", 1), guard=r.get("fight_guard", 0),
                            fights=r["fights"], decisions=dmap.get(id(r), []), folder=name,
                            nsplit=len(dsplit), nwf=len(with_fights)))
    return out

def strip(c):
    return c[4:] if isinstance(c, str) and c.startswith("gen:") else c

def card_of(action):
    a = action.split("@")[0]
    return strip(a)
