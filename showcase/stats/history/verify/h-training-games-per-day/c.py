import json,os,glob,collections,datetime as dt
R=''
first={}
for rj in glob.glob(R+'runs/*/run.json'):
    r=json.load(open(rj)); c=r.get('created')
    if not c: continue
    for d in r.get('datasets') or []: first[d]=min(first.get(d,'9'),c[5:10])
rows=[]
for p in glob.glob(R+'datasets/*/manifest.json'):
    k=os.path.basename(os.path.dirname(p))
    if k.endswith('.tmp'): continue
    m=json.load(open(p)); md=first.get(k, dt.datetime.fromtimestamp(os.path.getmtime(p)).strftime('%m-%d'))
    rows.append((md,k,m['n_games'],m.get('games_sha256'),m.get('parent_model')))
rows.sort(); seen=set(); day=collections.Counter(); tot=0; heur=0; net=0; nds=0
for md,k,n,s,par in rows:
    if s in seen: continue
    seen.add(s); day[md]+=n; tot+=n; nds+=1
    if par: net+=n
    else: heur+=n
print(nds,tot,heur,heur/tot,net)
for d in sorted(day): print(d,day[d])
P={1:('10-23','10-24'),2:('10-25','10-28'),3:('10-29','10-31'),4:('11-01','11-02'),5:('11-03','11-05'),6:('11-06','11-09'),7:('11-10','11-12'),8:('11-13','11-14')}
pp={p:sum(n for d,n in day.items() if a<=d<=b) for p,(a,b) in P.items()}; print(pp, day['10-31'], sum(pp[i] for i in (1,2,5,6,8)))
