import json,re,collections
rows=json.load(open('gauntlet_rows.json'))
keys=collections.Counter(r[5] for r in rows); main=keys.most_common(1)[0][0]
g=collections.defaultdict(list)
for t,b,f,n,c,k,pl in rows:
    if k!=main or n!=500: continue
    m=re.search(r'-s(\d+)(?=[-.])',f)
    if not m: continue
    rec=re.sub(r'^\d{4}-\d\d-\d\d-','',f[:m.start()])+'|'+re.sub(r'-[0-9a-f]{7}(?=[-.])','',f[m.end():])
    g[rec].append((m.group(1),c,t,pl))
out=[]
for rec,v in g.items():
    ss={}
    for s,c,t,pl in v: ss.setdefault(s,(c,t))
    if len(ss)>=2:
        cs=[x[0] for x in ss.values()]
        out.append((max(cs)-min(cs),rec,len(ss),min(cs),max(cs),min(x[1] for x in ss.values())))
out.sort(reverse=True)
for o in out: print('%.3f'%o[0],o[1:])
print(len(out))
