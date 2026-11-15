import json,glob,os,collections
R='runs/'
c=collections.defaultdict(collections.Counter)
for d in sorted(glob.glob(R+'*-r0-*')):
    try: cf=json.load(open(d+'/config.json'))
    except Exception: continue
    c[os.path.basename(d)[:10]][cf.get('n_train')]+=1
for k in sorted(c): print(k,dict(c[k]))
