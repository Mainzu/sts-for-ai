import os, json, collections
R="results/real-game"
def lab(o):
    a=o[0].split("@")[0]; return a[4:] if a.startswith("gen:") else a
for A in (None,20):
  anyb=collections.Counter(); uniq=collections.Counter(); topick=collections.Counter(); nb=collections.Counter()
  for name in sorted(os.listdir(R)):
    p=os.path.join(R,name,"decisions.jsonl")
    if not (name[:1].isdigit() and os.path.exists(p)): continue
    for ln in open(p,encoding="utf-8"):
        if not ln.strip(): continue
        d=json.loads(ln)
        if "view" not in d or d["view"].get("ascension")!=A or d.get("cut") or len(d["options"])<2 or d.get("two") is None: continue
        one=d["one"]; m=max(one); best=[i for i,v in enumerate(one) if v>=m-1e-9]; pk=d["pick"]
        if pk in best: continue
        t=lab(d["options"][pk]); L={lab(d["options"][i]) for i in best}
        topick[t]+=1; nb[len(best)]+=1
        if t in L: continue
        for o in L: anyb[(o,t)]+=1
        if len(L)==1: uniq[(next(iter(L)),t)]+=1
  print(A,"pick label:",topick.most_common(6)); print(" one-turn best size",sorted(nb.items()))
  print(" fav among tied best -> pick:",anyb.most_common(10))
  print(" sole one-turn favourite -> pick:",uniq.most_common(10))
