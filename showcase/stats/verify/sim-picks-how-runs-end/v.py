import json, collections
G='results/gauntlet/'
def load(f): return json.load(open(G+f))
def runs(files):
    out={}
    for f in files:
        d=load(f); print(f, d['settings'].get('shape'), d['settings'].get('player'), len(d['sequences']))
        for s in d['sequences']:
            assert s['i'] not in out, ('dup',s['i']); out[s['i']]=s
    return out
for name,files in [('prod',['net1029-hpe0.01-two-line-step-starter-simboss-a.json','net1029-hpe0.01-two-line-step-starter-simboss-500.json']),('heur',['heuristic-starter-simboss.json'])]:
    R=runs(files); print(name,len(R),min(R),max(R))
    c=collections.Counter(); fl=collections.Counter(); hp=[]; nfl=collections.Counter()
    for s in R.values():
        F=s['floors']; nfl[len(F)]+=1
        lost=[k for k,x in enumerate(F) if not x['won']]
        if not lost:
            assert len(F)==11; c['clear']+=1; hp.append(F[-1]['hp_end'])
        else:
            k=lost[0]; assert k==len(F)-1
            kind=['h']*5+['e','h','h','e','h','b'][0:0]
            shape=['easy','easy','easy','hard','hard','elite','hard','hard','elite','hard','boss'][k]
            g='boss' if shape=='boss' else 'elite' if shape=='elite' else 'hall'
            c[g]+=1; fl[(g,k+1)]+=1
    n=len(R)
    print({k:(v,round(100*v/n,1)) for k,v in c.items()}, sorted(fl.items()), 'clearhp mean',round(sum(hp)/len(hp),1),'min',min(hp), nfl)
