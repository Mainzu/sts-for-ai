import sys,collections
from datetime import timedelta
sys.argv=['x','none'];exec(open('jobs_stats.py').read())
g=collections.defaultdict(float)
st=[j for j in J if j['s'] and j['e']]
for j in st:
    t=j['s']
    while t<j['e']:
        nx=min(j['e'],(t+timedelta(hours=1)).replace(minute=0,second=0,microsecond=0))
        g[(per(t),t.hour)]+=(nx-t).total_seconds()/3600*j['threads'];t=nx
lo=min(j['s'] for j in st).replace(minute=0,second=0);hi=max(j['e'] for j in st)
cnt=collections.Counter();t=lo
while t<=hi: cnt[(per(t),t.hour)]+=1;t+=timedelta(hours=1)
print('span',lo,hi)
for p in range(3,9): print(p,[round(g[(p,h)]/cnt[(p,h)],1) if cnt[(p,h)] else 0 for h in range(24)])
tot=sum(g.values());n=sum(g[k] for k in g if k[1]<8);print('night share',n/tot)
day=[sum(g[(p,h)] for p in range(3,9))/sum(cnt[(p,h)] for p in range(3,9)) for h in range(24)];print([round(x,1) for x in day])
