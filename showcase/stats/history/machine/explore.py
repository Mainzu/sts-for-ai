import json,glob,collections,os,sys
R='jobs/'
keys=collections.Counter();st=collections.Counter();kinds=collections.Counter()
for f in glob.glob(R+'done/*.json'):
    j=json.load(open(f,encoding='utf-8'));keys.update(j.keys());st[j.get('status')]+=1
    kinds[j['id'].split('-',1)[1] if '-' in j['id'] else j['id']]+=1
print(keys);print(st);print(kinds.most_common(60))
for d in ['pending','parked']:
    print(d,len(os.listdir(R+d)))
