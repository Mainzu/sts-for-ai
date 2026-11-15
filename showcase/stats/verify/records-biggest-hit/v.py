import sys, json, os
ROOT="."
sys.path.insert(0, ROOT+"/scripts")
import real_game_report as R
runs=R.all_runs()
print("runs",len(runs))
idx={}
for i,r in enumerate(runs,1):
    idx[(r["folder"],r["seed"])]=(i,r)
nf={0:0,20:0}
for i,r in enumerate(runs,1):
    nf[r["ascension"]]+=sum(1 for f in r["fights"] if f["floor"]<=16)
print("fights",nf)
hits=[]
for folder in sorted({r["folder"] for r in runs}):
    cur=None  # (seed,floor,turn)
    last={}
    with open(os.path.join(R.RECORDS,folder,"states.jsonl"),encoding="utf-8") as fh:
        for line in fh:
            if '"combat_state"' not in line: continue
            gs=json.loads(line)["msg"].get("game_state") or {}
            cs=gs.get("combat_state")
            if not cs: continue
            key=(gs["seed"],gs["floor"])
            t=cs["turn"]; hp=cs["player"]["current_hp"]
            mons=[(m["name"],m.get("intent"),m.get("move_adjusted_damage"),m.get("move_hits")) for m in cs["monsters"] if not m.get("is_gone")]
            p=last.get(key)
            if p and t==p["turn"]+1:
                hits.append((p["hp"]-hp, folder, key, p["turn"], p["mons"]))
            if p is None or t!=p["turn"] or True:
                last[key]={"turn":t,"hp":hp,"mons":mons} if (p is None or t!=p["turn"]) else dict(p,hp=hp,mons=mons)
out=[]
for d,folder,(seed,floor),turn,mons in hits:
    if (folder,seed) not in idx: continue
    i,r=idx[(folder,seed)]
    if floor>16: continue
    out.append((r["ascension"],d,i,floor,turn,mons, [f["won"] for f in r["fights"] if f["floor"]==floor]))
for a in (20,0):
    s=sorted([o for o in out if o[0]==a],key=lambda o:-o[1])[:12]
    print("A",a)
    for o in s: print(o[1],"run",o[2],"F",o[3],"turn",o[4],"->",o[4]+1,o[6],o[5])
