import json,glob,os,re,collections,datetime as dt
P=[(1,'10-23','10-24'),(2,'10-25','10-28'),(3,'10-29','10-31'),(4,'11-01','11-02'),(5,'11-03','11-05'),(6,'11-06','11-09'),(7,'11-10','11-12'),(8,'11-13','11-14')]
def per(md):
    for p,a,b in P:
        if a<=md<=b: return p
jobs=[json.load(open(f)) for f in sorted(glob.glob('jobs/done/*.json'))]
ids=[j['id'] for j in jobs]; print('n',len(jobs),'unique ids',len(set(ids)))
pc=collections.Counter(); started=collections.Counter(); th=collections.Counter()
names=collections.Counter(); kp=collections.defaultdict(collections.Counter)
statuses=collections.Counter(j.get('status') for j in jobs)
print(statuses)
for j in jobs:
    t=j.get('started') or j['added']
    assert t[-6] in '+-',t
    p=per(t[5:10]); pc[p]+=1
    name=re.sub(r'^\d+-','',j['id'])
    names[name.split('-')[0]]+=1
    kp[name.split('-')[0]][p]+=1
    if j.get('started'):
        started[p]+=1
        if j.get('ended'):
            d=(dt.datetime.fromisoformat(j['ended'])-dt.datetime.fromisoformat(j['started'])).total_seconds()/3600
            th[p]+=d*j.get('threads',1)
print(sorted(pc.items())); print(sorted(started.items())); print({k:round(v) for k,v in sorted(th.items())})
for k,c in names.most_common(60): print(k,c,dict(sorted(kp[k].items())))
print(min(j['added'] for j in jobs))
