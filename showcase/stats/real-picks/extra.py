"""Extra real-game pick stats: argmax check, lopsided/close rewards, slowest rewards, clear rate by deck card."""
import sys, os, json
from collections import Counter, defaultdict
R = "."
sys.path.insert(0, R + "/scripts")
import real_game_report as g
def nm(x): return None if x is None else x.replace("gen:", "")
runs = g.all_runs(); runs.sort(key=lambda r: r["t0"])
for i, r in enumerate(runs, 1): r["n"] = i; r["rewards"] = []
byf = defaultdict(list)
for r in runs: byf[r["folder"]].append(r)
for f, rs in byf.items():
    rs.sort(key=lambda r: r["t0"]); k=-1; prev=None
    for line in open(os.path.join(g.RECORDS, f, "decisions.jsonl"), encoding="utf-8"):
        d = json.loads(line)
        if prev is None or d["floor"] < prev: k += 1
        prev = d["floor"]
        if "card_reward" in d: d["run"]=rs[k]["n"]; rs[k]["rewards"].append(d)
for A in (0,20):
    rs=[r for r in runs if (r.get("ascension") or 0)==A]
    print("=== A%d" % A)
    am=0; tot=0; gaps=[]
    for r in rs:
        for d in r["rewards"]:
            tot+=1; sc=d["scores"]; opts=[nm(o) for o in d["options"]]
            best=max(range(len(sc)),key=lambda i:sc[i])
            am += opts[best]==nm(d["pick"])
            s=sorted(sc,reverse=True); gaps.append((s[0]-s[1], d["run"], d["floor"], opts, [round(x,2) for x in sc], nm(d["pick"]), d.get("seconds")))
    print("pick==argmax", am, tot)
    gaps.sort(key=lambda x: x[0])
    print("closest:"); [print(" ",x) for x in gaps[:4]]
    print("most lopsided:"); [print(" ",x) for x in gaps[-5:]]
    sl=sorted(((d.get("seconds",0), d["run"], d["floor"], d["card_reward"], nm(d["pick"])) for r in rs for d in r["rewards"]),reverse=True)
    print("slowest:", sl[:5])
    secs=sorted(x[0] for x in sl); print("median secs", secs[len(secs)//2], "n", len(secs))
    # endings
    print("endings", Counter(g.ending(r)[:40] for r in rs).most_common(8))
