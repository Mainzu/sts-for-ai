import json,glob,collections,os
R='docs/claims'
fs=glob.glob(R+'/**/*.json',recursive=True)
c=collections.Counter(); keys=set(); revs=[]; created=collections.Counter(); hl=[]
for f in fs:
    d=json.load(open(f,encoding='utf-8'))
    area=os.path.relpath(f,R).split(os.sep)[0]
    c[(area,d['status'])]+=1; keys.add(d['key'])
    revs.append((d.get('rev'),d['key'],len(d.get('history',[]))))
    h=d.get('history') or []
    first=(h[0].get('at') if h and isinstance(h[0],dict) else None) or d['at']
    created[first[5:10]]+=1
print(len(fs),len(keys))
for k in sorted(c): print(k,c[k])
print(collections.Counter(s for (_,s),n in c.items() for _ in range(n)))
print(sorted(revs,reverse=True)[:3])
print(sorted(created.items()))
