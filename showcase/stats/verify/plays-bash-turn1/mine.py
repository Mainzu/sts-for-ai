import sys,os,json,collections
R="."
sys.path.insert(0,R+"/scripts")
import real_game_report as g
runs=g.all_runs()
num={(r["folder"],r["seed"]):i for i,r in enumerate(runs,1)}
strip=lambda s:s[4:] if s.startswith("gen:") else s
isbash=lambda a: a is not None and strip(a.split("@")[0]) in ("Bash","Bash+")
res=collections.defaultdict(lambda: collections.defaultdict(lambda:[0,0,0,0,0]))  # asc -> group -> [n, exec, lead, anyline, lastline]
tot=collections.defaultdict(lambda:[0,0,0,0,0]); runsseen=collections.defaultdict(set); hk=collections.Counter()
for name in sorted(os.listdir(R+"/results/real-game")):
    folder=R+"/results/real-game/"+name
    if not os.path.isdir(folder) or not name[:1].isdigit(): continue
    rs=[r for r in g.runs_of(folder) if r["combat"]]
    p=folder+"/decisions.jsonl"
    if not os.path.exists(p): continue
    k=-1;prev=None;fights=collections.OrderedDict()
    with open(p,encoding="utf-8") as f:
        for l in f:
            d=json.loads(l)
            if prev is None or d["floor"]<prev: k+=1
            prev=d["floor"]
            if "turn" in d and d["turn"]==1:
                fights.setdefault((k,d["floor"]),[]).append(d)
    for (k,fl),ds in fights.items():
        r=rs[k]
        if (r["folder"],r["seed"]) not in num: print("unnumbered",name,k); continue
        asc=r["ascension"]
        hand=ds[0]["view"]["hand"]
        for c in hand: hk[c]+=1
        if not any(strip(c) in("Bash","Bash+") for c in hand): continue
        grp=" + ".join(sorted(m["name"] for m in ds[0]["view"]["monsters"]))
        ex=[]
        for i,d in enumerate(ds):
            if i+1<len(ds):
                n=ds[i+1]["view"]["cards_played_this_turn"]-d["view"]["cards_played_this_turn"]
                ex+=d["line"][:max(n,1)]
            else: ex+=d["line"]
        first=ds[0]["options"][ds[0]["pick"]][0]
        v=[1,any(map(isbash,ex)),isbash(first),any(isbash(a) for d in ds for a in d["line"]),any(map(isbash,ds[-1]["line"]))]
        for i in range(5):
            res[asc][grp][i]+=v[i]; tot[asc][i]+=v[i]
        runsseen[asc].add(num[(r["folder"],r["seed"])])
for asc in sorted(res):
    print("ASC",asc,"tot [n,exec,lead,anyline,lastline]",tot[asc],"runs",min(runsseen[asc]),max(runsseen[asc]),len(runsseen[asc]))
    for gname,v in sorted(res[asc].items(),key=lambda x:-x[1][0]):
        if v[0]>=6: print("  ",v,gname)
print([c for c in hk if "ash" in c])
