import json,os,glob,hashlib,datetime,collections as C
R='results/gauntlet'
P=[(1,'10-23','10-24'),(2,'10-25','10-28'),(3,'10-29','10-31'),(4,'11-01','11-02'),(5,'11-03','11-05'),(6,'11-06','11-09'),(7,'11-10','11-12'),(8,'11-13','11-14')]
def per(d):
    for p,a,b in P:
        if a<=d<=b: return p
fights=C.Counter();loss=C.Counter();ends=C.Counter();lost_runs=0;runs=0
hashes=C.Counter();seqhash=C.Counter();pf=C.Counter();shapes=C.Counter();rests=C.Counter()
for f in sorted(glob.glob(R+'/*.json')):
    raw=open(f,'rb').read();hashes[hashlib.md5(raw).hexdigest()]+=1
    d=json.loads(raw);t=datetime.datetime.fromtimestamp(os.path.getmtime(f),datetime.timezone(datetime.timedelta(hours=0)))
    p=per(t.strftime('%m-%d'));pf[p]+=1
    s=d['settings'];shapes[(tuple(s.get('shape',[])))]+=1;rests[s.get('rest')]+=1
    seqhash[hashlib.md5(json.dumps(d['sequences'],sort_keys=True).encode()).hexdigest()]+=1
    for q in d['sequences']:
        runs+=1
        if not q.get('cleared'): lost_runs+=1
        for fl in q['floors']:
            e=fl['encounter'];fights[(p,e)]+=1
            if not fl['won']: loss[(p,e)]+=1;ends[e]+=1
print('files by period',dict(pf));print('dup files',sum(v-1 for v in hashes.values()),'dup seqs',sum(v-1 for v in seqhash.values()))
print('runs',runs,'lost',lost_runs,'endsum',sum(ends.values()))
for e,c in ends.most_common(6):print(e,c,round(100*c/lost_runs,1))
print('top3 share',round(100*sum(c for _,c in ends.most_common(3))/lost_runs,1))
tot=C.Counter()
for (p,e),n in fights.items(): tot[p]+=n
print('fights per period',dict(tot))
for e in ['hexaghost','the_guardian','slime_boss','lagavulin','three_sentries','gremlin_nob']:
    print(e,[(p,fights[(p,e)],round(100*loss[(p,e)]/fights[(p,e)],1)) for p in range(1,9) if fights[(p,e)]], sum(fights[(p,e)] for p in range(9)))
print('shapes',shapes.most_common(8));print('rests',rests)
