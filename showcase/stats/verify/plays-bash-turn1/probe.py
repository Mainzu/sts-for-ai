import sys,os,json,collections
R="."
sys.path.insert(0,R+"/scripts")
import real_game_report as g
runs=g.all_runs()
print(len(runs))
for i,r in enumerate(runs,1):
    if i in (1,3,5,21,27,28,29,57,58,90): print(i,r['folder'],r.get('ascension'),r['run_rules'],r['fight_guard'],len(r['fights']))
# multiple decisions per turn?
c=collections.Counter()
for name in sorted(os.listdir(R+"/results/real-game")):
    p=R+"/results/real-game/"+name+"/decisions.jsonl"
    if not os.path.exists(p): continue
    prev=None;n=0
    with open(p,encoding="utf-8") as f:
        for l in f:
            d=json.loads(l)
            if 'turn' not in d: continue
            k=(d['floor'],d['turn'])
            if k==prev: n+=1
            else:
                if prev: c[n]+=1
                n=1
            prev=k
print(c)
