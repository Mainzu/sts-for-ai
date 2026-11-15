import sys, os, json, collections
ROOT="."
sys.path.insert(0, ROOT+"/scripts")
import real_game_report as R
runs=R.all_runs()
print("runs", len(runs))
byfolder=collections.defaultdict(list)
for i,r in enumerate(runs,1):
    r["n"]=i; byfolder[r["folder"]].append(r)
offer=collections.Counter(); pick=collections.Counter(); rewards=0; rr=set(); mism=[]
dup_offer=0; skips=0
for folder, rs in byfolder.items():
    segs=[]; prev=None
    with open(os.path.join(R.RECORDS,folder,"decisions.jsonl"),encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            d=json.loads(line)
            if prev is None or d["floor"]<prev: segs.append([])
            prev=d["floor"]; segs[-1].append(d)
    withf=[r for r in rs if r["fights"]]
    if len(segs)!=len(withf): mism.append((folder,len(segs),len(withf),[r["n"] for r in rs]))
    for r,seg in zip(withf,segs):
        if (r.get("ascension") or 0)!=20: continue
        # check floors
        for d in seg:
            if "card_reward" not in d: continue
            rewards+=1; rr.add(r["n"])
            names=[c.replace("gen:","") for c in d["card_reward"]]
            if len(set(names))<len(names): dup_offer+=1
            for c in set(names): offer[c]+=1
            p=d["pick"]
            if p is None: skips+=1
            else: pick[p.replace("gen:","")]+=1
print("mismatch",mism)
print("A20 rewards",rewards,"runs",len(rr),min(rr),max(rr),"skips",skips,"dupoffers",dup_offer)
print("A20 runs total",sum(1 for r in runs if r.get("ascension")==20), [r["n"] for r in runs if r.get("ascension")==20][:3])
rows=sorted(((pick[c]/offer[c],c,pick[c],offer[c]) for c in offer if offer[c]>=5),reverse=True)
for x in rows: print("%5.1f %-20s %d/%d"%(x[0]*100,x[1],x[2],x[3]))
print("most picked total", pick.most_common(5))
