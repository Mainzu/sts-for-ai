import json,os,collections,sys
R=''
c=collections.Counter(); rk=collections.Counter(); files=collections.Counter(); mk=collections.Counter()
for d in os.listdir(R+'runs'):
    p=R+'runs/'+d
    if not os.path.isdir(p) or not d.startswith('2026'): continue
    for f in os.listdir(p): files[f]+=1
    try: cfg=json.load(open(p+'/config.json'))
    except Exception: continue
    for k,v in cfg.items(): c[k]+=1
    if os.path.exists(p+'/round.json'):
        for k in json.load(open(p+'/round.json')): rk[k]+=1
for d in os.listdir(R+'datasets'):
    try:
        for k in json.load(open(R+'datasets/'+d+'/manifest.json')): mk[k]+=1
    except Exception as e: mk['ERR']+=1
print(files);print(c);print(rk);print(mk)
