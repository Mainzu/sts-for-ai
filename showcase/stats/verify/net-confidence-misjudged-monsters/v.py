import sys, os, json, collections
REPO="."
sys.path.insert(0, REPO+"/scripts")
import real_game_report as R
runs = R.all_runs()
print("runs", len(runs))
# decisions split per folder
def dec_runs(folder):
    out=[]; prev=None
    with open(os.path.join(R.RECORDS, folder, "decisions.jsonl"), encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            d=json.loads(line)
            if prev is None or d["floor"]<prev: out.append([])
            prev=d["floor"]; out[-1].append(d)
    return out
byfolder=collections.defaultdict(list)
for i,r in enumerate(runs,1): byfolder[r["folder"]].append(i)
rows=[]  # (runno, asc, enc, group, start, actual, won)
miss=0
for folder, idx in byfolder.items():
    dr = dec_runs(folder)
    fr=[i for i in idx if runs[i-1]["fights"]]
    if len(dr)!=len(fr): print("MISMATCH", folder, len(dr), len(fr), idx)
    for k,i in enumerate(fr):
        r=runs[i-1]; ds=dr[k] if k<len(dr) else []
        first={}
        for d in ds:
            if "card_reward" in d or "two" not in d: continue
            first.setdefault(d["floor"], d)
        for f in r["fights"]:
            if f["floor"]>17 or f.get("handed_over") is not None: continue
            d=first.get(f["floor"])
            if d is None: miss+=1; continue
            s=(d["two"] or d["one"])[d["pick"]]
            act = (2-max(f["hp_start"]-f["hp_after"],0)/100) if f["won"] else 0.0
            rows.append((i,R.asc(r),tuple(f["monsters"]),f["group"],s,act,f["won"],d["two"] is None,d["turn"]))
print("missing first decision", miss)
json.dump(rows, open("rows.json","w"))
for A in (0,20):
    sub=[x for x in rows if x[1]==A]
    print("ASC",A,"fights",len(sub), "runs", sorted(set(x[0] for x in sub))[:3], "..", max(x[0] for x in sub))
    g=collections.defaultdict(list)
    for x in sub: g[(x[2] if x[3]!="hallway" or True else None)].append(x)
    tot=0
    for k,v in sorted(g.items(), key=lambda kv:-sum(x[4]-x[5] for x in kv[1])/len(kv[1])):
        if len(v)>=6:
            tot+=len(v)
            won=[x for x in v if x[6]]
            print(f"{'/'.join(k):45s} {v[0][3]:8s} n={len(v):3d} lost={sum(not x[6] for x in v):2d} mean={100*sum(x[4]-x[5] for x in v)/len(v):6.1f} won: exp={100*(2-sum(x[4] for x in won)/max(len(won),1)):5.1f} act={100*(2-sum(x[5] for x in won)/max(len(won),1)):5.1f}")
    print("shown total", tot)
