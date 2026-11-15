"""Loader: real-game runs with their fight decisions, numbered 1..N in all_runs order."""
import json, os, sys
ROOT = "."
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import real_game_report as rg

def strip(n):
    return n[4:] if n and n.startswith("gen:") else n

def decision_runs(folder):
    out, prev = [], None
    p = os.path.join(folder, "decisions.jsonl")
    if not os.path.exists(p):
        return out
    with open(p, encoding="utf-8") as f:
        for l in f:
            if not l.strip():
                continue
            x = json.loads(l)
            if prev is None or x["floor"] < prev:
                out.append([])
            prev = x["floor"]
            out[-1].append(x)
    return out

def load():
    """List of runs: dict with no (1-based), asc, rules, guard, fights, decisions (fight ones), rewards."""
    runs = []
    rec = rg.RECORDS
    for name in sorted(os.listdir(rec)):
        folder = os.path.join(rec, name)
        if not (os.path.isdir(folder) and name[:1].isdigit()):
            continue
        rs = [r for r in rg.runs_of(folder) if r["fights"] or r["end"]]
        drs = decision_runs(folder)
        # match decision-runs to runs: by order among runs that have any decision
        # (runs with fights or a Neow pick). Check by fight-decision counts.
        k = 0
        for r in rs:
            want = sum(f.get("decisions", 0) for f in r["fights"])
            d = drs[k] if k < len(drs) else []
            got = sum(1 for x in d if "turn" in x)
            if want == 0 and got > 0 and not r["fights"]:
                d = []
            else:
                k += 1
            r["_dec"] = d
            r["_check"] = (want, got)
        runs += rs
    out = []
    for i, r in enumerate(runs, 1):
        a, ru, g = rg.setting(r)
        out.append({"no": i, "asc": a, "rules": ru, "guard": g, "fights": r["fights"],
                    "dec": [x for x in r["_dec"] if "turn" in x],
                    "rewards": [x for x in r["_dec"] if "card_reward" in x],
                    "check": r["_check"], "end": r["end"], "folder": r["folder"], "seed": r["seed"]})
    return out

def executed(decs):
    """Per fight decision, the actions actually sent: the planned line up to the next
    decision of the same turn (cards counted by cards_played_this_turn), else the whole line."""
    res = []
    for i, x in enumerate(decs):
        line = x["line"]
        nxt = decs[i + 1] if i + 1 < len(decs) else None
        if nxt and nxt["floor"] == x["floor"] and nxt["turn"] == x["turn"]:
            n = nxt["view"]["cards_played_this_turn"] - x["view"]["cards_played_this_turn"]
            acts, c = [], 0
            for a in line:
                if c >= n and not a.startswith("Potion"):
                    break
                if c >= n and a.startswith("Potion"):
                    break
                acts.append(a)
                if not a.startswith(("Potion", "End", "Choose", "Done")):
                    c += 1
            res.append(acts)
        else:
            res.append(line)
    return res

def card_of(a):
    return strip(a.split("@")[0].split("{")[0])
