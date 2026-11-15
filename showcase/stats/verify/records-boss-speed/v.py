import sys, json, os, statistics as S
R="."
sys.path.insert(0,R+"/scripts")
import real_game_report as g
runs=g.all_runs(R+"/results/real-game")
print(len(runs))
# max combat turn per (seed, floor 16), streamed
turns={}
for folder in sorted({r["folder"] for r in runs}):
    with open(os.path.join(R,"results/real-game",folder,"states.jsonl"),encoding="utf-8") as f:
        for line in f:
            if '"combat_state"' not in line: continue
            gs=json.loads(line)["msg"].get("game_state") or {}
            if gs.get("floor")!=16 or "combat_state" not in gs: continue
            t=gs["combat_state"].get("turn")
            if t is None: continue
            k=gs["seed"]; turns[k]=max(turns.get(k,0),t)
tab={}
for i,r in enumerate(runs,1):
    for f in r["fights"]:
        if f["group"]!="boss": continue
        a=g.asc(r); b=f["monsters"][0]
        tab.setdefault((a,b),[]).append((i,f["won"],turns.get(r["seed"]),f["hp_start"],f["hp_end"],f.get("handed_over"),g.setting_tag(r)))
for k in sorted(tab):
    v=tab[k]; w=[x for x in v if x[1]]
    wt=[x[2] for x in w]
    print(k,"fights",len(v),"won",len(w),"min",min(wt) if wt else None,"median",S.median(wt) if wt else None,"fastest runs",[x[0] for x in w if x[2]==min(wt)] if wt else None)
    for x in v: print("   ",x)
print("A20 total",sum(len(v) for k,v in tab.items() if k[0]==20),"won",sum(x[1] for k,v in tab.items() if k[0]==20 for x in v))
print("A0 total",sum(len(v) for k,v in tab.items() if k[0]==0),"won",sum(x[1] for k,v in tab.items() if k[0]==0 for x in v))
