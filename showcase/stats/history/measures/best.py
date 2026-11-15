import json,os,collections
R='results/gauntlet'
rows=json.load(open('gauntlet_rows.json'))
keys=collections.Counter(r[5] for r in rows); main=keys.most_common(1)[0][0]
P=[('10-23','10-24'),('10-25','10-28'),('10-29','10-31'),('11-01','11-02'),('11-03','11-05'),('11-06','11-09'),('11-10','11-12'),('11-13','11-14')]
per=lambda d:[i+1 for i,(a,b) in enumerate(P) if a<=d[:5]<=b][0]
by=collections.defaultdict(lambda:collections.defaultdict(list))
for t,b,f,n,c,k,pl in rows:
    if k!=main or n!=500: continue
    i0=json.load(open(os.path.join(R,f)))['sequences'][0]['i']
    blk='A' if i0==0 else 'B'
    by[blk][per(t)].append((c,f,t,pl))
for blk in 'AB':
    run=0
    for p in sorted(by[blk]):
        v=sorted(by[blk][p],reverse=True); run=max(run,v[0][0])
        h=[x for x in v if x[3]=='heuristic']
        print(blk,'P%d'%p,'n=%d'%len(v),'best %.3f'%v[0][0],v[0][1],v[0][2],'running %.3f'%run,'| median %.3f'%v[len(v)//2][0], 'heur',[x[0] for x in h])
