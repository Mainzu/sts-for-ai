import sys,collections
sys.path.insert(0,r"scripts")
import os; os.chdir(r".")
import real_game_report as R
runs=R.all_runs()
print("runs",len(runs))
tot=collections.Counter(); fl=collections.Counter(); ex=collections.defaultdict(list)
grp=collections.Counter(); grpf=collections.Counter(); oneturn=[]
for i,r in enumerate(runs,1):
    a=R.asc(r); key="A20" if a==20 else "A0" if a==0 else a
    for f in r["fights"]:
        if f["floor"]>16: continue
        if not f["won"] or f.get("handed_over"): continue
        enc=" + ".join(sorted(f["monsters"]))
        flaw=f["hp_end"]>=f["hp_start"]
        if f["decisions"]<=1 or f["group"]!="hallway" and f["decisions"]<3: oneturn.append((i,f["floor"],f["group"],enc,f["decisions"],flaw))
        tot[(key,f["group"],enc)]+=1; grp[(key,f["group"])]+=1
        if flaw: fl[(key,f["group"],enc)]+=1; grpf[(key,f["group"])]+=1; ex[(key,f["group"],enc)].append((i,f["floor"],f["decisions"]))
for k in sorted(grp): print(k,grp[k],grpf[k])
for k in sorted(tot,key=lambda k:(k[0],k[1],-tot[k])): print(k,fl[k],"/",tot[k],ex[k] if k[1]!="hallway" else "")
print(oneturn)
print([(i,R.asc(r),r.get("run_rules"),r.get("fight_guard")) for i,r in enumerate(runs,1) if i in (1,27,28,54,58,65,90)])
