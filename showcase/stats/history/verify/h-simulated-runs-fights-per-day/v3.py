import json,glob,os,datetime,collections
R=''
tz=datetime.timezone(datetime.timedelta(hours=0))
c=collections.Counter();nf=collections.Counter()
def games(o):
    if isinstance(o,dict):
        t=o.get('games',0) if isinstance(o.get('games'),int) else 0
        return t+sum(games(v) for k,v in o.items() if k!='games')
    if isinstance(o,list): return sum(games(v) for v in o)
    return 0
for f in glob.glob(R+'runs/*/bench.json'):
    md=datetime.datetime.fromtimestamp(os.path.getmtime(f),tz).strftime('%m-%d')
    try: c[md]+=games(json.load(open(f)));nf[md]+=1
    except Exception: pass
print(sorted(c.items()));print(sorted(nf.items()))
