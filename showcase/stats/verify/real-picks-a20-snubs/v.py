import json,os,sys,collections
R="."
sys.path.insert(0,R+"/scripts")
import real_game_report as g
runs=g.all_runs()
print("runs",len(runs),collections.Counter(g.asc(r) for r in runs))
recs=R+"/results/real-game"
segs=[]
for name in sorted(os.listdir(recs)):
    f=os.path.join(recs,name)
    if not (os.path.isdir(f) and name[:1].isdigit()): continue
    prev=None;cur=None
    p=os.path.join(f,"decisions.jsonl")
    if not os.path.exists(p): continue
    for line in open(p,encoding="utf-8"):
        if not line.strip(): continue
        d=json.loads(line)
        if prev is None or d["floor"]<prev:
            cur={"folder":name,"asc":set(),"cr":[]};segs.append(cur)
        prev=d["floor"]
        if "card_reward" in d: cur["cr"].append(d)
        else:
            a=d.get("view",{}).get("ascension")
            cur["asc"].add(a)
print("segments",len(segs))
# compare with runs per folder
fr=collections.Counter(r["folder"] for r in runs if r["fights"]); fs=collections.Counter(s["folder"] for s in segs)
for k in set(fr)|set(fs):
    if fr[k]!=fs[k]: print("mismatch",k,fr[k],fs[k])
# align by folder order to runs with fights
byf=collections.defaultdict(list)
for r in runs:
    if r["fights"]: byf[r["folder"]].append(r)
k=collections.Counter()
off=collections.Counter();take=collections.Counter();nrew={0:0,20:0};nruns={0:0,20:0}
for s in segs:
    i=k[s["folder"]];k[s["folder"]]+=1
    r=byf[s["folder"]][i] if i<len(byf[s["folder"]]) else None
    a=g.asc(r) if r else None
    if s["asc"]-{None} and r and s["asc"]-{None}!={a}: print("asc disagree",s["folder"],s["asc"],a)
    if a!=20: 
        if a==0: nrew[0]+=len(s["cr"]); nruns[0]+=1
        continue
    nruns[20]+=1
    for d in s["cr"]:
        nrew[20]+=1
        names=[c.replace("gen:","") for c in d["card_reward"]]
        for c in set(names): off[c]+=1
        if d["pick"]: take[d["pick"].replace("gen:","")]+=1
print(nrew,nruns)
for c,n in off.most_common():
    if n>=14: print(c,take[c],n,round(100*take[c]/n))
print("---check")
k=collections.Counter()
for s in segs:
    i=k[s["folder"]];k[s["folder"]]+=1
    r=byf[s["folder"]][i]
    if g.asc(r)!=20: continue
    for d in s["cr"]:
        cr=[c.replace("gen:","") for c in d["card_reward"]]; op=[o.replace("gen:","") for o in d["options"] if o]
        if sorted(cr)!=sorted(op) or len(set(cr))!=len(cr): print(s["folder"],d["floor"],cr,op,d["pick"])
