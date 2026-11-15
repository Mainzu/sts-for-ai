import json,os,collections,hashlib
R='runs'
P=[(1,'10-23','10-24'),(2,'10-25','10-28'),(3,'10-29','10-31'),(4,'11-01','11-02'),(5,'11-03','11-05'),(6,'11-06','11-09'),(7,'11-10','11-12'),(8,'11-13','11-14')]
def per(md):
    for p,a,b in P:
        if a<=md<=b: return p
cnt=collections.Counter(); keys=collections.Counter(); nomodel=[]; mism=0; hashes=collections.Counter(); tot=0
others=[d for d in os.listdir(R) if not d.startswith('2026-')]
for d in sorted(os.listdir(R)):
    if not d.startswith('2026-'): continue
    p=os.path.join(R,d)
    if not os.path.exists(os.path.join(p,'model.pt')): nomodel.append(d); continue
    rj=json.load(open(os.path.join(p,'run.json')))
    c=json.load(open(os.path.join(p,'config.json'))) if os.path.exists(os.path.join(p,'config.json')) else {}
    cr=rj.get('created','')
    if cr[5:10]!=d[5:10]: mism+=1
    ks=set(c)
    if 'n_train' in ks and 'rounds' in ks: kind='scratch'
    elif any(k in ks for k in ('parent','init','games','from')): kind='ft'
    else: kind='other:'+','.join(sorted(ks))
    pr=per(cr[5:10]); cnt[(pr,kind)]+=1; tot+=1
    hashes[hashlib.md5(open(os.path.join(p,'model.pt'),'rb').read()).hexdigest()]+=1
print('tot',tot,'nomodel',len(nomodel),nomodel,'others',others,'datemism',mism)
print('dup model hashes',sum(v-1 for v in hashes.values() if v>1))
for k in sorted(cnt,key=str): print(k,cnt[k])
