import sys, json, os, collections
sys.path.insert(0, "scripts")
import real_game_report as R
runs = R.all_runs()
# deck at the boss fight: last state in combat on the boss floor, per seed
want={(r["folder"],r["seed"]):r for r in runs if R.asc(r)==20 and any(f.get("group")=="boss" for f in r["fights"])}
atboss={}
for folder in sorted({k[0] for k in want}):
    with open(os.path.join(R.RECORDS,folder,"states.jsonl"),encoding="utf-8") as f:
        for line in f:
            if '"combat_state"' not in line: continue
            gs=json.loads(line)["msg"].get("game_state") or {}
            k=(folder,gs.get("seed"))
            if k in want and gs.get("floor",0)>=16 and gs.get("deck"):
                atboss[k]=[c["id"].replace("_R","") for c in gs["deck"]]
diff=collections.Counter(); S=[]
for k,r in want.items():
    end=[c["id"].replace("_R","") for c in r["last"]["deck"]]
    b=atboss.get(k)
    if b is None: print("no boss deck", k); continue
    won=any(f["won"] for f in r["fights"] if f.get("group")=="boss")
    extra=collections.Counter(end)-collections.Counter(b)
    if extra: diff[won]+=1; print(won, dict(extra))
    S.append((b,won))
print(diff)
for c in ["Fire Breathing","Spot Weakness","Clash","Pommel Strike","Armaments","Shrug It Off","Perfected Strike","Iron Wave","Heavy Blade","Wild Strike"]:
    w=[x for x in S if c in x[0]]; print(c, sum(x[1] for x in w), len(w))
