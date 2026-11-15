import sys, os, json, collections, datetime
R="."
sys.path.insert(0, R+"/scripts")
import real_game_report as rg
runs = rg.all_runs()
print("runs", len(runs))
seedinfo = {}
for i, r in enumerate(runs, 1):
    seedinfo[r["seed"]] = (i, rg.asc(r), r.get("run_rules",1))
loss = collections.defaultdict(list)   # (asc, event, choice text) -> list of (run, amount)
met = collections.Counter()
endgold = collections.Counter()
lastgold = {}
for d in sorted(os.listdir(R+"/results/real-game")):
    p = R+"/results/real-game/"+d
    if not os.path.isdir(p): continue
    # log sends
    sends=[]
    for ln in open(p+"/log.txt", encoding="utf-8", errors="replace"):
        if " send: " in ln:
            sends.append((ln[:8], ln.split(" send: ",1)[1].strip()))
    prev = {}
    seen_ev = set()
    for ln in open(p+"/states.jsonl", encoding="utf-8"):
        row = json.loads(ln); gs=row["msg"].get("game_state")
        if not gs or gs.get("seed") is None: continue
        s = gs["seed"]
        if s not in seedinfo: continue
        lastgold[s]=gs.get("gold")
        if gs.get("screen_type")=="EVENT":
            en = gs["screen_state"].get("event_name")
            if en!="Neow": seen_ev.add((s, gs.get("floor"), en))
        pv = prev.get(s)
        if pv and pv[1].get("screen_type")=="EVENT" and gs.get("gold") is not None and pv[1].get("gold") is not None and gs["gold"]<pv[1]["gold"]:
            g0=pv[1]; amt=g0["gold"]-gs["gold"]
            t0 = datetime.datetime.fromtimestamp(pv[0]).strftime("%H:%M:%S")
            t1 = datetime.datetime.fromtimestamp(row["t"]).strftime("%H:%M:%S")
            cmds=[c for (t,c) in sends if t0<=t<=t1 and c.startswith("choose")]
            opt="?"
            if len(cmds)>=1:
                k=int(cmds[-1].split()[1]) if cmds[-1].split()[1].isdigit() else None
                for o in g0["screen_state"].get("options",[]):
                    if o.get("choice_index")==k: opt=o.get("text")[:60]
            loss[(seedinfo[s][1], g0["screen_state"].get("event_name"), opt)].append((seedinfo[s][0], amt, len(cmds), g0.get("floor")))
        prev[s]=(row["t"], gs)
    for k in seen_ev: met[seedinfo[k[0]][1]]+=1
for s,g in lastgold.items(): endgold[seedinfo[s][1]]+=g or 0
tot=collections.Counter()
for k,v in sorted(loss.items(), key=lambda kv:(kv[0][0], -sum(a for _,a,_,_ in kv[1]))):
    tot[k[0]]+=sum(a for _,a,_,_ in v)
    print(k, sum(a for _,a,_,_ in v), v)
print("total",tot,"met",met,"endgold",endgold)
