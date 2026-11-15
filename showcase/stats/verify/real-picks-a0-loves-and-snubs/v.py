import sys, os, json, collections
R="."
sys.path.insert(0,R+"/scripts")
import real_game_report as g
recs=R+"/results/real-game"
n=0; off=collections.Counter(); pk=collections.Counter(); rewards=0; runs_used=set(); skips=0; notopt=collections.Counter(); hi=collections.Counter()
for name in sorted(os.listdir(recs)):
    folder=os.path.join(recs,name)
    if not(os.path.isdir(folder) and name[:1].isdigit()): continue
    allr=g.runs_of(folder); kept=[r for r in allr if r["fights"] or r["end"]]
    # split decisions
    groups=[]; prev=None
    p=os.path.join(folder,"decisions.jsonl")
    if os.path.exists(p):
        for line in open(p,encoding="utf-8"):
            if not line.strip(): continue
            d=json.loads(line); f=d.get("floor")
            if prev is None or (f is not None and f<prev): groups.append([])
            if f is not None: prev=f
            groups[-1].append(d)
    if len(groups)!=len(kept): print("MISMATCH",name,len(groups),len(kept),len(allr))
    for i,r in enumerate(kept):
        n+=1
        if i>=len(groups): continue
        if (r.get("ascension") or 0)!=0: continue
        runs_used.add(n)
        for d in groups[i]:
            if "card_reward" not in d: continue
            rewards+=1; hi.update([n]) if d["floor"]>17 else None
            names=[c.replace("gen:","") for c in d["card_reward"]]
            for c in set(names): off[c]+=1
            if d.get("pick") is None: skips+=1
            else: pk[d["pick"].replace("gen:","").rstrip("+")]+=1
            opts=set((o or "").replace("gen:","").rstrip("+") for o in d["options"])
            [notopt.update([c]) for c in names if c not in opts]
            print("DUPE",d["card_reward"]) if len(set(names))!=len(names) else None
print("runs",sorted(runs_used),"rewards",rewards,"skips",skips,"total runs",n)
for c,o in sorted(off.items(),key=lambda x:(-pk[x[0]]/x[1],-x[1])):
    print(f"{c:20s} {pk[c]}/{o} {round(100*pk[c]/o)}")
print("not-option offers",notopt.most_common(15))
print("act2 rewards by run",dict(hi))
