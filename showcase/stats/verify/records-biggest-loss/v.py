import sys, os, json
ROOT="."
sys.path.insert(0, ROOT+"/scripts")
import real_game_report as R
REC=ROOT+"/results/real-game"
runs=R.all_runs(REC)
print("runs",len(runs))
# turns per (seed,floor) from states
turns={}
for name in sorted(os.listdir(REC)):
    p=os.path.join(REC,name,"states.jsonl")
    if not os.path.isfile(p): continue
    with open(p,encoding="utf-8") as f:
        for ln in f:
            if '"combat_state"' not in ln: continue
            gs=json.loads(ln)["msg"].get("game_state") or {}
            cs=gs.get("combat_state")
            if not cs: continue
            k=(gs.get("seed"),gs.get("floor"))
            t=cs.get("turn")
            if t is not None: turns[k]=max(turns.get(k,0),t)
rows={0:[],20:[]}; cnt={0:0,20:0}; ho={0:0,20:0}
for i,r in enumerate(runs,1):
    a=r.get("ascension") or 0
    for f in r["fights"]:
        if f["floor"]>16 or not f["won"]: continue
        if f.get("handed_over") is not None: ho[a]+=1; continue
        cnt[a]+=1
        rows[a].append((f["hp_start"]-f["hp_end"],i,f["floor"],f["monsters"],f["hp_start"],f["hp_end"],turns.get((r["seed"],f["floor"])),f.get("group"),r["run_rules"],r["fight_guard"]))
print(cnt, "handed over won",ho)
for a in (20,0):
    for x in sorted(rows[a],reverse=True)[:9]: print(a,x)
print([ (i+1,r.get('ascension'),r['folder']) for i,r in enumerate(runs) if i+1 in (1,27,28,90)])
