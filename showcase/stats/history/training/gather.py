import json,os,datetime as dt,csv,gzip
R=''
P=[('10-23','10-24'),('10-25','10-28'),('10-29','10-31'),('11-01','11-02'),('11-03','11-05'),('11-06','11-09'),('11-10','11-12'),('11-13','11-14')]
def period(md):
    for i,(a,b) in enumerate(P):
        if a<=md<=b: return i+1
TZ=dt.timezone(dt.timedelta(hours=0))
def parse(s):
    t=dt.datetime.fromisoformat(s)
    if t.tzinfo is None: t=t.replace(tzinfo=TZ)
    return t.astimezone(TZ)
runs=[]
for d in sorted(os.listdir(R+'runs')):
    p=R+'runs/'+d
    if not d.startswith('2026') or not os.path.isfile(p+'/run.json'): continue
    rj=json.load(open(p+'/run.json')); cfg=json.load(open(p+'/config.json'))
    c=parse(rj['created']); m=None
    if os.path.exists(p+'/model.pt'):
        m=dt.datetime.fromtimestamp(os.path.getmtime(p+'/model.pt'),TZ)
    rd=json.load(open(p+'/round.json')) if os.path.exists(p+'/round.json') else {}
    cur=json.load(open(p+'/curves.json')) if os.path.exists(p+'/curves.json') else {}
    runs.append(dict(run=d,created=c.isoformat(),md=c.strftime('%m-%d'),period=period(c.strftime('%m-%d')),model=m is not None,
      hours=((m-c).total_seconds()/3600 if m else None),n_train=cfg.get('n_train'),games=cfg.get('games'),rounds=(cfg.get('rounds') or {}).get('n'),
      lr=cfg.get('lr'),name=cfg.get('name'),parent_run=rd.get('parent_run'),parent=(rj.get('parent') or {}).get('path'),
      new_dataset=rd.get('new_dataset'),datasets=rj.get('datasets'),epochs=len(cur.get('train',[])),round=rd.get('round'),
      packs=cfg.get('packs'),content=cfg.get('content'),source=cfg.get('source')))
ds=[]
for d in sorted(os.listdir(R+'datasets')):
    p=R+'datasets/'+d
    try: mf=json.load(open(p+'/manifest.json'))
    except Exception: continue
    g=p+'/games.jsonl.gz'
    sz=os.path.getsize(g) if os.path.exists(g) else 0
    t=dt.datetime.fromtimestamp(os.path.getmtime(p+'/manifest.json'),TZ)
    ds.append(dict(id=d,n_games=mf['n_games'],bytes=sz,md=t.strftime('%m-%d'),period=period(t.strftime('%m-%d')),parent=mf.get('parent_model'),cfg=mf['config']))
json.dump(dict(runs=runs,ds=ds),open('gathered.json','w'),indent=0,default=str)
print(len(runs),len(ds))
