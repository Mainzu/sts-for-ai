import sys, os, json
from collections import defaultdict, Counter
ROOT = "."
sys.path.insert(0, ROOT + "/scripts")
import real_game_report as R
runs = R.all_runs()
print("runs", len(runs))
byfolder = defaultdict(list)
for i, r in enumerate(runs, 1):
    r["n"] = i; byfolder[r["folder"]].append(r)
rows = []  # (run, floor, skipped, argmax_ok, asc, rules, guard)
bad = []
for folder, rs in byfolder.items():
    segs, prev = [], None
    allfl = []
    with open(os.path.join(R.RECORDS, folder, "decisions.jsonl"), encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            d = json.loads(line)
            fl = d["floor"]
            if prev is None or fl < prev: segs.append([])
            prev = fl
            if "card_reward" in d: segs[-1].append(d)
    if len(segs) != len(rs): bad.append((folder, len(segs), [r["n"] for r in rs]))
    for k, seg in enumerate(segs):
        r = rs[min(k, len(rs)-1)]
        for d in seg:
            sc = d["scores"]; best = max(range(len(sc)), key=lambda i: sc[i])
            pi = d["options"].index(d["pick"])
            rows.append((r["n"], d["floor"], d["pick"] is None, sc[pi] == sc[best], R.asc(r), r.get("run_rules",1), r.get("fight_guard",0), len(d["options"]), len(d["card_reward"])))
print("segment mismatches", bad)
def band(fl):
    return "1-6" if fl<=6 else "7-12" if fl<=12 else "13-17" if fl<=17 else "18+"
for a in (0,20):
    sub=[x for x in rows if x[4]==a]
    s=sum(x[2] for x in sub); print(a,"all",s,len(sub),round(100*s/len(sub),1),"runs",len({x[0] for x in sub}), "runrange",min(x[0] for x in sub),max(x[0] for x in sub))
    for b in ("1-6","7-12","13-17","18+"):
        ss=[x for x in sub if band(x[1])==b]
        if ss: print("  ",b,sum(x[2] for x in ss),len(ss),round(100*sum(x[2] for x in ss)/len(ss),1))
    c=Counter((x[5],x[6]) for x in sub); 
    for k in sorted(c):
        ss=[x for x in sub if (x[5],x[6])==k]; print("  setting",k,sum(x[2] for x in ss),len(ss),round(100*sum(x[2] for x in ss)/len(ss)), "runs",len({x[0] for x in ss}))
print("argmax ok", sum(x[3] for x in rows), len(rows))
print("options sizes", Counter(x[7] for x in rows), Counter(x[8] for x in rows))
for n in (3,5,21): print("run",n,[ (x[1],x[2]) for x in rows if x[0]==n])
# A0 18+ runs
print("A0 18+ runs", Counter(x[0] for x in rows if x[4]==0 and x[1]>=18))
print("A20 18+", [x for x in rows if x[4]==20 and x[1]>=18][:5])
