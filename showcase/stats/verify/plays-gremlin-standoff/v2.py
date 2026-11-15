import json
from collections import Counter
D = r'results/real-game/20261114-205554/decisions.jsonl'
runi = 0; prev = 0; rows = []
for l in open(D):
    d = json.loads(l)
    if d['floor'] < prev: runi += 1
    prev = d['floor']
    if runi == 1 and d['floor'] == 5 and 'options' in d and 'view' in d: rows.append(d)
c = Counter(); turns=set(); first=None; acts=0
for x in rows:
    mons = x['view']['monsters']; act = x['options'][x['pick']]
    sg = [m for m in mons if 'Shield' in m['name'] and m['hp']>0]
    if sg and sg[0]['hp']==4:
        turns.add(x['turn']); first = first or x['turn']
        for a in act:
            if '@' in a:
                card,t = a.split('@'); m = mons[int(t)]
                c[(card, m['name'].replace('gen:',''), 'blk' if m['block']>0 else 'noblk')] += 1
            else: c[(a,)] += 1
    if x['turn'] in (82,83,84,85) or len(act)>1 and x['turn']<6: print(x['turn'], [(m['name'],m['hp'],m['block']) for m in mons if m['hp']>0], act, x['view']['player']['hp'])
print('first',first,'last',max(turns),'nturns',len(turns))
for k,v in c.most_common(): print(k,v)
# block per turn on mad gremlin while SG alive
bl=Counter()
for x in rows:
    mons=x['view']['monsters']
    if any('Shield' in m['name'] and m['hp']==4 for m in mons):
        for m in mons:
            if 'Mad' in m['name'] and m['hp']>0: bl[m['block']]+=1
print('mad block dist', bl)
print(Counter(len(x['options'][x['pick']]) for x in rows))
