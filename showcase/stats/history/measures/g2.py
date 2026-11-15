import json,collections
rows=json.load(open('gauntlet_rows.json'))
P=[('10-23','10-24'),('10-25','10-28'),('10-29','10-31'),('11-01','11-02'),('11-03','11-05'),('11-06','11-09'),('11-10','11-12'),('11-13','11-14')]
def per(d):
    for i,(a,b) in enumerate(P):
        if a<=d[:5]<=b: return i+1
keys=collections.Counter(r[5] for r in rows); rank={k:i for i,(k,_) in enumerate(keys.most_common())}
by=collections.defaultdict(list)
for r in rows: by[per(r[0])].append(r)
for p in sorted(by, key=lambda x:(x is None,x)):
    rs=by[p]; ks=collections.Counter(rank[r[5]] for r in rs)
    print('P',p,len(rs),'settings',dict(ks), 'ncounts',collections.Counter(r[3] for r in rs).most_common(4))
    for k in sorted(ks):
        best=max((r for r in rs if rank[r[5]]==k), key=lambda r:r[4])
        print('   set',k,'best %.3f n=%d'%(best[4],best[3]),best[2],best[0])
print('mtime vs birth diffs', sum(r[0][:5]!=r[1][:5] for r in rows))
