import os, json, collections, statistics
R="results/real-game"
def lab(o):
    a=o[0].split("@")[0]; return a[4:] if a.startswith("gen:") else a
for A in (None,20):
  n=ch=0; g=[]; sw=collections.Counter(); multi=collections.Counter(); same=0
  for name in sorted(os.listdir(R)):
    p=os.path.join(R,name,"decisions.jsonl")
    if not (name[:1].isdigit() and os.path.exists(p)): continue
    for ln in open(p,encoding="utf-8"):
        if not ln.strip(): continue
        d=json.loads(ln)
        if "view" not in d or d["view"].get("ascension")!=A or d.get("cut") or len(d["options"])<2 or d.get("two") is None: continue
        n+=1; one=d["one"]; m=max(one); best=[i for i,v in enumerate(one) if v>=m-1e-9]; pk=d["pick"]
        if pk in best: continue
        ch+=1; g.append((m-one[pk])*100)
        o=lab(d["options"][best[0]]); t=lab(d["options"][pk])
        if o==t: same+=1; continue
        sw[(o,t)]+=1
        if len({lab(d["options"][i]) for i in best})>1: multi[(o,t)]+=1
  print(A,n,ch,round(100*ch/n,1),"median",round(statistics.median(g),2),">5",sum(x>5 for x in g),">1",sum(x>1 for x in g),"same-label(target only)",same)
  print(sw.most_common(10)); print("origin ambiguous (tied labels):",multi.most_common(5), sum(multi.values()))
