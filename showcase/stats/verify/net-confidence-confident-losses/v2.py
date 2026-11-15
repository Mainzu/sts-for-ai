import sys, os, json
ROOT = "."
sys.path.insert(0, ROOT + "/scripts")
import real_game_report as R
runs = R.all_runs()
for i,r in enumerate(runs,1): r["n"]=i
want = {8:16,26:7,36:16,45:16,48:16,50:8,82:16,79:10,30:7,76:8}
byf={}
for r in runs: byf.setdefault(r["folder"],[]).append(r)
for name, rs in byf.items():
    wf=[r for r in rs if r["fights"]]
    k=-1; prev=None
    p=os.path.join(R.RECORDS,name,"decisions.jsonl")
    if not os.path.exists(p): continue
    seen=set()
    for line in open(p,encoding="utf-8"):
        if not line.strip(): continue
        d=json.loads(line); fl=d.get("floor")
        if prev is None or fl<prev: k+=1
        prev=fl
        r=wf[k]
        if want.get(r["n"])==fl and "card_reward" not in d:
            if (r["n"],fl) in seen and r["n"] not in (8,26,50): continue
            seen.add((r["n"],fl))
            v=d.get("view",{}); pl=v.get("player",{})
            print(r["n"], fl, "turn",d.get("turn"), sorted(k2 for k2 in d if k2!="view"), "two" in d and (d["two"][d["pick"]] if d["two"] else d["two"]), "one", d.get("one") and d["one"][d["pick"]] if d.get("one") else None, "hp",pl.get("hp"),pl.get("max_hp"), "opts", len(d.get("options",[])))
