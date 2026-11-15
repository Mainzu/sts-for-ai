import json,glob,datetime as dt,collections
fs=sorted(glob.glob('jobs/done/*.json'))
P=[(3,'10-29','10-31'),(4,'11-01','11-02'),(5,'11-03','11-05'),(6,'11-06','11-09'),(7,'11-10','11-12'),(8,'11-13','11-14')]
def per(d):
    k=d.strftime('%m-%d')
    for p,a,b in P:
        if a<=k<=b: return p
th=collections.defaultdict(float); n=0; tot=0; st=collections.Counter(); first=None; last=None; ids=set()
for f in fs:
    j=json.load(open(f))
    st[j.get('status')]+=1
    if not j.get('started') or not j.get('ended'): continue
    s=dt.datetime.fromisoformat(j['started']); e=dt.datetime.fromisoformat(j['ended'])
    if e<=s: continue
    n+=1; ids.add(j['id']); t=j.get('threads',1)
    first=min(first or s,s); last=max(last or e,e)
    c=s
    while c<e:
        nx=min(e,c.replace(minute=0,second=0,microsecond=0)+dt.timedelta(hours=1))
        h=(nx-c).total_seconds()/3600*t
        th[(per(c),c.hour)]+=h; tot+=h; c=nx
print(st,n,len(ids),round(tot),first,last)
night=sum(v for (p,h),v in th.items() if h<8); print('night',night/tot)
# hours existing
cnt=collections.Counter(); c=first.replace(minute=0,second=0)
while c<last: cnt[(per(c),c.hour)]+=1; c+=dt.timedelta(hours=1)
allh=collections.Counter(); allc=collections.Counter()
for (p,h),v in th.items(): allh[h]+=v
for (p,h),v in cnt.items(): allc[h]+=v
print({h:round(allh[h]/allc[h],1) for h in range(24)})
for p,_,_ in P: print(p,[round(th[(p,h)]/cnt[(p,h)],1) if cnt[(p,h)] else None for h in range(24)])
