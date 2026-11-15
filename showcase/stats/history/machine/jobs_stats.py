import json,glob,collections,statistics as S
from datetime import datetime,timedelta
R='jobs/done/'
P=[(1,'10-23','10-24'),(2,'10-25','10-28'),(3,'10-29','10-31'),(4,'11-01','11-02'),(5,'11-03','11-05'),(6,'11-06','11-09'),(7,'11-10','11-12'),(8,'11-13','11-14')]
def per(d):
    md=d.strftime('%m-%d')
    for p,a,b in P:
        if a<=md<=b: return p
def T(s): return datetime.fromisoformat(s).replace(tzinfo=None) if s else None
def kind(i):
    k=i.split('-',1)[1]
    for pre,lab in [('gauntlet','gauntlet'),('finetune','finetune'),('family','family'),('mutate','mutate'),('learn','learn (training)'),('ladder','ladder'),('boss','boss'),('test','tests'),('depth','depth'),('gen','gen/pack'),('pack','gen/pack'),('series','bench')]:
        if k.startswith(pre): return lab
    return 'other'
J=[json.load(open(f,encoding='utf-8')) for f in sorted(glob.glob(R+'*.json'))]
for j in J:
    j['k']=kind(j['id']);j['a']=T(j['added']);j['s']=T(j.get('started'));j['e']=T(j.get('ended'))
    j['p']=per(j['s'] or j['a'])
mode=__import__('sys').argv[1]
if mode=='perkind':
    c=collections.Counter((j['p'],j['k']) for j in J)
    ks=[k for k,_ in collections.Counter(j['k'] for j in J).most_common()]
    for k in ks: print(k,[c[(p,k)] for p in range(3,9)])
    print('tot',collections.Counter(j['p'] for j in J))
if mode=='longest':
    r=[(j['e']-j['s'],j['id'],j['status'],j['threads'],j['estimate_min'],j['note'][:150]) for j in J if j['s'] and j['e']]
    r.sort(reverse=True)
    for x in r[:8]: print(x[0],x[1:])
    print('n',len(r),'total h',sum((x[0].total_seconds() for x in r))/3600,'thread-h',sum((j['e']-j['s']).total_seconds()*j['threads'] for j in J if j['s'] and j['e'])/3600)
if mode=='status':
    for st in ['cancelled','failed','killed','lost','ended-unknown']:
        print('==',st)
        for j in J:
            if j['status']==st: print(j['id'],j['p'],'| r:',j.get('reason') or j.get('verdict_reason') or '', '| started' if j['s'] else '| never started','| note:',j['note'][:90])
if mode=='est':
    d=collections.defaultdict(list)
    for j in J:
        if j['status']=='ok' and j['s'] and j['e'] and j['estimate_min']:
            act=(j['e']-j['s']).total_seconds()/60
            d[j['k']].append((act/j['estimate_min'],act,j['estimate_min']))
    for k,v in sorted(d.items(),key=lambda x:-len(x[1])):
        rs=sorted(x[0] for x in v);print(k,len(v),'median ratio %.2f'%S.median(rs),'IQR %.2f-%.2f'%(rs[len(rs)//4],rs[3*len(rs)//4]),'median est %.0f act %.1f'%(S.median(x[2] for x in v),S.median(x[1] for x in v)),'over2x',sum(r>2 for r in rs),'under0.5',sum(r<0.5 for r in rs))
    # per period overall
    for p in range(3,9):
        rs=[(j['e']-j['s']).total_seconds()/60/j['estimate_min'] for j in J if j['p']==p and j['status']=='ok' and j['s'] and j['e'] and j['estimate_min']]
        print('P',p,len(rs),'%.2f'%S.median(rs))
if mode=='wait':
    for p in range(3,9):
        w=[(j['s']-j['a']).total_seconds()/60 for j in J if j['p']==p and j['s']]
        w.sort();print(p,len(w),'median %.1f p90 %.0f max %.0f'%(S.median(w),w[int(.9*len(w))],w[-1]))
    w=sorted(((j['s']-j['a']).total_seconds()/3600,j['id'],j.get('after'),j['note'][:80]) for j in J if j['s']);print(w[-5:])
if mode=='hour':
    # running thread-minutes by hour of day and period
    g=collections.defaultdict(float)
    for j in J:
        if not(j['s'] and j['e']): continue
        t=j['s']
        while t<j['e']:
            nx=min(j['e'],(t+timedelta(hours=1)).replace(minute=0,second=0,microsecond=0))
            g[(per(t),t.hour)]+=(nx-t).total_seconds()/3600*j['threads']
            t=nx
    for p in range(3,9):
        print(p,[round(g[(p,h)]) for h in range(24)])
    tot=[sum(g[(p,h)] for p in range(3,9)) for h in range(24)];print('all',[round(x) for x in tot])
    night=sum(tot[h] for h in range(0,8));print('night 00-08 share %.3f'%(night/sum(tot)))
    # starts by hour
    sc=collections.Counter(j['s'].hour for j in J if j['s']);print('starts',[sc[h] for h in range(24)])
    ac=collections.Counter(j['a'].hour for j in J);print('added',[ac[h] for h in range(24)])
