exec(open("v.py").read().split("for a in (0,20):")[0])
import re
L=rows[20]
print("sentry counts in Dazed fights", collections.Counter(len(x[1]["monsters"]) for x in L if "Dazed" in x[2]["st"] and set(x[1]["monsters"])=={"Sentry"}))
for m in ["Hexaghost","Sentry","SlaverBlue","Lagavulin"]:
    s=[x[3] for x in L if m in x[1]["monsters"]]; print(m,len(s),round(statistics.mean(s),1))
# sign of Dexterity/Strength: rescan
neg=collections.Counter()
for folder in byfolder:
    with open(os.path.join(REPO,"results/real-game",folder,"decisions.jsonl"),encoding="utf-8") as f:
        for line in f:
            if '"Dexterity"' not in line: continue
            d=json.loads(line); v=d.get("view")
            if v and v.get("ascension")==20:
                neg["dex<0" if v["player"]["powers"].get("Dexterity",0)<0 else "dex>0"]+=1
print(neg)
# negative dex fights
nd=[]
# per-fight: negative Str or Dex at any decision (Lagavulin-type debuff)
def negfights():
    out=[]
    for folder,lst in byfolder.items():
        wf=[x for x in lst if x[1]["fights"]]
        prev=None; segs_=[]
        with open(os.path.join(REPO,"results/real-game",folder,"decisions.jsonl"),encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                d=json.loads(line)
                if prev is None or d["floor"]<prev: segs_.append(set())
                prev=d["floor"]
                v=d.get("view")
                if v and (v["player"]["powers"].get("Dexterity",0)<0 or v["player"]["powers"].get("Strength",0)<0): segs_[-1].add(d["floor"])
        for (i,r),s in zip(wf,segs_):
            if R.asc(r)==20:
                for fl in r["fights"]:
                    if fl["floor"] in s: out.append((fl["hp_start"]-fl["hp_end"],fl["monsters"]))
    return out
nf=negfights(); print("neg Str/Dex fights",len(nf),round(statistics.mean(x[0] for x in nf),1),collections.Counter(m for x in nf for m in set(x[1])).most_common(3))
