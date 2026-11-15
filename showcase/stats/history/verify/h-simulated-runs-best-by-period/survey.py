import json,glob,os,collections
R='results/gauntlet/'
keys=collections.Counter(); vals=collections.defaultdict(collections.Counter)
for f in glob.glob(R+'*.json'):
    try: d=json.load(open(f))
    except Exception as e: print('bad',f,e); continue
    s=d.get('settings',{})
    for k,v in s.items():
        keys[k]+=1
        if k!='player': vals[k][json.dumps(v)[:80]]+=1
    seq=d.get('sequences',[])
    vals['_n'][len(seq)]+=1
    if seq: vals['_seqkeys'][','.join(sorted(seq[0]))]+=1
print(keys)
for k,c in vals.items(): print(k, c.most_common(12))
