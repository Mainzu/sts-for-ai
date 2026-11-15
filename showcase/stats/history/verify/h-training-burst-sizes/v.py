import json,glob,os,collections
R='runs'
rows=[]
for d in sorted(glob.glob(R+'/*')):
    try: run=json.load(open(d+'/run.json'))
    except Exception: continue
    c=run.get('created','')
    if not ('2026-11-06'<=c[:10]<='2026-11-09'): continue
    try: cfg=json.load(open(d+'/config.json'))
    except Exception: cfg={}
    rows.append((os.path.basename(d),c,cfg,run))
print(len(rows))
kc=collections.Counter()
for n,c,cfg,run in rows: kc.update(cfg.keys())
print(kc.most_common(80))
print(collections.Counter(k for n,c,cfg,run in rows for k in run))
for n,c,cfg,run in rows[:200]:
    print(n,c[:16],cfg.get('mode'),cfg.get('games'),cfg.get('pool'),cfg.get('source'),run.get('parent'),cfg.get('n_train'))
