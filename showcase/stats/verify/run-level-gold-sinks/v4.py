import os, json, collections
R="results/real-game"
# per (seed,floor): gold at first combat state, gold at first MAP state after; stolen in fight
res=collections.defaultdict(lambda:[0,0,0])  # asc -> [fights with theft, stolen, net change in gold over that floor from combat start to map]
for d in sorted(os.listdir(R)):
    p=R+"/"+d
    if not os.path.isdir(p): continue
    prev={}; cur={}
    for ln in open(p+"/states.jsonl",encoding="utf-8"):
        gs=json.loads(ln)["msg"].get("game_state")
        if not gs or gs.get("seed") is None: continue
        s=gs["seed"]; a=gs.get("ascension_level",0); pv=prev.get(s)
        if gs.get("room_phase")=="COMBAT" and (s not in cur or cur[s]["floor"]!=gs.get("floor")):
            cur[s]={"floor":gs.get("floor"),"g0":gs.get("gold"),"st":0,"done":False}
        c=cur.get(s)
        if c and pv and pv.get("room_phase")=="COMBAT" and gs.get("gold",0)<pv.get("gold",0): c["st"]+=pv["gold"]-gs["gold"]
        if c and not c["done"] and gs.get("screen_type")=="MAP" and gs.get("floor")==c["floor"] and c["st"]:
            c["done"]=True; r=res[a]; r[0]+=1; r[1]+=c["st"]; r[2]+=gs["gold"]-c["g0"]
        prev[s]=gs
print(dict(res))
