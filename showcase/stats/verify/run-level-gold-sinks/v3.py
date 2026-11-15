import os, json, collections
R="results/real-game"
stolen=collections.Counter(); back=collections.Counter(); seenrw=set()
for d in sorted(os.listdir(R)):
    p=R+"/"+d
    if not os.path.isdir(p): continue
    prev={}
    for ln in open(p+"/states.jsonl",encoding="utf-8"):
        gs=json.loads(ln)["msg"].get("game_state")
        if not gs or gs.get("seed") is None: continue
        a=gs.get("ascension_level",0)
        pv=prev.get(gs["seed"])
        if pv and gs.get("gold") is not None and pv.get("gold") is not None and gs["gold"]<pv["gold"] and pv.get("room_phase")=="COMBAT":
            stolen[a]+=pv["gold"]-gs["gold"]
        if gs.get("screen_type")=="COMBAT_REWARD":
            for rw in gs["screen_state"].get("rewards",[]):
                if rw.get("reward_type")=="STOLEN_GOLD":
                    k=(gs["seed"],gs.get("floor"))
                    if k not in seenrw: seenrw.add(k); back[a]+=rw.get("gold",0)
        prev[gs["seed"]]=gs
print("stolen",stolen,"returned offered",back)
