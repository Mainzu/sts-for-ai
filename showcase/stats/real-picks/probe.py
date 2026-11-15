import sys, os, json
R="."
sys.path.insert(0, R+"/scripts")
import real_game_report as g
runs = g.all_runs()
print(len(runs))
from collections import Counter
byf = Counter(r["folder"] for r in runs)
bad=0
for f,n in sorted(byf.items()):
    p=os.path.join(g.RECORDS,f,"decisions.jsonl")
    k=0; prev=None; cr=0
    for line in open(p,encoding="utf-8"):
        d=json.loads(line)
        if prev is None or d["floor"]<prev: k+=1
        prev=d["floor"]
        if "card_reward" in d: cr+=1
    if k!=n: bad+=1; print(f,n,k,cr)
print("bad",bad)
