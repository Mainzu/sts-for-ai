import json,os,statistics,collections,datetime,hashlib
R='.'
G=R+'/results/gauntlet'
SH=['easy','easy','easy','hard','hard','elite','hard','hard','elite','hard','boss']
P=[(1,'10-23','10-24'),(2,'10-25','10-28'),(3,'10-29','10-31'),(4,'11-01','11-02'),(5,'11-03','11-05'),(6,'11-06','11-09'),(7,'11-10','11-12'),(8,'11-13','11-14')]
tz=datetime.timezone(datetime.timedelta(hours=0))
def per(md):
    for p,a,b in P:
        if a<=md<=b: return p
rows=[]
for f in sorted(os.listdir(G)):
    if not f.endswith('.json'): continue
    fp=os.path.join(G,f)
    try: d=json.load(open(fp))
    except Exception: continue
    if not isinstance(d,dict) or 'settings' not in d: continue
    s=d['settings']
    if set(s)!={'player','two_turn','shape','rest','seed'}: continue
    if s['shape']!=SH or s['two_turn'] or s['rest']!=0.3 or s['seed']!=20261101: continue
    idx=sorted(q['i'] for q in d['sequences'])
    if idx!=list(range(500)): continue
    cr=sum(q['cleared'] for q in d['sequences'])/500
    md=datetime.datetime.fromtimestamp(os.path.getmtime(fp),tz).strftime('%m-%d %H:%M')
    sig=hashlib.md5(json.dumps([q['cleared'] for q in d['sequences']]+[[x['hp_end'] for x in q['floors']] for q in d['sequences']]).encode()).hexdigest()
    rows.append(dict(f=f,pl=s['player'].replace(R+'/',''),cr=cr,md=md,p=per(md[:5]),sig=sig))
print(len(rows))
def summ(rs,tag):
    by=collections.defaultdict(list)
    for r in rs: by[r['p']].append(r['cr'])
    print(tag,{p:(len(v),max(v),statistics.median(v)) for p,v in sorted(by.items(),key=lambda x:str(x[0]))})
summ(rows,'all')
# dedupe identical player
seen={};ded=[]
for r in sorted(rows,key=lambda r:r['md']):
    if r['pl'] in seen: continue
    seen[r['pl']]=1; ded.append(r)
summ(ded,'first read per player')
sc=collections.Counter(r['sig'] for r in rows)
print('identical-result files',sum(c-1 for c in sc.values()))
for r in rows:
    if sc[r['sig']]>1: print('  dup',r['f'],r['pl'],r['cr'],r['md'])
for r in sorted(rows,key=lambda r:r['md']):
    if r['p'] in (8,) or r['cr']>=0.66 or 'heur' in r['pl']: print(r['p'],r['md'],r['cr'],r['f'],r['pl'])
summ([r for r in rows if r['pl'].startswith('runs/2026-10-29') is False or True],'x')
