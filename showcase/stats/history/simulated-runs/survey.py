import json,os,glob,collections,datetime
R='results/gauntlet'
fk=collections.Counter(); sk=collections.Counter(); seqk=collections.Counter(); topk=collections.Counter()
rows=[]
for f in sorted(glob.glob(R+'/*.json')):
    m=datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime('%m-%d %H:%M')
    try: d=json.load(open(f))
    except Exception as e: print('ERR',f,e); continue
    if not isinstance(d,dict) or 'sequences' not in d: print('ODD',os.path.basename(f), type(d), list(d)[:10] if isinstance(d,dict) else ''); continue
    topk.update(d.keys()); sk.update(d['settings'].keys())
    for s in d['sequences'][:50]:
        seqk.update(s.keys())
        for fl in s['floors']: fk.update(fl.keys())
    rows.append((m,os.path.basename(f),len(d['sequences'])))
print(topk); print(sk); print(seqk); print(fk)
c=collections.Counter(r[0][:5] for r in rows); print(sorted(c.items()))
print(collections.Counter(r[2] for r in rows))
