import json,glob,datetime as dt,collections
jobs=[json.load(open(f)) for f in sorted(glob.glob('jobs/done/*.json'))]
lad=collections.Counter((j.get('started') or j['added'])[5:10] for j in jobs if 'ladder.py' in ' '.join(j['cmd']))
print('ladder.py by day',sorted(lad.items()))
ts=sorted(dt.datetime.fromisoformat(j['added']) for j in jobs if j['added'][5:10]=='11-07')
best=(0,None)
for i,a in enumerate(ts):
    n=sum(1 for b in ts[i:] if (b-a).total_seconds()<=32*60)
    if n>best[0]: best=(n,a)
print('best 32min window 11-07',best)
w=[j for j in jobs if best[1]<=dt.datetime.fromisoformat(j['added'])<=best[1]+dt.timedelta(minutes=32)]
print(collections.Counter(j['id'].split('-')[1] for j in w), w[0]['added'], w[-1]['added'])
# family.py in cmd
fam=[j for j in jobs if any('family' in c for c in j['cmd'])]
print('family cmd jobs',len(fam))
