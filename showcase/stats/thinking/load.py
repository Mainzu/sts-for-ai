"""Decisions of the real-game runs, each tagged with its run number (1-90) and setting."""
import json, os, sys
ROOT = "."
sys.path.insert(0, ROOT + "/scripts")
import real_game_report as R

def decisions():
    """Yield (run_no, setting, decision dict) for every fight decision and card reward."""
    n = 0
    mism = 0
    for name in sorted(os.listdir(R.RECORDS)):
        folder = os.path.join(R.RECORDS, name)
        if not (os.path.isdir(folder) and name[:1].isdigit()):
            continue
        runs = [r for r in R.runs_of(folder) if r["fights"] or r["end"]]
        nums = {id(r): n + 1 + i for i, r in enumerate(runs)}
        n += len(runs)
        wf = [r for r in runs if r["combat"]]
        p = os.path.join(folder, "decisions.jsonl")
        if not os.path.exists(p):
            continue
        k, prev = -1, None
        with open(p, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                d = json.loads(line)
                if prev is None or d["floor"] < prev:
                    k += 1
                prev = d["floor"]
                if k >= len(wf):
                    mism += 1
                    continue
                r = wf[k]
                yield nums[id(r)], R.setting(r), d
    if mism:
        print("unassigned decision lines:", mism, file=sys.stderr)

def clean(c):
    return c.replace("gen:", "")
