import pickle,collections,hashlib,json
R='results/gauntlet/'
recs=pickle.load(open('scratch/hist/simulated-runs/recs.pkl','rb'))
p6=[r for r in recs if r['period']==6]
print([ (r['file'],r['when'],r['src']) for r in p6 if r['file'].startswith('g2-net1029-hpe0.01-two-line-step')])
seen=set(); keep=[]
for r in p6:
    h=hashlib.md5(open(R+r['file'],'rb').read()).hexdigest()
    if h in seen: print('drop',r['file'],len(r['seqs'])); continue
    seen.add(h); keep.append(r)
# also dup by (settings, seqs) content
def agg(rs):
    n=collections.Counter(); l=collections.Counter(); runs=0
    for r in rs:
        for i,c,fl in r['seqs']:
            runs+=1
            for e,a,b,w in fl: n[e]+=1; l[e]+=(not w)
    return n,l,runs
for name,rs in [('all',p6),('dedup',keep)]:
    n,l,runs=agg(rs); print(name,len(rs),runs,sum(n.values()),len(n))
    for e,c in n.most_common(): print(f'  {e:28}{c:7}{l[e]:6}{100*l[e]/c:7.2f}')
    t=n.most_common(4); print('  top4',sum(l[e] for e,_ in t),sum(c for _,c in t))
print(json.dumps(json.load(open(R+'c1-sanity-new.json'))['settings']))
