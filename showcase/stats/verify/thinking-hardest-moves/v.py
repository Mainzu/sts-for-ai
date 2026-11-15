import sys, os, json
R="."
sys.path.insert(0,R+"/scripts")
import real_game_report as g
runs=g.all_runs()
print("runs",len(runs))
# per folder, runs with combat in order
byf={}
for i,r in enumerate(runs,1):
    byf.setdefault(r["folder"],[]).append((i,r))
recs=[]
for f,lst in byf.items():
    wc=[(i,r) for i,r in lst if r["combat"]]
    k=-1;prev=None
    for line in open(os.path.join(R,"results/real-game",f,"decisions.jsonl"),encoding="utf-8"):
        d=json.loads(line)
        fl=d.get("floor")
        if prev is None or (fl is not None and fl<prev): k+=1
        if fl is not None: prev=fl
        if "card_reward" in d: continue
        if k>=len(wc): print("overflow",f); continue
        i,r=wc[k]
        recs.append((i,r.get("ascension"),d))
    # sanity: count runs per folder vs decision segments
    print(f,len(lst),len(wc),k+1)
for asc in (0,20):
    s=[x for x in recs if x[1]==asc]
    print("asc",asc,"n",len(s),"runs",sorted(set(x[0] for x in s))[:3],"..",max(x[0] for x in s))
    s.sort(key=lambda x:-(x[2].get("seconds") or 0))
    for i,a,d in s[:7]:
        v=d["view"];p=v["player"]
        print(" run",i,"fl",d["floor"],"turn",d["turn"],"s",d["seconds"],"cut",d.get("cut"))
        print("   hand",v["hand"],"pow",p.get("powers"),"relics",p.get("relics"),"pots",p.get("potions"))
        print("   mons",[(m["name"],m["hp"],m.get("powers")) for m in v["monsters"]])
        print("   pick",d["options"][d["pick"]] if isinstance(d["pick"],int) else d["pick"],"line",d.get("line"))
