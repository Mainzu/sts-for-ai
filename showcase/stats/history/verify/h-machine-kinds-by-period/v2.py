import json,glob,re,collections
P=[(3,'10-29','10-31'),(4,'11-01','11-02'),(5,'11-03','11-05'),(6,'11-06','11-09'),(7,'11-10','11-12'),(8,'11-13','11-14')]
def per(md):
    for p,a,b in P:
        if a<=md<=b: return p
jobs=[json.load(open(f)) for f in sorted(glob.glob('jobs/done/*.json'))]
for p in (3,4):
    print('== P',p)
    for j in jobs:
        t=j.get('started') or j['added']
        if per(t[5:10])==p: print(j['id'],'|',' '.join(j['cmd'])[:110])
