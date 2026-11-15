import sys, os, json, statistics as st
R="."
sys.path.insert(0,R+"/scripts")
import real_game_report as rg
runs=rg.all_runs(R+"/results/real-game")
print("runs",len(runs))
idx={id(r):i+1 for i,r in enumerate(runs)}
by={} ; byv={}; runsets={}; mism=0; alive_hp0=0
for name in sorted(os.listdir(R+"/results/real-game")):
    folder=R+"/results/real-game/"+name
    if not os.path.isdir(folder): continue
    rs=[r for r in runs if r["folder"]==name and r["combat"]]
    k=-1; prev=None
    with open(folder+"/decisions.jsonl",encoding="utf-8") as f:
        for ln in f:
            if not ln.strip(): continue
            d=json.loads(ln)
            fl=d.get("floor")
            if fl is not None:
                if prev is None or fl<prev: k+=1
                prev=fl
            if "view" not in d: continue
            r=rs[k] if k<len(rs) else None
            rn=idx.get(id(r)) if r else None
            a=d["view"].get("ascension")
            ra=rg.asc(r) if r else None
            if a!=ra: mism+=1
            if ra!=20: continue
            ms=d["view"]["monsters"]
            n=sum(1 for m in ms if m.get("hp",0)>0 and not m.get("is_gone") and not m.get("gone"))
            by.setdefault(n,[]).append((d["seconds"],bool(d.get("cut")),rn,len(d["options"])))
print("asc mismatch",mism)
tot=0
for n in sorted(by):
    L=by[n]; s=[x[0] for x in L]; tot+=len(L)
    print(n,len(L),round(st.mean(s),2),round(st.median(s),2),round(100*sum(x[1] for x in L)/len(L)),"runs",len({x[2] for x in L}),"opts",round(st.mean(x[3] for x in L),1), sorted({x[2] for x in L})[:3])
print("tot",tot)
