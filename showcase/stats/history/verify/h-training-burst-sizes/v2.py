import json,glob,os,collections,re
R='runs'
rows=[]
for d in sorted(glob.glob(R+'/*')):
    try: run=json.load(open(d+'/run.json'))
    except Exception: continue
    c=run.get('created','')
    if not ('2026-11-06'<=c[:10]<='2026-11-09'): continue
    cfg=json.load(open(d+'/config.json'))
    rows.append((os.path.basename(d),c,cfg,run))
g=collections.Counter(cfg.get('games') for n,c,cfg,run in rows)
print(sorted(g.items(),key=lambda x:(x[0] is None,x[0] or 0)))
fam=collections.Counter()
for n,c,cfg,run in rows:
    if 'games' not in cfg: continue
    fam[(re.sub(r'-s\d+.*|-[0-9a-f]{7}$','',n[11:]),cfg['games'],cfg.get('pool'),c[:10])]+=1
for k,v in sorted(fam.items()): print(v,k)
print(collections.Counter(str(run.get('parent'))[:60] for n,c,cfg,run in rows).most_common(10))
# exact dupes: same config minus seed
sig=collections.Counter(json.dumps({k:v for k,v in cfg.items() if k not in('name',)},sort_keys=True) for n,c,cfg,run in rows)
print('dupe configs',sum(v-1 for v in sig.values() if v>1))
grp=collections.defaultdict(list)
for n,c,cfg,run in rows:
    grp[json.dumps({k:v for k,v in cfg.items() if k not in('name',)},sort_keys=True)].append(n)
for k,v in grp.items():
    if len(v)>1: print(v)
for n,c,cfg,run in rows:
    if 'copy' in n: print(n, run.get('datasets'))
