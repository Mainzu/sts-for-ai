import sys,json,os,collections
sys.path.insert(0,r"scripts")
os.chdir(r".")
import real_game_report as R
runs=R.all_runs()
want={(31,4),(60,10),(64,5),(64,8),(65,13),(86,3),(87,3),(54,14)}
# per folder, run order among runs in that folder
byf=collections.defaultdict(list)
for i,r in enumerate(runs,1): byf[r["folder"]].append(i)
for fo,ids in byf.items():
    k=-1;prev=None
    p=os.path.join("results/real-game",fo,"decisions.jsonl")
    with open(p,encoding="utf-8") as fh:
        for ln in fh:
            d=json.loads(ln)
            if prev is None or d["floor"]<prev: k+=1
            prev=d["floor"]
            if k>=len(ids): continue
            i=ids[k]
            if (i,d["floor"]) in want and "options" in d and "card_reward" not in d:
                o=d["options"][d["pick"]] if isinstance(d.get("pick"),int) else d.get("pick")
                print(i,d["floor"],d.get("turn"),o,d.get("line"),d["view"]["player"].get("potions"),d["view"]["player"].get("energy"),{k:v for k,v in d["view"]["hand"].items()},[m["name"]+":"+str(m["hp"]) for m in d["view"]["monsters"]],d["view"]["player"]["hp"])
