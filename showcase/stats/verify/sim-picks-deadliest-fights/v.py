import json, collections
G='results/gauntlet/'
ids=collections.Counter(); seqs=[]
for f in ['net1029-hpe0.01-two-line-step-starter-simboss-a.json','net1029-hpe0.01-two-line-step-starter-simboss-500.json']:
    d=json.load(open(G+f))
    print(f, d['settings'] if len(str(d['settings']))<600 else str(d['settings'])[:600])
    for s in d['sequences']: ids[s['i']]+=1; seqs.append(s)
print('runs',len(seqs),'unique',len(ids),min(ids),max(ids), 'dups',sum(v>1 for v in ids.values()))
print('floor keys', list(seqs[0]['floors'][0].keys()))
c=collections.defaultdict(lambda:[0,0]); tot=0; afterloss=0
for s in seqs:
    dead=False
    for fl in s['floors']:
        if dead: afterloss+=1
        c[fl['encounter']][0]+=1; tot+=1
        if not fl['won']: c[fl['encounter']][1]+=1; dead=True
print('fights',tot,'after loss',afterloss)
for e,(n,l) in sorted(c.items(), key=lambda x:-x[1][1]/x[1][0]): print(f'{e:30s} {l:4d}/{n:4d} {100*l/n:.1f}')
z=[e for e,(n,l) in c.items() if l==0]; print('zero',z,sum(c[e][0] for e in z))
print('lens',collections.Counter(len(s['floors']) for s in seqs))
