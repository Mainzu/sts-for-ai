import json,glob,statistics as st
from datetime import datetime
P=[(1,'10-23','10-24'),(2,'10-25','10-28'),(3,'10-29','10-31'),(4,'11-01','11-02'),(5,'11-03','11-05'),(6,'11-06','11-09'),(7,'11-10','11-12'),(8,'11-13','11-14')]
def per(s):
    md=s[5:10]
    for p,a,b in P:
        if a<=md<=b: return p
by={};allw=[];ids=set();n=0;stat={}
for f in glob.glob('jobs/done/*.json'):
    d=json.load(open(f,encoding='utf-8'));n+=1
    stat[d.get('status')]=stat.get(d.get('status'),0)+1
    if not d.get('started') or not d.get('added'): continue
    assert d['started'][-6] in '+-' and d['added'][-6] in '+-', (d['started'],d['added'])
    w=(datetime.fromisoformat(d['started'])-datetime.fromisoformat(d['added'])).total_seconds()/60
    p=per(d['started']); by.setdefault(p,[]).append(w); allw.append((w,d['id'],d['added'],d['started'],d.get('after'),d.get('if_passed')))
    ids.add(d['id'])
print(n,len(allw),len(ids),stat)
def q(x,k):
    x=sorted(x); return st.quantiles(x,n=10,method='inclusive')[k-1]
for p in sorted(by):
    x=by[p];print(p,len(x),round(st.median(x),1),round(q(x,9),1),round(min(x),1),sum(1 for v in x if v>282)/len(x))
allw.sort(reverse=True)
for r in allw[:4]: print(r)
print(sum(1 for r in allw if r[4] or r[5]))
