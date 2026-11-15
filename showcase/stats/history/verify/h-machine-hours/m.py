import json,glob,datetime as dt,collections
day=collections.Counter();night=collections.Counter()
for f in glob.glob('jobs/done/*.json'):
    j=json.load(open(f))
    if not j.get('started') or not j.get('ended'): continue
    s=dt.datetime.fromisoformat(j['started']); e=dt.datetime.fromisoformat(j['ended'])
    if not ('11-03'<=s.strftime('%m-%d')<='11-05'): continue
    kind='mut' if 'mutat' in ' '.join(map(str,j['cmd'])).lower()+j['id'] else 'other'
    c=s
    while c<e:
        nx=min(e,c.replace(minute=0,second=0,microsecond=0)+dt.timedelta(hours=1))
        h=(nx-c).total_seconds()/3600*j.get('threads',1)
        (night if c.hour>=22 or c.hour<5 else day)[kind]+=h; c=nx
print(day,night)
