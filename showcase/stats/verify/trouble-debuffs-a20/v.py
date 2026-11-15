import sys, os, json, collections, statistics
REPO="."
sys.path.insert(0, REPO+"/scripts")
import real_game_report as R
runs = R.all_runs(os.path.join(REPO,"results/real-game"))
print("runs", len(runs))
def strip(n): return n[4:] if n.startswith("gen:") else n
STAT={"Burn","Dazed","Wound","Slimed","Void"}
# decisions per folder -> segments
def segs(folder):
    out=[];prev=None
    with open(os.path.join(REPO,"results/real-game",folder,"decisions.jsonl"),encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            d=json.loads(line)
            if prev is None or d["floor"]<prev: out.append({})
            prev=d["floor"]
            if "view" not in d: continue
            v=d["view"]; e=out[-1].setdefault(d["floor"],{"pw":set(),"st":collections.Counter(),"n":0})
            e["n"]+=1
            for p,a in (v["player"].get("powers") or {}).items(): e["pw"].add(p)
            c=collections.Counter()
            for pile in ("hand","draw","discard"):
                for k,n in (v.get(pile) or {}).items(): c[strip(k)]+=n
            for k in STAT:
                if c[k]: e["st"][k]=max(e["st"][k],c[k])
    return out
byfolder=collections.defaultdict(list)
for i,r in enumerate(runs,1): byfolder[r["folder"]].append((i,r))
rows={0:[],20:[]}
for folder,lst in byfolder.items():
    S=segs(folder)
    wf=[x for x in lst if x[1]["fights"]]
    if len(S)!=len(wf): print("MISMATCH",folder,len(S),len(wf))
    for (i,r),s in zip(wf,S):
        a=R.asc(r)
        for f in r["fights"]:
            e=s.get(f["floor"])
            if not e: continue
            lost=f["hp_start"]-f["hp_end"]
            rows[a].append((i,f,e,lost))
for a in (0,20):
    L=rows[a]; print("ASC",a,"fights",len(L),"runs",sorted({x[0] for x in L})[:3],"..",sorted({x[0] for x in L})[-3:],"mean",round(statistics.mean(x[3] for x in L),2))
    allp=collections.Counter(p for x in L for p in x[2]["pw"]); print(allp.most_common(40))
    keys=list(STAT)+[p for p,_ in allp.most_common(40)]
    for k in keys:
        sel=[x for x in L if (k in x[2]["st"] if k in STAT else k in x[2]["pw"])]
        if not sel: continue
        mons=collections.Counter("+".join(sorted(set(x[1]["monsters"]))) for x in sel).most_common(3)
        mx=max((x[2]["st"].get(k,0) for x in sel),default=0)
        print(" %-14s n=%3d mean=%.1f max=%s %s"%(k,len(sel),statistics.mean(x[3] for x in sel),mx,mons))
