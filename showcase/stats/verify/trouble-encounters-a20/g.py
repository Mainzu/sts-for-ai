import sys, statistics as st, collections
sys.path.insert(0, "scripts")
import real_game_report as R
runs = R.all_runs()
g=[]; lice=collections.defaultdict(list); cult=[]; deaths=collections.Counter(); neg=[]
for i, r in enumerate(runs, 1):
    if R.asc(r) != 20: continue
    for f in r["fights"]:
        m=f["monsters"]; lost=f["hp_start"]-f["hp_end"]
        if not f["won"]: deaths[" + ".join(sorted(m))]+=1
        if lost<0: neg.append((i,m,f["hp_start"],f["hp_end"]))
        if any(x.startswith("Gremlin") for x in m) and "GremlinNob" not in m: g.append((lost, sorted(m), f["won"]))
        if all("Louse" in x for x in m): lice[len(m)].append(lost)
        if m==["Cultist"]: cult.append((lost, f["decisions"], f.get("hp_start")))
print("gang", len(g), st.mean(x[0] for x in g), st.median(x[0] for x in g), sorted(x[0] for x in g))
print(collections.Counter(len(x[1]) for x in g))
for k,v in lice.items(): print("lice",k,len(v),round(st.mean(v),2),st.median(v))
print("cult decisions mean", st.mean(c[1] for c in cult), "median", st.median(c[1] for c in cult), "max", max(c[1] for c in cult))
print("deaths", deaths); print("neg", neg)
