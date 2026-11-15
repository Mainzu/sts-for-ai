import json
R='results/mutate/'
M='GE-AttackLoss-Damage'
d=json.load(open(R+'gen-enemies-b1.json'))
for pol in ['heuristic','one']:
  L=[r['hp']-(hp if ok else 0) for r in d['rows'] if r['encounter']=='gremlin_nob' for ok,hp in r['mods'][M][pol][:4]]
  W=[ok for r in d['rows'] if r['encounter']=='gremlin_nob' for ok,hp in r['mods'][M][pol][:4]]
  print(pol,sum(W),len(W),sum(W)/len(W),sum(L)/len(L))
