import sys,os,json,collections
R="."
sys.path.insert(0,R+"/scripts")
import real_game_report as g
strip=lambda s:s[4:] if s.startswith("gen:") else s
card=lambda a: strip(a.split("@")[0])
isbash=lambda a: card(a) in ("Bash","Bash+")
res=collections.defaultdict(lambda: collections.defaultdict(lambda:[0,0,0,0]))
tot=collections.defaultdict(lambda:[0,0,0,0]); firsts=collections.Counter(); multi=0
for name in sorted(os.listdir(R+"/results/real-game")):
    folder=R+"/results/real-game/"+name
    if not os.path.isdir(folder) or not name[:1].isdigit(): continue
    rs=[r for r in g.runs_of(folder) if r["combat"]]
    k=-1;prev=None;fights=collections.OrderedDict()
    with open(folder+"/decisions.jsonl",encoding="utf-8") as f:
        for l in f:
            d=json.loads(l)
            if prev is None or d["floor"]<prev: k+=1
            prev=d["floor"]
            if d.get("turn")==1: fights.setdefault((k,d["floor"]),[]).append(d)
    for (k,fl),ds in fights.items():
        asc=rs[k]["ascension"]
        if not any(strip(c) in("Bash","Bash+") for c in ds[0]["view"]["hand"]): continue
        grp=" + ".join(sorted(set(strip(m["name"]) for m in ds[0]["view"]["monsters"])))
        ex=[]
        for i,d in enumerate(ds):
            if i+1<len(ds):
                n=ds[i+1]["view"]["cards_played_this_turn"]-d["view"]["cards_played_this_turn"]; ex+=d["line"][:max(n,1)]
            else: ex+=d["line"]
        ex_cards=[a for a in ex if a!="End" and not a.lower().startswith("potion") and "Potion" not in a]
        if asc==20: firsts[ex[0].split("@")[0]]+=1
        if len(ds)>1: multi+=1
        v=[1,any(map(isbash,ex)),isbash(ex[0]),bool(ex_cards) and isbash(ex_cards[0])]
        for i in range(4): res[asc][grp][i]+=v[i]; tot[asc][i]+=v[i]
for asc in sorted(res):
    print("ASC",asc,"[n,played,lead_first_action,lead_first_card]",tot[asc])
    for gname,v in sorted(res[asc].items(),key=lambda x:-x[1][0]):
        if v[0]>=6: print("  ",v,gname)
print(firsts.most_common(40)); print("multi",multi)
