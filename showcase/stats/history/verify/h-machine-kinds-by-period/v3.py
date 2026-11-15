import json,glob,re,collections
P=[(3,'10-29','10-31'),(4,'11-01','11-02'),(5,'11-03','11-05'),(6,'11-06','11-09'),(7,'11-10','11-12'),(8,'11-13','11-14')]
def per(md):
    for p,a,b in P:
        if a<=md<=b: return p
K=[('gauntlet','gauntlet'),('finetune','finetune'),('family','family'),('mutate','mutate'),('learn','learn'),('ladder','ladder'),('gen','gen'),('pack','gen'),('depth','depth'),('boss','boss'),('test','test'),('series','bench'),('bench','bench')]
jobs=[json.load(open(f)) for f in sorted(glob.glob('jobs/done/*.json'))]
grid=collections.defaultdict(collections.Counter); ex=collections.defaultdict(list)
for j in jobs:
    t=j.get('started') or j['added']; p=per(t[5:10])
    name=re.sub(r'^[0-9a-z]*?\d[0-9a-z]*-','',j['id'],count=1)
    k='other'
    for kw,lab in K:
        if kw in name: k=lab;break
    grid[k][p]+=1; ex[(k,p)].append(j['id'])
for k in ['gauntlet','finetune','family','mutate','learn','ladder','gen','depth','boss','test','bench','other']:
    print(k,[grid[k][p] for p in range(3,9)],sum(grid[k].values()))
print(ex[('ladder',4)][:10]); print(ex[('other',4)]); print(ex[('gauntlet',4)][:5])
# burst 11-07 family
fam=sorted(j['added'] for j in jobs if 'family' in j['id'] and j['added'][5:10]=='11-07')
print(len(fam),fam[:3],fam[-3:])
