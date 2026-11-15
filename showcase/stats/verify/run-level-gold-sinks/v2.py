import os, json, collections
R="results/real-game"
other=collections.Counter(); bandit=[]
for d in sorted(os.listdir(R)):
    p=R+"/"+d
    if not os.path.isdir(p): continue
    prev={}
    for ln in open(p+"/states.jsonl",encoding="utf-8"):
        gs=json.loads(ln)["msg"].get("game_state")
        if not gs or gs.get("seed") is None: continue
        pv=prev.get(gs["seed"])
        if pv and gs.get("gold") is not None and pv.get("gold") is not None and gs["gold"]<pv["gold"]:
            if pv.get("screen_type")!="EVENT": other[(pv.get("screen_type"),pv.get("room_phase"))]+=pv["gold"]-gs["gold"]
            elif pv["screen_state"].get("event_name")=="Masked Bandits": bandit.append((d,pv["gold"],gs["gold"],[o["text"] for o in pv["screen_state"]["options"]],gs["screen_state"].get("body_text","")[:120]))
        prev[gs["seed"]]=gs
print(other); [print(b) for b in bandit]
