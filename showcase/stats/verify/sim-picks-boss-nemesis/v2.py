import json
G='results/gauntlet/'
def load(f): return {s['i']:s for s in json.load(open(G+f))['sequences']}
p=load('net1029-hpe0.01-two-line-step-starter-simboss-a.json'); h=load('heuristic-starter-simboss.json')
same=diff=0
for i in range(500):
    a=[f['encounter'] for f in p[i]['floors']]; b=[f['encounter'] for f in h[i]['floors']]
    n=min(len(a),len(b)); same+= a[:n]==b[:n]; diff+= a[:n]!=b[:n]
print('enc seq agree',same,diff)
# boss among both-arrived seeds
import collections
c=collections.defaultdict(lambda:[0,0,0])
for i in range(500):
    if len(p[i]['floors'])==11 and len(h[i]['floors'])==11:
        k=p[i]['floors'][10]['encounter']; c[k][0]+=1; c[k][1]+=p[i]['floors'][10]['won']; c[k][2]+=h[i]['floors'][10]['won']
print(dict(c))
