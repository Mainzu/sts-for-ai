import json, collections
G='results/gauntlet/'
def load(f): return json.load(open(G+f))['sequences']
def tally(seqs, label):
    ids=[s['i'] for s in seqs]; print(label, 'n',len(seqs),'uniq',len(set(ids)),min(ids),max(ids))
    c=collections.defaultdict(lambda:[0,0]); lens=collections.Counter(); halves=collections.Counter(s.get('half') for s in seqs)
    for s in seqs:
        fl=s['floors']; lens[len(fl)]+=1
        if len(fl)==11:
            b=fl[10]; c[b['encounter']][1]+=1; c[b['encounter']][0]+=bool(b['won'])
    print(' lens',dict(lens),'halves',dict(halves))
    tot=sum(v[1] for v in c.values()); print(' arrivals',tot)
    for k,(w,n) in sorted(c.items()): print(f'  {k}: {w}/{n} = {100*w/n:.1f}')
for f in ['net1029-hpe0.01-two-line-step-starter-simboss-a.json','net1029-hpe0.01-two-line-step-starter-simboss-500.json']:
    tally(load(f),f)
tally(load('net1029-hpe0.01-two-line-step-starter-simboss-a.json')+load('net1029-hpe0.01-two-line-step-starter-simboss-500.json'),'PROD all')
tally(load('heuristic-starter-simboss.json'),'HEUR')
print(json.load(open(G+'net1029-hpe0.01-two-line-step-starter-simboss-500.json'))['settings'])
print(json.load(open(G+'net1029-hpe0.01-two-line-step-starter-simboss-a.json'))['settings'])
