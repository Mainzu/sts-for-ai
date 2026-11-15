import json,os,glob,collections,datetime
R=''
ds={}
for p in glob.glob(R+'datasets/*/manifest.json'):
    m=json.load(open(p)); i=p.split(os.sep)[-2] if os.sep in p else p.split('/')[-2]
    i=os.path.basename(os.path.dirname(p))
    ds[i]=(m.get('n_games',0),m.get('parent_model'),m.get('config',{}).get('round'),os.path.getmtime(p))
print('datasets',len(ds),'games',sum(v[0] for v in ds.values()))
first={}
for rj in glob.glob(R+'runs/*/run.json'):
    r=json.load(open(rj)); c=r.get('created')
    if not c: continue
    for d in r.get('datasets',[]) or []:
        if d not in first or c<first[d]: first[d]=c
print('unused',[ (k,v[0]) for k,v in ds.items() if k not in first])
day=collections.Counter(); bad=0
for k,v in ds.items():
    if k in first:
        day[first[k][5:10]]+=v[0]
        mt=datetime.datetime.fromtimestamp(v[3]).isoformat()
        if mt>first[k]: bad+=1
    else: day['unused']+=v[0]
for k in sorted(day): print(k,day[k])
print('mtime after first use',bad)
heur=sum(v[0] for v in ds.values() if not v[1]); print('no parent',heur, heur/sum(v[0] for v in ds.values()))
print('parent',sum(v[0] for v in ds.values() if v[1]))
rc=collections.Counter((v[2],bool(v[1])) for v in ds.values()); print(rc)
# dup by games_sha
sh=collections.Counter(json.load(open(R+'datasets/'+k+'/manifest.json')).get('games_sha256') for k in ds)
print('dup sha',[(s,c) for s,c in sh.items() if c>1][:5])
P={1:('10-23','10-24'),2:('10-25','10-28'),3:('10-29','10-31'),4:('11-01','11-02'),5:('11-03','11-05'),6:('11-06','11-09'),7:('11-10','11-12'),8:('11-13','11-14')}
for p,(a,b) in P.items(): print(p,sum(n for d,n in day.items() if a<=d<=b))
